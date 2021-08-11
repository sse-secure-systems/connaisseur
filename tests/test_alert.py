import pytest
from datetime import datetime, timedelta
import json

from . import conftest as fix
import connaisseur.alert as alert
from connaisseur.admission_request import AdmissionRequest
from connaisseur.exceptions import AlertSendingError, ConfigurationError

with open(
    "tests/data/sample_admission_requests/ad_request_deployments.json", "r"
) as readfile:
    admission_request_deployment = json.load(readfile)

with open(
    "tests/data/sample_admission_requests/ad_request_allowlisted.json", "r"
) as readfile:
    admission_request_allowlisted = json.load(readfile)

with open("tests/data/alerting/alertconfig_schema.json", "r") as readfile:
    alertconfig_schema = json.load(readfile)

opsgenie_receiver_config_throw = {
    "custom_headers": ["Authorization: GenieKey <Your-Genie-Key>"],
    "fail_if_alert_sending_fails": True,
    "payload_fields": {
        "responders": [{"type": "user", "username": "testuser@testcompany.de"}],
        "tags": ["image_deployed"],
        "visibleTo": [{"type": "user", "username": "testuser@testcompany.de"}],
    },
    "priority": 4,
    "receiver_url": "https://api.eu.opsgenie.com/v2/alerts",
    "template": "opsgenie",
}

opsgenie_receiver_config = {
    "custom_headers": ["Authorization: GenieKey <Your-Genie-Key>"],
    "fail_if_alert_sending_fails": False,
    "payload_fields": {
        "responders": [{"type": "user", "username": "testuser@testcompany.de"}],
        "tags": ["image_rejected"],
        "visibleTo": [{"type": "user", "username": "testuser@testcompany.de"}],
    },
    "priority": 4,
    "receiver_url": "https://api.eu.opsgenie.com/v2/alerts",
    "template": "opsgenie",
}

slack_receiver_config = {
    "priority": 3,
    "receiver_url": "https://hooks.slack.com/services/123",
    "template": "slack",
}

custom_receiver_config = {
    "receiver_url": "this.is.a.testurl.conn",
    "template": "custom",
}

keybase_receiver_config = {
    "custom_headers": ["Content-Language: de-DE"],
    "fail_if_alert_sending_fails": True,
    "priority": 3,
    "receiver_url": "https://bots.keybase.io/webhookbot/123",
    "template": "keybase",
}

missing_template_receiver_config = {
    "fail_if_alert_sending_fails": True,
    "receiver_url": "www.my.custom.rest.endpoint.receiving.connaisseurs.post.requests.io",
    "template": "my_own_custom_endpoint_for_which_I_forgot_to_create_a_payload_template",
}

alert_headers_opsgenie = {
    "Content-Type": "application/json",
    "Authorization": "GenieKey <Your-Genie-Key>",
}

alert_headers_slack = {"Content-Type": "application/json"}

alert_payload_opsgenie_deployment = {
    "message": "CONNAISSEUR admitted a request",
    "alias": "CONNAISSEUR admitted a request to deploy the images ['docker.io/securesystemsengineering/alice-image:test'].",
    "description": "CONNAISSEUR admitted a request to deploy the following images:\n ['docker.io/securesystemsengineering/alice-image:test'] \n\n Please check the logs of the `connaisseur-pod-123` for more details.",
    "responders": [{"type": "user", "username": "testuser@testcompany.de"}],
    "visibleTo": [{"type": "user", "username": "testuser@testcompany.de"}],
    "actions": [],
    "tags": ["image_deployed"],
    "details": {
        "pod": "connaisseur-pod-123",
        "cluster": "minikube",
        "alert_created": datetime.now(),
        "request_id": "3a3a7b38-5512-4a85-94bb-3562269e0a6a",
    },
    "entity": "Connaisseur",
    "priority": "P4",
}

alert_payload_slack_deployment = {
    "text": "Connaisseur Slack Alert Message",
    "blocks": [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*CONNAISSEUR admitted a request* \n\n_*Cluster*_:                           minikube\n_*Request ID*_:                     3a3a7b38-5512-4a85-94bb-3562269e0a6a\n_*Images*_:                           ['docker.io/securesystemsengineering/alice-image:test']\n_*Connaisseur Pod ID*_:       connaisseur-pod-123\n_*Created*_:                          ${datetime.now()}\n_*Severity*_:                          4\n\nCheck the logs of `connaisseur-pod-123` for more details!",
            },
        },
    ],
}

injection_string = '"]}, "test": "Can I inject into json?", "cluster":'


@pytest.mark.parametrize(
    "alerting_path, empty, exception",
    [
        ("tests/data/alerting/alertconfig.json", False, fix.no_exc()),
        ("tests/data/alerting/missing.json", True, fix.no_exc()),
        (
            "tests/data/alerting/misconfigured_config/alertconfig.json",
            True,
            pytest.raises(ConfigurationError, match=r".*invalid format.*"),
        ),
        (
            "tests/data/alerting/invalid_config/alertconfig.json",
            True,
            pytest.raises(ConfigurationError, match=r".*invalid format.*"),
        ),
        ("/", True, pytest.raises(ConfigurationError, match=r".*error occurred.*")),
    ],
)
def test_alert_config_init(
    monkeypatch, m_alerting, m_ad_schema_path, alerting_path, empty, exception
):
    with exception:
        alert.AlertingConfiguration._AlertingConfiguration__PATH = alerting_path
        conf = alert.AlertingConfiguration()
        assert bool(conf.config) is not empty


