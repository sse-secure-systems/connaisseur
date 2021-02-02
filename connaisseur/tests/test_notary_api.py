import json
import re
import os
import pytest
import requests
import pytz
import datetime as dt
import connaisseur.trust_data
import connaisseur.notary_api as notary_api
from connaisseur.image import Image
from connaisseur.tuf_role import TUFRole
from connaisseur.exceptions import BaseConnaisseurException


@pytest.fixture
def napi(monkeypatch):
    monkeypatch.setenv("IS_ACR", "0")
    monkeypatch.setenv("SELFSIGNED_NOTARY", "1")
    return notary_api


@pytest.fixture
def acrapi(monkeypatch):
    monkeypatch.setenv("IS_ACR", "1")
    monkeypatch.setenv("SELFSIGNED_NOTARY", "1")
    return notary_api


@pytest.fixture
def mock_request(monkeypatch):
    class MockResponse:
        content: dict
        headers: dict
        status_code: int = 200

        def __init__(self, content: dict, headers: dict = None, status_code: int = 200):
            self.content = content
            self.headers = headers
            self.status_code = status_code

        def raise_for_status(self):
            pass

        def json(self):
            return self.content

    def mock_get_request(**kwargs):
        regex = (
            r"https:\/\/([^\/]+)\/v2\/([^\/]+)\/([^\/]+\/)?"
            r"([^\/]+)\/_trust\/tuf\/(.+)\.json"
        )
        m = re.search(regex, kwargs["url"])

        if m:
            host, registry, repo, image, role = (
                m.group(1),
                m.group(2),
                m.group(3),
                m.group(4),
                m.group(5),
            )

        if "unhealthy" in kwargs["url"]:
            return MockResponse({}, status_code=500)

        if "health" in kwargs["url"]:
            return MockResponse(None)

        if "azurecr.io" in kwargs["url"]:
            return MockResponse({"access_token": "d.e.f"})

        if "token" in kwargs["url"]:
            auth = kwargs.get("auth")
            if "bad" in kwargs["url"]:
                if "no" in kwargs["url"]:
                    return MockResponse({"nay": "butwhy"})
                if "aint" in kwargs["url"]:
                    return MockResponse({}, status_code=500)
                return MockResponse({"token": "token"})
            elif auth:
                return MockResponse({"token": f"BA.{auth.username}.{auth.password}a"})
            return MockResponse({"token": "no.BA.no"})
        elif registry == "auth.io" and not kwargs.get("headers"):
            return MockResponse(
                {},
                {
                    "Www-Authenticate": (
                        'Bearer realm="https://core.harbor.domain/service/'
                        'token",service="harbor-notary",scope="repository:'
                        'core.harbor.domain/connaisseur/sample-image:pull"'
                    )
                },
                401,
            )
        elif registry == "empty.io":
            return MockResponse({}, status_code=404)
        else:
            with open(f"tests/data/{image}/{role}.json", "r") as file:
                file_content = json.load(file)

        return MockResponse(file_content)

    monkeypatch.setattr(requests, "get", mock_get_request)


@pytest.fixture
def mock_trust_data(monkeypatch):
    def validate_expiry(self):
        pass

    def trust_init(self, data: dict, role: str):
        self.schema_path = "res/targets_schema.json"
        self.kind = role
        self._validate_schema(data)
        self.signed = data["signed"]
        self.signatures = data["signatures"]

    monkeypatch.setattr(
        connaisseur.trust_data.TrustData, "validate_expiry", validate_expiry
    )
    monkeypatch.setattr(connaisseur.trust_data.TargetsData, "__init__", trust_init)
    connaisseur.trust_data.TrustData.schema_path = "res/{}_schema.json"


def trust_data(path: str):
    with open(path, "r") as file:
        return json.load(file)


@pytest.mark.parametrize(
    "host, out", [("host", True), ("", False), ("https://unhealthy.registry", False)]
)
def test_health_check(napi, mock_request, host: str, out: bool):
    assert napi.health_check(host) == out


@pytest.mark.parametrize(
    "host, out", [("host", True), ("", False), ("https://unhealthy.registry", True)]
)
def test_health_check_acr(acrapi, mock_request, host: str, out: bool):
    assert acrapi.health_check(host) == out


@pytest.mark.parametrize("slfsig, out", [("1", True), ("0", False), ("", False)])
def test_is_notary_selfsigned(napi, slfsig: str, out: bool, monkeypatch):
    monkeypatch.setenv("SELFSIGNED_NOTARY", slfsig)
    assert napi.is_notary_selfsigned() == out


