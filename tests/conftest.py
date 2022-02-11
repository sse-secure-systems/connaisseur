import os
import re
import json
import pytest
import requests
from aioresponses import CallbackResult
import connaisseur.kube_api
import connaisseur.config as co
import connaisseur.admission_request as admreq
import connaisseur.alert as alert
from connaisseur.trust_root import TrustRoot
import connaisseur.validators.notaryv1.trust_data as td
import connaisseur.validators.notaryv1.key_store as ks
import connaisseur.validators.notaryv1.notary as no
import connaisseur.validators.notaryv1.notaryv1_validator as nv1
import connaisseur.util as util
from contextlib import contextmanager


"""
This file is used for sharing fixtures across all other test files.
https://docs.pytest.org/en/stable/fixture.html#scope-sharing-fixtures-across-classes-modules-packages-or-session
"""


@contextmanager
def no_exc():
    yield


def get_json(path):
    with open(path, "r") as file:
        return json.load(file)


def get_admreq(adm_type):
    try:
        return get_json(
            f"tests/data/sample_admission_requests/ad_request_{adm_type}.json"
        )
    except FileNotFoundError:
        return None


def get_td(path):
    return get_json(f"tests/data/trust_data/{path}.json")


def get_k8s_res(path):
    return get_json(f"tests/data/sample_kube_resources/{path}.json")


def get_cosign_err_msg(path):
    with open(f"tests/data/cosign/{path}.txt") as file:
        return file.read()


@pytest.fixture
def m_request(monkeypatch):

    monkeypatch.setattr(requests, "get", mock_get_request)
    monkeypatch.setattr(requests, "post", mock_post_request)
    monkeypatch.setattr(connaisseur.kube_api, "__get_token", kube_token)


class MockResponse:
    content: dict
    headers: dict
    status_code: int = 200

    def __init__(self, content: dict, headers: dict = None, status_code: int = 200):
        self.content = content
        self.headers = headers
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.exceptions.HTTPError

    def json(self):
        return self.content


def async_callback(url, **kwargs):
    mock_rsp = mock_get_request(str(url), **kwargs)
    return CallbackResult(
        status=mock_rsp.status_code,
        payload=mock_rsp.content,
        headers=mock_rsp.headers,
        reason="irrelevant",
    )


def mock_get_request(url, **kwargs):
    notary_regex = [
        (
            r"https:\/\/([^\/]+)\/v2\/([^\/]+)\/([^\/]+\/)?"
            r"([^\/]+)\/_trust\/tuf\/(.+)\.json"
        ),
        mock_request_notary,
    ]
    kube_regex = [
        (
            r"https:\/\/[^\/]+\/apis?\/(apps\/v1|v1|batch\/v1beta1)"
            r"\/namespaces\/([^\/]+)\/([^\/]+)\/([^\/]+)"
        ),
        mock_request_kube,
    ]
    notary_health_regex = [
        (r"https:\/\/([^\/]+)\/_notary_server\/health"),
        mock_request_notary_health,
    ]
    notary_token_regex = [
        (r"https:\/\/([^\/]+)\/token\?((service=[^&]+)|(scope=[^&]+)|&)*"),
        mock_request_notary_token,
    ]
    kube_namespace_less_regex = [
        (
            r"https:\/\/[^\/]+\/apis?\/(admissionregistration"
            r"\.k8s\.io\/v1beta1)\/[^\/]+\/([^\/]+)"
        ),
        mock_request_kube_namespace_less,
    ]

    for reg in (
        notary_regex,
        kube_regex,
        notary_health_regex,
        notary_token_regex,
        kube_namespace_less_regex,
    ):
        match = re.search(reg[0], url)

        if match:
            return reg[1](match, **kwargs)
    return MockResponse({}, status_code=500)


