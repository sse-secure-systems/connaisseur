import json
import logging
import re
import subprocess  # nosec

from connaisseur.crypto import decode_and_verify_ecdsa_key
from connaisseur.exceptions import (
    CosignError,
    CosignTimeout,
    NotFoundException,
    ValidationError,
    UnexpectedCosignData
)


def get_cosign_validated_digests(image: str, pubkey: str):
    """
    Gets and processes cosign validation output for a given `image` and `pubkey`
    and either returns a list of valid digests or raises a suitable exception
    in case no valid signature is found or cosign fails.
    """
    returncode, stdout, stderr = invoke_cosign(image, pubkey)
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
                    digest = sig_data["Critical"]["Image"].get("Docker-manifest-digest", "")
                    if re.match(r"(sha256:)?[0-9A-Fa-f]{64}", digest) is None:
                        raise Exception("digest does not match expected digest pattern.")
                except Exception as err:
                    raise UnexpectedCosignData(
                        f"could not retrieve valid digest from data obtained by cosign: {err}"
                        ) from err

                # remove prefix 'sha256' in case it exists
                digests.append(digest[7:] if digest[:7] == "sha256:" else digest)
            except json.JSONDecodeError:
                logging.info("Non-json signature data from Cosign: %s", sig)
                pass
    elif stderr == "error: no matching signatures:\nunable to verify signature\n":
        raise ValidationError(
            "failed to verify signature of trust data.",
            {"trust_data_type": "dev.cosignproject.cosign/signature", "stderr": stderr},
        )
    elif re.match(r"^error: GET https://[^ ]+ MANIFEST_UNKNOWN:.*", stderr):
        raise NotFoundException(
            f'no trust data for image "{image}".',
            {"trust_data_type": "dev.cosignproject.cosign/signature", "stderr": stderr},
        )
    else:
        raise CosignError(
            f'Unexpected Cosign Exception for image "{image}": {stderr}.',
            {"trust_data_type": "dev.cosignproject.cosign/signature"},
        )
    return digests


def invoke_cosign(image, pubkey):
    """
    Invokes a cosign binary in a subprocess for a specific `image` given a `pubkey` and
    returns the returncode, stdout and stderr. Will raise an exception if cosign times out.
    """

    decode_and_verify_ecdsa_key(pubkey)  # raises if invalid; return value not used
    cmd = ["/app/cosign/cosign", "verify", "-key", "/dev/stdin", image]
    stdinput = f"-----BEGIN PUBLIC KEY-----\n{pubkey}\n-----END PUBLIC KEY-----"

    with subprocess.Popen(  # nosec
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as process:
        try:
            stdout, stderr = process.communicate(bytes(stdinput, "utf-8"), timeout=120)
        except subprocess.TimeoutExpired as err:
            process.kill()
            raise CosignTimeout(
                "Cosign timed out.",
                {"trust_data_type": "dev.cosignproject.cosign/signature"},
            ) from err

    return process.returncode, stdout.decode("utf-8"), stderr.decode("utf-8")
