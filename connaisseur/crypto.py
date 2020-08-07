import hashlib
import base64
import ecdsa


def verify_signature(public_base64: str, signature_base64: str, message: str):
    """
    Verifies the given bas64-encoded signature with the base64-encoded public
    key and serialized message. The message should not contain any whitespaces.

    Raises ValidationError if unsuccessfull.
    """
    public = base64.b64decode(public_base64)
    pub_key = ecdsa.VerifyingKey.from_der(public)

    signature = base64.b64decode(signature_base64)

    msg_bytes = bytearray(message, "utf-8")

    return pub_key.verify(signature, msg_bytes, hashfunc=hashlib.sha256)
