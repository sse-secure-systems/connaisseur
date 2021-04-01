import pytest
import conftest as fix
import connaisseur.config as co
import connaisseur.exceptions as exc


@pytest.fixture(autouse=True)
def mock_config_path():
    co.Config._Config__PATH = "tests/data/config/sample_config.yaml"
    co.Config._Config__SCHEMA_PATH = "res/config_schema.json"


static_config = [
    {
        "name": "default",
        "host": "notary.docker.io",
    },
    {
        "name": "harbor",
        "host": "notary.harbor.domain",
    },
]


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
            pytest.raises(exc.InvalidConfigurationFormatError, match=r".*notary.*"),
        ),
        ("err4", pytest.raises(exc.InvalidConfigurationFormatError, match=r".*keys.*")),
    ],
)
def test_config(config_path, exception):
    co.Config._Config__PATH = f"tests/data/config/{config_path}.yaml"
    with exception:
        config = co.Config()
        assert len(config.notaries) == 2
        for index, notary in enumerate(config.notaries):
            assert notary.name == static_config[index]["name"]
            assert notary.host == static_config[index]["host"]


@pytest.mark.parametrize(
    "key_name, host, exception",
    [
        ("default", "notary.docker.io", fix.no_exc()),
        ("harbor", "notary.harbor.domain", fix.no_exc()),
        (None, "notary.docker.io", fix.no_exc()),
        ("harborr", "", pytest.raises(exc.NotFoundException)),
    ],
)
def test_get_notary(key_name, host, exception):
    config = co.Config()
    with exception:
        assert config.get_notary(key_name).host == host
