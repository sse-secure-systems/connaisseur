import json
import logging
import os
from datetime import datetime

import requests
from jinja2 import Template, StrictUndefined

from connaisseur.util import safe_json_open, validate_schema
from connaisseur.exceptions import (
    AlertSendingError,
    ConfigurationError,
    InvalidConfigurationFormatError,
    InvalidImageFormatError,
)
from connaisseur.image import Image
from connaisseur.admission_request import AdmissionRequest


class AlertingConfiguration:

    __PATH = "/app/config/alertconfig.json"
    __SCHEMA_PATH = "/app/connaisseur/res/alertconfig_schema.json"

    config: dict

    def __init__(self):
        try:
            self.config = safe_json_open("/app/config", self.__PATH)
            validate_schema(
                self.config,
                self.__SCHEMA_PATH,
                "AlertingConfiguration",
                InvalidConfigurationFormatError,
            )
        except FileNotFoundError:
            logging.info(
                "No alerting configuration file found."
                "To use the alerting feature you need to run `make upgrade`"
                "in a freshly pulled Connaisseur repository."
            )
            self.config = {}
        except InvalidConfigurationFormatError as err:
            raise ConfigurationError(err.message) from err
        except Exception as err:
            raise ConfigurationError(
                "An error occurred while loading the AlertingConfiguration file:"
                f"{str(err)}"
            ) from err

    def alerting_required(self, event_category: str):
        return bool(self.config.get(event_category))


class Alert:
    """
    Class to store image information about an alert as attributes and a sending
    functionality as method.
    Alert Sending can, depending on the configuration, throw an AlertSendingError
    causing Connaisseur responding with status code 500 to the request that was sent
    for admission control, causing a Kubernetes Error event.
    """

    template: str
    receiver_url: str
    payload: dict
    headers: dict

    context: dict
    throw_if_alert_sending_fails: bool

    __TEMPLATE_PATH = "/app/config/templates"

    def __init__(
        self, alert_message, receiver_config, admission_request: AdmissionRequest
    ):
        self.context = {
            "alert_message": alert_message,
            "priority": str(receiver_config.get("priority", 3)),
            "connaisseur_pod_id": os.getenv("POD_NAME"),
            "cluster": os.getenv("CLUSTER_NAME"),
            "namespace": admission_request.namespace,
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
        self.payload = self.__construct_payload(receiver_config)
        self.headers = self.__get_headers(receiver_config)

    def __construct_payload(self, receiver_config):
        try:
            template = safe_json_open(
                self.__TEMPLATE_PATH, f"{self.__TEMPLATE_PATH}/{self.template}.json"
            )
        except FileNotFoundError as err:
            raise ConfigurationError(
                f"Unable to find template file {self.template}."
            ) from err
        except Exception as err:
            raise ConfigurationError(
                f"Error loading template file {self.template}: {str(err)}"
            ) from err
        payload = self.__render_template(template)
        if receiver_config.get("payload_fields") is not None:
            payload.update(receiver_config.get("payload_fields"))
        return json.dumps(payload)

    def __render_template(self, template):
        if isinstance(template, dict):
            for key in template.keys():
                template[key] = self.__render_template(template[key])
        elif isinstance(template, list):
            template[:] = [self.__render_template(entry) for entry in template]
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
            logging.error(err)
            if self.throw_if_alert_sending_fails:
                raise AlertSendingError(str(err)) from err
        return response

    @staticmethod
    def __get_headers(receiver_config):
        headers = {"Content-Type": "application/json"}
        additional_headers = receiver_config.get("custom_headers")
        if additional_headers is not None:
            for header in additional_headers:
                key, value = header.split(":", 1)
                headers.update({key.strip(): value.strip()})
        return headers


def send_alerts(
    admission_request: AdmissionRequest, admit_event: bool, reason: str = None
):
    al_config = AlertingConfiguration()
    event_category = "admit_request" if admit_event else "reject_request"
    if al_config.alerting_required(event_category) and __is_not_hook_image(
        admission_request
    ):
        for receiver in al_config.config[event_category]["templates"]:
            message = (
                "CONNAISSEUR admitted a request."
                if admit_event
                else f"CONNAISSEUR rejected a request: {reason}"
            )
            Alert(message, receiver, admission_request).send_alert()


def __is_not_hook_image(admission_request: AdmissionRequest):
    try:
        normalized_hook_image = Image(os.getenv("HELM_HOOK_IMAGE"))
        return [
            str(Image(image)) for image in admission_request.wl_object.container_images
        ] != [str(normalized_hook_image)]
    except InvalidImageFormatError:
        return True