def mock_request_notary(match: re.Match, **kwargs):
    host, registry, repo, image, role = (
        match.group(1),
        match.group(2),
        match.group(3),
        match.group(4),
        match.group(5),
    )

    if registry == "auth.io" and not kwargs.get("headers"):
        return MockResponse(
            {},
            headers={
                "Www-authenticate": (
                    'Bearer realm="https://sample.notary.io/token,"'
                    'service="notary",scope="repository:sample-image:pull"'
                )
            },
            status_code=401,
        )
    if registry == "empty.io":
        return MockResponse({}, status_code=404)

    return MockResponse(get_td(f"{image}/{role}"))


def mock_request_kube(match: re.Match, **kwargs):
    version, namespace, kind, name = (
        match.group(1),
        match.group(2),
        match.group(3),
        match.group(4),
    )

    try:
        return MockResponse(get_k8s_res(kind))
    except FileNotFoundError as err:
        return MockResponse({}, status_code=500)


def mock_request_notary_health(match: re.Match, **kwargs):
    host = match.group(1)

    if "unhealthy" in host:
        return MockResponse({}, status_code=500)
    elif "exceptional" in host:
        raise Exception
    else:
        return MockResponse({})


def kube_token(path: str):
    return ""


def mock_request_notary_token(match: re.Match, **kwargs):
    host, scope, service = match.group(1), match.group(2), match.group(3)
    auth = kwargs.get("auth")

    if host == "notary.acr.io":
        return MockResponse({"access_token": "a.valid.token"})
    if host == "empty.io":
        return MockResponse({}, status_code=500)
    if host == "notary.hans.io":
        if (
            getattr(auth, "login", None) == "hans"
            and getattr(auth, "password", None) == "wurst"
        ):
            return MockResponse({"access_token": "a.valid.token"})
        return MockResponse({}, status_code=401)
    if "wrong_token" in scope:
        return MockResponse({"tocken": "a.valid.token"})
    if "invalid_token" in scope:
        return MockResponse({"token": "invalidtoken"})
    return MockResponse({"token": "a.valid.token"})


def mock_request_kube_namespace_less(match: re.Match, **kwargs):
    name = match.group(2)
    return MockResponse(get_k8s_res(name))


def mock_post_request(url, **kwargs):
    opsgenie_regex = [
        (r"https:\/\/api\.eu\.opsgenie\.com\/v2\/alerts"),
        mock_opsgenie_request,
    ]

    for reg in [opsgenie_regex]:
        match = re.search(reg[0], url)

        if match:
            return reg[1](match, **kwargs)
    return MockResponse({}, status_code=500)


def mock_opsgenie_request(match: re.Match, **kwargs):
    if kwargs.get("headers", {}).get("Authorization"):
        return MockResponse(
            {
                "result": "Request will be processed",
                "took": 0.302,
                "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120",
            }
        )
    return MockResponse({}, status_code=401)


@pytest.fixture
def m_trust_data():
    connaisseur.validators.notaryv1.trust_data.RootData._TrustData__SCHEMA_PATH = (
        "connaisseur/res/root_schema.json"
    )
    connaisseur.validators.notaryv1.trust_data.TargetsData._TrustData__SCHEMA_PATH = (
        "connaisseur/res/targets_schema.json"
    )
    connaisseur.validators.notaryv1.trust_data.SnapshotData._TrustData__SCHEMA_PATH = (
        "connaisseur/res/snapshot_schema.json"
    )
    connaisseur.validators.notaryv1.trust_data.TimestampData._TrustData__SCHEMA_PATH = (
        "connaisseur/res/timestamp_schema.json"
    )


@pytest.fixture
def m_expiry(monkeypatch):
    def mock_expiry(self):
        pass

    monkeypatch.setattr(td.TrustData, "validate_expiry", mock_expiry)


@pytest.fixture
def sample_key_store(m_trust_data):
    sample_key = TrustRoot(
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu"
        "7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDG"
        "l+W2k3elHkPbR+gNkK2PCA=="
    )
    k = ks.KeyStore(sample_key)
    for role in ("root", "targets", "snapshot", "timestamp"):
        k.update(td.TrustData(get_td(f"sample_{role}"), role))
    return k


