import pytest
from datetime import datetime, timedelta
import json
from connaisseur.alert import Alert, send_alerts, call_alerting_on_request
from connaisseur.exceptions import AlertSendingError, ConfigurationError
from connaisseur.policy import ImagePolicy

with open("tests/data/ad_request_deployments.json", "r") as readfile:
    admission_request_deployment = json.load(readfile)

with open("tests/data/ad_request_allowlisted.json", "r") as readfile:
    admission_request_allowlisted = json.load(readfile)

opsgenie_receiver_config_throw = {
    "custom_headers": ["Authorization: GenieKey 12345678-abcd-2222-3333-1234567890ef"],
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
    "custom_headers": ["Authorization: GenieKey 12345678-abcd-2222-3333-1234567890ef"],
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
    "fail_if_alert_sending_fails": False,
    "priority": 3,
    "receiver_url": "https://hooks.slack.com/services/A0123456789/ABCDEFGHIJ/HFb3Gs7FFscjQNJYWHGY7GPV",
    "template": "slack",
}

keybase_receiver_config = {
    "custom_headers": ["Content-Language: de-DE"],
    "fail_if_alert_sending_fails": True,
    "priority": 3,
    "receiver_url": "https://bots.keybase.io/webhookbot/IFP--tpV2wBxEP3ArYx4gVS_B-0",
    "template": "keybase",
}

misconfigured_receiver_config = {
    "fail_if_alert_sending_fails": True,
    "receiver_url": "https://bots.keybase.io/webhookbot/IFP--tpV2wBxEP3ArYx4gVS_B-0",
}

missing_template_receiver_config = {
    "fail_if_alert_sending_fails": True,
    "receiver_url": "www.my.custom.rest.endpoint.receiving.connaisseurs.post.requests.io",
    "template": "my_own_custom_endpoint_for_which_I_forgot_to_create_a_payload_template",
}

alert_headers_opsgenie = {
    "Content-Type": "application/json",
    "Authorization": "GenieKey 12345678-abcd-2222-3333-1234567890ef",
}

alert_headers_slack = {"Content-Type": "application/json"}

alert_payload_opsgenie_deployment = {
    "message": "CONNAISSEUR admitted a request",
    "alias": "CONNAISSEUR admitted a request to deploy the images ['securesystemsengineering/alice-image:test'].",
    "description": "CONNAISSEUR admitted a request to deploy the following images:\n ['securesystemsengineering/alice-image:test'] \n\n Please check the logs of the `connaisseur-pod-123` for more details.",
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
                "text": f"*CONNAISSEUR admitted a request*: \n\n_*Cluster*_:                           minikube\n_*Request ID*_:                     3a3a7b38-5512-4a85-94bb-3562269e0a6a\n_*Images*_:                           ['securesystemsengineering/alice-image:test']\n_*Connaisseur Pod ID*_:       connaisseur-pod-123\n_*Created*_:                          ${datetime.now()}\n_*Severity*_:                          4\n\nCheck the logs of `connaisseur-pod-123` for more details!",
            },
        },
    ],
}


@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("ALERT_CONFIG_DIR", "tests/data/alerting")
    monkeypatch.setenv("POD_NAME", "connaisseur-pod-123")
    monkeypatch.setenv(
        "HELM_HOOK_IMAGE", "securesystemsengineering/connaisseur:helm-hook"
    )


@pytest.fixture
def mock_image_policy(monkeypatch):
    def read_policy():
        with open("tests/data/imagepolicy.json") as readfile:
            policy = json.load(readfile)
            return policy["spec"]

    monkeypatch.setattr(ImagePolicy, "JSON_SCHEMA_PATH", "res/policy_schema.json")
    monkeypatch.setattr(ImagePolicy, "get_image_policy", read_policy)


@pytest.mark.parametrize(
    "message, receiver_config, admission_request, alert_payload, alert_headers",
    [
        (
            "CONNAISSEUR admitted a request",
            opsgenie_receiver_config_throw,
            admission_request_deployment,
            alert_payload_opsgenie_deployment,
            alert_headers_opsgenie,
        ),
        (
            "CONNAISSEUR admitted a request",
            slack_receiver_config,
            admission_request_deployment,
            alert_payload_slack_deployment,
            alert_headers_slack,
        ),
    ],
)
def test_alert(
    mock_env_vars,
    message: str,
    receiver_config: dict,
    admission_request: dict,
    alert_payload: dict,
    alert_headers: dict,
):
    alert = Alert(message, receiver_config, admission_request)
    assert (
        alert.throw_if_alert_sending_fails
        == receiver_config["fail_if_alert_sending_fails"]
    )
    assert alert.receiver_url == receiver_config["receiver_url"]
    assert alert.headers == alert_headers
    payload = alert.payload

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
            in alert.payload["blocks"][1]["text"]["text"]
        )


@pytest.mark.parametrize(
    "message, receiver_config, admission_request",
    [
        (
            "CONNAISSEUR admitted a request",
            misconfigured_receiver_config,
            admission_request_deployment,
        ),
        (
            "CONNAISSEUR admitted a request",
            missing_template_receiver_config,
            admission_request_deployment,
        ),
    ],
)
def test_configuration_error(
    capfd, mock_env_vars, message, receiver_config, admission_request
):
    with pytest.raises(Exception):
        Alert(message, receiver_config, admission_request)
        out, err = capfd.readouterr()
        with pytest.raises(ConfigurationError) as config_error:
            if receiver_config == misconfigured_receiver_config:
                assert (
                    "Either 'receiver_url' or 'template' or both are missing to construct the alert. Both can be configured in the 'values.yaml' file in the 'helm' directory"
                    in str(config_error)
                )
            if receiver_config == missing_template_receiver_config:
                assert (
                    "Template file for alerting payload is either missing or invalid JSON:"
                ) in str(config_error)
            assert ConfigurationError(config_error) == err


