from connaisseur.crypto import load_key
from connaisseur.exceptions import InvalidKeyFormatError, NotFoundException


class KeyStore:
    """
    Store all public keys in `keys` and hashes in `hashes`, collected from
    trust data. Load the public root keys from the container itself.
    """

    keys: dict
    hashes: dict

    def __init__(self, root_pub_key: str = None):
        self.hashes = {}

        if root_pub_key:
            try:
                key = load_key(root_pub_key)
            except ValueError as err:
                msg = "The public root key has an invalid format."
                raise InvalidKeyFormatError(
                    message=msg, root_pub_key=root_pub_key
                ) from err
            self.keys = {"root": key}
        else:
            self.keys = {}

    def get_key(self, key_id: str):
        """
        Return a public key, given its `key_id`.

        Raise a `NotFoundException` should the `key_id` not exist.
        """
        try:
            return self.keys[key_id]
        except KeyError as err:
            msg = "Unable to find key {key_id} in keystore."
            raise NotFoundException(message=msg, key_id=key_id) from err

    def get_hash(self, role: str):
        """
        Return the hash of the given `role`'s trust data.

        Raise a `NotFoundException` if the `role` is not found.
        """
        try:
            return self.hashes[role]
        except KeyError as err:
            msg = "Unable to find hash for {tuf_role} in keystore."
            raise NotFoundException(message=msg, tuf_role=role) from err

    def update(self, trust_data):
        """
        Update the `KeyStore` with all keys and hashes found in the given
        `trust_data.`
        """
        keys = dict(trust_data.get_keys())

        # the root.json stores the public keys for all other JSONs in DER format, except
        # its own key. its own key, which is also referenced in the signature, is stored
        # as a certificate in PEM format and therefore can't be loaded like the other
        # keys. since we don't do trust on first use and have the public key inside the
        # certificate pre-provisioned anyways, we'll delete it from the dictionary, so
        # it's never loaded into the key store. note, that this only happens for the
        # root.json, as it is the only file that contains a key which was used to sign
        # itself.
        signature_keys = [sig.get("keyid") for sig in trust_data.signatures]
        keys = {k: v for k, v in keys.items() if k not in signature_keys}

        for key_id in keys:
            try:
                key = load_key(keys[key_id]["keyval"]["public"])
            except ValueError as err:
                msg = "Key {key_id} has an invalid format."
                raise InvalidKeyFormatError(
                    message=msg, key_id=key_id, key=keys[key_id]["keyval"]["public"]
                ) from err
            self.keys.setdefault(key_id, key)

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
