import json
import sys
import pytest
import traceback
import re
from falcon import testing
from . import conftest as fix
from aioresponses import aioresponses
import connaisseur.exceptions as exc
import connaisseur.config as co
from connaisseur.validators.static.static_validator import StaticValidator
from connaisseur.admission_request import AdmissionRequest


@pytest.fixture
def app(monkeypatch, sample_nv1):
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

    import connaisseur.falcon_server as fs

    return fs


def test_health(app):
    client = testing.TestClient(app.APP)
    assert client.simulate_get("/health").status_code == 200


def test_ready(app):
    client = testing.TestClient(app.APP)
    assert client.simulate_get("/ready").status_code == 200


@pytest.mark.parametrize(
    "index, allowed, status_code, detection_mode",
    [(0, True, 202, 0), (5, False, 403, 0)],
)
def test_mutate(
    monkeypatch,
    app,
    adm_req_samples,
    index,
    m_request,
    m_trust_data,
    m_alerting,
    m_expiry,
    allowed,
    status_code,
    detection_mode,
):
    client = testing.TestClient(app.APP)
    with aioresponses() as aio:
        aio.get(re.compile(r".*"), callback=fix.async_callback, repeat=True)
        response = client.simulate_post("/mutate", json=adm_req_samples[index])

        assert response.status_code == 200
        assert response.json["response"]["allowed"] == allowed
        assert response.json["response"]["status"]["code"] == status_code


@pytest.mark.parametrize(
    "msg, kwargs, out",
    [
        (
            "message",
            {"kw1": "value1"},
            {"message": "message", "context": {"kw1": "value1"}},
        )
    ],
)
def test_create_logging_msg(app, msg, kwargs, out):
    assert app.Mutate(app.config)._Mutate__create_logging_msg(msg, **kwargs) == str(out)


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
                        "W3sib3AiOiAicmVwbGFjZSIsICJwYXRoIjogI"
                        "i9zcGVjL3RlbXBsYXRlL3NwZWMvY29udGFpbmVycy8wL2lt"
                        "YWdlIiwgInZhbHVlIjogImRvY2tlci5pby9zZWN1cmVzeXN"
                        "0ZW1zZW5naW5lZXJpbmcvYWxpY2UtaW1hZ2VAc2hhMjU2Om"
                        "FjOTA0YzliMTkxZDE0ZmFmNTRiNzk1MmYyNjUwYTRiYjIxY"
                        "zIwMWJmMzQxMzEzODhiODUxZThjZTk5MmE2NTIifV0="
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
    ],
)
async def test_admit(
    app, adm_req_samples, index, m_request, m_expiry, m_trust_data, out, exception
):
    mu = app.Mutate(app.config)
    with exception:
        with aioresponses() as aio:
            aio.get(re.compile(r".*"), callback=fix.async_callback, repeat=True)
            response = await mu._Mutate__admit(AdmissionRequest(adm_req_samples[index]))
            assert response == out


@pytest.mark.parametrize(
    "function, err",
    [
        (
            {
                "target": "connaisseur.falcon_server.send_alerts",
                "side_effect": exc.AlertSendingError(""),
            },
            "Alert could not be sent. Check the logs for more details!",
        ),
        (
            {
                "target": "connaisseur.falcon_server.send_alerts",
                "side_effect": exc.ConfigurationError(""),
            },
            "Alerting configuration is not valid. Check the logs for more details!",
        ),
    ],
)
def test_error_handler(
    app,
    mocker,
    m_ad_schema_path,
    m_alerting,
    function,
    err,
):

    mocker.patch("connaisseur.falcon_server.Mutate._Mutate__admit", return_value=True)
    mock_function = mocker.patch(**function)
    client = testing.TestClient(app.APP)
    mock_request_data = fix.get_admreq("deployments")
    response = client.simulate_post("/mutate", json=mock_request_data)
    assert response.status_code == 500
    assert response.text == err
