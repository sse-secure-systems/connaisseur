import os
import collections
import json
import yaml
from jsonschema import validate, ValidationError
from connaisseur.exceptions import NotFoundException, InvalidFormatException
from connaisseur.util import safe_path_func


class Config:
    """
    Config Object, that contains all notary configurations inside a list.
    """

    path = "/etc/connaisseur-config/config.yaml"
    schema_path = "/app/connaisseur/res/config_schema.json"
    notaries: list = []

    def __init__(self):
        """
        Creates a Config object, containing all notary configurations. It does so by
        reading a config file, doing input validation and then creating Notary objects,
        storing them in a list.

        Raises `NotFoundException` if the configuration file is not found.

        Raises `InvalidFormatException` if the configuration file has an invalid format.
        """
        with open(self.path, "r") as configfile:
            config_content = yaml.safe_load(configfile)

        if not config_content:
            raise NotFoundException("error getting any notary host configurations.")

        self._validate(config_content)

        self.notaries = [Notary(**notary) for notary in config_content]

    def _validate(self, config: dict):
        with open(self.schema_path, "r") as schema_file:
            schema = json.load(schema_file)

        try:
            validate(instance=config, schema=schema)
            notary_names = [notary.get("name") for notary in config]
            if collections.Counter(notary_names)["default"] > 1:
                raise ValidationError("")

            for notary in config:
                key_names = [key.get("name") for key in notary.get("root_keys")]
                if collections.Counter(key_names)["default"] > 1:
                    raise ValidationError("")
        except ValidationError as err:
            raise InvalidFormatException(
                "invalid format for Connaisseur configuration."
            ) from err

    def get_notary(self, notary_name: str = None):
        """
        Returns the notary configuration with the given `notary_name`. If `notary_name`
        is None, the element with `name=default` is taken, or the only existing element.

        Raises `NotFoundException` if no matching or default element can be found.
        """
        try:
            if len(self.notaries) < 2:
                return next(iter(self.notaries))

            notary_name = notary_name or "default"
            return next(
                notary for notary in self.notaries if notary.name == notary_name
            )
        except StopIteration as err:
            raise NotFoundException(
                "the given notary configuration could not be found.",
                {"notary_name": notary_name},
            ) from err


class Notary:
    """
    Notary object, that holds all information for a single notary configuration.
    """

    name: str
    host: str
    root_keys: list
    is_acr: bool = False

    SELFSIGNED_PATH = "/etc/certs/{}.crt"
    AUTH_PATH = "/etc/creds/{}/cred.yaml"

    def __init__(self, name: str, host: str, root_keys: list, **kwargs):
        """
        Creates a Notary object from a dictionary.

        Raises `InvalidFormatException` should the mandatory fields be missing.
        """

        if not (name and host and root_keys):
            raise InvalidFormatException("insufficient fields fo notary configuration.")

        self.name = name
        self.host = host
        self.root_keys = root_keys
        self.is_acr = kwargs.get("is_acr", False)

    def get_key(self, key_name: str = None):
        """
        Returns the public root key with name `key_name` in DER format, without any
        whitespaces. If `key_name` is None, the element with `name=default` is returned,
        or the only existing element.

        Raises `NotFoundException` if no matching or default element can be found.
        """

        try:
            if len(self.root_keys) < 2:
                key = next(iter(self.root_keys))["key"]
            else:
                key_name = key_name or "default"
                key = next(
                    key["key"] for key in self.root_keys if key["name"] == key_name
                )
            return "".join(key)
        except StopIteration as err:
            raise NotFoundException(
                "the given public key could not be found.", {"key_name": key_name}
            ) from err

    @property
    def auth(self):
        """
        Returns authentication credentials as a dict. If notary configuration has no
        authentication, an empty dict is returned. Otherwise a YAML file with the
        credentials is read and returned.

        Raises `InvalidFormatException` if credential file has an invalid format.
        """
        try:
            with safe_path_func(
                open, "/etc/creds/", self.AUTH_PATH.format(self.name), "r"
            ) as cred_file:
                auth = yaml.safe_load(cred_file)

                try:
                    return auth["USER"], auth["PASS"]
                except KeyError as err:
                    msg = (
                        f"credentials for host configuration "
                        f"{self.name} are in a wrong format."
                    )
                    raise InvalidFormatException(msg) from err
        except FileNotFoundError:
            return None

    @property
    def selfsigned_cert(self):
        """
        Returns the path to a selfsigned certificate, should it exist. Otherwise None is
        returned.
        """
        path = self.SELFSIGNED_PATH.format(self.name)
        return path if safe_path_func(os.path.exists, "/etc/certs/", path) else None
