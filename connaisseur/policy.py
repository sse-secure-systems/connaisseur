import os
import fnmatch
import json
from jsonschema import validate, ValidationError
import connaisseur.kube_api as kapi
from connaisseur.image import Image
from connaisseur.exceptions import (
    InvalidPolicyFormatError,
    NoMatchingPolicyRuleError,
)


class ImagePolicy:
    """
    Holds the image policy as a `dict` and can return a matching rule, given
    an image.

    Accesses the policy from the kubernetes cluster via its API and validates
    it.

    Raises an `InvalidFormatException` should the policy not conform a defined
    schema.
    """

    policy: dict
    _schema_path = "connaisseur/res/policy_schema.json"

    def __init__(self):
        # load policy from k8s
        image_policy = ImagePolicy.__get_image_policy()

        # validate policy
        with open(self._schema_path, "r") as schema_file:
            schema = json.load(schema_file)
        try:
            validate(instance=image_policy, schema=schema)
        except ValidationError as err:
            msg = "Image policy has an invalid format: {validation_err}."
            raise InvalidPolicyFormatError(
                message=msg, validation_err=str(err)
            ) from err

        self.policy = image_policy

    @staticmethod
    def __get_image_policy():
        """
        Loads the image policy from the kubernetes API.
        """
        image_policy = os.environ.get("CONNAISSEUR_IMAGE_POLICY")

        path = f"apis/connaisseur.policy/v1/imagepolicies/{image_policy}"
        response = kapi.request_kube_api(path)

        return response["spec"]

    def get_matching_rule(self, image: Image):
        """
        Returns for a given `image` the most specific matching rule.
        """
        rules = [rule["pattern"] for rule in self.policy["rules"]]

        best_match = Match("", "")
        for rule in rules:
            rule_with_tag = f"{rule}:*" if ":" not in rule else rule
            if fnmatch.fnmatch(str(image), rule_with_tag):
                match = Match(rule, str(image))
                best_match = match.compare(best_match)

        if not best_match:
            msg = "No matching policy rule could be found for image {image_name}."
            raise NoMatchingPolicyRuleError(message=msg, image_name=str(image))

        most_specific_rule = next(
            filter(lambda x: x["pattern"] == best_match.key, self.policy["rules"]), None
        )

        return Rule(**most_specific_rule)


class Rule:
    def __init__(self, pattern: str, **kwargs):
        self.pattern = pattern
        self.verify = kwargs.get("verify", True)
        self.delegations = kwargs.get("delegations", [])
        self.notary = kwargs.get("notary")
        self.key = kwargs.get("key")

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

    def longest_common_prefix(self, strings: list):
        """
        Returns the longest matching prefix among all given `strings`.
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
        Compares the match object with another `match`. Returns the more
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
