import json
import logging
import re
import subprocess  # nosec
from connaisseur.validators.interface import ValidatorInterface
from connaisseur.image import Image
from connaisseur.exceptions import (
    CosignError,
    CosignTimeout,
    NotFoundException,
    ValidationError,
    UnexpectedCosignData,
    InvalidFormatException,
)
from connaisseur.crypto import load_key


class CosignValidator(ValidatorInterface):
    name: str
    keys: list

    def __init__(self, name: str, pub_keys: list, **kwargs):
        self.name = name
        self.keys = pub_keys

    def __get_key(self, key_name: str = None):
        key_name = key_name or "default"
        try:
            key = next(key["key"] for key in self.keys if key["name"] == key_name)
        except StopIteration as err:
            msg = "Key {key_name} could not be found."
            raise NotFoundException(
                message=msg, key_name=key_name, notary_name=self.name
            ) from err
        return "".join(key)

    def validate(self, image: Image, key: str = None, **kwargs):
        pub_key = self.__get_key(key)
        return self.__get_cosign_validated_digests(str(image), pub_key).pop()

    def __get_cosign_validated_digests(self, image: str, pubkey: str):
        """
        Gets and processes cosign validation output for a given `image` and `pubkey`
        and either returns a list of valid digests or raises a suitable exception
        in case no valid signature is found or cosign fails.
        """
        returncode, stdout, stderr = self.__invoke_cosign(image, pubkey)
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
                        digest = sig_data["Critical"]["Image"].get(
                            "Docker-manifest-digest", ""
                        )
                        if re.match(r"sha256:[0-9A-Fa-f]{64}", digest) is None:
                            msg = "Digest '{digest}' does not match expected digest pattern."
                            raise InvalidFormatException(message=msg, digest=digest)
                    except Exception as err:
                        msg = (
                            "Could not retrieve valid and unambiguous digest from data "
                            "received by cosign: {err_type}: {err}"
                        )
                        raise UnexpectedCosignData(
                            message=msg, err_type=type(err).__name__, err=str(err)
                        ) from err
                    # remove prefix 'sha256'
                    digests.append(digest.removeprefix("sha256:"))
                except json.JSONDecodeError:
                    logging.info("non-json signature data from cosign: %s", sig)
                    pass
        elif "error: no matching signatures:\nunable to verify signature\n" in stderr:
            msg = "Failed to verify signature of trust data."
            raise ValidationError(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
            )
        elif re.match(r"^error: GET https://[^ ]+ MANIFEST_UNKNOWN:.*", stderr):
            msg = 'No trust data for image "{image}".'
            raise NotFoundException(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
            )
        else:
            msg = 'Unexpected cosign exception for image "{image}": {stderr}.'
            raise CosignError(
                message=msg,
                trust_data_type="dev.cosignproject.cosign/signature",
                stderr=stderr,
                image=str(image),
            )
        if not digests:
            msg = (
                "Could not extract any digest from data received by cosign "
                "despite successful image verification."
            )
            raise UnexpectedCosignData(message=msg)
        return digests

    def __invoke_cosign(self, image, pubkey):
        """
        Invokes a cosign binary in a subprocess for a specific `image` given a `pubkey` and
        returns the returncode, stdout and stderr. Will raise an exception if cosign times out.
        """

        key = load_key(pubkey)  # raises if invalid; return value not used
        cmd = ["/app/cosign/cosign", "verify", "-key", "/dev/stdin", image]

        with subprocess.Popen(  # nosec
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ) as process:
            try:
                stdout, stderr = process.communicate(key.to_pem(), timeout=60)
            except subprocess.TimeoutExpired as err:
                process.kill()
                msg = "Cosign timed out."
                raise CosignTimeout(
                    message=msg, trust_data_type="dev.cosignproject.cosign/signature"
                ) from err

        return process.returncode, stdout.decode("utf-8"), stderr.decode("utf-8")

    @property
    def healthy(self):
        return True
