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
from connaisseur.admission_request import AdmissionRequest


__SCHEMA_PATH = "connaisseur/res/alertconfig_schema.json"


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
    throw_if_alert_sending_fails: bool

    def __init__(
        self, alert_message, receiver_config, admission_request: AdmissionRequest
    ):
        self.context = {
            "alert_message": alert_message,
            "priority": str(receiver_config.get("priority", 3)),
            "connaisseur_pod_id": os.getenv("POD_NAME"),
            "cluster": os.getenv("CLUSTER_NAME"),
            "timestamp": datetime.now(),
            "request_id": admission_request.uid or "No given UID",
            "images": (
                str(admission_request.wl_object.container_images) or "No given images"
            ),
        }
        self.receiver_url = receiver_config["receiver_url"]
        self.template = receiver_config["template"]
        self.throw_if_alert_sending_fails = receiver_config.get(
            "fail_if_alert_sending_fails", False
        )
        self.payload = self._construct_payload(receiver_config)
        self.headers = self._get_headers(receiver_config)

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
            ) from err
        payload = self._render_template(template)
        if receiver_config.get("payload_fields") is not None:
            payload.update(receiver_config.get("payload_fields"))
        return json.dumps(payload)

    def _render_template(self, template):
        if isinstance(template, dict):
            for key in template.keys():
                template[key] = self._render_template(template[key])
        elif isinstance(template, list):
            template[:] = [self._render_template(entry) for entry in template]
        elif isinstance(template, str):
            template = Template(template).render(
                self.context, undefined=StrictUndefined
            )
        return template

    def send_alert(self):
        try:
            response = requests.post(
                self.receiver_url, data=self.payload, headers=self.headers
            )
            response.raise_for_status()
            logging.info("sent alert to %s", self.template)
        except Exception as err:
            if self.throw_if_alert_sending_fails:
                raise AlertSendingError(str(err)) from err
            logging.error(err)
        return response

    @staticmethod
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
        alert_config_dir = f'{os.getenv("ALERT_CONFIG_DIR", "/app")}'
        with safe_path_func(
            open, alert_config_dir, f"{alert_config_dir}/alertconfig.json", "r"
        ) as configfile:
            alertconfig = json.load(configfile)
        schema = get_alert_config_validation_schema()
        json_validate(instance=alertconfig, schema=schema)
    except Exception as err:
        if isinstance(err, FileNotFoundError):
            logging.info(
                "No alerting configuration file found."
                "To use the alerting feature you need to run `make upgrade`"
                "in a freshly pulled Connaisseur repository."
            )
            return {}
        else:
            raise ConfigurationError(
                "Alerting configuration file not valid."
                "Check in the 'helm/values.yml' whether everything is correctly configured. {}".format(
                    str(err)
                )
            ) from err
    return alertconfig


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
    if no_alerting_configured_for_event(admitted) is True:
        return False
    else:
        normalized_hook_image = Image(os.getenv("HELM_HOOK_IMAGE"))
        hook_image = "{}/{}/{}:{}".format(
            normalized_hook_image.registry,
            normalized_hook_image.repository,
            normalized_hook_image.name,
            normalized_hook_image.tag,
        )
        images = []
        for image in admission_request.wl_object.container_images:
            normalized_image = Image(image)
            images.append(
                "{}/{}/{}:{}".format(
                    normalized_image.registry,
                    normalized_image.repository,
                    normalized_image.name,
                    normalized_image.tag,
                )
            )
        return images != [hook_image]


def no_alerting_configured_for_event(admitted):
    config = load_config()
    templates = (
        config.get("admit_request") if admitted else config.get("reject_request")
    )
    return templates is None


def get_alert_config_validation_schema():
    with open(__SCHEMA_PATH) as schemafile:
        return json.load(schemafile)
