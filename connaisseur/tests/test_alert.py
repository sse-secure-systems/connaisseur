import pytest
from datetime import datetime, timedelta
import json

from connaisseur.alert import (
    Alert,
    send_alerts,
    call_alerting_on_request,
    get_alert_config_validation_schema,
    load_config,
)
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
                "text": "*CONNAISSEUR admitted a request* \n\n_*Cluster*_:                           minikube\n_*Request ID*_:                     3a3a7b38-5512-4a85-94bb-3562269e0a6a\n_*Images*_:                           ['securesystemsengineering/alice-image:test']\n_*Connaisseur Pod ID*_:       connaisseur-pod-123\n_*Created*_:                          ${datetime.now()}\n_*Severity*_:                          4\n\nCheck the logs of `connaisseur-pod-123` for more details!",
            },
        },
    ],
}

injection_string = '"]}, "test": "Can I inject into json?", "cluster":'


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("ALERT_CONFIG_DIR", "tests/data/alerting")
    monkeypatch.setenv("POD_NAME", "connaisseur-pod-123")
    monkeypatch.setenv("CLUSTER_NAME", "minikube")
    monkeypatch.setenv(
        "HELM_HOOK_IMAGE", "securesystemsengineering/connaisseur:helm-hook"
    )


@pytest.fixture()
def mock_alertconfig_validation_schema(mocker):
    mocker.patch(
        "connaisseur.alert.get_alert_config_validation_schema",
        return_value=alertconfig_schema,
    )


@pytest.fixture(autouse=True)
def mock_safe_path_func_load_config(mocker):
    side_effect = lambda callback, base_dir, path, *args, **kwargs: callback(
        path, *args, **kwargs
    )
    mocker.patch("connaisseur.alert.safe_path_func", side_effect)


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
        (
            "CONNAISSEUR does great",
            custom_receiver_config,
            admission_request_deployment,
            [
                {"test": ["connaisseur-pod-123", "3"]},
                {"test1": ["CONNAISSEUR does great", "minikube"]},
            ],
            {"Content-Type": "application/json"},
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
        ),
    ],
)
def test_alert(
    m_ad_schema_path,
    mock_alertconfig_validation_schema,
    message: str,
    receiver_config: dict,
    admission_request: dict,
    alert_payload: dict,
    alert_headers: dict,
):
    alert = Alert(message, receiver_config, AdmissionRequest(admission_request))
    assert alert.throw_if_alert_sending_fails == receiver_config.get(
        "fail_if_alert_sending_fails", False
    )
    assert alert.receiver_url == receiver_config["receiver_url"]
    assert alert.headers == alert_headers
    payload = json.loads(alert.payload)
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
            in json.loads(alert.payload)["blocks"][1]["text"]["text"]
        )
    if receiver_config["template"] == "custom":
        assert alert_payload == json.loads(alert.payload)


@pytest.mark.parametrize(
    "message, receiver_config, admission_request",
    [
        (
            "CONNAISSEUR admitted a request",
            missing_template_receiver_config,
            admission_request_deployment,
        ),
    ],
)
def test_configuration_error_missing_template(
    m_ad_schema_path,
    mock_alertconfig_validation_schema,
    message,
    receiver_config,
    admission_request,
):
    with pytest.raises(ConfigurationError) as err:
        Alert(message, receiver_config, AdmissionRequest(admission_request))
    assert (
        "Template file for alerting payload is either missing or invalid JSON"
        in str(err.value)
    )


@pytest.mark.parametrize(
    "message, receiver_config, admission_request",
    [
        (
            "CONNAISSEUR admitted a request",
            slack_receiver_config,
            admission_request_deployment,
        ),
    ],
)
def test_configuration_error_missing_or_invalid_config(
    mock_alertconfig_validation_schema,
    mocker,
    monkeypatch,
    message,
    receiver_config,
    admission_request,
):
    alert_config_dirs = [
        "tests/data/alerting/misconfigured_config",
        "tests/data/alerting/invalid_config",
    ]
    for alert_config_dir in alert_config_dirs:
        monkeypatch.setenv("ALERT_CONFIG_DIR", alert_config_dir)
        with pytest.raises(ConfigurationError) as err:
            load_config()
        assert (
            "Alerting configuration file not valid."
            "Check in the 'helm/values.yml' whether everything is correctly configured"
            in str(err.value)
        )

    monkeypatch.setenv("ALERT_CONFIG_DIR", "tests/data/alerting/empty_dir")
    mock_info_log = mocker.patch("logging.info")
    load_config()
    mock_info_log.assert_has_calls(
        [
            mocker.call(
                "No alerting configuration file found."
                "To use the alerting feature you need to run `make upgrade`"
                "in a freshly pulled Connaisseur repository."
            )
        ]
    )


@pytest.mark.parametrize(
    "message, receiver_config, admission_request",
    [
        (
            "CONNAISSEUR admitted a request",
            opsgenie_receiver_config_throw,
            admission_request_deployment,
        ),
    ],
)
def test_alert_sending_error(
    m_ad_schema_path,
    requests_mock,
    mock_alertconfig_validation_schema,
    message: str,
    receiver_config: dict,
    admission_request: dict,
):
    requests_mock.post(
        "https://api.eu.opsgenie.com/v2/alerts",
        status_code=401,
    )
    with pytest.raises(AlertSendingError) as err:
        alert = Alert(message, receiver_config, AdmissionRequest(admission_request))
        alert.send_alert()
    assert (
        "401 Client Error: None for url: https://api.eu.opsgenie.com/v2/alerts"
        in str(err.value)
    )


