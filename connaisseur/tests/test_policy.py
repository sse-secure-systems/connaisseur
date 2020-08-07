import pytest
import connaisseur.policy
from connaisseur.image import Image
from connaisseur.exceptions import BaseConnaisseurException

match_image_tag = "docker.io/phbelitz/sample:v1"
match_image_digest = (
    "docker.io/phbelitz/sample@sha256:"
    "1388abc7a12532836c3a81bdb0087409b15208f5aeba7a87aedcfd56d637c145"
)
policy = {
    "rules": [
        {"pattern": "*:*", "verify": True, "delegations": ["phbelitz", "chamsen"]},
        {"pattern": "docker.io/*:*", "verify": True, "delegations": ["phbelitz"]},
        {"pattern": "k8s.gcr.io/*:*", "verify": False},
        {"pattern": "gcr.io/*:*", "verify": False},
        {
            "pattern": "docker.io/phbelitz/*:*",
            "verify": True,
            "delegations": ["daugustin"],
        },
        {
            "pattern": "docker.io/phbelitz/sample",
            "verify": True,
            "delegations": ["phbelitz", "chamsen"],
        },
        {"pattern": "docker.io/phbelitz/sample:v4", "verify": False},
        {
            "pattern": "docker.io/securesystemsengineering/connaisseur:*",
            "verify": False,
        },
        {"pattern": "docker.io/phbelitz/sample-san-sama", "verify": True},
    ]
}


@pytest.fixture
def pol():
    return connaisseur.policy


@pytest.fixture
def mock_policy(monkeypatch):
    def get_policy():
        return policy

    connaisseur.policy.ImagePolicy.get_image_policy = staticmethod(get_policy)
    connaisseur.policy.ImagePolicy.JSON_SCHEMA_PATH = "res/policy_schema.json"


@pytest.mark.parametrize(
    "rule, image, comp_count, comp_len, pre_len",
    [
        ("", "", 1, [2], [0]),
        ("*:*", match_image_tag, 1, [3], [0]),
        ("doc*/*", match_image_tag, 2, [4, 3], [3, 0]),
        ("*/phb*/*:*", match_image_tag, 3, [1, 4, 3], [0, 3, 0]),
        ("*@sha256:*", match_image_digest, 1, [10], [0]),
    ],
)
def test_match(
    pol, rule: str, image: str, comp_count: int, comp_len: list, pre_len: list
):
    match = pol.Match(rule, image)
    rule_with_tag = rule if ":" in rule else f"{rule}:*"
    assert match.key == rule
    assert match.pattern == rule_with_tag
    assert match.component_count == comp_count
    assert match.component_lengths == comp_len
    assert match.prefix_lengths == pre_len


@pytest.mark.parametrize("rule, exist", [("", False), ("*", True)])
def test_match_bool(pol, rule: str, exist: bool):
    match = pol.Match(rule, "image")
    assert bool(match) == exist


@pytest.mark.parametrize(
    "rule1, rule2, image",
    [
        ("", "*", match_image_tag),
        ("*", "*:*", match_image_tag),
        ("*:*", "*/*", match_image_tag),
        ("*/*", "docker*/*", match_image_tag),
        ("docker*/*", "*/*/*", match_image_tag),
        ("*/*/image:v1", "*/sam*/*", match_image_tag),
    ],
)
def test_match_compare(pol, rule1: str, rule2: str, image: str):
    m1 = pol.Match(rule1, image)
    m2 = pol.Match(rule2, image)
    fighters = [m1, m2]
    assert m1.compare(m2) == fighters[1]


def test_image_pol(pol, mock_policy):
    p = pol.ImagePolicy()
    assert p.policy == policy


@pytest.mark.parametrize(
    "image, rule",
    [
        (
            "image:tag",
            {"pattern": "docker.io/*:*", "verify": True, "delegations": ["phbelitz"]},
        ),
        (
            "reg.io/image:tag",
            {"pattern": "*:*", "verify": True, "delegations": ["phbelitz", "chamsen"]},
        ),
        ("k8s.gcr.io/path/image", {"pattern": "k8s.gcr.io/*:*", "verify": False}),
        (
            "docker.io/phbelitz/sample:v4",
            {"pattern": "docker.io/phbelitz/sample:v4", "verify": False},
        ),
    ],
)
def test_get_matching_rule(pol, mock_policy, image: str, rule: dict):
    p = pol.ImagePolicy()
    assert p.get_matching_rule(Image(image)) == rule


def test_get_matching_rule_error(pol, mock_policy):
    p = pol.ImagePolicy()
    p.policy["rules"] = p.policy["rules"][1:]
    with pytest.raises(BaseConnaisseurException) as err:
        p.get_matching_rule(Image("reg.io/image"))
    assert (
        "no matching rule for image " '"reg.io/image:latest" could be found.'
    ) in str(err.value)


def test_image_pol_error(pol, mock_policy):
    policy["rules"] += {"pattern": "***"}
    with pytest.raises(BaseConnaisseurException) as err:
        assert pol.ImagePolicy()
    assert "invalid format for image policy." in str(err.value)