@pytest.mark.parametrize(
    "alerting_path, admission_request, event_category, out",
    [
        (
            "tests/data/alerting/alertconfig.json",
            admission_request_deployment,
            "admit_request",
            True,
        ),
        (
            "tests/data/alerting/config_only_send_on_admit/alertconfig.json",
            admission_request_deployment,
            "reject_request",
            False,
        ),
    ],
)
def test_alerting_required(
    m_alerting,
    m_ad_schema_path,
    alerting_path,
    admission_request,
    event_category,
    out,
):
    alert.AlertingConfiguration._AlertingConfiguration__PATH = alerting_path
    assert alert.AlertingConfiguration().alerting_required(event_category) is out


@pytest.mark.parametrize(
    "message, receiver_config, admission_request, alert_payload, alert_headers, exception",
    [
        (
            "CONNAISSEUR admitted a request",
            opsgenie_receiver_config_throw,
            admission_request_deployment,
            alert_payload_opsgenie_deployment,
            alert_headers_opsgenie,
            fix.no_exc(),
        ),
        (
            "CONNAISSEUR admitted a request",
            slack_receiver_config,
            admission_request_deployment,
            alert_payload_slack_deployment,
            alert_headers_slack,
            fix.no_exc(),
        ),
        (
            "CONNAISSEUR does great",
            custom_receiver_config,
            admission_request_deployment,
            [
                {"test": ["connaisseur-pod-123", "3"]},
                {"test1": ["CONNAISSEUR does great", "minikube"]},
            ],
            {"Content-Type": "application/json"},
            fix.no_exc(),
        ),
        (
            injection_string,
            custom_receiver_config,
            admission_request_deployment,
            [
                {"test": ["connaisseur-pod-123", "3"]},
                {"test1": [injection_string, "minikube"]},
            ],
            {"Content-Type": "application/json"},
            fix.no_exc(),
        ),
        (
            "CONNAISSEUR admitted a request",
            missing_template_receiver_config,
            admission_request_deployment,
            {},
            {},
            pytest.raises(ConfigurationError, match=r".*Unable.*"),
        ),
    ],
)
def test_alert_init(
    m_ad_schema_path,
    m_alerting,
    message: str,
    receiver_config: dict,
    admission_request: dict,
    alert_payload: dict,
    alert_headers: dict,
    exception,
):
    with exception:
        alert_ = alert.Alert(
            message, receiver_config, AdmissionRequest(admission_request)
        )
        assert alert_.throw_if_alert_sending_fails == receiver_config.get(
            "fail_if_alert_sending_fails", False
        )
        assert alert_.receiver_url == receiver_config["receiver_url"]
        assert alert_.headers == alert_headers
        payload = json.loads(alert_.payload)
        if receiver_config["template"] == "opsgenie":
            assert payload["details"]["alert_created"] is not None
            assert datetime.strptime(
                payload["details"]["alert_created"], "%Y-%m-%d %H:%M:%S.%f"
            ) > datetime.now() - timedelta(seconds=30)
            payload["details"].pop("alert_created")
            alert_payload["details"].pop("alert_created")
            assert payload == alert_payload
        if receiver_config["template"] == "slack":
            assert (
                alert_payload_slack_deployment["blocks"][1]["text"]["text"].split(
                    "Created"
                )[0]
                in json.loads(alert_.payload)["blocks"][1]["text"]["text"]
            )
        if receiver_config["template"] == "custom":
            assert alert_payload == json.loads(alert_.payload)


@pytest.mark.parametrize(
    "receiver_config, key, status, out, exception",
    [
        (
            opsgenie_receiver_config,
            "key",
            200,
            {
                "result": "Request will be processed",
                "took": 0.302,
                "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120",
            },
            fix.no_exc(),
        ),
        (
            opsgenie_receiver_config,
            "",
            401,
            {},
            fix.no_exc(),
        ),
        (
            opsgenie_receiver_config_throw,
            "",
            401,
            {},
            pytest.raises(AlertSendingError),
        ),
    ],
)
def test_alert_send_alert(
    m_request,
    m_ad_schema_path,
    m_alerting,
    receiver_config: dict,
    key: str,
    status: int,
    out: dict,
    exception,
):
    with exception:
        receiver_config["custom_headers"] = [f"Authorization: {key}"]
        alert_ = alert.Alert(
            "CONNAISSEUR admitted a request.",
            receiver_config,
            AdmissionRequest(admission_request_deployment),
        )
        response = alert_.send_alert()
        assert response.status_code == status
        assert response.json() == out


@pytest.mark.parametrize(
    "admission_request, admit_event, message, exception",
    [
        (fix.get_admreq("deployments"), True, None, fix.no_exc()),
        (fix.get_admreq("invalid_image"), False, "ERROR", fix.no_exc()),
    ],
)
def test_send_alerts(
    m_request,
    m_ad_schema_path,
    m_alerting,
    admission_request,
    admit_event,
    message,
    exception,
):
    with exception:
        assert (
            alert.send_alerts(AdmissionRequest(admission_request), admit_event, message)
            is None
        )
