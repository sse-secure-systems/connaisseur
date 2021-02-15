import base64
import binascii
import ecdsa
from connaisseur.exceptions import NotFoundException, InvalidFormatException


class KeyStore:
    """
    Stores all public keys in `keys` and hashes in `hashes`, collected from
    trust data. The public root keys is loaded from the container itself.
    """

    keys: dict
    hashes: dict

    def __init__(self, root_pub_key: str):
        # will always be loaded there as k8s secret
        self.keys = {"root": self.load_key_string("root", root_pub_key)}
        self.hashes = {}

    def get_key(self, key_id: str):
        """
        Return a public key, given its `key_id`.

        Raises a `NotFoundException` should the `key_id` not exist.
        """
        try:
            return self.keys[key_id]
        except KeyError:
            raise NotFoundException(
                'could not find key id "{}" in keystore.'.format(key_id)
            )

    def get_hash(self, role: str):
        """
        Returns the hash of the given `role`'s trust data.

        Raises a `NotFoundException` if the `role` is not found.
        """
        try:
            return self.hashes[role]
        except KeyError:
            raise NotFoundException(
                'could not find hash for role "{}" in keystore.'.format(role)
            )

    def update(self, trust_data):
        """
        Updates the `KeyStore` with all keys and hashes found in the given
        `trust_data.`
        """

        keys = dict(trust_data.get_keys())
        signature_keys = [sig.get("keyid") for sig in trust_data.signatures]

        # delete the key, which was used to sign the current trust data, since since we
        # don't follow trust on first use. this is only the case for the root.json which
        # has its public key in PEM format and as a certificate, which will cause
        # problems when loading it. so we'll delete it.
        for key in signature_keys:
            if key in keys:
                del keys[key]

        # update keys
        for key in keys:
            self.keys.setdefault(
                key, self.load_key_string(key, keys[key]["keyval"]["public"])
            )

        # update hashes
        hashes = trust_data.get_hashes()
        for role in hashes:
            self.hashes.setdefault(
                role,
                (
                    hashes[role].get("hashes", {}).get("sha256"),
                    hashes[role].get("length", 0),
                ),
            )

    @staticmethod
    def load_key_string(key_id: str, key_base64: str):
        try:
            key_der = base64.b64decode(key_base64)
            key = ecdsa.VerifyingKey.from_der(key_der)
            return key
        except (ecdsa.der.UnexpectedDER, binascii.Error, TypeError):
            raise InvalidFormatException(
                f"error loading key {key_id}.", {"key_id": key_id}
            )
