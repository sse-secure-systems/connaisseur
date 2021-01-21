from connaisseur.exceptions import NotFoundException


class KeyStore:
    """
    Stores all public keys in `keys` and hashes in `hashes`, collected from
    trust data. The public root keys is loaded from the container itself.
    """

    keys: dict
    hashes: dict

    def __init__(self, root_pub_key: str):
        # will always be loaded there as k8s secret
        self.keys = {"root": root_pub_key}
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

        # update keys
        keys = trust_data.get_keys()
        for key in keys:
            self.keys.setdefault(key, keys[key]["keyval"]["public"])

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
