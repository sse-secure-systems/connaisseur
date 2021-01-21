import os
import pytest
import pytest_subprocess
import re
import json
import requests
import connaisseur.trust_data
import connaisseur.validate as val
from connaisseur.image import Image
from connaisseur.key_store import KeyStore
from connaisseur.exceptions import BaseConnaisseurException
from connaisseur.config import Notary


policy_rule1 = {
    "pattern": "docker.io/securesystemsengineering/alice-image",
    "verify": True,
    "delegations": ["phbelitz", "chamsen"],
    "notary": "dockerhub",
    "key": "alice",
}
policy_rule2 = {
    "pattern": "docker.io/securesystemsengineering/*:*",
    "verify": True,
    "notary": "dockerhub",
    "key": "alice",
}
policy_rule3 = {
    "pattern": "docker.io/securesystemsengineering/*:*",
    "verify": True,
    "delegations": ["del1"],
    "key": "charlie",
}
policy_rule4 = {
    "pattern": "docker.io/securesystemsengineering/*:*",
    "verify": True,
    "key": "charlie",
    "delegations": ["del1", "del2"],
}

req_delegations1 = ["targets/phbelitz", "targets/chamsen"]
req_delegations2 = []
req_delegations3 = ["targets/someuserthatdidnotsign"]
req_delegations4 = ["targets/del1"]
req_delegations5 = ["targets/del2"]
req_delegations6 = ["targets/phbelitz", "targets/someuserthatdidnotsign"]

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

cosign_trust_data = '{"Critical":{"Identity":{"docker-reference":""},"Image":{"Docker-manifest-digest":"sha256:c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"},"Type":"cosign container signature"},"Optional":null}'


pub_root_keys = [
    {
        "name": "alice",
        "key": (
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu7WMF8tCjVgeORA"
            "S2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA=="
        ),
    },
    {
        "name": "charlie",
        "key": (
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtkQuBJ/wL1MEDy/6kgfSBls04MT1"
            "aUWM7eZ19L2WPJfjt105PPieCM1CZybSZ2h3O4+E4hPz1X5RfmojpXKePg=="
        ),
    },
    {"name": "cosign"},
]

sample_notary = {
    "name": "dockerhub",
    "host": "notary.docker.io",
    "pub_root_keys": pub_root_keys,
    "is_acr": False,
    "hasAuth": True,
    "auth": {"USER": "bert", "PASS": "bertig"},
    "isSelfsigned": False,
    "selfsigned_cert": None,
}


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


@pytest.fixture
def mock_notary(monkeypatch):
    def notary_init(self, name: str, host: str, pub_root_keys: list, **kwargs):
        self.name = name
        self.host = host
        self.pub_root_keys = pub_root_keys
        self.is_acr = kwargs.get("is_acr")
        self.auth = kwargs.get("auth")
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
        return self.auth

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
                    "securesystemsengineering/alice-image@sha256"
                    ":ac904c9b191d14faf54b7952f2650a4bb21"
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
    mock_request,
    mock_notary,
    image: str,
    policy_rule: dict,
    digest: str,
):
    notary = Notary(**sample_notary)
    assert val.get_trusted_digest(notary, Image(image), policy_rule) == digest


@pytest.mark.parametrize(
    "image, policy_rule, digest",
    [
        (
            "docker.io/securesystemsengineering/testimage:co-signed",
            policy_rule2,
            "c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7",
        ),
    ],
)
def test_get_trusted_digest_cosigned(
    fake_process, mock_notary, image: str, policy_rule: dict, digest: str
):
    notary = Notary(**sample_notary)
    notary.host = "host"
    notary.is_cosign = True
    fake_process.register_subprocess(
        ["/app/cosign/cosign", "verify", "-key", "/dev/stdin", image],
        stdout=bytes(cosign_trust_data, "utf-8"),
    )
    assert val.get_trusted_digest(notary, Image(image), policy_rule) == digest


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
    mock_notary,
    mock_request,
    image: str,
    policy: dict,
    error: str,
):
    notary = Notary(**sample_notary)
    with pytest.raises(BaseConnaisseurException) as err:
        val.get_trusted_digest(notary, Image(image), policy)
    assert error in str(err.value)


@pytest.mark.parametrize(
    "image, req_delegations, root_key, targets",
    [
        (
            "securesystemsengineering/alice-image",
            req_delegations1,
            pub_root_keys[0]["key"],
            targets1,
        ),
        (
            "securesystemsengineering/sample-image",
            req_delegations2,
            pub_root_keys[0]["key"],
            targets2,
        ),
        (
            "securesystemsengineering/bob-image",
            req_delegations2,
            pub_root_keys[1]["key"],
            targets3,
        ),
        (
            "securesystemsengineering/charlie-image",
            req_delegations2,
            pub_root_keys[1]["key"],
            targets4,
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations2,
            pub_root_keys[1]["key"],
            targets5,
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations4,
            pub_root_keys[1]["key"],
            targets5,
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations5,
            pub_root_keys[1]["key"],
            targets6,
        ),
    ],
)
def test_process_chain_of_trust(
    monkeypatch,
    mock_notary,
    mock_request,
    mock_trust_data,
    image: str,
    req_delegations: dict,
    root_key: str,
    targets: list,
):
    notary = Notary(**sample_notary)
    assert (
        val.process_chain_of_trust(notary, Image(image), req_delegations, root_key)
        == targets
    )


@pytest.mark.parametrize(
    "image, req_delegations, root_key, error",
    [
        (
            # no delegations
            "docker.io/securesystemsengineering/sample-image",
            req_delegations1,
            pub_root_keys[0]["key"],
            "could not find any delegations in trust data.",
        ),
        (
            # single invalid delegation
            "securesystemsengineering/alice-image",
            req_delegations3,
            pub_root_keys[0]["key"],
            (
                "could not find delegation roles "
                "['targets/someuserthatdidnotsign'] in trust data."
            ),
        ),
        (
            # invalid and valid delegations
            "securesystemsengineering/alice-image",
            req_delegations6,
            pub_root_keys[0]["key"],
            "could not find delegation roles ['targets/someuserthatdidnotsign'] in trust data.",
        ),
    ],
)
def test_process_chain_of_trust_error(
    mock_notary,
    mock_request,
    mock_trust_data,
    image: str,
    req_delegations: list,
    root_key: str,
    error: str,
):
    notary = Notary(**sample_notary)
    with pytest.raises(BaseConnaisseurException) as err:
        val.process_chain_of_trust(notary, Image(image), req_delegations, root_key)
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
