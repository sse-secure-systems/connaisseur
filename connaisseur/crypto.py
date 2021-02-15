import hashlib
import base64
import ecdsa


def verify_signature(
    public_key: ecdsa.VerifyingKey, signature_base64: str, message: str
):
    """
    Verifies the given bas64-encoded signature with the public
    key and serialized message. The message should not contain any whitespaces.

    Raises ValidationError if unsuccessfull.
    """

    signature = base64.b64decode(signature_base64)

    msg_bytes = bytearray(message, "utf-8")

    return public_key.verify(signature, msg_bytes, hashfunc=hashlib.sha256)
