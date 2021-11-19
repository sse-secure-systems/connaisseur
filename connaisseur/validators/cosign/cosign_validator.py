import json
import logging
import os
import re
import subprocess  # nosec

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
from connaisseur.validators.interface import ValidatorInterface


class CosignValidator(ValidatorInterface):
    name: str
    trust_roots: list

    def __init__(self, name: str, trust_roots: list, **kwargs):
        super().__init__(name, **kwargs)
        self.trust_roots = trust_roots

    def __get_key(self, key_name: str = None):
        key_name = key_name or "default"
        try:
            key = next(
                key["key"] for key in self.trust_roots if key["name"] == key_name
            )
        except StopIteration as err:
            msg = 'Trust root "{key_name}" not configured for validator "{validator_name}".'
            raise NotFoundException(
                message=msg, key_name=key_name, validator_name=self.name
            ) from err
        return "".join(key)

    async def validate(
        self, image: Image, trust_root: str = None, **kwargs
    ):  # pylint: disable=arguments-differ
        key = self.__get_key(trust_root)
        return self.__get_cosign_validated_digests(str(image), key).pop()

    def __get_cosign_validated_digests(self, image: str, key: str):
        """
        Get and process Cosign validation output for a given `image` and `key`
        and either return a list of valid digests or raise a suitable exception
        in case no valid signature is found or Cosign fails.
        """
        returncode, stdout, stderr = self.__invoke_cosign(image, key)
        logging.info(
            "COSIGN output for image: %s; RETURNCODE: %s; STDOUT: %s; STDERR: %s",
            image,
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
                            message=msg, err_type=type(err).__name__, err=str(err)
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
            )
        elif "Error: no matching signatures:\n\nmain.go:" in stderr:
            msg = 'No trust data for image "{image}".'
            raise NotFoundException(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
            )
        else:
            msg = 'Unexpected Cosign exception for image "{image}": {stderr}.'
            raise CosignError(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
            )
        if not digests:
            msg = (
                "Could not extract any digest from data received by Cosign "
                "despite successful image verification."
            )
            raise UnexpectedCosignData(message=msg)
        return digests

    def __invoke_cosign(self, image, key):
        """
        Invoke the Cosign binary in a subprocess for a specific `image` given a `key` and
        return the returncode, stdout and stderr. Will raise an exception if Cosign times out.
        """
        pubkey_config, env_vars, pubkey = CosignValidator.__get_pubkey_config(key)

        env = os.environ
        # Extend the OS env vars only for passing to the subprocess below
        env["DOCKER_CONFIG"] = f"/app/connaisseur-config/{self.name}/.docker/"
        env.update(env_vars)

        cmd = [
            "/app/cosign/cosign",
            "verify",
            "--output",
            "text",
            *pubkey_config,
            image,
        ]

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

    @property
    def healthy(self):
        return True
