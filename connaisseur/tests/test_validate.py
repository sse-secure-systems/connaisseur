import os
import pytest
import re
import json
import requests
import connaisseur.trust_data
import connaisseur.validate as val
from connaisseur.image import Image
from connaisseur.key_store import KeyStore
from connaisseur.exceptions import BaseConnaisseurException

policy_rule1 = {
    "pattern": "docker.io/securesystemsengineering/alice-image",
    "verify": True,
    "delegations": ["phbelitz", "chamsen"],
}
policy_rule2 = {"pattern": "docker.io/securesystemsengineering/*:*", "verify": True}
policy_rule3 = {
    "pattern": "docker.io/securesystemsengineering/*:*",
    "verify": True,
    "delegations": ["del1"],
}
policy_rule4 = {
    "pattern": "docker.io/securesystemsengineering/*:*",
    "verify": True,
    "delegations": ["del1", "del2"],
}

req_delegations1 = ["targets/phbelitz", "targets/chamsen"]
req_delegations2 = []
req_delegations3 = ["targets/someuserthatdidnotsign"]
req_delegations4 = ["targets/del1"]
req_delegations5 = ["targets/del2"]

targets1 = [
    {
        "test": {
            "hashes": {"sha256": "rJBMmxkdFPr1S3lS8mUKS7IcIBvzQTE4i4UejOmSplI="},
            "length": 1993,
        }
    },
    {
        "test": {
            "hashes": {"sha256": "rJBMmxkdFPr1S3lS8mUKS7IcIBvzQTE4i4UejOmSplI="},
            "length": 1993,
        }
    },
]
targets2 = [
    {
        "sign": {
            "hashes": {"sha256": "oVR5e4MAFllW7h8W2Y86FCYwHBFo8EYsc86bwDNhyr8="},
            "length": 1994,
        },
        "v1": {
            "hashes": {"sha256": "eZwPqKpMn7/1qZrvG0tcOrucLzQTQ0UAWYL600iYk8c="},
            "length": 1994,
        },
    }
]
targets3 = [
    {
        "test": {
            "hashes": {"sha256": "TgYbzUu1pMskoZbfWdcj2RF0HVUg+J4034p5LVa97j4="},
            "length": 528,
        }
    }
]
targets4 = [
    {
        "test": {
            "hashes": {"sha256": "pkeg+cgtxfPnxL1kg7SWpJ1XC0/bH+rL/VfpZdKh1mI="},
            "length": 528,
        }
    }
]
targets5 = [
    {
        "test": {
            "hashes": {"sha256": "K3tQZXLk87nedST/hCh9uI7SSwz5RIp7BK0GZOze9xs="},
            "length": 528,
        }
    }
]
targets6 = [
    {
        "test": {
            "hashes": {"sha256": "qCXo6VDc64HH2G9tNOTkcwfpjzVQXRgNQE4ZR0KigHk="},
            "length": 528,
        }
    }
]


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
def mock_keystore(monkeypatch, root_pub: str = None):
    def init(self):
        self.keys = {
            "2cd463575a31cb3184320e889e82fb1f9e3bbebee2ae42b2f825b0c8a734e798": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu7WMF8tCjVgeORA"
                "S2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA=="
            ),
            "a873ab3f157cfd51c9ccdc445caac92e8aef9f57881169d3bc3cc4868a20add2": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu7WMF8tCjVgeORA"
                "S2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA=="
            ),
            "950430dd6ff06b4a3b4e6f29f7fc7e07f1386718fc936795b0ca27d85645cace": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu7WMF8tCjVgeORA"
                "S2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA=="
            ),
            "2b53d5708f0defb3e7023b59a32d85938139ee613b85f1aa862cd484f53edc2e": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtkQuBJ/wL1MEDy/6kgfSBls04MT1"
                "aUWM7eZ19L2WPJfjt105PPieCM1CZybSZ2h3O4+E4hPz1X5RfmojpXKePg=="
            ),
        }
        self.hashes = {}

    monkeypatch.setattr(KeyStore, "__init__", init)


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


def trust_data(path: str):
    with open(path, "r") as file:
        return json.load(file)


