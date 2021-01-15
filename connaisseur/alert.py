import json
import logging
import os
from datetime import datetime

import requests
from jinja2 import Template, StrictUndefined

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

    connaisseur_pod_id: str
    cluster: str
    timestamp: int

    request_id: str
    images: list

    template: str
    receiver_url: str
    payload: dict
    headers: dict

    alert_message: str
    priority: int

    def __init__(self, alert_message, receiver_config, admission_request):
        if "receiver_url" not in receiver_config or "template" not in receiver_config:
            raise ConfigurationError(
                "Either 'receiver_url' or 'template' or both are missing to construct the alert. "
                "Both can be configured in the 'values.yaml' file in the 'helm' directory"
            )
        self.context = {
            "alert_message": alert_message,
            "priority": str(receiver_config.get("priority", 3)),
            "connaisseur_pod_id": os.getenv("POD_NAME"),
            "cluster": load_config()["cluster_name"],
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
            "fail_if_alert_sending_fails", True
        )
        self.payload = self._construct_payload(receiver_config)
        self.headers = get_headers(receiver_config)

    def _construct_payload(self, receiver_config):
        try:
            with open(
                "{}/{}.json".format(os.getenv("ALERT_CONFIG_DIR"), self.template),
                "r",
            ) as templatefile:
                template = json.load(templatefile)
        except Exception as err:
            raise ConfigurationError(
                "Template file for alerting payload is either missing or invalid JSON: {}".format(
                    str(err)
                )
            )
        payload = sanitize(template, self.context)
        if receiver_config.get("payload_fields") is not None:
            payload.update(receiver_config.get("payload_fields"))
        return payload

    def send_alert(self):
        try:
            response = requests.post(
                self.receiver_url, data=self.payload, headers=self.headers
            )
            response.raise_for_status()
            logging.info("sent alert to %s", self.template.split("_")[0])
        except Exception as err:
            if self.throw_if_alert_sending_fails:
                raise AlertSendingError(str(err))
            logging.error(err)
        return response


def load_config():
    with open(
        "{}/alertconfig.json".format(os.getenv("ALERT_CONFIG_DIR")), "r"
    ) as configfile:
        return json.loads(configfile.read())


def get_images(admission_request):
    relevant_spec = get_container_specs(
        admission_request.get("request", {}).get("object", {})
    )
    return [container.get("image") for container in relevant_spec]


def get_headers(receiver_config):
    headers = {"Content-Type": "application/json"}
    additional_headers = receiver_config.get("custom_headers")
    if additional_headers is not None:
        for header in additional_headers:
            key, value = header.split(":", 1)
            headers.update({key.strip(): value.strip()})
    return headers


def send_alerts(admission_request, *, admitted):
    alert_config = load_config()
    event_category = "admit_request" if admitted else "reject_request"
    if alert_config.get(event_category) is not None:
        for receiver in alert_config[event_category]["templates"]:
            message = (
                alert_config[event_category].get(
                    "message", "CONNAISSEUR admitted a request."
                )
                if admitted
                else alert_config[event_category].get(
                    "message", "CONNAISSEUR rejected a request."
                )
            )
            alert = Alert(message, receiver, admission_request)
            alert.send_alert()


def sanitize(template_dict, context):
    if isinstance(template_dict, (dict, list)):
        for key, value in template_dict.items():
            if isinstance(value, dict):
                sanitize(value, context)
            elif isinstance(value, list):
                for entry in value:
                    sanitize(entry, context)
            else:
                template_dict[key] = Template(value).render(
                    context, undefined=StrictUndefined
                )
    return template_dict


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
    config = load_config()
    templates = (
        config.get("admit_request") if admitted else config.get("reject_request")
    )
    if images == [hook_image] or templates is None:
        return False
    return True