@pytest.mark.parametrize(
    "image, role, out",
    [
        ("alice-image:tag", "root", trust_data("tests/data/alice-image/root.json")),
        (
            "alice-image:tag",
            "targets",
            trust_data("tests/data/alice-image/targets.json"),
        ),
        (
            "alice-image:tag",
            "targets/phbelitz",
            trust_data("tests/data/alice-image/targets/phbelitz.json"),
        ),
        (
            "auth.io/sample-image:tag",
            "targets",
            trust_data("tests/data/sample-image/targets.json"),
        ),
    ],
)
def test_get_trust_data(
    napi, mock_request, mock_trust_data, image: str, role: str, out: dict
):
    trust_data_ = napi.get_trust_data("host", Image(image), TUFRole(role))
    assert trust_data_.signed == out["signed"]
    assert trust_data_.signatures == out["signatures"]


def test_get_trust_data_error(napi, mock_request, mock_trust_data):
    with pytest.raises(BaseConnaisseurException) as err:
        napi.get_trust_data("host", Image("empty.io/image:tag"), TUFRole("targets"))
    assert 'no trust data for image "empty.io/image:tag".' in str(err.value)


def test_parse_auth(napi):
    header = (
        'Bearer realm="https://core.harbor.domain/service/token",'
        'service="harbor-notary",scope="repository:core.harbor.domain/'
        'connaisseur/sample-image:pull"'
    )
    url = (
        "https://core.harbor.domain/service/token?service=harbor-notary"
        "&scope=repository:core.harbor.domain/connaisseur/sample-image:pull"
    )
    assert napi.parse_auth(header) == url


@pytest.mark.parametrize(
    "header, error",
    [
        (
            'Basic realm="https://mordor.de",scope="conquer"',
            "unsupported authentication type for getting trust data.",
        ),
        (
            'Super realm="https://super.de",service="toll"',
            "unsupported authentication type for getting trust data.",
        ),
        (
            'Bearer realmm="https://auth.server.com",service="auth"',
            "could not find any realm in authentication header.",
        ),
        (
            'Bearer realm="http://auth.server.com",service="auth"',
            "authentication through insecure channel.",
        ),
        (
            'Bearer realm="https://exam.pl/path/../traversal.key",service="no"',
            "potential path traversal.",
        ),
    ],
)
def test_parse_auth_error(napi, header: str, error: str):
    with pytest.raises(BaseConnaisseurException) as err:
        napi.parse_auth(header)
    assert error in str(err.value)


@pytest.mark.parametrize(
    "user, password, out",
    [
        (None, None, "no.BA.no"),
        (None, "password123", "no.BA.no"),
        ("myname", "password456", "BA.myname.password456a"),
        ("myname", None, "BA.myname.a"),
    ],
)
def test_get_auth_token(napi, mock_request, monkeypatch, user, password, out):
    if user:
        monkeypatch.setenv("NOTARY_USER", user)
    if password is not None:
        monkeypatch.setenv("NOTARY_PASS", password)
    url = "https://auth.server.good/token/very/good"
    assert napi.get_auth_token(url) == out


def test_get_auth_token_acr(acrapi, mock_request):
    url = "https://myregistry.azurecr.io/auth/oauth2?scope=someId"
    assert acrapi.get_auth_token(url) == "d.e.f"


@pytest.mark.parametrize(
    "url, error",
    [
        (
            "https://auth.server.bad/token/very/bad/very",
            "authentication token has wrong format.",
        ),
        (
            "https://auth.server.bad/token/no/token",
            "no token in authentication server response.",
        ),
        (
            "https://auth.server.bad/token/it/aint/there/token",
            "unable to get auth token, likely because of missing trust data.",
        ),
        (
            "https://myregistry.azurecr.io/auth/oauth2?scope=someId",
            "no token in authentication server response.",
        ),
    ],
)
def test_get_auth_token_error(napi, mock_request, url: str, error: str):
    with pytest.raises(BaseConnaisseurException) as err:
        napi.get_auth_token(url)
    assert error in str(err.value)


@pytest.mark.parametrize(
    "url, error",
    [
        (
            "https://auth.server.bad/token/very/bad/very",
            "no token in authentication server response.",
        ),
        (
            "https://auth.server.good/token/very/good",
            "no token in authentication server response.",
        ),
    ],
)
def test_get_auth_token_error_acr(acrapi, mock_request, url: str, error: str):
    with pytest.raises(BaseConnaisseurException) as err:
        acrapi.get_auth_token(url)
    assert error in str(err.value)
