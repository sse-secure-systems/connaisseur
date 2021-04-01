import pytest
import conftest as fix
import connaisseur.policy as pol
import connaisseur.exceptions as exc
from connaisseur.image import Image
from connaisseur.exceptions import BaseConnaisseurException

match_image_tag = "docker.io/securesystemsengineering/sample:v1"
match_image_digest = (
    "docker.io/securesystemsengineering/sample@sha256:"
    "1388abc7a12532836c3a81bdb0087409b15208f5aeba7a87aedcfd56d637c145"
)


@pytest.mark.parametrize(
    "rule, image, comp_count, comp_len, pre_len",
    [
        ("", "", 1, [2], [0]),
        ("*:*", match_image_tag, 1, [3], [0]),
        ("doc*/*", match_image_tag, 2, [4, 3], [3, 0]),
        ("*/sec*/*:*", match_image_tag, 3, [1, 4, 3], [0, 3, 0]),
        ("*@sha256:*", match_image_digest, 1, [10], [0]),
    ],
)
def test_match(rule: str, image: str, comp_count: int, comp_len: list, pre_len: list):
    match = pol.Match(rule, image)
    rule_with_tag = rule if ":" in rule else f"{rule}:*"
    assert match.key == rule
    assert match.pattern == rule_with_tag
    assert match.component_count == comp_count
    assert match.component_lengths == comp_len
    assert match.prefix_lengths == pre_len


@pytest.mark.parametrize("rule, exist", [("", False), ("*", True)])
def test_match_bool(rule: str, exist: bool):
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
def test_match_compare(rule1: str, rule2: str, image: str):
    m1 = pol.Match(rule1, image)
    m2 = pol.Match(rule2, image)
    fighters = [m1, m2]
    assert m1.compare(m2) == fighters[1]


@pytest.mark.parametrize(
    "func, exception",
    [
        (lambda: {"rules": [{"pattern": "*:*", "verify": True}]}, fix.no_exc()),
        (lambda: {"wrong": "format"}, pytest.raises(exc.InvalidPolicyFormatError)),
    ],
)
def test_image_pol_init(m_policy, func, exception):
    with exception:
        pol.ImagePolicy._ImagePolicy__get_image_policy = func
        p = pol.ImagePolicy()
        assert p.policy


@pytest.mark.parametrize(
    "image, rule",
    [
        ("image:tag", "docker.io/*:*"),
        ("reg.io/image:tag", "*:*"),
        ("k8s.gcr.io/path/image", "k8s.gcr.io/*:*"),
        (
            "docker.io/securesystemsengineering/sample:v4",
            "docker.io/securesystemsengineering/sample:v4",
        ),
    ],
)
def test_get_matching_rule(m_policy, image: str, rule):
    p = pol.ImagePolicy()
    assert str(p.get_matching_rule(Image(image))) == rule


def test_get_matching_rule_error(m_policy):
    with pytest.raises(exc.NoMatchingPolicyRuleError):
        p = pol.ImagePolicy()
        p.policy["rules"] = p.policy["rules"][1:]
        assert p.get_matching_rule(Image("reg.io/image"))
