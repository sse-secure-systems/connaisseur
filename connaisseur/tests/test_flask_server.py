import json

import pytest
import requests
from requests.exceptions import HTTPError

import connaisseur.kube_api as api
import connaisseur.mutate as mutate
import connaisseur.policy as policy
from connaisseur.exceptions import AlertSendingError, ConfigurationError
from connaisseur.exceptions import NotFoundException
from connaisseur.image import Image
from connaisseur.config import Config, Notary

sample_config = [
    {
        "name": "dockerhub",
        "host": "notary.docker.io",
        "pub_root_keys": [
            {
                "name": "alice",
                "key": (
                    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu7WMF8tCjVgeORA"
                    "S2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA=="
                ),
            }
        ],
        "is_acr": False,
        "auth": {"USER": "bert", "PASS": "bertig"},
        "selfsigned_cert": None,
    }
]

with open("tests/data/alerting/alertconfig_schema.json", "r") as readfile:
    alertconfig_schema = json.load(readfile)


@pytest.fixture(autouse=True)
def mock_alertconfig_schema(mocker):
    mocker.patch(
        "connaisseur.alert.get_alert_config_validation_schema",
        return_value=alertconfig_schema,
    )


@pytest.fixture
def mock_kube_request(monkeypatch):
    def m_request(path: str):
        name = path.split("/")[-1]
        try:
            return get_file_json(f"tests/data/{name}.json")
        except FileNotFoundError:
            raise HTTPError

    monkeypatch.setattr(api, "request_kube_api", m_request)


@pytest.fixture
def mock_policy_no_verify(monkeypatch):
    def m__init__(self):
        self.policy = {"rules": [{"pattern": "*:*", "verify": False}]}

    monkeypatch.setattr(policy.ImagePolicy, "__init__", m__init__)


@pytest.fixture
def mock_policy_verify(monkeypatch):
    def m__init__(self):
        self.policy = {"rules": [{"pattern": "*:*", "verify": True}]}

    monkeypatch.setattr(policy.ImagePolicy, "__init__", m__init__)


@pytest.fixture(autouse=True)
def mock_safe_path_func_load_config(mocker):
    side_effect = lambda callback, base_dir, path, *args, **kwargs: callback(
        path, *args, **kwargs
    )
    mocker.patch("connaisseur.alert.safe_path_func", side_effect)


@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv(
        "HELM_HOOK_IMAGE", "securesystemsengineering/connaisseur:helm-hook"
    )
    monkeypatch.setenv("ALERT_CONFIG_DIR", "tests/data/alerting")


@pytest.fixture
def mock_notary_allow_leet(monkeypatch):
    def m_get_trusted_digest(host: str, image: Image, policy_rule: dict):
        if (
            image.digest
            == "1337133713371337133713371337133713371337133713371337133713371337"
        ):
            return "abcdefghijklmnopqrst"
        else:
            raise NotFoundException(
                'could not find signed digest for image "{}" in trust data.'.format(
                    str(image)
                )
            )

    monkeypatch.setattr(mutate, "get_trusted_digest", m_get_trusted_digest)


@pytest.fixture
def mock_mutate(monkeypatch):
    def m_get_parent_images(request: dict, index: int, namespace: str):
        return []

    monkeypatch.setattr(mutate, "get_parent_images", m_get_parent_images)


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


@pytest.fixture
def mock_config(mock_notary, monkeypatch):
    def config_init(self):
        self.notaries = [Notary(**notary) for notary in sample_config]

    monkeypatch.setattr(Config, "__init__", config_init)

    import connaisseur.flask_server as fs

    pytest.fs = fs


def get_file_json(path: str):
    with open(path, "r") as file:
        return json.load(file)


def test_healthz(mock_config):
    assert pytest.fs.healthz() == ("", 200)


