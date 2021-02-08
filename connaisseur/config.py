import json
import yaml
from jsonschema import validate, ValidationError
from connaisseur.exceptions import NotFoundException, InvalidFormatException
from connaisseur.util import safe_path_exists


class Config:
    """
    Config Object, that contains all notary configurations inside a list.
    """

    CONFIG_PATH = "/etc/connaisseur-config/config.yaml"
    CONFIG_SCHEMA_PATH = "/app/connaisseur/res/config_schema.json"
    notaries: list = []

    def __init__(self):
        """
        Creates a Config object, containing all notary configurations. It does so by
        reading a config file, doing input validation and then creating Notary object,
        storing them in a list.

        Raises `NotFoundException` if the configuration file is not found.

        Raises `InvalidFormatException` if the configuration file has an invalid format.
        """
        with open(self.CONFIG_PATH, "r") as configfile:
            config_content = yaml.safe_load(configfile)

        if not config_content:
            raise NotFoundException("error getting any notary host configurations.")

        with open(self.CONFIG_SCHEMA_PATH, "r") as schema_file:
            schema = json.load(schema_file)

        try:
            validate(instance=config_content, schema=schema)
        except ValidationError:
            raise InvalidFormatException(
                "invalid format for Connaisseur configuration."
            )

        self.notaries = [Notary(notary) for notary in config_content]

    def get_notary(self, notary_name: str = None):
        """
        Returns the notary configuration with the given `notary_name`. If `notary_name`
        is None, the top most element of the notary configuration list is returned.

        Raises `NotFoundException` if no top most element can be found.
        """
        try:
            if notary_name:
                return next(
                    notary for notary in self.notaries if notary.name == notary_name
                )
            return next(iter(self.notaries))
        except StopIteration:
            raise NotFoundException(
                "the given notary configuration could not be found.",
                {"notary_name": notary_name},
            )


class Notary:  # pylint: disable=too-many-instance-attributes
    """
    Notary object, that holds all information for a single notary configuration.
    """

    name: str
    host: str
    root_keys: list
    has_auth: bool = False
    auth: dict = {}
    is_selfsigned: bool = False
    selfsigned_cert: str = None
    is_acr: bool = False

    SELFSIGNED_PATH = "/etc/certs/{}.crt"
    AUTH_PATH = "/etc/creds/{}/cred.yaml"

    def __init__(self, notary_config: dict):
        """
        Creates a Notary object from a dictionary.

        Raises `InvalidFormatException` should teh mandatory fields be missing.
        """

        self.name = notary_config.get("name")
        self.host = notary_config.get("host")
        self.root_keys = notary_config.get("rootKeys")
        self.is_acr = notary_config.get("isAcr", False)

        if not (self.name and self.host and self.root_keys):
            raise InvalidFormatException(
                "error parsing the the Connaisseur configuration file."
            )

        self.is_selfsigned = safe_path_exists(
            "/etc/certs/", self.SELFSIGNED_PATH.format(self.name)
        )
        self.has_auth = safe_path_exists(
            "/etc/creds/", self.AUTH_PATH.format(self.name)
        )

    def get_key(self, key_name: str = None):
        """
        Returns the public root key with name `key_name` in DER format, without any
        whitespaces. If `key_name` is None, the top most element of the public root key
        list is returned.

        Raises `NotFoundException` if no top most element can be found.
        """

        try:
            if key_name:
                key = next(
                    key.get("key")
                    for key in self.root_keys
                    if key.get("name") == key_name
                )
            else:
                key = next(iter(self.root_keys)).get("key")
            return "".join(key.split("\n")[1:-2])
        except StopIteration:
            raise NotFoundException(
                "the give public key could not be found.", {"key_name": key_name}
            )

    def get_auth(self):
        """
        Returns authentication credentials as a dict. If notary configuration has no
        authentication, an empty dict is returned. Otherwise a YAML file with the
        credentials is read and returned.

        Raises `InvalidFormatException` if credential file has an invalid format.
        """
        if not self.auth and self.has_auth:
            with open(self.AUTH_PATH.format(self.name), "r") as cred_file:
                self.auth = yaml.safe_load(cred_file)

                if not (self.auth.get("USER") and self.auth.get("PASS")):
                    raise InvalidFormatException(
                        (
                            "credentials for host configuration "
                            "{} are in a wrong format."
                        ).format(self.name)
                    )
        return self.auth

    def get_selfsigned_cert(self):
        """
        Returns the path to a selfsigned certificate, should it exist. Otherwise None is
        returned.
        """
        if self.is_selfsigned and not self.selfsigned_cert:
            self.selfsigned_cert = self.SELFSIGNED_PATH.format(self.name)
        return self.selfsigned_cert