@pytest.mark.parametrize(
    "image, policy_rule, digest",
    [
        (
            "securesystemsengineering/alice-image:test",
            policy_rule1,
            "ac904c9b191d14faf54b7952f2650a4bb21c201bf34131388b851e8ce992a652",
        ),
        (
            (
                (
                    "securesystemsengineering/alice-image@sha256:ac904c9b191d14faf54b7952f2650a4bb21"
                    "c201bf34131388b851e8ce992a652"
                )
            ),
            policy_rule1,
            "ac904c9b191d14faf54b7952f2650a4bb21c201bf34131388b851e8ce992a652",
        ),
        (
            "securesystemsengineering/sample-image:sign",
            policy_rule2,
            "a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
        ),
        (
            "securesystemsengineering/sample-image:v1",
            policy_rule2,
            "799c0fa8aa4c9fbff5a99aef1b4b5c3abb9c2f34134345005982fad3489893c7",
        ),
    ],
)
def test_get_trusted_digest(
    mock_trust_data,
    mock_keystore,
    mock_request,
    image: str,
    policy_rule: dict,
    digest: str,
):
    assert val.get_trusted_digest("host", Image(image), policy_rule) == digest


@pytest.mark.parametrize(
    "image, policy, error",
    [
        (
            "securesystemsengineering/charlie-image:test2",
            policy_rule3,
            (
                "not all required delegations have trust data for image "
                '"docker.io/securesystemsengineering/charlie-image:test2".'
            ),
        ),
        (
            "securesystmesengineering/dave-image:test",
            policy_rule4,
            "found multiple signed digests for the same image.",
        ),
    ],
)
def test_get_trusted_digest_error(
    monkeypatch,
    mock_trust_data,
    mock_keystore,
    mock_request,
    image: str,
    policy: dict,
    error: str,
):
    with pytest.raises(BaseConnaisseurException) as err:
        val.get_trusted_digest("host", Image(image), policy)
    assert error in str(err.value)


@pytest.mark.parametrize(
    "image, req_delegations, targets",
    [
        ("securesystemsengineering/alice-image", req_delegations1, targets1),
        ("securesystemsengineering/sample-image", req_delegations2, targets2),
        (
            "securesystemsengineering/bob-image",
            req_delegations2,
            targets3,
        ),
        (
            "securesystemsengineering/charlie-image",
            req_delegations2,
            targets4,
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations2,
            targets5,
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations4,
            targets5,
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations5,
            targets6,
        ),
    ],
)
def test_process_chain_of_trust(
    monkeypatch,
    mock_keystore,
    mock_request,
    mock_trust_data,
    image: str,
    req_delegations: dict,
    targets: list,
):
    assert val.process_chain_of_trust("host", Image(image), req_delegations) == targets


@pytest.mark.parametrize(
    "image, req_delegations, error",
    [
        (
            "docker.io/securesystemsengineering/sample-image",
            req_delegations1,
            "could not find any delegations in trust data.",
        ),
        (
            "securesystemsengineering/alice-image",
            req_delegations3,
            "could not find delegation roles ['targets/someuserthatdidnotsign'] in trust data.",
        ),
    ],
)
def test_process_chain_of_trust_error(
    mock_keystore,
    mock_request,
    mock_trust_data,
    image: str,
    req_delegations: list,
    error: str,
):
    with pytest.raises(BaseConnaisseurException) as err:
        val.process_chain_of_trust("host", Image(image), req_delegations)
    assert error in str(err.value)


@pytest.mark.parametrize(
    "image, digest",
    [
        (
            (
                "image@sha256:1388abc7a12532836c3a81"
                "bdb0087409b15208f5aeba7a87aedcfd56d637c145"
            ),
            "1388abc7a12532836c3a81bdb0087409b15208f5aeba7a87aedcfd56d637c145",
        ),
        (
            (
                "image@sha256:b8a38522876a9e2550d582"
                "ce51a1d87ebdc6c570e5e585d08560bfd646f7f804"
            ),
            "b8a38522876a9e2550d582ce51a1d87ebdc6c570e5e585d08560bfd646f7f804",
        ),
        (
            (
                "image@sha256:b8a38522876a9e2550d582"
                "ce51a1d87ebdc6c570e5e585d08560bfd646f7f805"
            ),
            None,
        ),
    ],
)
def test_search_image_targets_for_digest(image: str, digest: str):
    data = trust_data("tests/data/sample_releases.json")["signed"]["targets"]
    assert val.search_image_targets_for_digest(data, Image(image)) == digest


@pytest.mark.parametrize(
    "image, digest",
    [
        (
            "image:v1",
            "1388abc7a12532836c3a81bdb0087409b15208f5aeba7a87aedcfd56d637c145",
        ),
        (
            "image:v2",
            "b8a38522876a9e2550d582ce51a1d87ebdc6c570e5e585d08560bfd646f7f804",
        ),
        ("image:v3", None),
    ],
)
def test_search_image_targets_for_tag(image: str, digest: str):
    data = trust_data("tests/data/sample_releases.json")["signed"]["targets"]
    assert val.search_image_targets_for_tag(data, Image(image)) == digest
