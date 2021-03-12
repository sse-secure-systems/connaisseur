import json
import logging
import re
import subprocess  # nosec

from connaisseur.crypto import load_key
from connaisseur.exceptions import (
    CosignError,
    CosignTimeout,
    NotFoundException,
    ValidationError,
    UnexpectedCosignData,
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
                    digest = sig_data["Critical"]["Image"].get(
                        "Docker-manifest-digest", ""
                    )
                    if re.match(r"sha256:[0-9A-Fa-f]{64}", digest) is None:
                        msg = (
                            "Digest '{digest}' does not match expected digest pattern."
                        )
                except Exception as err:
                    msg = (
                        "Could not retrieve valid and unambiguous digest from data "
                        "received by cosign: {err_type}: {err}"
                    )
                    raise UnexpectedCosignData(
                        "could not retrieve valid and unambiguous digest "
                        f"from data received by cosign: {type(err).__name__}: {err}"
                    ) from err
                # remove prefix 'sha256'
                digests.append(digest[7:])
            except json.JSONDecodeError:
                logging.info("non-json signature data from cosign: %s", sig)
                pass
    elif "error: no matching signatures:\nunable to verify signature\n" in stderr:
        msg = "Failed to verify signature of trust data."
        raise ValidationError(
            "failed to verify signature of trust data.",
            {"trust_data_type": "dev.cosignproject.cosign/signature", "stderr": stderr},
        )
    elif re.match(r"^error: GET https://[^ ]+ MANIFEST_UNKNOWN:.*", stderr):
        msg = 'No trust data for image "{image}".'
        raise NotFoundException(
            f'no trust data for image "{image}".',
            {"trust_data_type": "dev.cosignproject.cosign/signature", "stderr": stderr},
        )
    else:
        msg = 'Unexpected cosign exception for image "{image}": {stderr}.'
        raise CosignError(
            f'unexpected cosign exception for image "{image}": {stderr}.',
            {"trust_data_type": "dev.cosignproject.cosign/signature"},
        )
    if not digests:
        msg = (
            "Could not extract any digest from data received by cosign "
            "despite successful image verification."
        )
    return digests


def invoke_cosign(image, pubkey):
    """
    Invokes a cosign binary in a subprocess for a specific `image` given a `pubkey` and
    returns the returncode, stdout and stderr. Will raise an exception if cosign times out.
    """

    load_key(pubkey)  # raises if invalid; return value not used
    cmd = ["/app/cosign/cosign", "verify", "-key", "/dev/stdin", image]
    stdinput = f"-----BEGIN PUBLIC KEY-----\n{pubkey}\n-----END PUBLIC KEY-----"

    with subprocess.Popen(  # nosec
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as process:
        try:
            stdout, stderr = process.communicate(bytes(stdinput, "utf-8"), timeout=60)
        except subprocess.TimeoutExpired as err:
            process.kill()
            msg = "Cosign timed out."
            raise CosignTimeout(
                "cosign timed out.",
                {"trust_data_type": "dev.cosignproject.cosign/signature"},
            ) from err

    return process.returncode, stdout.decode("utf-8"), stderr.decode("utf-8")
