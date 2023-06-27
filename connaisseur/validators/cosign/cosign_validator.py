import asyncio
import json
import logging
import os
import re
import subprocess  # nosec

import connaisseur.constants as const
from connaisseur.exceptions import (
    CosignError,
    CosignTimeout,
    InvalidFormatException,
    NotFoundException,
    UnexpectedCosignData,
    ValidationError,
    WrongKeyError,
)
from connaisseur.image import Image
from connaisseur.trust_root import ECDSAKey, KMSKey, RSAKey, TrustRoot
from connaisseur.util import safe_path_func  # nosec
from connaisseur.validators.interface import ValidatorInterface


class CosignValidator(ValidatorInterface):
    name: str
    trust_roots: list
    k8s_keychain: bool
    rekor_url: str

    def __init__(
        self,
        name: str,
        host: dict = None,
        trustRoots: list = None,  # pylint: disable=invalid-name
        auth: dict = None,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.trust_roots = trustRoots
        self.k8s_keychain = False if auth is None else auth.get("k8sKeychain", False)
        rekor_host = None if host is None else host.get("rekor", None)
        self.rekor_url = (
            rekor_host
            if rekor_host is None or rekor_host.startswith(("https://", "http://"))
            else f"https://{rekor_host}"
        )

    async def validate(
        self,
        image: Image,
        trustRoot: str = None,
        verifyInTransparencyLog: bool = True,
        **kwargs,
    ):  # pylint: disable=arguments-differ,invalid-name
        required = kwargs.get("required", [])
        # if not configured, `threshold` is 1 if trust root is not "*" or
        # `required` is specified and number of trust roots otherwise
        threshold = kwargs.get(
            "threshold",
            1 if trustRoot != "*" or any(required) else len(self.trust_roots),
        )
        # vals is a validations dict for each required trust root containing validated
        # digests and errors
        vals = self.__get_pinned_trust_roots(
            trustRoot, required, threshold, verifyInTransparencyLog
        )

        # prepare tasks
        # a copy of vals dictionaries is passed to concurrent validation to ensure
        # thread-safe execution
        arguments = [(k, v.copy(), str(image)) for k, v in vals.items()]
        results = await asyncio.gather(
            *[self.__validation_task(*args) for args in arguments]
        )
        for result in results:
            vals.update(result)

        return CosignValidator.__apply_policy(
            vals=vals, threshold=threshold, required=required
        )

    def __get_pinned_trust_roots(
        self,
        tr_name: str,
        required: list,
        threshold: int,
        verify_tlog: bool,
    ):
        """
        Extract the pinned trust root(s) selected for validation from the list of trust
        roots.
        """
        tr_name = tr_name or "default"
        available_trs = list(map(lambda t: t["name"], self.trust_roots))

        # generate list of pinned trust roots
        if tr_name == "*":
            if len(required) >= threshold:
                pinned_trs = required
            else:
                pinned_trs = available_trs
        else:
            pinned_trs = [tr_name]

        # check if pinned trust roots exist in available trust roots
        missing_trs = set(pinned_trs) - set(available_trs)
        if missing_trs:
            msg = 'Trust roots "{tr_names}" not configured for validator "{validator_name}".'
            raise NotFoundException(
                message=msg, tr_names=", ".join(missing_trs), validator_name=self.name
            )

        # construct key validation dictionary for pinned keys
        trust_roots = {
            t["name"]: {
                "name": t["name"],
                "trust_root": TrustRoot("".join(t["key"])),
                "digest": None,
                "verify_tlog": verify_tlog,
                "error": None,
            }
            for t in self.trust_roots
            if t["name"] in pinned_trs
        }

        return trust_roots

    async def __validation_task(self, trust_root: str, values: dict, image: str):
        """
        Task for each validation to gather all required validations,
        execute concurrently and update results.
        """
        try:
            values["digest"] = await self.__get_cosign_validated_digests(image, values)
        except Exception as err:
            values["error"] = err
            logging.info(err)

        return {trust_root: values}

    async def __get_cosign_validated_digests(self, image: str, values: dict):
        """
        Get and process Cosign validation output for a given `image` and `trust_root`
        and either return a list of valid digests or raise a suitable exception
        in case no valid signature is found or Cosign fails.
        """
        returncode, stdout, stderr = await self.__validate_using_trust_root(
            image, values["trust_root"], values["verify_tlog"]
        )
        logging.info(
            "COSIGN output of trust root '%s' for image'%s': RETURNCODE: %s; STDOUT: %s; STDERR: %s",
            values["name"],
            str(image),
            returncode,
            stdout,
            stderr,
        )
        digests = []
        if returncode == 0:
            for sig in stdout.splitlines():
                try:
                    sig_data = json.loads(sig)
                    try:
                        digest = sig_data["critical"]["image"].get(
                            "docker-manifest-digest", ""
                        )
                        if (
                            re.match(rf"{const.SHA256}:[0-9A-Fa-f]{{64}}", digest)
                            is None
                        ):
                            msg = "Digest '{digest}' does not match expected digest pattern."
                            raise InvalidFormatException(message=msg, digest=digest)
                    except Exception as err:
                        msg = (
                            "Could not retrieve valid and unambiguous digest from data "
                            "received by Cosign: {err_type}: {err}"
                        )
                        raise UnexpectedCosignData(
                            message=msg,
                            err_type=type(err).__name__,
                            err=str(err),
                            trust_data_type="dev.cosignproject.cosign/signature",
                            stderr=stderr,
                            image=str(image),
                            trust_root=values["name"],
                        ) from err
                    # remove prefix 'sha256'
                    digests.append(digest.removeprefix(f"{const.SHA256}:"))
                except json.JSONDecodeError:
                    logging.info("non-json signature data from Cosign: %s", sig)
                    pass
        elif (
            "Error: no matching signatures:\ninvalid signature when validating ASN.1 encoded signature\n"
            in stderr
        ):
            msg = "Failed to verify signature of trust data."
            raise ValidationError(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
                trust_root=values["name"],
            )
        elif (
            "Error: no matching signatures:\nsignature not found in transparency log"
            in stderr
        ):
            msg = "Failed to find signature in transparency log."
            raise ValidationError(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
                trust_root=values["name"],
            )
        elif (
            "Error: no matching signatures:\n\nmain.go:" in stderr
            or "Error: no matching signatures:\ncrypto/rsa: verification error"
            in stderr
        ):
            msg = 'No trust data for image "{image}".'
            raise NotFoundException(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
                trust_root=values["name"],
            )
        elif "MANIFEST_UNKNOWN" in stderr:
            msg = 'Image "{image}" does not exist.'
            raise NotFoundException(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
                trust_root=values["name"],
            )
        else:
            msg = 'Unexpected Cosign exception for image "{image}": {stderr}.'
            raise CosignError(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
                trust_root=values["name"],
            )
        if not digests:
            msg = (
                "Could not extract any digest from data received by Cosign "
                "despite successful image verification."
            )
            raise UnexpectedCosignData(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
                trust_root=values["name"],
            )
        return digests.pop()

    async def __validate_using_trust_root(
        self,
        image: str,
        trust_root: TrustRoot,
        verify_tlog: bool,
    ):
        """
        Call the `CosignValidator.__invoke_cosign` method, using a specific trust root.
        """
        # reminder when implementing RSA validation:
        # ["--key", "/dev/stdin", self.value.save_pkcs1()]

        # reminder when implementing Keyless validation:
        # ["--cert-email", self.value, b""]

        if isinstance(trust_root, (ECDSAKey, RSAKey)):
            return await self.__invoke_cosign(
                image,
                {
                    "option_kword": "--key",
                    "inline_tr": "/dev/stdin",
                    "trust_root": trust_root.pem(),
                },
                verify_tlog,
            )
        elif isinstance(trust_root, KMSKey):
            return await self.__invoke_cosign(
                image,
                {"option_kword": "--key", "inline_tr": trust_root.value},
                verify_tlog,
            )
        msg = (
            "The trust_root type {tr_type} is unsupported for a validator of type"
            "{val_type}."
        )
        raise WrongKeyError(message=msg, tr_type=type(trust_root), val_type="cosign")

    async def __invoke_cosign(
        self,
        image: str,
        tr_args: dict,
        verify_tlog: bool,
    ):
        """
        Invoke the Cosign binary in a subprocess for a specific `image` given trust root
        argument dict (`tr_args`) and return the returncode, stdout and stderr. The trust
        root argument dict includes a Cosign option keyword and the trust root itself,
        either as inline argument or pipeable input with an inline reference. The
        composition of the dict is dependant on the type of trust root.

        Raises an exception if Cosign times out.
        """

        # on the use of `--insecure-ignore-sct`: this flag disables/enables
        # the validation that a certificate was added to the transparency log.
        # without the support of keyless, no certificates are being used in the
        # first place, so it can be safely ignored.
        # once we do enable it, we run into problems that multiple parallel
        # processes try to access a local file, of which only one process
        # will win, while the others fail.
        args = [
            "verify",
            *([] if verify_tlog else ["--insecure-ignore-tlog"]),
            "--insecure-ignore-sct",
            "--output",
            "text",
            tr_args["option_kword"],
            tr_args["inline_tr"],
            *(["--k8s-keychain"] if self.k8s_keychain else []),
            *(["--rekor-url", self.rekor_url] if self.rekor_url else []),
            image,
        ]

        process = await asyncio.create_subprocess_exec(  # nosec
            "/app/cosign/cosign",
            *args,
            env=self.__get_envs(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=tr_args.get("trust_root", None)), timeout=60
            )
        except subprocess.TimeoutExpired as err:
            process.kill()
            msg = "Cosign timed out."
            raise CosignTimeout(
                message=msg, trust_data_type="dev.cosignproject.cosign/signature"
            ) from err

        return (process.returncode, stdout.decode("utf-8"), stderr.decode("utf-8"))

    def __get_envs(self):
        """
        Set up environment variables used by cosign.
        """
        env = os.environ.copy()
        # Extend the OS env vars only for passing to the subprocess below
        env["DOCKER_CONFIG"] = f"/app/connaisseur-config/{self.name}/.docker/"
        env["TUF_ROOT"] = "/app/.sigstore"
        if safe_path_func(
            os.path.exists, "/app/certs/cosign", f"/app/certs/cosign/{self.name}.crt"
        ):
            env["SSL_CERT_FILE"] = f"/app/certs/cosign/{self.name}.crt"
        return env

    @staticmethod
    def __apply_policy(vals: dict, threshold: int, required: list):
        """
        Validate the signature verification outcome against the policy for
        threshold and required trust roots.

        Raises an exception if not compliant.
        """

        # verify threshold
        signed_digests = [k["digest"] for k in vals.values() if k["digest"] is not None]
        # raise exception if the same digest does not appear 'threshold' times
        if not len(set(signed_digests)) == 1 or not len(signed_digests) >= threshold:
            # simply raise the specific error if single specified trust root
            if len(vals) == 1:
                raise list(vals.values())[0]["error"]

            # aggregate exception message and reasons for multiple trust roots
            errs = "\n".join(
                [
                    f"* trust root '{e['name']}': {e['error'].message}"
                    for e in vals.values()
                    if e["error"] is not None
                ]
            )
            msg = (
                "Image not compliant with validation policy (threshold of "
                "'{threshold}' not reached). The following errors occurred "
                "(please check the logs for more information):\n{errors}"
            )
            raise ValidationError(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                threshold=str(threshold),
                required=required,
                errors=errs,
            )

        digest = signed_digests[0]

        # verify required trust roots
        missing_trust_roots = []
        for trust_root in required:
            if not vals[trust_root]["digest"] == digest:
                missing_trust_roots.append(trust_root)

        if missing_trust_roots:
            errs = "\n".join(
                [
                    f"* trust root '{e['name']}': {e['error'].message}"
                    for e in vals.values()
                    if e["name"] in missing_trust_roots
                ]
            )
            msg = (
                "Image not compliant with validation policy (missing signatures "
                "for required trust roots: {missing}). The following errors occurred "
                "(please check the logs for more information):\n{errors}"
            )

            raise ValidationError(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                threshold=str(threshold),
                required=required,
                missing=", ".join(missing_trust_roots),
                errors=errs,
            )

        return digest

    @property
    def healthy(self):
        return True
