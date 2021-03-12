import base64
import json
import re
import hashlib
from datetime import datetime
import pytz
from dateutil import parser
from jsonschema import validate as json_validate
from jsonschema import ValidationError as JValidationError
from jsonschema import FormatChecker as JFormatChecker
from connaisseur.key_store import KeyStore
from connaisseur.crypto import verify_signature
from connaisseur.exceptions import (
    ValidationError,
    NotFoundException,
    InvalidTrustDataFormatError,
    NoSuchClassError,
)


class TrustData:
    """
    Base trust data class, that holds the `data` as two dicts. Depending on
    the `role` another subclass will be created.
    """

    kind: str
    signed: dict
    signatures: list
    schema_path: str = "connaisseur/res/{}_schema.json"

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
        self.schema_path = self.schema_path.format(role)
        self.kind = role
        self.__validate_schema(data)
        self.signed = data["signed"]
        self.signatures = data["signatures"]

    def __validate_schema(self, data: dict):
        """
        Validates the schema of the given trust `data`.

        Raises a `ValidationError` should the schema not conform.
        """
        with open(self.schema_path, "r") as schema_file:
            schema = json.load(schema_file)

        try:
            json_validate(instance=data, schema=schema, format_checker=JFormatChecker())
        except JValidationError as err:
            msg = "Trust data {trust_data_kind} has an invalid format."
            raise InvalidTrustDataFormatError(
                message=msg, trust_data_kind=self.kind
            ) from err

    def validate(self, keystore: KeyStore):
        """
        Validates the trust data's signature, expiry date and hash value, given
        a `keystore` containing keys and hashes.
        """
        self.validate_signature(keystore)
        self.validate_expiry()
        self.validate_hash(keystore)

    def validate_expiry(self):
        """
        Validates the expiry date of the trust data.

        Raises a `ValidationError` should the date be expired.
        """
        expire = parser.parse(self.signed.get("expires"))
        now = datetime.now(pytz.utc)

        if expire < now:
            msg = "Trust data {trust_data_kind} has expired."
            raise ValidationError(message=msg, trust_data_kind=self.kind)

    def validate_signature(self, keystore: KeyStore):
        """
        Validates the signature of the trust data, using keys from a
        `keystore`.

        Raises a `ValidationError` should the the signature be faulty.
        """
        msg = json.dumps(self.signed, separators=(",", ":"))
        for signature in self.signatures:
            key_id = "root" if self.kind == "root" else signature["keyid"]
            pub_key = keystore.get_key(key_id)
            sig = signature["sig"]

            if not pub_key:
                msg = "Unable to find public key {key_id}."
                raise NotFoundException(
                    message=msg, key_id=key_id, trust_data_kind=self.kind
                )

            try:
                verify_signature(pub_key, sig, msg)
            except Exception as err:
                msg = "Failed to verify signature of trust data {trust_data_kind}."
                raise ValidationError(message=msg, trust_data_kind=self.kind) from err

    def validate_hash(self, keystore: KeyStore):
        """
        Validates the given hash from a `keystore` corresponds to the trust
        data's calculated hash.

        Raises a `ValidationError` should the hashes not match.
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
        """
        Returns all keys found in the trust data.
        """
        return {}

    def get_hashes(self):
        """
        Returns all hashes found in the trust data.
        """
        return {}


class RootData(TrustData):  # pylint: disable=abstract-method
    def get_keys(self):
        """
        Returns all keys found in the trust data.
        """
        return self.signed["keys"]


class SnapshotData(TrustData):  # pylint: disable=abstract-method
    def get_hashes(self):
        """
        Returns all hashes found in the trust data.
        """
        return self.signed["meta"]


class TimestampData(TrustData):  # pylint: disable=abstract-method
    def validate_hash(self, keystore: KeyStore):
        pass

    def get_hashes(self):
        """
        Returns all hashes found in the trust data.
        """
        return self.signed["meta"]


class TargetsData(TrustData):  # pylint: disable=abstract-method
    def __init__(self, data: dict, role: str):
        self.schema_path = "connaisseur/res/targets_schema.json"
        super().__init__(data, role)

    def has_delegations(self):
        """
        Returns `true` if the trust data provides keys and roles for delegation
        and has no image targets. `False` otherwise.
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
        """
        Returns all keys found in the trust data.
        """
        if self.has_delegations():
            return self.signed["delegations"]["keys"]
        return {}
