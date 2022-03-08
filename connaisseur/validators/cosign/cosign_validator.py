# import asyncio
import json
import logging
import os
import re
import subprocess  # nosec

from concurrent.futures import ThreadPoolExecutor

from connaisseur.crypto import load_key
from connaisseur.exceptions import (
    CosignError,
    CosignTimeout,
    NotFoundException,
    InvalidFormatException,
    UnexpectedCosignData,
    ValidationError,
)
from connaisseur.image import Image
from connaisseur.util import safe_path_func  # nosec
from connaisseur.validators.interface import ValidatorInterface


class CosignValidator(ValidatorInterface):
    name: str
    trust_roots: list
    vals: dict  # validations, a dict for each required trust root containing validated digests or errors
    k8s_keychain: bool

    def __init__(self, name: str, trust_roots: list, auth: dict = None, **kwargs):
        super().__init__(name, **kwargs)
        self.trust_roots = trust_roots
        self.vals = {}
        self.k8s_keychain = False if auth is None else auth.get("k8s_keychain", False)

    async def validate(
        self, image: Image, trust_root: str = None, **kwargs
    ):  # pylint: disable=arguments-differ
        required = kwargs.get("required", [])
        # if not configured, `threshold` is 1 if trust root is not "*" or
        # `required` is specified and number of trust roots otherwise
        threshold = kwargs.get(
            "threshold",
            1 if trust_root != "*" or any(required) else len(self.trust_roots),
        )

        self.vals = self.__get_pinned_keys(trust_root, required, threshold)

        # use concurrent.futures for now
        # tasks = [self.__validation_task(k, str(image)) for k in self.vals.keys()]
        # await asyncio.gather(*tasks)

        # prepare executor
        num_workers = len(self.vals)
        executor = ThreadPoolExecutor(num_workers)
        # prepare tasks
        arguments = [(k, str(image)) for k in self.vals.keys()]
        futures = [executor.submit(self.__validation_task, *arg) for arg in arguments]
        # await results (output dropped as `self.vals` is updated within function)
        for future in futures:
            future.result()

        return CosignValidator.__apply_policy(
            vals=self.vals, threshold=threshold, required=required
        )

    def __get_pinned_keys(self, key_name: str, required: list, threshold: int):
        """
        Extract the pinned key(s) selected for validation from the list of trust roots.
        """
        key_name = key_name or "default"
        available_keys = list(map(lambda k: k["name"], self.trust_roots))

        # generate list of pinned keys
        if key_name == "*":
            if len(required) >= threshold:
                pinned_keys = required
            else:
                pinned_keys = available_keys
        else:
            pinned_keys = [key_name]

        # check if pinned keys exist in available trust roots
        missing_keys = set(pinned_keys) - set(available_keys)
        if missing_keys:
            msg = 'Trust roots "{key_names}" not configured for validator "{validator_name}".'
            raise NotFoundException(
                message=msg,
                key_names=", ".join(missing_keys),
                validator_name=self.name,
            )

        # construct key validation dictionary for pinned keys
        keys = {
            k["name"]: {
                "name": k["name"],
                "key": "".join(k["key"]),
                "digest": None,
                "error": None,
            }
            for k in self.trust_roots
            if k["name"] in pinned_keys
        }

        return keys

    # async def __validation_task(self, trust_root: str, image: str):
    def __validation_task(self, trust_root: str, image: str):
        """
        Async task for each validation to gather all required validations,
        execute concurrently and update results.
        """
        try:
            # self.vals[trust_root]["digest"] = await self.__get_cosign_validated_digests(
            self.vals[trust_root]["digest"] = self.__get_cosign_validated_digests(
                image, self.vals[trust_root]
            )
        except Exception as err:
            self.vals[trust_root]["error"] = err
            logging.info(err)

    # async def __get_cosign_validated_digests(self, image: str, trust_root: dict):
    def __get_cosign_validated_digests(self, image: str, trust_root: dict):
        """
        Get and process Cosign validation output for a given `image` and `key`
        and either return a list of valid digests or raise a suitable exception
        in case no valid signature is found or Cosign fails.
        """
        # returncode, stdout, stderr = await self.__invoke_cosign(image, trust_root["key"])
        returncode, stdout, stderr = self.__invoke_cosign(image, trust_root["key"])

        logging.info(
            "COSIGN output of trust root '%s' for image'%s': RETURNCODE: %s; STDOUT: %s; STDERR: %s",
            trust_root["name"],
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
                        if re.match(r"sha256:[0-9A-Fa-f]{64}", digest) is None:
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
                            trust_root=trust_root["name"],
                        ) from err
                    # remove prefix 'sha256'
                    digests.append(digest.removeprefix("sha256:"))
                except json.JSONDecodeError:
                    logging.info("non-json signature data from Cosign: %s", sig)
                    pass
        elif "Error: no matching signatures:\nfailed to verify signature\n" in stderr:
            msg = "Failed to verify signature of trust data."
            raise ValidationError(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
                trust_root=trust_root["name"],
            )
        elif "Error: no matching signatures:\n\nmain.go:" in stderr:
            msg = 'No trust data for image "{image}".'
            raise NotFoundException(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
                trust_root=trust_root["name"],
            )
        else:
            msg = 'Unexpected Cosign exception for image "{image}": {stderr}.'
            raise CosignError(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
                trust_root=trust_root["name"],
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
                trust_root=trust_root["name"],
            )
        return digests.pop()

    # async def __invoke_cosign(self, image: str, key: str):
    def __invoke_cosign(self, image: str, key: str):
        """
        Invoke the Cosign binary in a subprocess for a specific `image` given a `key` and
        return the returncode, stdout and stderr. Will raise an exception if Cosign times out.
        """
        pubkey_config, env_vars, pubkey = CosignValidator.__get_pubkey_config(key)

        cmd = [
            "/app/cosign/cosign",
            "verify",
            "--output",
            "text",
            *pubkey_config,
            *(["--k8s-keychain"] if self.k8s_keychain else []),
            image,
        ]
        env = self.__get_envs()
        env.update(env_vars)

        with subprocess.Popen(  # nosec
            cmd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as process:
            try:
                stdout, stderr = process.communicate(pubkey, timeout=60)
            except subprocess.TimeoutExpired as err:
                process.kill()
                msg = "Cosign timed out."
                raise CosignTimeout(
                    message=msg, trust_data_type="dev.cosignproject.cosign/signature"
                ) from err

        return process.returncode, stdout.decode("utf-8"), stderr.decode("utf-8")

    @staticmethod
    def __get_pubkey_config(key: str):
        """
        Return a tuple of the used Cosign verification command (flag-value list), a
        dict of potentially required environment variables and public key in binary
        PEM format to be used as stdin to Cosign based on the format of the input
        key (reference).

        Raise InvalidFormatException if none of the supported patterns is matched.
        """
        try:
            # key is ecdsa public key
            pkey = load_key(key).to_pem()  # raises if invalid
            return ["--key", "/dev/stdin"], {}, pkey
        except ValueError:
            pass

        # key is KMS reference
        if re.match(r"^\w{2,20}://[\w:/-]{3,255}$", key):
            return ["--key", key], {}, b""

        msg = "Public key (reference) '{input_str}' does not match expected patterns."
        raise InvalidFormatException(message=msg, input_str=key)

    def __get_envs(self):
        """
        Sets up environment variables used by cosign.
        """
        env = os.environ.copy()
        # Extend the OS env vars only for passing to the subprocess below
        env["DOCKER_CONFIG"] = f"/app/connaisseur-config/{self.name}/.docker/"
        if safe_path_func(
            os.path.exists, "/app/certs/cosign", f"/app/certs/cosign/{self.name}.crt"
        ):
            env["SSL_CERT_FILE"] = f"/app/certs/cosign/{self.name}.crt"
        return env

    @staticmethod
    def __apply_policy(vals: dict, threshold: int, required: list):
        """
        Validates the signature verification outcome against the policy for
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