@pytest.mark.parametrize(
    "message, receiver_config, admission_request",
    [
        (
            "CONNAISSEUR admitted a request",
            slack_receiver_config,
            admission_request_deployment,
        ),
    ],
)
def test_log_alert_sending_error(
    m_ad_schema_path,
    requests_mock,
    mocker,
    mock_alertconfig_validation_schema,
    message: str,
    receiver_config: dict,
    admission_request: dict,
):
    mock_error_log = mocker.patch("logging.error")
    requests_mock.post(
        "https://hooks.slack.com/services/123",
        status_code=401,
    )
    alert = Alert(message, receiver_config, AdmissionRequest(admission_request))
    alert.send_alert()
    assert mock_error_log.called is True


@pytest.mark.parametrize(
    "message, receiver_config, admission_request",
    [
        (
            "CONNAISSEUR admitted a request.",
            opsgenie_receiver_config,
            admission_request_deployment,
        )
    ],
)
def test_alert_sending(
    m_ad_schema_path,
    requests_mock,
    mocker,
    mock_alertconfig_validation_schema,
    message: str,
    receiver_config: dict,
    admission_request: dict,
):
    mock_info_log = mocker.patch("logging.info")
    requests_mock.post(
        "https://api.eu.opsgenie.com/v2/alerts",
        json={
            "result": "Request will be processed",
            "took": 0.302,
            "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120",
        },
        status_code=200,
    )
    alert = Alert(message, receiver_config, AdmissionRequest(admission_request))
    response = alert.send_alert()
    mock_info_log.assert_has_calls([mocker.call("sent alert to %s", "opsgenie")])
    assert response.status_code == 200
    assert response.json()["result"] == "Request will be processed"


@pytest.mark.parametrize(
    "message, receiver_config, admission_request",
    [
        (
            "CONNAISSEUR admitted a request.",
            opsgenie_receiver_config_throw,
            admission_request_allowlisted,
        ),
    ],
)
def test_alert_sending_bypass_for_only_allowlisted_images(
    m_ad_schema_path,
    mock_alertconfig_validation_schema,
    message: str,
    receiver_config: dict,
    admission_request: dict,
):

    Alert(message, receiver_config, AdmissionRequest(admission_request))


@pytest.mark.parametrize(
    "admission_request, admission_decision",
    [
        (admission_request_deployment, {"admitted": True}),
        (admission_request_deployment, {"admitted": False}),
    ],
)
def test_send_alerts(
    mocker,
    m_ad_schema_path,
    mock_alertconfig_validation_schema,
    admission_decision: bool,
    admission_request: dict,
):
    mock_alert = mocker.patch("connaisseur.alert.Alert")
    admission_request_instance = AdmissionRequest(admission_request)
    send_alerts(admission_request_instance, admitted=True)
    admit_calls = [
        mocker.call(
            "CONNAISSEUR admitted a request.",
            opsgenie_receiver_config_throw,
            admission_request_instance,
        ),
        mocker.call(
            "CONNAISSEUR admitted a request.",
            slack_receiver_config,
            admission_request_instance,
        ),
    ]
    mock_alert.assert_has_calls(admit_calls, any_order=True)
    mocker.resetall()
    mocker.patch(
        "connaisseur.alert.get_alert_config_validation_schema",
        return_value=alertconfig_schema,
    )
    mock_alert = mocker.patch("connaisseur.alert.Alert")
    send_alerts(
        admission_request_instance,
        admitted=False,
        reason="Couldn't find trust data.",
    )
    reject_calls = [
        mocker.call(
            "CONNAISSEUR rejected a request: Couldn't find trust data.",
            opsgenie_receiver_config,
            admission_request_instance,
        ),
        mocker.call(
            "CONNAISSEUR rejected a request: Couldn't find trust data.",
            keybase_receiver_config,
            admission_request_instance,
        ),
    ]
    mock_alert.assert_has_calls(reject_calls, any_order=True)
    mocker.resetall()

    mock_alert_sending = mocker.patch(
        "connaisseur.alert.Alert.send_alert", return_value=True
    )
    send_alerts(AdmissionRequest(admission_request), **admission_decision)
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
        (
            admission_request_allowlisted,
            {"admitted": True},
            "tests/data/alerting/empty_dir",
            False,
        ),
        (
            admission_request_allowlisted,
            {"admitted": False},
            "tests/data/alerting/empty_dir",
            False,
        ),
    ],
)
def test_call_alerting_on_request(
    mock_alertconfig_validation_schema,
    mocker,
    m_ad_schema_path,
    monkeypatch,
    admission_request,
    admission_decision,
    alert_config_dir,
    alert_call_decision,
):
    monkeypatch.setenv("ALERT_CONFIG_DIR", alert_config_dir)
    decision = call_alerting_on_request(
        AdmissionRequest(admission_request), **admission_decision
    )
    assert decision == alert_call_decision


def test_get_alert_config_validation_schema(mocker, mock_env_vars):
    with open("tests/data/alerting/alertconfig_schema.json") as f:
        content = f.read()
    mocker.patch("builtins.open", mocker.mock_open(read_data=content))
    assert get_alert_config_validation_schema() == alertconfig_schema