@pytest.fixture
def alice_key_store(m_trust_data):
    sample_key = TrustRoot(
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrD"
        "K22SyCu7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1"
        "w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA=="
    )
    k = ks.KeyStore(sample_key)
    for role in ("root", "targets", "snapshot", "timestamp"):
        k.update(td.TrustData(get_td(f"alice-image/{role}"), role))
    return k


@pytest.fixture
def m_notary(monkeypatch):
    def mock_healthy(self):
        return True

    monkeypatch.setattr(no.Notary, "healthy", mock_healthy)


@pytest.fixture
def sample_nv1(m_notary):
    sample_notary = {
        "name": "dockerhub",
        "host": "notary.docker.io",
        "trust_roots": [
            {
                "name": "default",
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
            {"name": "missingkey", "key": ""},
        ],
        "is_acr": False,
        "auth": {"username": "bert", "password": "bertig"},
        "cert": None,
    }
    return nv1.NotaryV1Validator(**sample_notary)


@pytest.fixture()
def m_ad_schema_path():
    admreq.AdmissionRequest._AdmissionRequest__SCHEMA_PATH = (
        "connaisseur/res/ad_request_schema.json"
    )


@pytest.fixture
def adm_req_samples(m_ad_schema_path):
    return [
        get_admreq(t)
        for t in (
            "deployments",
            "pods",
            "replicasets",
            "cronjob",
            "err",
            "invalid_image",
            "auto_approval",
            "invalid",
        )
    ]


@pytest.fixture()
def m_safe_path_func(monkeypatch):
    side_effect = lambda callback, base_dir, path, *args, **kwargs: callback(
        path, *args, **kwargs
    )
    monkeypatch.setattr(connaisseur.util, "safe_path_func", side_effect)


@pytest.fixture
def m_alerting(monkeypatch, m_safe_path_func):
    monkeypatch.setenv("DETECTION_MODE", "0")
    monkeypatch.setenv("POD_NAME", "connaisseur-pod-123")
    monkeypatch.setenv("CLUSTER_NAME", "minikube")
    connaisseur.alert.AlertingConfiguration._AlertingConfiguration__PATH = (
        "tests/data/alerting/alertconfig.json"
    )
    connaisseur.alert.AlertingConfiguration._AlertingConfiguration__SCHEMA_PATH = (
        "connaisseur/res/alertconfig_schema.json"
    )
    connaisseur.alert.Alert._Alert__TEMPLATE_PATH = "tests/data/alerting/templates"


@pytest.fixture
def m_alerting_without_send(monkeypatch, m_safe_path_func, mocker):
    monkeypatch.setenv("DETECTION_MODE", "0")
    monkeypatch.setenv("POD_NAME", "connaisseur-pod-123")
    monkeypatch.setenv("CLUSTER_NAME", "minikube")
    monkeypatch.setattr(
        connaisseur.alert.Alert, "send_alert", mocker.stub("alert.Alert.send_alert")
    )
    connaisseur.alert.AlertingConfiguration._AlertingConfiguration__PATH = (
        "tests/data/alerting/alertconfig.json"
    )
    connaisseur.alert.AlertingConfiguration._AlertingConfiguration__SCHEMA_PATH = (
        "connaisseur/res/alertconfig_schema.json"
    )
    connaisseur.alert.Alert._Alert__TEMPLATE_PATH = "tests/data/alerting/templates"


@pytest.fixture
def count_loaded_delegations(monkeypatch):
    async def get_delegation_trust_data_counted(self, image, role, token=None):
        monkeypatch.setenv(
            "DELEGATION_COUNT", str(int(os.getenv("DELEGATION_COUNT")) + 1)
        )
        try:
            return await no.Notary.get_trust_data(self, image, role, token)
        except Exception as ex:
            if os.environ.get("LOG_LEVEL", "INFO") == "DEBUG":
                raise ex
            return None

    monkeypatch.setattr(
        no.Notary, "get_delegation_trust_data", get_delegation_trust_data_counted
    )
