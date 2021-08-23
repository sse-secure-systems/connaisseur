import os
import collections
import yaml
from connaisseur.util import validate_schema
from connaisseur.exceptions import NotFoundException, InvalidConfigurationFormatError
from connaisseur.validators.validator import Validator
from connaisseur.util import safe_path_func


class Config:
    """
    Config Object, that contains all notary configurations inside a list.
    """

    __PATH = "/app/connaisseur-config/config.yaml"
    __SECRETS_PATH = "/app/connaisseur-config/config-secrets.yaml"
    __EXTERNAL_PATH = "/app/connaisseur-config/"
    __SCHEMA_PATH = "/app/connaisseur/res/config_schema.json"
    validators: list = []

    def __init__(self):
        """
        Creates a Config object, containing all validator configurations. It does so by
        reading a config file, doing input validation and then creating Validator objects,
        storing them in a list.

        Raises `NotFoundException` if the configuration file is not found.

        Raises `InvalidFormatException` if the configuration file has an invalid format.
        """
        with open(self.__PATH, "r", encoding="utf-8") as configfile:
            config_content = yaml.safe_load(configfile)

        if not config_content:
            msg = "Error loading connaisseur config file."
            raise NotFoundException(message=msg)

        with open(self.__SECRETS_PATH, "r", encoding="utf-8") as secrets_configfile:
            secrets_config_content = yaml.safe_load(secrets_configfile)

        config = self.__merge_configs(config_content, secrets_config_content)

        self.__validate(config)

        self.validators = [Validator(**validator) for validator in config]

    def __merge_configs(self, config: dict, secrets_config: dict):
        for validator in config:
            validator.update(secrets_config.get(validator.get("name"), {}))
            # keep in mind that neither the contents of `validator`, `secrets_config` or
            # `auth_file` are considered secure yet, as they haven't been matched against
            # the JSON schema. the use of the `safe_path_func` and the later overall
            # validation still allows to use them freely
            try:
                auth_path = f'{self.__EXTERNAL_PATH}{validator["name"]}/auth.yaml'
                if safe_path_func(os.path.exists, self.__EXTERNAL_PATH, auth_path):
                    with safe_path_func(
                        open, self.__EXTERNAL_PATH, auth_path, "r"
                    ) as auth_file:
                        auth_dict = {"auth": yaml.safe_load(auth_file)}
                    validator.update(auth_dict)
            except KeyError:
                pass
        return config

    def __validate(self, config: dict):
        validate_schema(
            config,
            self.__SCHEMA_PATH,
            "Connaisseur configuration",
            InvalidConfigurationFormatError,
        )
        validator_names = [validator.get("name") for validator in config]
        if collections.Counter(validator_names)["default"] > 1:
            msg = "Too many default validator configurations."
            raise InvalidConfigurationFormatError(message=msg)

    def get_validator(self, validator_name: str = None):
        """
        Returns the validator configuration with the given `validator_name`. If
        `validator_name` is None, the element with `name=default` is taken, or the only
        existing element.

        Raises `NotFoundException` if no matching or default element can be found.
        """
        try:
            return list(
                filter(
                    lambda v: v.name == (validator_name or "default"), self.validators
                )
            )[0]
        except IndexError as err:
            msg = "Unable to find validator configuration {validator_name}."
            raise NotFoundException(message=msg, validator_name=validator_name) from err
