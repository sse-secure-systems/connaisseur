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
from connaisseur.config import Notary

sample_notary = {
    "name": "dockerhub",
    "host": "notary.docker.io",
    "pub_root_keys": [{"name": "sample", "key": "akey"}],
    "is_acr": False,
    "hasAuth": True,
    "auth": {"USER": "bert", "PASS": "bertig"},
    "isSelfsigned": False,
    "selfsigned_cert": None,
}


@pytest.fixture
def napi():
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

        if "crash" in kwargs["url"]:
            raise Exception

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
                if kwargs.get("verify"):
                    return MockResponse(
                        {"token": f"BA.self.{auth.username}.{auth.password}a"}
                    )
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


@pytest.fixture
def mock_notary(monkeypatch):
    def notary_init(self, name: str, host: str, pub_root_keys: list, **kwargs):
        self.name = name
        self.host = host
        self.pub_root_keys = pub_root_keys
        self.is_acr = kwargs.get("is_acr")
        self.authh = kwargs.get("auth")
        self.selfsigned_cert = kwargs.get("selfsigned_cert")

    def notary_get_key(self, key_name: str = None):
        if key_name:
            key = next(
                key_["key"] for key_ in self.pub_root_keys if key_["name"] == key_name
            )
        else:
            key = self.pub_root_keys[0]["key"]
        return key

    def auth(self):
        return self.authh["USER"], self.authh["PASS"]

    def selfsigned_cert(self):
        return self.selfsigned_cert

    monkeypatch.setattr(Notary, "__init__", notary_init)
    monkeypatch.setattr(Notary, "get_key", notary_get_key)
    monkeypatch.setattr(Notary, "auth", auth)
    monkeypatch.setattr(Notary, "selfsigned_cert", selfsigned_cert)


def trust_data(path: str):
    with open(path, "r") as file:
        return json.load(file)


@pytest.mark.parametrize(
    "host, out", [("host", True), ("unhealthy.registry", False), ("crash.org", False)]
)
def test_health_check(napi, mock_request, host: str, out: bool):
    notary = Notary(**sample_notary)
    notary.host = host
    assert napi.get_health(notary) == out


def test_health_check_acr(napi, mock_request):
    notary = Notary(**sample_notary)
    notary.is_acr = True
    assert napi.get_health(notary) is True


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
    napi, mock_request, mock_trust_data, mock_notary, image: str, role: str, out: dict
):
    notary = Notary(**sample_notary)
    trust_data_ = napi.get_trust_data(notary, Image(image), TUFRole(role))
    assert trust_data_.signed == out["signed"]
    assert trust_data_.signatures == out["signatures"]


def test_get_trust_data_error(napi, mock_request, mock_trust_data, mock_notary):
    notary = Notary(**sample_notary)
    with pytest.raises(BaseConnaisseurException) as err:
        napi.get_trust_data(notary, Image("empty.io/image:tag"), TUFRole("targets"))
    assert 'no trust data for image "empty.io/image:tag".' in str(err.value)


def test_get_trust_data_error2(napi, mock_request, mock_trust_data, mock_notary):
    notary = Notary(**sample_notary)
    notary.host = "crash.org"
    with pytest.raises(BaseConnaisseurException) as err:
        napi.get_trust_data(notary, Image("empty.io/image:tag"), TUFRole("targets"))
    assert "couldn't reach notary host crash.org." in str(err.value)


@pytest.mark.parametrize(
    "image, role, out",
    [
        ("alice-image:tag", "root", trust_data("tests/data/alice-image/root.json")),
        ("empty.io/image:tag", "targets", None),
    ],
)
def test_get_delegation_trust_data(
    napi, mock_request, mock_trust_data, mock_notary, image, role, out
):
    notary = Notary(**sample_notary)
    trust_data_ = napi.get_delegation_trust_data(notary, Image(image), TUFRole(role))
    if not trust_data_:
        assert trust_data_ == out
    else:
        assert trust_data_.signed == out["signed"]
        assert trust_data_.signatures == out["signatures"]


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
    "auth, selfsigned, is_acr, out",
    [
        ({"USER": None, "PASS": None}, False, False, "BA.None.Nonea"),
        (
            {"USER": None, "PASS": "password123"},
            False,
            False,
            "BA.None.password123a",
        ),
        (
            {"USER": "myname", "PASS": "password456"},
            False,
            False,
            "BA.myname.password456a",
        ),
        ({"USER": "myname", "PASS": None}, False, False, "BA.myname.Nonea"),
        (
            {"USER": "myname", "PASS": "password123"},
            True,
            False,
            "BA.self.myname.password123a",
        ),
        ({"USER": "myname", "PASS": None}, False, True, "d.e.f"),
    ],
)
def test_get_auth_token(napi, mock_request, mock_notary, auth, selfsigned, is_acr, out):
    notary = Notary(**sample_notary)
    notary.auth = (auth["USER"], auth["PASS"])
    if selfsigned:
        notary.selfsigned_cert = "2"
    notary.is_acr = is_acr
    url = (
        "https://auth.server.good/token/very/good"
        if not is_acr
        else "https://myregistry.azurecr.io/auth/oauth2?scope=someId"
    )
    assert napi.get_auth_token(notary, url) == out


@pytest.mark.parametrize(
    "url, is_acr, error",
    [
        (
            "https://auth.server.bad/token/very/bad/very",
            False,
            "authentication token has wrong format.",
        ),
        (
            "https://auth.server.bad/token/no/token",
            False,
            "no token in authentication server response.",
        ),
        (
            "https://auth.server.bad/token/it/aint/there/token",
            False,
            "unable to get auth token, likely because of missing trust data.",
        ),
        (
            "https://myregistry.azurecr.io/auth/oauth2?scope=someId",
            False,
            "no token in authentication server response.",
        ),
        (
            "https://auth.server.bad/token/very/bad/very",
            True,
            "no token in authentication server response.",
        ),
        (
            "https://auth.server.good/token/very/good",
            True,
            "no token in authentication server response.",
        ),
    ],
)
def test_get_auth_token_error(
    napi, mock_request, mock_notary, url: str, is_acr: bool, error: str
):
    notary = Notary(**sample_notary)
    notary.is_acr = is_acr
    with pytest.raises(BaseConnaisseurException) as err:
        napi.get_auth_token(notary, url)
    assert error in str(err.value)
