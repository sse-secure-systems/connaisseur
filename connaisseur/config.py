import collections
import yaml
from connaisseur.util import validate_schema
from connaisseur.exceptions import NotFoundException, InvalidConfigurationFormatError
from connaisseur.notary import Notary


class Config:
    """
    Config Object, that contains all notary configurations inside a list.
    """

    __PATH = "/etc/connaisseur-config/config.yaml"
    __SCHEMA_PATH = "/app/connaisseur/res/config_schema.json"
    notaries: list = []

    def __init__(self):
        """
        Creates a Config object, containing all notary configurations. It does so by
        reading a config file, doing input validation and then creating Notary objects,
        storing them in a list.

        Raises `NotFoundException` if the configuration file is not found.

        Raises `InvalidFormatException` if the configuration file has an invalid format.
        """
        with open(self.__PATH, "r") as configfile:
            config_content = yaml.safe_load(configfile)

        if not config_content:
            msg = "Error loading connaisseur config file."
            raise NotFoundException(message=msg)

        self.__validate(config_content)

        self.notaries = [Notary(**notary) for notary in config_content]

    def __validate(self, config: dict):

        validate_schema(
            config,
            self.__SCHEMA_PATH,
            "Connaisseur configuration",
            InvalidConfigurationFormatError,
        )
        notary_names = [notary.get("name") for notary in config]
        if collections.Counter(notary_names)["default"] > 1:
            msg = "Too many default notary configurations."
            raise InvalidConfigurationFormatError(message=msg)

        for notary in config:
            key_names = [key.get("name") for key in notary.get("pub_root_keys")]
            if collections.Counter(key_names)["default"] > 1:
                msg = "Too many default keys in notary configuration {notary_name}."
                raise InvalidConfigurationFormatError(
                    message=msg, notary_name=notary.get("name")
                )

        self.notaries = [Notary(**notary) for notary in config]

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
            if len(self.notaries) < 2:
                msg = "No notary configurations could be found."
            else:
                msg = "Unable to find notary configuration {notary_name}."
            raise NotFoundException(message=msg, notary_name=notary_name) from err
