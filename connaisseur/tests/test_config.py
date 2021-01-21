import pytest
import connaisseur.config as co
from connaisseur.exceptions import BaseConnaisseurException


sample_config = [
    {
        "name": "default",
        "host": "notary.docker.io",
        "root_keys": [
            {
                "name": "default",
                "key": (
                    "-----BEGIN PUBLIC KEY-----"
                    "\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEOXYta5TgdCwXTCnLU09W5T4M4r9f"
                    "\nQQrqJuADP6U7g5r9ICgPSmZuRHP/1AYUfOQW3baveKsT969EfELKj1lfCA=="
                    "\n-----END PUBLIC KEY-----\n"
                ),
            },
            {
                "name": "connytest",
                "key": (
                    "-----BEGIN PUBLIC KEY-----"
                    "\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAETBDLAICCabJQXB01DOy315nDm0aD"
                    "\nBREZ4aWG+uphuFrZWw0uAVLW9B/AIcJkHa7xQ/NLtrDi3Ou5dENzDy+Lkg=="
                    "\n-----END PUBLIC KEY-----\n"
                ),
            },
        ],
    },
    {
        "name": "harbor",
        "host": "notary.harbor.domain",
        "selfsigned_cert": (
            "-----BEGIN CERTIFICATE-----"
            "\nMIIDEzCCAfugAwIBAgIQEHy1Je1mbrt0RaLDjDajszANBgkqhkiG9w0BAQsFADAU"
            "\nMRIwEAYDVQQDEwloYXJib3ItY2EwHhcNMjEwMTI2MTQyNTE5WhcNMjIwMTI2MTQy"
            "\nNTE5WjAUMRIwEAYDVQQDEwloYXJib3ItY2EwggEiMA0GCSqGSIb3DQEBAQUAA4IB"
            "\nDwAwggEKAoIBAQCfy2A79g4KGx1BN8LgNwF34pSJaKqzV9hsanNKi5iU6Sn2Qrjx"
            "\na++HlCYK8TAZ54cacP1T+d+eqlDwgMlbkXsjSFiRr3Z+KxtrrFbM9yNrNzyUiDVW"
            "\nczUQM+PFEETk2uwp7GSHFFBXeo+6p/cI2vqSqxpkVVojKmX6vEdEdPh9mwBt9nuk"
            "\nMNfaJxzzjpAPdH9TkWME+J+GpxuLhtRnE0PStC6ioYI4FeH5MCwLKv7ZVyxWYDpY"
            "\nf5qG2H00rGNOHsq9jidyLbp90jboMbVHMO6ragM6sqrjPF/cLE8oifuguCR6dbVk"
            "\nyQuIacfG/vglnp5juvFLDmf0ZVBytazWMUQzAgMBAAGjYTBfMA4GA1UdDwEB/wQE"
            "\nAwICpDAdBgNVHSUEFjAUBggrBgEFBQcDAQYIKwYBBQUHAwIwDwYDVR0TAQH/BAUw"
            "\nAwEB/zAdBgNVHQ4EFgQUwtWtGfG+NU6ZcqhJI+lKRHOW/qQwDQYJKoZIhvcNAQEL"
            "\nBQADggEBABiBHCuadw+SlmQHuK9egZSzIjvaLdKcTWdYwICtzuymZyyAWxWGeY8O"
            "\nZRZ9ZvsVX8jgTsSlFe+nV/+3MokYCvCaaDmyre7zZmRsq65ILSrwJMWjSqyvt8/X"
            "\ns78uvGgi8/ooP7eldlduOA3AdV81Ty9GeCWWqEVIjEgfVQhpYquNTyOcUp8Tuks6"
            "\n5OkY1pS58NRkoIM6/jfGtgbzsvvHooZwslmq8eaT+MucuzuGpY2GelEE5pI9Q7tf"
            "\nhMC42zeU+yxxy3vukMa4xX2BGzyjAg+qaDh6YwWui80r2/BlYXvSsSl3dIgtVwL4"
            "\nDSo1s+3uJ4evVKDRf3vLwKLTtiYfd20="
            "\n-----END CERTIFICATE-----\n"
        ),
        "root_keys": [
            {
                "name": "library",
                "key": (
                    "-----BEGIN PUBLIC KEY-----"
                    "\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEH+G0yM9CQ8KjN2cF8iHpiTA9Q69q"
                    "\n3brrzLkY1kjmRNOs0c2sx2nm8j2hFZRbyaVsd52Mkw0k5WrX+9vBfbjtdQ=="
                    "\n-----END PUBLIC KEY-----\n"
                ),
            }
        ],
        "auth": {"secretName": "harbor-creds"},
        "is_acr": True,
    },
]


