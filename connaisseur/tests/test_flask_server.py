import pytest
import conftest as fix
import connaisseur.exceptions as exc
import connaisseur.config as co
from connaisseur.image import Image
from connaisseur.admission_request import AdmissionRequest


@pytest.fixture(autouse=True)
def m_config(monkeypatch, sample_notary):
    def mock_init(self):
        self.notaries = [sample_notary]

    monkeypatch.setattr(co.Config, "__init__", mock_init)

    import connaisseur.flask_server as fs

    pytest.fs = fs


@pytest.mark.parametrize(
    "index, allowed, status_code, detection_mode",
    [(0, True, 202, 0), (5, False, 403, 0)],
)
def test_mutate(
    monkeypatch,
    adm_req_samples,
    index,
    m_request,
    m_policy,
    m_expiry,
    m_trust_data,
    allowed,
    status_code,
    detection_mode,
):
    monkeypatch.setenv("DETECTION_MODE", str(detection_mode))
    client = pytest.fs.APP.test_client()
    response = client.post("/mutate", json=adm_req_samples[index])
    admission_response = response.get_json()["response"]

    assert response.status_code == 200
    assert response.is_json
    assert admission_response["allowed"] == allowed
    assert admission_response["status"]["code"] == status_code


def test_healthz(m_config):
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
    m_request,
    monkeypatch,
    sentinel_name,
    webhook,
    status,
):
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "127.0.0.1")
    monkeypatch.setenv("KUBERNETES_SERVICE_PORT", "1234")
    monkeypatch.setenv("CONNAISSEUR_NAMESPACE", "conny")
    monkeypatch.setenv("CONNAISSEUR_SENTINEL", sentinel_name)
    monkeypatch.setenv("CONNAISSEUR_WEBHOOK", webhook)

    assert pytest.fs.readyz() == ("", status)


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
def test_create_logging_msg(msg, kwargs, out):
    assert pytest.fs.__create_logging_msg(msg, **kwargs) == str(out)


@pytest.mark.parametrize(
    "path, index, image, out",
    [
        (
            "/sample/path/{}/image",
            3,
            "sample-image",
            {
                "op": "replace",
                "path": "/sample/path/3/image",
                "value": "docker.io/library/sample-image:latest",
            },
        )
    ],
)
def test_create_json_patch(path, index, image, out):
    assert pytest.fs.__create_json_patch(path, index, Image(image)) == out


@pytest.mark.parametrize(
    "index, out, exception",
    [
        (
            0,
            {
                "apiVersion": "admission.k8s.io/v1beta1",
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
                "apiVersion": "admission.k8s.io/v1beta1",
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
                "apiVersion": "admission.k8s.io/v1beta1",
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
def test_admit(
    adm_req_samples, index, m_request, m_policy, m_expiry, m_trust_data, out, exception
):
    with exception:
        assert pytest.fs.__admit(AdmissionRequest(adm_req_samples[index])) == out


@pytest.mark.parametrize(
    "function, err",
    [
        (
            {
                "target": "connaisseur.flask_server.send_alerts",
                "side_effect": exc.AlertSendingError(""),
            },
            "Alert could not be sent. Check the logs for more details!",
        ),
        (
            {
                "target": "connaisseur.flask_server.call_alerting_on_request",
                "side_effect": exc.ConfigurationError(""),
            },
            "Alerting configuration is not valid. Check the logs for more details!",
        ),
    ],
)
def test_error_handler(
    mocker,
    m_ad_schema_path,
    m_alerting,
    function,
    err,
):

    mocker.patch("connaisseur.flask_server.__admit", return_value=True)
    mock_function = mocker.patch(**function)
    client = pytest.fs.APP.test_client()
    mock_request_data = fix.get_admreq("deployments")
    response = client.post("/mutate", json=mock_request_data)
    assert response.status_code == 500
    assert response.get_data().decode() == err