@pytest.mark.parametrize(
    "message, receiver_config, admission_request",
    [
        (
            "CONNAISSEUR admitted a request",
            opsgenie_receiver_config_throw,
            admission_request_deployment,
        ),
        (
            "CONNAISSEUR admitted a request",
            opsgenie_receiver_config,
            admission_request_deployment,
        ),
    ],
)
def test_alert_sending_error(
    requests_mock,
    capfd,
    caplog,
    mock_env_vars,
    mock_image_policy,
    message: str,
    receiver_config: dict,
    admission_request: dict,
):
    requests_mock.post(
        "https://api.eu.opsgenie.com/v2/alerts",
        text="401 Client Error: Unauthorized for url: https://api.eu.opsgenie.com/v2/alerts",
        status_code=401,
    )
    alert = Alert(message, receiver_config, admission_request)
    with pytest.raises(Exception):
        alert.send_alert()
        if alert.throw_if_alert_sending_fails is True:
            out, err = capfd.readouterr()
            with pytest.raises(AlertSendingError) as alert_error:
                assert (
                    "401 Client Error: Unauthorized for url: https://api.eu.opsgenie.com/v2/alerts"
                    in str(alert_error)
                )
                assert AlertSendingError(alert_error) == err
        else:
            assert (
                "401 Client Error: Unauthorized for url: https://api.eu.opsgenie.com/v2/alerts"
                in caplog.text
            )


@pytest.mark.parametrize(
    "message, receiver_config, admission_request",
    [
        (
            "CONNAISSEUR admitted a request",
            opsgenie_receiver_config,
            admission_request_deployment,
        )
    ],
)
def test_alert_sending(
    requests_mock,
    caplog,
    mock_env_vars,
    mock_image_policy,
    message: str,
    receiver_config: dict,
    admission_request: dict,
):
    requests_mock.post(
        "https://api.eu.opsgenie.com/v2/alerts",
        json={
            "result": "Request will be processed",
            "took": 0.302,
            "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120",
        },
        status_code=200,
    )
    alert = Alert(message, receiver_config, admission_request)
    with pytest.raises(Exception):
        response = alert.send_alert()
        assert "sent alert to opsgenie" in caplog.text
        assert response.status_code == 200
        assert response.json.result == "Request will be processed"


@pytest.mark.parametrize(
    "message, receiver_config, admission_request",
    [
        (
            "CONNAISSEUR admitted a request",
            opsgenie_receiver_config_throw,
            admission_request_allowlisted,
        ),
    ],
)
def test_alert_sending_bypass_for_only_allowlisted_images(
    mock_env_vars,
    mock_image_policy,
    message: str,
    receiver_config: dict,
    admission_request: dict,
):
    Alert(message, receiver_config, admission_request)


@pytest.mark.parametrize(
    "admission_request, admission_decision",
    [
        (admission_request_deployment, {"admitted": True}),
        (admission_request_deployment, {"admitted": False}),
    ],
)
def test_send_alerts(
    mock_env_vars, mocker, admission_decision: bool, admission_request: dict
):
    mock_alert = mocker.patch("connaisseur.alert.Alert")
    send_alerts(admission_request, admitted=True)
    admit_calls = [
        mocker.call(
            "CONNAISSEUR admitted a request",
            opsgenie_receiver_config_throw,
            admission_request_deployment,
        ),
        mocker.call(
            "CONNAISSEUR admitted a request",
            slack_receiver_config,
            admission_request_deployment,
        ),
    ]
    assert mock_alert.has_calls(admit_calls)
    mocker.resetall()

    mock_alert = mocker.patch("connaisseur.alert.Alert")
    send_alerts(admission_request, admitted=False)
    reject_calls = [
        mocker.call(
            "CONNAISSEUR rejected a request",
            opsgenie_receiver_config,
            admission_request_deployment,
        ),
        mocker.call(
            "CONNAISSEUR rejected a request",
            keybase_receiver_config,
            admission_request_deployment,
        ),
    ]
    assert mock_alert.has_calls(reject_calls)
    mocker.resetall()

    mock_alert_sending = mocker.patch(
        "connaisseur.alert.Alert.send_alert", return_value=True
    )
    send_alerts(admission_request, **admission_decision)
    assert mock_alert_sending.has_calls([mocker.call(), mocker.call()])


@pytest.mark.parametrize(
    "admission_request, admission_decision, alert_config_dir, alert_call_decision",
    [
        (
            admission_request_deployment,
            {"admitted": True},
            "tests/data/alerting/config_only_send_on_reject",
            False,
        ),
        (
            admission_request_deployment,
            {"admitted": True},
            "tests/data/alerting/config_only_send_on_admit",
            True,
        ),
        (
            admission_request_deployment,
            {"admitted": False},
            "tests/data/alerting/config_only_send_on_admit",
            False,
        ),
        (
            admission_request_deployment,
            {"admitted": False},
            "tests/data/alerting",
            True,
        ),
        (
            admission_request_allowlisted,
            {"admitted": False},
            "tests/data/alerting",
            False,
        ),
        (
            admission_request_allowlisted,
            {"admitted": True},
            "tests/data/alerting",
            False,
        ),
    ],
)
def test_call_alerting_on_request(
    mock_env_vars,
    monkeypatch,
    admission_request,
    admission_decision,
    alert_config_dir,
    alert_call_decision,
):
    monkeypatch.setenv("ALERT_CONFIG_DIR", alert_config_dir)
    decision = call_alerting_on_request(admission_request, **admission_decision)
    assert decision == alert_call_decision
