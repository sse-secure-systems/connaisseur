import hashlib
import base64
import ecdsa

from connaisseur.exceptions import InvalidPublicKey


def verify_signature(public_base64: str, signature_base64: str, message: str):
    """
    Verifies the given bas64-encoded signature with the base64-encoded public
    key and serialized message. The message should not contain any whitespaces.

    Raises ValidationError if unsuccessful.
    """
    pub_key = decode_and_verify_ecdsa_key(public_base64)

    signature = base64.b64decode(signature_base64)

    msg_bytes = bytearray(message, "utf-8")

    return pub_key.verify(signature, msg_bytes, hashfunc=hashlib.sha256)


def decode_and_verify_ecdsa_key(public_base64: str):
    """
    Verifies that the provided public key in base64 encoding qualifies as a
    proper ecdsa key and throws if not.
    """
    public = base64.b64decode(public_base64)
    try:
        pubkey = ecdsa.VerifyingKey.from_der(public)
    except ecdsa.keys.MalformedPointError as err:
        raise InvalidPublicKey(
            f"The public key provided is not a base64-encoded ECDSA key: {err}."
        )

    return pubkey