@pytest.mark.parametrize(
    "sentinel_name, webhook, status",
    [
        ("sample_sentinel_run", "", 200),
        ("sample_sentinel_fin", "", 500),
        ("sample_sentinel_err", "", 500),
        ("", "", 500),
        ("sample_sentinel_fin", "sample_webhook", 200),
        ("sample_sentinel_fin", "", 500),
    ],
)
def test_readyz(
    mock_kube_request,
    mock_env_vars,
    mock_config,
    monkeypatch,
    sentinel_name,
    webhook,
    status,
):
    monkeypatch.setenv("CONNAISSEUR_NAMESPACE", "conny")
    monkeypatch.setenv("CONNAISSEUR_SENTINEL", sentinel_name)
    monkeypatch.setenv("CONNAISSEUR_WEBHOOK", webhook)

    assert pytest.fs.readyz() == ("", status)


@pytest.mark.parametrize(
    "ad_request_filename",
    [("ad_request_deployments"), ("ad_request_pods"), ("ad_request_replicasets")],
)
def test_mutate_no_verify(
    mocker,
    mock_config,
    mock_env_vars,
    mock_mutate,
    mock_policy_no_verify,
    ad_request_filename,
):

    client = pytest.fs.APP.test_client()
    mocker.patch("connaisseur.flask_server.call_alerting_on_request", return_value=True)
    mock_send_alerts = mocker.patch(
        "connaisseur.flask_server.send_alerts", return_value=None
    )
    mock_request_data = get_file_json(f"tests/data/{ad_request_filename}.json")
    response = client.post("/mutate", json=mock_request_data)
    assert response.status_code == 200
    assert response.is_json
    admission_response = response.get_json()["response"]
    assert admission_response["allowed"] == True
    assert admission_response["status"]["code"] == 202
    assert not "response" in admission_response["status"]
    mock_send_alerts.assert_has_calls([mocker.call(mock_request_data, admitted=True)])
    mocker.resetall()
    mocker.patch(
        "connaisseur.flask_server.call_alerting_on_request", return_value=False
    )
    mock_send_alerts = mocker.patch(
        "connaisseur.flask_server.send_alerts", return_value=None
    )
    assert mock_send_alerts.called is False


@pytest.mark.parametrize(
    "ad_request_filename, api_version, allowed, code, message",
    [
        ("ad_request_pods", "v2", False, 403, "API version v2 unknown."),
        (
            "sample_releases",
            "admission.k8s.io/v1beta1",
            False,
            403,
            "unknown request object kind None",
        ),
    ],
)
def test_mutate_invalid(
    monkeypatch,
    mock_env_vars,
    mock_config,
    mocker,
    ad_request_filename,
    api_version,
    allowed,
    code,
    message,
):
    monkeypatch.setenv("DETECTION_MODE", "0")
    mocker.patch("connaisseur.flask_server.call_alerting_on_request", return_value=True)
    mock_send_alerts = mocker.patch(
        "connaisseur.flask_server.send_alerts", return_value=None
    )
    client = pytest.fs.APP.test_client()

    mock_request_data = get_file_json(f"tests/data/{ad_request_filename}.json")
    mock_request_data["apiVersion"] = api_version
    response = client.post("/mutate", json=mock_request_data)
    assert response.status_code == 200
    assert response.is_json
    admission_response = response.get_json()["response"]
    assert admission_response["allowed"] == allowed
    assert admission_response["status"]["code"] == code
    assert admission_response["status"]["message"] == message
    mock_send_alerts.assert_has_calls(
        [mocker.call(mock_request_data, admitted=False, reason=message)]
    )


