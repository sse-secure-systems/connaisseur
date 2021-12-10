import pytest
from . import conftest as fix
import connaisseur.config as co
import connaisseur.exceptions as exc
import connaisseur.validators as vals
from connaisseur.image import Image


@pytest.fixture(autouse=True)
def mock_config_path(monkeypatch):
    def m_safe_path_func(callback: callable, base_dir: str, path: str, *args, **kwargs):
        return callback(path, *args, **kwargs)

    monkeypatch.setattr(co, "safe_path_func", m_safe_path_func)

    co.Config._Config__PATH = "tests/data/config/sample_config.yaml"
    co.Config._Config__SECRETS_PATH = "tests/data/config/sample_secrets.yaml"
    co.Config._Config__EXTERNAL_PATH = "tests/data/config/"
    co.Config._Config__SCHEMA_PATH = "connaisseur/res/config_schema.json"


nv1 = vals.notaryv1.notaryv1_validator.NotaryV1Validator
static = vals.static.static_validator.StaticValidator
cosign = vals.cosign.cosign_validator.CosignValidator
static_config = {
    "validators": [
        {
            "name": "default",
            "type": nv1,
        },
        {
            "name": "harbor",
            "type": nv1,
        },
        {"name": "allow", "type": static},
        {"name": "deny", "type": static},
        {"name": "cosign-example", "type": cosign},
        {"name": "ext", "type": nv1},
        {"name": "localhost", "type": nv1},
        {"name": "localhost_port", "type": nv1},
    ],
    "policy": [
        {"pattern": "*:*", "with": {"delegations": ["phbelitz", "chamsen"]}},
        {
            "pattern": "docker.io/*:*",
            "validator": "dockerhub",
            "with": {"delegations": ["phbelitz"]},
        },
        {"pattern": "k8s.gcr.io/*:*", "validator": "allow"},
        {"pattern": "gcr.io/*:*", "validator": "allow"},
        {
            "pattern": "docker.io/securesystemsengineering/*:*",
            "validator": "dockerhub",
            "with": {"delegations": ["someuserthatdidnotsign"]},
        },
        {
            "pattern": "docker.io/securesystemsengineering/sample",
            "validator": "dockerhub",
            "with": {"delegations": ["phbelitz", "chamsen"]},
        },
        {
            "pattern": "docker.io/securesystemsengineering/sample:v4",
            "validator": "allow",
        },
        {
            "pattern": "docker.io/securesystemsengineering/connaisseur:*",
            "validator": "allow",
        },
        {
            "pattern": "docker.io/securesystemsengineering/sample-san-sama",
            "validator": "allow",
        },
        {
            "pattern": "docker.io/securesystemsengineering/alice-image",
            "validator": "dockerhub",
        },
    ],
}
match_image_tag = "docker.io/securesystemsengineering/sample:v1"
match_image_digest = (
    "docker.io/securesystemsengineering/sample@sha256:"
    "1388abc7a12532836c3a81bdb0087409b15208f5aeba7a87aedcfd56d637c145"
)


@pytest.mark.parametrize(
    "config_path, exception",
    [
        ("sample_config", fix.no_exc()),
        ("err", pytest.raises(FileNotFoundError)),
        ("err1", pytest.raises(exc.NotFoundException)),
        (
            "err2",
            pytest.raises(
                exc.InvalidConfigurationFormatError, match=r".*invalid format.*"
            ),
        ),
        (
            "err3",
            pytest.raises(exc.InvalidConfigurationFormatError, match=r".*validator.*"),
        ),
        (
            "err4",
            pytest.raises(exc.InvalidConfigurationFormatError, match=r".*roots.*"),
        ),
        (
            "err5",
            pytest.raises(
                exc.InvalidConfigurationFormatError, match=r".*invalid format.*"
            ),
        ),
        (
            "err6",
            pytest.raises(
                exc.InvalidConfigurationFormatError,
                match=r".*Connaisseur configuration.*",
            ),
        ),
    ],
)
def test_config(config_path, exception):
    co.Config._Config__PATH = f"tests/data/config/{config_path}.yaml"
    with exception:
        config = co.Config()
        assert len(config.validators) == len(static_config["validators"])
        assert len(config.policy) == len(static_config["policy"])
        for index, validator in enumerate(config.validators):
            assert validator.name == static_config["validators"][index]["name"]
            assert isinstance(validator, static_config["validators"][index]["type"])
        for index, rule in enumerate(config.policy):
            assert rule["pattern"] == static_config["policy"][index]["pattern"]


@pytest.mark.parametrize(
    "key_name, name, exception",
    [
        ("default", "default", fix.no_exc()),
        ("harbor", "harbor", fix.no_exc()),
        (None, "default", fix.no_exc()),
        ("harborr", "", pytest.raises(exc.NotFoundException)),
    ],
)
def test_get_notary(key_name, name, exception):
    config = co.Config()
    with exception:
        assert config.get_validator(key_name).name == name


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
    match = co.Match(rule, image)
    rule_with_tag = rule if ":" in rule else f"{rule}:*"
    assert match.key == rule
    assert match.pattern == rule_with_tag
    assert match.component_count == comp_count
    assert match.component_lengths == comp_len
    assert match.prefix_lengths == pre_len


@pytest.mark.parametrize("rule, exist", [("", False), ("*", True)])
def test_match_bool(rule: str, exist: bool):
    match = co.Match(rule, "image")
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
    m1 = co.Match(rule1, image)
    m2 = co.Match(rule2, image)
    fighters = [m1, m2]
    assert m1.compare(m2) == fighters[1]


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
def test_get_policy_rule(image: str, rule):
    c = co.Config()
    assert str(c.get_policy_rule(Image(image))) == rule


def test_get_matching_rule_error():
    with pytest.raises(exc.NoMatchingPolicyRuleError):
        c = co.Config()
        c.policy = c.policy[1:]
        assert c.get_policy_rule(Image("reg.io/image"))
