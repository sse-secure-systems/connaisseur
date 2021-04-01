import yaml
import pytest
import conftest as fix
import connaisseur.notary as notary
import connaisseur.exceptions as exc
import connaisseur.util
from connaisseur.image import Image


@pytest.fixture
def mock_safe_path_func(monkeypatch):
    def m_safe_path_func(callback: callable, base_dir: str, path: str, *args, **kwargs):
        return callback(path, *args, **kwargs)

    monkeypatch.setattr(notary, "safe_path_func", m_safe_path_func)


@pytest.fixture
def sample_notaries():
    li = []
    for file_name in ("notary1", "notary2", "err1", "err2", "err3", "unhealthy_notary"):
        with open(f"tests/data/notary/{file_name}.yaml") as file:
            li.append(yaml.safe_load(file))
    return li


static_notaries = [
    {
        "name": "default",
        "host": "notary.docker.io",
        "pub_root_keys": [
            {
                "name": "default",
                "key": (
                    "-----BEGIN PUBLIC KEY-----\n"
                    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEOXYta5TgdCwXTCnLU09W5T4M4r9f\n"
                    "QQrqJuADP6U7g5r9ICgPSmZuRHP/1AYUfOQW3baveKsT969EfELKj1lfCA==\n"
                    "-----END PUBLIC KEY-----\n"
                ),
            },
            {
                "name": "connytest",
                "key": (
                    "-----BEGIN PUBLIC KEY-----\n"
                    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAETBDLAICCabJQXB01DOy315nDm0aD\n"
                    "BREZ4aWG+uphuFrZWw0uAVLW9B/AIcJkHa7xQ/NLtrDi3Ou5dENzDy+Lkg==\n"
                    "-----END PUBLIC KEY-----\n"
                ),
            },
        ],
        "is_acr": False,
    },
    {
        "name": "harbor",
        "host": "notary.harbor.domain",
        "pub_root_keys": [
            {
                "name": "library",
                "key": "-----BEGIN PUBLIC KEY-----\n"
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEH+G0yM9CQ8KjN2cF8iHpiTA9Q69q\n"
                "3brrzLkY1kjmRNOs0c2sx2nm8j2hFZRbyaVsd52Mkw0k5WrX+9vBfbjtdQ==\n"
                "-----END PUBLIC KEY-----\n",
            }
        ],
        "is_acr": True,
    },
]


@pytest.mark.parametrize(
    "index, exception",
    [
        (0, fix.no_exc()),
        (1, fix.no_exc()),
        (2, pytest.raises(exc.InvalidFormatException)),
        (3, pytest.raises(exc.InvalidFormatException)),
        (4, pytest.raises(exc.InvalidFormatException)),
    ],
)
def test_notary(sample_notaries, index, exception):
    with exception:
        no = notary.Notary(**sample_notaries[index])
        assert no.name == static_notaries[index]["name"]
        assert no.host == static_notaries[index]["host"]
        assert no.pub_root_keys == static_notaries[index]["pub_root_keys"]
        assert no.is_acr == static_notaries[index].get("is_acr", False)


@pytest.mark.parametrize(
    "index, key_name, key, exception",
    [
        (0, "default", 0, fix.no_exc()),
        (0, "connytest", 1, fix.no_exc()),
        (0, None, 0, fix.no_exc()),
        (1, "library", 0, fix.no_exc()),
        (1, None, 0, fix.no_exc()),
        (0, "sample_key", 0, pytest.raises(exc.NotFoundException)),
    ],
)
def test_get_key(sample_notaries, index, key_name, key, exception):
    no = notary.Notary(**sample_notaries[index])
    with exception:
        assert (
            no.get_key(key_name) == static_notaries[index]["pub_root_keys"][key]["key"]
        )


@pytest.mark.parametrize(
    "auth_file, creds, exception",
    [
        ("sample_auth", ("hans", "wurst"), fix.no_exc()),
        ("sample_authhh", None, fix.no_exc()),
        ("sample_auth_err", None, pytest.raises(exc.InvalidFormatException)),
    ],
)
def test_auth(mock_safe_path_func, sample_notaries, auth_file, creds, exception):
    no = notary.Notary(**sample_notaries[0])
    no.name = auth_file
    no.AUTH_PATH = "tests/data/notary/{}.yaml"
    with exception:
        assert no.auth == creds


@pytest.mark.parametrize(
    "index, out", [(1, "tests/data/notary/harbor.cert"), (0, None)]
)
def test_selfsigned_cert(mock_safe_path_func, sample_notaries, index, out):
    no = notary.Notary(**sample_notaries[index])
    no.SELFSIGNED_PATH = "tests/data/notary/{}.cert"
    assert no.selfsigned_cert == out


