import asyncio
import re

import aiohttp
import pytest
from aioresponses import aioresponses

import connaisseur.alert as alert
import connaisseur.config as co
import connaisseur.exceptions as exc
from connaisseur.admission_request import AdmissionRequest
from connaisseur.validators.static.static_validator import StaticValidator

from . import conftest as fix


@pytest.fixture(autouse=True)
def m_config(monkeypatch, sample_nv1):
    def mock_init(self):
        self.validators = [sample_nv1, StaticValidator("allow", True)]
        self.policy = [
            {
                "pattern": "*:*",
                "validator": "",
                "with": {"delegations": ["phbelitz", "chamsen"]},
            },
            {
                "pattern": "docker.io/*:*",
                "validator": "dockerhub",
                "with": {"delegations": ["phbelitz"]},
            },
            {"pattern": "k8s.gcr.io/*:*", "validator": "allow"},
            {"pattern": "gcr.io/*:*", "validator": "allow"},
            {
                "pattern": "docker.io/securesystemsengineering/*:*",
                "validator": "dockerhub",
                "with": {"delegations": ["someuserthatdidnotsign"]},
            },
            {
                "pattern": "docker.io/securesystemsengineering/sample",
                "validator": "dockerhub",
                "with": {"delegations": ["phbelitz", "chamsen"]},
            },
            {
                "pattern": "docker.io/securesystemsengineering/sample:v4",
                "validator": "allow",
            },
            {
                "pattern": "docker.io/securesystemsengineering/connaisseur:*",
                "validator": "allow",
            },
            {
                "pattern": "docker.io/securesystemsengineering/sample-san-sama",
                "validator": "allow",
            },
            {
                "pattern": "docker.io/securesystemsengineering/alice-image",
                "validator": "dockerhub",
            },
        ]

    monkeypatch.setattr(co.Config, "__init__", mock_init)
    monkeypatch.setenv("KUBE_VERSION", "v1.20.0")

    import connaisseur.flask_application as fa

    pytest.fa = fa


@pytest.fixture(autouse=True)
def set_envs(monkeypatch):
    monkeypatch.setenv("AUTOMATIC_CHILD_APPROVAL", "true")
    monkeypatch.setenv("AUTOMATIC_UNCHANGED_APPROVAL", "true")
    monkeypatch.setenv("DETECTION_MODE", "false")


@pytest.mark.parametrize(
    "index, allowed, status_code, detection_mode",
    [(0, True, 202, False), (5, False, 403, False)],
)
def test_mutate(
    monkeypatch,
    adm_req_samples,
    index,
    m_request,
    m_expiry,
    m_trust_data,
    m_alerting,
    allowed,
    status_code,
    detection_mode,
):
    with aioresponses() as aio:
        aio.get(re.compile(r".*"), callback=fix.async_callback, repeat=True)
        monkeypatch.setenv("DETECTION_MODE", str(detection_mode))
        client = pytest.fa.APP.test_client()
        response = client.post("/mutate", json=adm_req_samples[index])
        admission_response = response.get_json()["response"]

        assert response.status_code == 200
        assert response.is_json
        assert admission_response["allowed"] == allowed
        assert admission_response["status"]["code"] == status_code


def test_mutate_calls_send_alert_for_invalid_admission_request(
    monkeypatch, adm_req_samples, m_request, m_trust_data, m_alerting_without_send
):
    with aioresponses() as aio:
        aio.get(re.compile(r".*"), callback=fix.async_callback, repeat=True)
        monkeypatch.setenv("DETECTION_MODE", "false")
        client = pytest.fa.APP.test_client()
        response = client.post("/mutate", json=adm_req_samples[7])
        admission_response = response.get_json()["response"]

        assert response.status_code == 200
        assert response.is_json
        assert admission_response["allowed"] == False
        assert admission_response["status"]["code"] == 403
        assert (
            alert.Alert.send_alert.call_count == 2
        )  # Alerting config has two configured receivers


def test_healthz():
    with pytest.fa.APP.test_request_context():
        assert pytest.fa.healthz() == ("", 200)


