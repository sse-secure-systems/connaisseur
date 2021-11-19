import collections
import fnmatch
import os
import yaml

from connaisseur.exceptions import (
    InvalidConfigurationFormatError,
    NoMatchingPolicyRuleError,
    NotFoundException,
)
from connaisseur.image import Image
from connaisseur.util import safe_path_func, validate_schema
from connaisseur.validators.validator import Validator


class Config:
    """
    Config Object that contains all notary configurations.
    """

    __PATH = "/app/connaisseur-config/config.yaml"
    __SECRETS_PATH = "/app/connaisseur-config/config-secrets.yaml"
    __EXTERNAL_PATH = "/app/connaisseur-config/"
    __SCHEMA_PATH = "/app/connaisseur/res/config_schema.json"
    validators: list = []
    policy: list = []

    def __init__(self):
        """
        Create a Config object, containing all validator configurations.
        Read a config file, validate its contents and then create Validator objects,
        storing them.

        Raise `NotFoundException` if the configuration file is not found.

        Raise `InvalidFormatException` if the configuration file has an invalid format.
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

        self.validators = [
            Validator(**validator) for validator in config.get("validators")
        ]
        self.policy = config.get("policy")

    def __merge_configs(self, config: dict, secrets_config: dict):
        for validator in config.get("validators", {}):
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
        validator_names = [
            validator.get("name") for validator in config.get("validators")
        ]
        if collections.Counter(validator_names)["default"] > 1:
            msg = "Too many default validator configurations."
            raise InvalidConfigurationFormatError(message=msg)

    def get_validator(self, validator_name: str = None):
        """
        Return the validator configuration with the given `validator_name`. If
        `validator_name` is None, return the element with `name=default`, or the only
        existing element.

        Raise `NotFoundException` if no matching or default element can be found.
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

    def get_policy_rule(self, image: Image):
        best_match = Match("", "")
        for rule in map(lambda x: x["pattern"], self.policy):
            rule_with_tag = f"{rule}:*" if ":" not in rule else rule
            if fnmatch.fnmatch(str(image), rule_with_tag):
                match = Match(rule, str(image))
                best_match = match.compare(best_match)

        if not best_match:
            msg = "No matching policy rule could be found for image {image_name}."
            raise NoMatchingPolicyRuleError(message=msg, image_name=str(image))

        most_specific_rule = next(
            filter(lambda x: x["pattern"] == best_match.key, self.policy), None
        )

        return Rule(**most_specific_rule)


class Rule:
    def __init__(self, pattern: str, **kwargs):
        self.pattern = pattern
        self.validator = kwargs.get("validator")
        self.arguments = kwargs.get("with", {})

    def __str__(self):
        return self.pattern


class Match:
    """
    Matching object that represents a `rule` pattern. Hold information about
    number of components and longest prefix matches between its components and
    the `images` components.
    """

    key: str
    pattern: str
    component_count: int
    component_lengths: list
    prefix_lengths: list

    def __init__(self, rule: str, image: str):
        self.key = rule

        self.pattern = f"{rule}:*" if ":" not in rule else rule

        components = self.pattern.split("/")
        self.component_count = len(components)

        self.component_lengths = [
            len(components[index]) for index in range(self.component_count)
        ]

        image_components = str(image).split("/")
        self.prefix_lengths = [
            len(
                self.longest_common_prefix([image_components[index], components[index]])
            )
            for index in range(len(components))
        ]

    def __bool__(self):
        return bool(self.key)

    @staticmethod
    def longest_common_prefix(strings: list):
        """
        Return the longest matching prefix among all given `strings`.
        """
        if not strings:
            return ""
        low, high = 0, min(map(len, strings))
        # the binary search on the length of prefix on the first word
        while low <= high:
            mid = (low + high) // 2
            # take all strings of length `mid` and put them into a set
            # if all strings match, the set has size 1
            if len({x[:mid] for x in strings}) == 1:
                low = mid + 1
            else:
                high = mid - 1
        return strings[0][:high]

    def compare(self, match):
        """
        Compare the match object with another `match`. Return the more
        specific one.
        """
        if self.component_count > match.component_count:
            return self
        elif self.component_count < match.component_count:
            return match
        else:
            for p_i in range(len(self.prefix_lengths)):
                if self.prefix_lengths[p_i] > match.prefix_lengths[p_i]:
                    return self
                elif self.prefix_lengths[p_i] < match.prefix_lengths[p_i]:
                    return match
            for c_i in range(len(self.component_lengths)):
                if self.component_lengths[c_i] > match.component_lengths[c_i]:
                    return self
                else:
                    return match
