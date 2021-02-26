import json
import logging
import os
from datetime import datetime

import requests
from jinja2 import Template, StrictUndefined
from jsonschema import validate as json_validate

from connaisseur.util import safe_path_func
from connaisseur.exceptions import AlertSendingError, ConfigurationError
from connaisseur.image import Image
from connaisseur.mutate import get_container_specs


class Alert:
    """
    Class to store image information about an alert as attributes and a sending functionality as method.
    Alert Sending can, depending on the configuration, throw an AlertSendingError causing Connaisseur
    responding with status code 500 to the request that was sent for admission control,
    causing a Kubernetes Error event.
    """

    template: str
    receiver_url: str
    payload: dict
    headers: dict

    context: dict
    admission_request: dict
    throw_if_alert_sending_fails: bool

    def __init__(self, alert_message, receiver_config, admission_request):
        self.context = {
            "alert_message": alert_message,
            "priority": str(receiver_config.get("priority", 3)),
            "connaisseur_pod_id": os.getenv("POD_NAME"),
            "cluster": os.getenv("CLUSTER_NAME"),
            "timestamp": datetime.now(),
            "request_id": admission_request.get("request", {}).get(
                "uid", "No given UID"
            ),
            "images": (str(get_images(admission_request)) or "No given images"),
        }
        self.admission_request = admission_request
        self.receiver_url = receiver_config["receiver_url"]
        self.template = receiver_config["template"]
        self.throw_if_alert_sending_fails = receiver_config.get(
            "fail_if_alert_sending_fails", False
        )
        self.payload = self._construct_payload(receiver_config)
        self.headers = _get_headers(receiver_config)

    def _construct_payload(self, receiver_config):
        try:
            alert_templates_dir = f'{os.getenv("ALERT_CONFIG_DIR")}/templates'
            with safe_path_func(
                open,
                alert_templates_dir,
                f"{alert_templates_dir}/{self.template}.json",
                "r",
            ) as templatefile:
                template = json.load(templatefile)
        except Exception as err:
            raise ConfigurationError(
                "Template file for alerting payload is either missing or invalid JSON: {}".format(
                    str(err)
                )
            )
        payload = self._render_template(template)
        if receiver_config.get("payload_fields") is not None:
            payload.update(receiver_config.get("payload_fields"))
        return json.dumps(payload)

    def _render_template(self, template_dict):
        if isinstance(template_dict, (dict, list)):
            for key, value in template_dict.items():
                if isinstance(value, dict):
                    self._render_template(value)
                elif isinstance(value, list):
                    for entry in value:
                        self._render_template(entry)
                else:
                    template_dict[key] = Template(value).render(
                        self.context, undefined=StrictUndefined
                    )
        return template_dict

    def send_alert(self):
        try:
            response = requests.post(
                self.receiver_url, data=self.payload, headers=self.headers
            )
            response.raise_for_status()
            logging.info("sent alert to %s", self.template)
        except Exception as err:
            if self.throw_if_alert_sending_fails:
                raise AlertSendingError(str(err))
            logging.error(err)
        return response


def _get_headers(receiver_config):
    headers = {"Content-Type": "application/json"}
    additional_headers = receiver_config.get("custom_headers")
    if additional_headers is not None:
        for header in additional_headers:
            key, value = header.split(":", 1)
            headers.update({key.strip(): value.strip()})
    return headers


def load_config():
    try:
        alert_config_dir = f'{os.getenv("ALERT_CONFIG_DIR")}'
        with safe_path_func(
            open, alert_config_dir, f"{alert_config_dir}/alertconfig.json", "r"
        ) as configfile:
            alertconfig = json.load(configfile)
            schema = get_alert_config_validation_schema()
            json_validate(instance=alertconfig, schema=schema)
    except Exception as err:
        raise ConfigurationError(
            "Alerting configuration file either not present or not valid."
            "Check in the 'helm/values.yml' whether everything is correctly configured. {}".format(
                str(err)
            )
        )
    return alertconfig


def get_images(admission_request):
    relevant_spec = get_container_specs(
        admission_request.get("request", {}).get("object", {})
    )
    return [container.get("image") for container in relevant_spec]


def send_alerts(admission_request, *, admitted, reason=None):
    alert_config = load_config()
    event_category = "admit_request" if admitted else "reject_request"
    if alert_config.get(event_category) is not None:
        for receiver in alert_config[event_category]["templates"]:
            message = (
                "CONNAISSEUR admitted a request."
                if admitted
                else "CONNAISSEUR rejected a request: {}".format(reason)
            )
            alert = Alert(message, receiver, admission_request)
            alert.send_alert()


def call_alerting_on_request(admission_request, *, admitted):
    normalized_hook_image = Image(os.getenv("HELM_HOOK_IMAGE"))
    hook_image = "{}/{}/{}:{}".format(
        normalized_hook_image.registry,
        normalized_hook_image.repository,
        normalized_hook_image.name,
        normalized_hook_image.tag,
    )
    images = []
    for image in get_images(admission_request):
        normalized_image = Image(image)
        images.append(
            "{}/{}/{}:{}".format(
                normalized_image.registry,
                normalized_image.repository,
                normalized_image.name,
                normalized_image.tag,
            )
        )
    if images == [hook_image]:
        return False
    return not no_alerting_configured_for_event(admitted)


def no_alerting_configured_for_event(admitted):
    config = load_config()
    templates = (
        config.get("admit_request") if admitted else config.get("reject_request")
    )
    return templates is None


def get_alert_config_validation_schema():
    with open("connaisseur/res/alertconfig_schema.json") as schemafile:
        return json.load(schemafile)