def test_readyz():
    with pytest.fa.APP.test_request_context():
        assert pytest.fa.readyz() == ("", 200)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "index, out, exception",
    [
        (
            0,
            {
                "apiVersion": "admission.k8s.io/v1",
                "kind": "AdmissionReview",
                "response": {
                    "uid": "3a3a7b38-5512-4a85-94bb-3562269e0a6a",
                    "allowed": True,
                    "status": {"code": 202},
                    "patchType": "JSONPatch",
                    "patch": (
                        "W3sib3AiOiAicmVwbGFjZSIsICJwYXRoIjogIi9zcGVjL3RlbXBs"
                        "YXRlL3NwZWMvY29udGFpbmVycy8wL2ltYWdlIiwgInZhbHVlIjog"
                        "ImRvY2tlci5pby9zZWN1cmVzeXN0ZW1zZW5naW5lZXJpbmcvYWxp"
                        "Y2UtaW1hZ2U6dGVzdEBzaGEyNTY6YWM5MDRjOWIxOTFkMTRmYWY1"
                        "NGI3OTUyZjI2NTBhNGJiMjFjMjAxYmYzNDEzMTM4OGI4NTFlOGNl"
                        "OTkyYTY1MiJ9XQ=="
                    ),
                },
            },
            fix.no_exc(),
        ),
        (
            1,
            {
                "apiVersion": "admission.k8s.io/v1",
                "kind": "AdmissionReview",
                "response": {
                    "uid": "0c3331b6-1812-11ea-b3fc-02897404852e",
                    "allowed": True,
                    "status": {"code": 202},
                },
            },
            fix.no_exc(),
        ),
        (5, {}, pytest.raises(exc.BaseConnaisseurException)),
        (
            6,
            {
                "apiVersion": "admission.k8s.io/v1",
                "kind": "AdmissionReview",
                "response": {
                    "uid": "3a3a7b38-5512-4a85-94bb-3562269e0a6a",
                    "allowed": True,
                    "status": {"code": 202},
                },
            },
            fix.no_exc(),
        ),
        (
            8,
            {
                "apiVersion": "admission.k8s.io/v1",
                "kind": "AdmissionReview",
                "response": {
                    "uid": "6418f614-b7f1-4c57-94bf-14fc30b2d791",
                    "allowed": True,
                    "status": {"code": 202},
                },
            },
            fix.no_exc(),
        ),
    ],
)
async def test_admit(
    monkeypatch,
    adm_req_samples,
    index,
    m_request,
    m_expiry,
    m_trust_data,
    out,
    exception,
):
    session = aiohttp.ClientSession()
    with exception:
        if index == 8:
            monkeypatch.setenv("AUTOMATIC_UNCHANGED_APPROVAL", "true")
        with aioresponses() as aio:
            aio.get(re.compile(r".*"), callback=fix.async_callback, repeat=True)
            response = await pytest.fa.__admit(
                AdmissionRequest(adm_req_samples[index]), session
            )
            assert response == out


@pytest.mark.parametrize(
    "function, err, status",
    [
        (
            {
                "target": "connaisseur.flask_application.dispatch_alerts",
                "side_effect": exc.AlertSendingError(""),
            },
            "Alert could not be sent. Check the logs for more details!",
            500,
        ),
        (
            {
                "target": "connaisseur.flask_application.dispatch_alerts",
                "side_effect": exc.ConfigurationError(""),
            },
            "Alerting configuration is not valid. Check the logs for more details!",
            500,
        ),
        (
            {
                "target": "connaisseur.flask_application.__admit",
                "side_effect": exc.BaseConnaisseurException("Some message"),
            },
            "Some message",
            200,
        ),
        (
            {
                "target": "connaisseur.flask_application.__admit",
                "side_effect": asyncio.TimeoutError(""),
            },
            "couldn't retrieve the necessary trust data for verification within 30s. most likely there was a network failure. check connectivity to external servers or retry",
            200,
        ),
        (
            {
                "target": "connaisseur.flask_application.__admit",
                "side_effect": Exception(""),
            },
            "unknown error. please check the logs.",
            200,
        ),
    ],
)
def test_error_handler(
    mocker,
    m_ad_schema_path,
    m_alerting,
    function,
    err,
    status,
):
    mocker.patch("connaisseur.flask_application.__admit", return_value=True)
    mock_function = mocker.patch(**function)
    with pytest.fa.APP.test_request_context():
        client = pytest.fa.APP.test_client()
        pytest.fa.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(pytest.fa.loop)
        mock_request_data = fix.get_admreq("deployments")
        response = client.post("/mutate", json=mock_request_data)
        assert response.status_code == status
        # If Connaisseur fails, response is error
        if status == 500:
            assert response.get_data().decode() == err
        # Else Connaisseur returns the error in its message and denies the request
        else:
            print(response.get_json())
            print(response.get_json().get("response"))
            assert response.get_json().get("response").get("allowed") == False
            assert (
                response.get_json().get("response").get("status").get("message") == err
            )


@pytest.mark.asyncio
async def test__validate_image_adds_context(mocker, adm_req_samples):
    mocker.patch(
        "connaisseur.config.Config.get_validator",
        return_value=StaticValidator("", False),
    )
    session = aiohttp.ClientSession()
    with pytest.raises(exc.ValidationError, match=r"'image': '[^']*myimagename:andtag"):
        await pytest.fa.__validate_image(
            (0, 0), "myimagename:andtag", AdmissionRequest(adm_req_samples[0]), session
        )
