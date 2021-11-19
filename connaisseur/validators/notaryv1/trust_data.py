import base64
import hashlib
import json
import re
from datetime import datetime

import pytz
from dateutil import parser

from connaisseur.crypto import verify_signature
from connaisseur.exceptions import (
    InvalidTrustDataFormatError,
    NoSuchClassError,
    NotFoundException,
    ValidationError,
)
from connaisseur.util import validate_schema
from connaisseur.validators.notaryv1.key_store import KeyStore


class TrustData:
    """
    Base trust data class. Depending on the `role`
    another subclass will be created.
    """

    kind: str
    signed: dict
    signatures: list

    def __new__(cls, data: dict, role: str):
        # pylint: disable=unused-argument
        classes = {
            "root": RootData,
            "snapshot": SnapshotData,
            "timestamp": TimestampData,
            "targets": TargetsData,
        }

        try:
            return super(TrustData, cls).__new__(classes[role])
        except KeyError as err:
            if re.match("^targets/[^/\\s]+$", role):
                return super(TrustData, cls).__new__(TargetsData)

            msg = "Unable to find find class {class_name}."
            raise NoSuchClassError(message=msg, class_name=role) from err

    def __init__(self, data: dict, role: str):
        self.kind = role
        validate_schema(
            data,
            self.__SCHEMA_PATH,  # pylint: disable=no-member
            f"Trust data {self.kind}",
            InvalidTrustDataFormatError,
        )
        self.signed = data["signed"]
        self.signatures = data["signatures"]

    def validate(self, keystore: KeyStore):
        """
        Validate the trust data's signature, expiry date and hash value, given
        a `keystore` containing keys and hashes.
        """
        self.validate_signature(keystore)
        self.validate_expiry()
        self.validate_hash(keystore)

    def validate_expiry(self):
        """
        Validate the expiry date of the trust data.

        Raise a `ValidationError` should the date be expired.
        """
        expire = parser.parse(self.signed.get("expires"))
        now = datetime.now(pytz.utc)

        if expire < now:
            msg = "Trust data {trust_data_kind} has expired."
            raise ValidationError(message=msg, trust_data_kind=self.kind)

    def validate_signature(self, keystore: KeyStore):
        """
        Validate the signature of the trust data, using keys from a
        `keystore`.

        Raise a `ValidationError` should the the signature be faulty.
        """
        msg = json.dumps(self.signed, separators=(",", ":"))
        for signature in self.signatures:
            key_id = "root" if self.kind == "root" else signature["keyid"]
            pub_key = keystore.get_key(key_id)
            sig = signature["sig"]

            try:
                verify_signature(pub_key, sig, msg)
            except Exception as err:
                msg = "Failed to verify signature of trust data {trust_data_kind}."
                raise ValidationError(message=msg, trust_data_kind=self.kind) from err

    def validate_hash(self, keystore: KeyStore):
        """
        Validate the given hash from a `keystore` corresponds to the trust
        data's calculated hash.

        Raise a `ValidationError` should the hashes not match.
        """
        data = {"signed": self.signed, "signatures": self.signatures}
        data_dump = bytearray(json.dumps(data, separators=(",", ":")), "utf-8")

        hash_b64, len_ = keystore.get_hash(self.kind)
        hash_ = base64.b64decode(hash_b64).hex()

        data_hash = hashlib.sha256(data_dump).hexdigest()
        data_len = len(data_dump)

        if hash_ != data_hash or len_ != data_len:
            msg = "Failed to validate hash of trust data {trust_data_kind}."
            raise ValidationError(message=msg, trust_data_kind=self.kind)

    def get_keys(self):
        """Return all keys found in the trust data."""
        return {}

    def get_hashes(self):
        """Return all hashes found in the trust data."""
        return {}


class RootData(TrustData):  # pylint: disable=abstract-method
    _TrustData__SCHEMA_PATH: str = "connaisseur/res/root_schema.json"

    def get_keys(self):
        return self.signed["keys"]


class SnapshotData(TrustData):  # pylint: disable=abstract-method
    _TrustData__SCHEMA_PATH: str = "connaisseur/res/snapshot_schema.json"

    def get_hashes(self):
        return self.signed["meta"]


class TimestampData(TrustData):  # pylint: disable=abstract-method
    _TrustData__SCHEMA_PATH: str = "connaisseur/res/timestamp_schema.json"

    def validate_hash(self, keystore: KeyStore):
        pass

    def get_hashes(self):
        return self.signed["meta"]


class TargetsData(TrustData):  # pylint: disable=abstract-method
    _TrustData__SCHEMA_PATH: str = "connaisseur/res/targets_schema.json"

    def has_delegations(self) -> bool:
        """
        Return `True` if the trust data provides keys and roles for delegation
        and has no image targets, `False` otherwise.
        """
        return bool(
            self.signed["delegations"]["keys"] and self.signed["delegations"]["roles"]
        )

    def get_delegations(self):
        return [role["name"] for role in self.signed["delegations"].get("roles", [])]

    def get_tags(self):
        return self.signed.get("targets", {}).keys()

    def get_digest(self, tag: str):
        try:
            return self.signed.get("targets", {})[tag]["hashes"]["sha256"]
        except KeyError as err:
            msg = "Unable to find digest for tag {tag}."
            raise NotFoundException(message=msg, tag=tag) from err

    def get_keys(self):
        if self.has_delegations():
            return self.signed["delegations"]["keys"]
        return {}