@pytest.fixture
def mock_config_path():
    co.Config.path = "tests/data/sample_config.yaml"
    co.Config.schema_path = "res/config_schema.json"


@pytest.fixture
def mock_safe_path_func(monkeypatch):
    def m_safe_path_func(callback: callable, base_dir: str, path: str, *args, **kwargs):
        return callback(path, *args, **kwargs)

    monkeypatch.setattr(co, "safe_path_func", m_safe_path_func)


def test_config(mock_config_path):
    config = co.Config()
    assert len(config.notaries) == 2
    for index, notary in enumerate(config.notaries):
        assert notary.name == sample_config[index]["name"]
        assert notary.host == sample_config[index]["host"]


@pytest.mark.parametrize(
    "config_path, error",
    [
        (
            "tests/data/sample_config_err1.yaml",
            "error getting any notary host configurations.",
        ),
        (
            "tests/data/sample_config_err2.yaml",
            "invalid format for Connaisseur configuration.",
        ),
        (
            "tests/data/sample_config_err3.yaml",
            "invalid format for Connaisseur configuration.",
        ),
        (
            "tests/data/sample_config_err4.yaml",
            "invalid format for Connaisseur configuration.",
        ),
    ],
)
def test_config_error(mock_config_path, config_path, error):
    co.Config.path = config_path
    with pytest.raises(BaseConnaisseurException) as err:
        config = co.Config()
    assert error in str(err.value)


@pytest.mark.parametrize(
    "key_name, host",
    [
        ("default", "notary.docker.io"),
        ("harbor", "notary.harbor.domain"),
        (None, "notary.docker.io"),
    ],
)
def test_get_notary(mock_config_path, key_name, host):
    config = co.Config()
    assert config.get_notary(key_name).host == host


def test_get_notary_error(mock_config_path):
    config = co.Config()
    config.notaries = []
    with pytest.raises(BaseConnaisseurException) as err:
        config.get_notary()
    assert "the given notary configuration could not be found." in str(err.value)


@pytest.mark.parametrize("notary_config", [(sample_config[0]), (sample_config[1])])
def test_notary(notary_config: dict):
    notary = co.Notary(**notary_config)
    assert notary.name == notary_config["name"]
    assert notary.host == notary_config["host"]
    assert notary.root_keys == notary_config["root_keys"]
    assert notary.is_acr == notary_config.get("is_acr", False)
    assert notary.selfsigned_cert is None
    assert notary.auth is None


@pytest.mark.parametrize("del_field", [("name"), ("host"), ("root_keys")])
def test_notary_error(del_field: str):
    notary_config = dict(sample_config[0])
    notary_config[del_field] = None
    with pytest.raises(BaseConnaisseurException) as err:
        co.Notary(**notary_config)
    assert "insufficient fields fo notary configuration." in str(err.value)


@pytest.mark.parametrize(
    "notary_config_num, key_name, key",
    [
        (0, "default", 0),
        (0, "connytest", 1),
        (0, None, 0),
        (1, "library", 0),
        (1, None, 0),
    ],
)
def test_get_key(notary_config_num, key_name, key):
    notary = co.Notary(**sample_config[notary_config_num])
    assert (
        notary.get_key(key_name)
        == sample_config[notary_config_num]["root_keys"][key]["key"]
    )


def test_get_key_error():
    notary = co.Notary(**sample_config[0])
    with pytest.raises(BaseConnaisseurException) as err:
        notary.get_key("hello")
    assert "the given public key could not be found." in str(err.value)


def test_get_auth(mock_safe_path_func):
    notary = co.Notary(**sample_config[0])
    notary.name = "sample_auth"
    notary.AUTH_PATH = "tests/data/{}.yaml"
    assert notary.auth == ("hans", "wurst")


def test_get_auth_empty(mock_safe_path_func):
    notary = co.Notary(**sample_config[0])
    notary.name = "sample_authh"
    notary.AUTH_PATH = "tests/data/{}.yaml"
    assert notary.auth is None


def test_get_auth_error(mock_safe_path_func):
    notary = co.Notary(**sample_config[0])
    notary.name = "sample_auth_err"
    notary.AUTH_PATH = "tests/data/{}.yaml"
    with pytest.raises(BaseConnaisseurException) as err:
        notary.auth
    assert (
        f"credentials for host configuration {notary.name} are in a wrong format."
        in str(err.value)
    )


@pytest.mark.parametrize("notary, out", [(1, "tests/data/harbor.cert"), (0, None)])
def test_selfsigned_cert(mock_safe_path_func, notary, out):
    notary = co.Notary(**sample_config[notary])
    notary.SELFSIGNED_PATH = "tests/data/{}.cert"
    assert notary.selfsigned_cert == out
