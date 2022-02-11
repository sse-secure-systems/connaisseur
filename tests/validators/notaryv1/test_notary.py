from requests.models import HTTPError
import yaml
import pytest
import re
from aioresponses import aioresponses
from aiohttp.client_exceptions import ClientResponseError
from ... import conftest as fix
import connaisseur.validators.notaryv1.notary as notary
import connaisseur.exceptions as exc
import connaisseur.util
from connaisseur.image import Image


@pytest.fixture
def sample_notaries():
    notary.Notary.CERT_PATH = "tests/data/notary/{}.cert"
    li = []
    for file_name in ("notary1", "notary2", "unhealthy_notary"):
        with open(f"tests/data/notary/{file_name}.yaml") as file:
            li.append(yaml.safe_load(file))
    return li


static_notaries = [
    {
        "name": "default",
        "host": "notary.docker.io",
        "trust_roots": [
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
        "trust_roots": [
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
    ],
)
def test_notary(sample_notaries, index, exception):
    with exception:
        no = notary.Notary(**sample_notaries[index])
        assert no.name == static_notaries[index]["name"]
        assert no.host == static_notaries[index]["host"]
        assert no.root_keys == static_notaries[index]["trust_roots"]
        assert no.is_acr == static_notaries[index].get("is_acr", False)


@pytest.mark.parametrize(
    "index, key_name, key, exception",
    [
        (0, "default", 0, fix.no_exc()),
        (0, "connytest", 1, fix.no_exc()),
        (0, None, 0, fix.no_exc()),
        (1, "library", 0, fix.no_exc()),
        (1, None, 0, pytest.raises(exc.NotFoundException)),
        (0, "sample_key", 0, pytest.raises(exc.NotFoundException)),
    ],
)
def test_get_key(sample_notaries, index, key_name, key, exception):
    no = notary.Notary(**sample_notaries[index])
    with exception:
        assert no.get_key(key_name) == static_notaries[index]["trust_roots"][key]["key"]


@pytest.mark.parametrize(
    "index, out", [(1, "107CB525ED666EBB7445A2C38C36A3B3"), (0, None)]
)
def test_get_context(sample_notaries, index, out):
    no = notary.Notary(**sample_notaries[index])
    assert (
        getattr(no.cert, "get_ca_certs", lambda x: [{}])(None)[0].get(
            "serialNumber", None
        )
        == out
    )


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


@pytest.mark.asyncio
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
async def test_get_trust_data(
    sample_notaries,
    m_request,
    m_trust_data,
    index,
    image,
    role,
    output,
    exception,
):
    with exception:
        with aioresponses() as aio:
            aio.get(re.compile(r".*"), callback=fix.async_callback, repeat=True)
            no = notary.Notary(**sample_notaries[index])
            td = await no.get_trust_data(Image(image), role)
            assert td.signed == output["signed"]
            assert td.signatures == output["signatures"]


@pytest.mark.asyncio
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
async def test_get_delegation_trust_data(
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
        with aioresponses() as aio:
            aio.get(re.compile(r".*"), callback=fix.async_callback)
            no = notary.Notary(**sample_notaries[index])
            td = await no.get_delegation_trust_data(Image(image), "targets/phbelitz")
            assert output is bool(td)


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


@pytest.mark.asyncio
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
        (
            0,
            "https://notary.hans.io/token?service=notary",
            "",
            pytest.raises(ClientResponseError),
        ),
        (
            1,
            "https://notary.hans.io/token?service=notary",
            "a.valid.token",
            fix.no_exc(),
        ),
    ],
)
async def test_get_auth_token(sample_notaries, m_request, index, url, token, exception):
    with exception:
        with aioresponses() as aio:
            aio.get(url, callback=fix.async_callback)
            no = notary.Notary(**sample_notaries[index])
            auth_token = await no._Notary__get_auth_token(url)
            assert auth_token == token