@pytest.mark.parametrize(
    "index, host, health",
    [
        (0, "healthy.url", True),
        (0, "unhealthy.url", False),
        (0, "exceptional.url", False),
        (1, "irrelevant.url", True),
    ],
)
def test_healthy(sample_notaries, m_request, index, host, health):
    no = notary.Notary(**sample_notaries[index])
    no.host = host
    assert no.healthy == health


@pytest.mark.parametrize(
    "index, image, role, output, exception",
    [
        (0, "alice-image", "root", fix.get_td("alice-image/root"), fix.no_exc()),
        (
            0,
            "alice-image",
            "targets/phbelitz",
            fix.get_td("alice-image/targets/phbelitz"),
            fix.no_exc(),
        ),
        (0, "bob-image", "root", fix.get_td("bob-image/root"), fix.no_exc()),
        (5, "irrelevant", "", {}, pytest.raises(exc.UnreachableError)),
        (
            0,
            "auth.io/alice-image",
            "root",
            fix.get_td("alice-image/root"),
            fix.no_exc(),
        ),
        (0, "empty.io/alice-image", "root", {}, pytest.raises(exc.NotFoundException)),
    ],
)
def test_get_trust_data(
    sample_notaries, m_request, m_trust_data, index, image, role, output, exception
):
    with exception:
        no = notary.Notary(**sample_notaries[index])
        td = no.get_trust_data(Image(image), role)
        assert td.signed == output["signed"]
        assert td.signatures == output["signatures"]


@pytest.mark.parametrize(
    "index, image, output, exception, log_lvl",
    [
        (0, "alice-image", True, fix.no_exc(), "INFO"),
        (0, "empty.io/alice-image", False, fix.no_exc(), "INFO"),
        (
            0,
            "empty.io/alice-image",
            False,
            pytest.raises(exc.NotFoundException),
            "DEBUG",
        ),
    ],
)
def test_get_delegation_trust_data(
    monkeypatch,
    sample_notaries,
    m_request,
    m_trust_data,
    index,
    image,
    output,
    exception,
    log_lvl,
):
    monkeypatch.setenv("LOG_LEVEL", log_lvl)
    with exception:
        no = notary.Notary(**sample_notaries[index])
        assert output is bool(
            no.get_delegation_trust_data(Image(image), "targets/phbelitz")
        )


@pytest.mark.parametrize(
    "headers, url, exception",
    [
        (
            (
                'Bearer realm="https://sample.notary.io/token",service="notary"'
                ',scope="repository:sample-image:pull"'
            ),
            (
                "https://sample.notary.io/token?service=notary"
                "&scope=repository:sample-image:pull"
            ),
            fix.no_exc(),
        ),
        (
            'Basic realm="https://sample.notary.io/token",service="notary",scope="pull"',
            "",
            pytest.raises(exc.UnknownTypeException),
        ),
        ("Bearer realm", "", pytest.raises(exc.NotFoundException)),
        (
            'Bearer realm="http://sample.notary.io/token"',
            "",
            pytest.raises(exc.InvalidFormatException),
        ),
        (
            'Bearer realm="https://sample.notary.io/token/..//passwd"',
            "",
            pytest.raises(exc.PathTraversalError),
        ),
    ],
)
def test_parse_auth(sample_notaries, headers, url, exception):
    with exception:
        no = notary.Notary(**sample_notaries[0])
        assert no._Notary__parse_auth(headers) == url


@pytest.mark.parametrize(
    "index, url, token, exception",
    [
        (
            0,
            "https://sample.notary.io/token?service=notary",
            "a.valid.token",
            fix.no_exc(),
        ),
        (1, "https://notary.acr.io/token?scope=token", "a.valid.token", fix.no_exc()),
        (
            0,
            "https://empty.io/token?scope=empty",
            "",
            pytest.raises(exc.NotFoundException, match=r".*get.*"),
        ),
        (
            0,
            "https://sample.notary.io/token?scope=wrong_token",
            "",
            pytest.raises(exc.NotFoundException, match=r".*retrieve.*"),
        ),
        (
            0,
            "https://sample.notary.io/token?scope=invalid_token",
            "",
            pytest.raises(exc.InvalidFormatException),
        ),
    ],
)
def test_get_auth_token(sample_notaries, m_request, index, url, token, exception):
    with exception:
        no = notary.Notary(**sample_notaries[index])
        assert no._Notary__get_auth_token(url) == token
