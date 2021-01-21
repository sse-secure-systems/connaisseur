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
    "rootKeys": [],
    "isAcr": False,
    "hasAuth": True,
    "auth": {"USER": "bert", "PASS": "bertig"},
    "isSelfsigned": False,
    "selfsignedCert": None,
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
    def _validate_expiry(self):
        pass

    def trust_init(self, data: dict, role: str):
        self.schema_path = "res/targets_schema.json"
        self.kind = role
        self._validate_schema(data)
        self.signed = data["signed"]
        self.signatures = data["signatures"]

    monkeypatch.setattr(
        connaisseur.trust_data.TrustData, "_validate_expiry", _validate_expiry
    )
    monkeypatch.setattr(connaisseur.trust_data.TargetsData, "__init__", trust_init)
    connaisseur.trust_data.TrustData.schema_path = "res/{}_schema.json"


@pytest.fixture
def mock_config(monkeypatch):
    def config_init(self, config: dict):
        self.name = config.get("name")
        self.host = config.get("host")
        self.root_keys = config.get("rootKeys")
        self.is_acr = config.get("isAcr")
        self.auth = config.get("auth")
        self.has_auth = config.get("hasAuth")
        self.is_selfsigned = config.get("isSelfsigned")
        self.selfsigned_cert = config.get("selfsignedCert")

    def config_get_key(self, key_name: str = None):
        if key_name:
            key = next(
                key.get("key") for key in self.root_keys if key.get("name") == key_name
            )
        else:
            key = self.root_keys[0].get("key")
        return key

    def config_get_auth(self):
        return self.auth

    def config_get_selfsigned_cert(self):
        return self.selfsigned_cert

    monkeypatch.setattr(connaisseur.config.Notary, "__init__", config_init)
    monkeypatch.setattr(connaisseur.config.Notary, "get_key", config_get_key)
    monkeypatch.setattr(connaisseur.config.Notary, "get_auth", config_get_auth)
    monkeypatch.setattr(
        connaisseur.config.Notary, "get_selfsigned_cert", config_get_selfsigned_cert
    )


def trust_data(path: str):
    with open(path, "r") as file:
        return json.load(file)


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
    napi, mock_request, mock_trust_data, mock_config, image: str, role: str, out: dict
):
    notary = Notary(sample_notary)
    trust_data_ = napi.get_trust_data(notary, Image(image), TUFRole(role))
    assert trust_data_.signed == out["signed"]
    assert trust_data_.signatures == out["signatures"]


def test_get_trust_data_error(napi, mock_request, mock_trust_data, mock_config):
    notary = Notary(sample_notary)
    with pytest.raises(BaseConnaisseurException) as err:
        napi.get_trust_data(notary, Image("empty.io/image:tag"), TUFRole("targets"))
    assert 'no trust data for image "empty.io/image:tag".' in str(err.value)


@pytest.mark.parametrize(
    "image, role, out",
    [
        ("alice-image:tag", "root", trust_data("tests/data/alice-image/root.json")),
        ("empty.io/image:tag", "targets", None),
    ],
)
def test_get_delegation_trust_data(
    napi, mock_request, mock_trust_data, mock_config, image, role, out
):
    notary = Notary(sample_notary)
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
    "has_auth, auth, selfsigned, is_acr, out",
    [
        (False, {"USER": None, "PASS": None}, False, False, "no.BA.no"),
        (True, {"USER": None, "PASS": None}, False, False, "BA.None.Nonea"),
        (
            True,
            {"USER": None, "PASS": "password123"},
            False,
            False,
            "BA.None.password123a",
        ),
        (
            True,
            {"USER": "myname", "PASS": "password456"},
            False,
            False,
            "BA.myname.password456a",
        ),
        (True, {"USER": "myname", "PASS": None}, False, False, "BA.myname.Nonea"),
        (
            True,
            {"USER": "myname", "PASS": "password123"},
            True,
            False,
            "BA.self.myname.password123a",
        ),
        (True, {"USER": "myname", "PASS": None}, False, True, "d.e.f"),
    ],
)
def test_get_auth_token(
    napi, mock_request, mock_config, has_auth, auth, selfsigned, is_acr, out
):
    notary = Notary(sample_notary)
    notary.auth["USER"] = auth["USER"]
    notary.auth["PASS"] = auth["PASS"]
    notary.has_auth = has_auth
    notary.is_selfsigned = selfsigned
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
    napi, mock_request, mock_config, url: str, is_acr: bool, error: str
):
    notary = Notary(sample_notary)
    notary.is_acr = is_acr
    with pytest.raises(BaseConnaisseurException) as err:
        napi.get_auth_token(notary, url)
    assert error in str(err.value)