@pytest.mark.parametrize(
    "ad_request_filename, allowed, image, detection",
    [
        (
            "ad_request_pods",
            False,
            "someguy/charlie-image@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
            "0",
        ),
        (
            "ad_request_pods",
            False,
            "docker.io/someguy/charlie-image@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
            "0",
        ),
        (
            "ad_request_pods",
            False,
            "docker.io/alice/goes-to-town-image@sha256:deadbeafdeadbeafdeadbeafdeadbeafdeadbeafdeadbeafdeadbeafdeadbeaf",
            "1",
        ),
        (
            "ad_request_pods",
            True,
            "someguy/bob-image@sha256:1337133713371337133713371337133713371337133713371337133713371337",
            "0",
        ),
        (
            "ad_request_pods",
            True,
            "docker.io/theotherguy/benign@sha256:1337133713371337133713371337133713371337133713371337133713371337",
            "1",
        ),
    ],
)
def test_mutate_verify(
    mocker,
    mock_config,
    mock_mutate,
    mock_policy_verify,
    mock_notary_allow_leet,
    mock_env_vars,
    ad_request_filename,
    allowed,
    image,
    detection,
    monkeypatch,
):
    monkeypatch.setenv("DETECTION_MODE", detection)
    mocker.patch("connaisseur.flask_server.call_alerting_on_request", return_value=True)
    mock_send_alerts = mocker.patch(
        "connaisseur.flask_server.send_alerts", return_value=None
    )
    client = pytest.fs.APP.test_client()

    mock_request_data = get_file_json(f"tests/data/{ad_request_filename}.json")
    mock_request_data["request"]["object"]["spec"]["containers"][0]["image"] = image
    response = client.post("/mutate", json=mock_request_data)
    assert response.status_code == 200
    assert response.is_json

    admission_response = response.get_json()["response"]

    assert admission_response["allowed"] == allowed

    if allowed:
        assert admission_response["status"]["code"] == 202
        assert not "message" in admission_response["status"]
        mock_send_alerts.assert_has_calls(
            [mocker.call(mock_request_data, admitted=True)]
        )
    else:
        assert admission_response["status"]["code"] == 403
        image = (
            image
            if image.startswith("docker.io/")
            else "{}{}".format("docker.io/", image)
        )
        detection_mode_string = (
            " (not denied due to DETECTION_MODE)" if detection == "1" else ""
        )
        expected_message = (
            'could not find signed digest for image "{}" in trust data.{}'.format(
                image, detection_mode_string
            )
        )
        assert admission_response["status"]["message"] == expected_message
        mock_send_alerts.assert_has_calls(
            [mocker.call(mock_request_data, admitted=False, reason=expected_message)]
        )


@pytest.mark.parametrize("ad_request_filename", [("ad_request_deployments")])
def test_alert_sending_error_handler(
    mocker,
    requests_mock,
    mock_config,
    mock_mutate,
    mock_policy_verify,
    mock_env_vars,
    monkeypatch,
    ad_request_filename,
):
    monkeypatch.setenv("DETECTION_MODE", "0")

    requests_mock.post(
        "https://www.mocked_test_connaisseur_url.xyz",
        status_code=401,
    )
    try:
        mock_response = requests.post(
            "https://www.mocked_test_connaisseur_url.xyz", {}, {}
        )
        mock_response.raise_for_status()
    except HTTPError as err:
        http_error = err
    mocker.patch("connaisseur.flask_server.admit", return_value=True)
    mock_send_alerts = mocker.patch(
        "connaisseur.flask_server.send_alerts",
        side_effect=AlertSendingError(http_error),
    )
    client = pytest.fs.APP.test_client()
    mock_request_data = get_file_json(f"tests/data/{ad_request_filename}.json")
    response = client.post("/mutate", json=mock_request_data)
    mock_send_alerts.assert_has_calls([mocker.call(mock_request_data, admitted=True)])
    assert response.status_code == 500
    assert (
        response.get_data().decode()
        == "Alert could not be sent. Check the logs for more details!"
    )


@pytest.mark.parametrize("ad_request_filename", [("ad_request_deployments")])
def test_configuration_error_handler(
    mocker,
    mock_mutate,
    mock_policy_verify,
    mock_env_vars,
    mock_config,
    monkeypatch,
    ad_request_filename,
):
    monkeypatch.setenv("DETECTION_MODE", "0")
    mocker.patch(
        "connaisseur.flask_server.admit",
        return_value=True,
    )
    mock_call_alerting_on_request = mocker.patch(
        "connaisseur.flask_server.call_alerting_on_request",
        side_effect=ConfigurationError(Exception("This is misconfigured.")),
    )
    client = pytest.fs.APP.test_client()
    mock_request_data = get_file_json(f"tests/data/{ad_request_filename}.json")
    response = client.post("/mutate", json=mock_request_data)
    assert response.status_code == 500
    assert (
        response.get_data().decode()
        == "Alerting configuration is not valid. Check the logs for more details!"
    )
    mock_call_alerting_on_request.assert_has_calls(
        [mocker.call(mock_request_data, admitted=True)]
    )
