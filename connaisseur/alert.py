import json
import logging
import os
from datetime import datetime
from threading import Thread
from typing import Optional

import requests
from jinja2 import StrictUndefined, Template

from connaisseur.admission_request import AdmissionRequest
from connaisseur.exceptions import (
    AlertSendingError,
    ConfigurationError,
    InvalidConfigurationFormatError,
    InvalidImageFormatError,
)
from connaisseur.util import safe_json_open, validate_schema


class AlertingConfiguration:
    __PATH = "/app/config/alertconfig.json"
    __SCHEMA_PATH = "/app/connaisseur/res/alertconfig_schema.json"

    ADMIT_CATEGORY_KEY = "admitRequest"
    FAIL_IF_SEND_FAILS_KEY = "failIfAlertSendingFails"
    HEADER_KEY = "customHeaders"
    PAYLOAD_FIELDS_KEY = "payloadFields"
    PRIORITY_KEY = "priority"
    RECEIVER_KEY = "receivers"
    REJECT_CATEGORY_KEY = "rejectRequest"
    TEMPLATE_KEY = "template"
    URL_KEY = "receiverUrl"

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
            logging.debug("No alerting configuration file found.")
            self.config = {}
        except InvalidConfigurationFormatError as err:
            raise ConfigurationError(err.message) from err
        except Exception as err:
            raise ConfigurationError(
                "An error occurred while loading the AlertingConfiguration file:"
                f"{str(err)}"
            ) from err

    def alerting_required(self, event_category: str) -> bool:
        return bool(self.config.get(event_category))


class Alert:
    """
    Class to store image information about an alert as attributes and a sending
    functionality as method.
    Alert sending can, depending on the configuration, throw an AlertSendingError
    causing Connaisseur to respond with status code 500 to the request that was sent
    for admission control, causing a Kubernetes Error event.
    """

    template: str
    receiver_url: str
    payload: str
    headers: dict

    context: dict
    throw_if_alert_sending_fails: bool

    __TEMPLATE_PATH = "/app/config/templates"

    def __init__(
        self,
        alert_message: str,
        receiver_config: dict,
        admission_request: AdmissionRequest,
    ):
        if admission_request is None:
            images = "Invalid admission request."
            namespace = "Invalid admission request."
            request_id = "Invalid admission request."
        else:
            namespace = admission_request.namespace
            request_id = admission_request.uid
            try:
                images = str(
                    [
                        str(image)
                        for image in admission_request.wl_object.containers.values()
                    ]
                )
            except InvalidImageFormatError:
                images = "Error retrieving images."

        self.context = {
            "alert_message": alert_message,
            "priority": str(receiver_config.get(AlertingConfiguration.PRIORITY_KEY, 3)),
            "connaisseur_pod_id": os.getenv("POD_NAME"),
            "cluster": os.getenv("CLUSTER_NAME"),
            "namespace": namespace,
            "timestamp": datetime.now(),
            "request_id": request_id or "No given UID",
            "images": images,
        }
        self.receiver_url = receiver_config[AlertingConfiguration.URL_KEY]
        self.template = receiver_config[AlertingConfiguration.TEMPLATE_KEY]
        self.throw_if_alert_sending_fails = receiver_config.get(
            AlertingConfiguration.FAIL_IF_SEND_FAILS_KEY, False
        )
        self.payload = self.__construct_payload(receiver_config)
        self.headers = self.__get_headers(receiver_config)

    def __construct_payload(self, receiver_config: dict) -> str:
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
        if receiver_config.get(AlertingConfiguration.PAYLOAD_FIELDS_KEY) is not None:
            payload.update(
                receiver_config.get(AlertingConfiguration.PAYLOAD_FIELDS_KEY)
            )
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

    def send_alert(self) -> Optional[requests.Response]:
        response = None
        try:
            response = requests.post(
                self.receiver_url, data=self.payload, headers=self.headers, timeout=30
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
        additional_headers = receiver_config.get(AlertingConfiguration.HEADER_KEY)
        if additional_headers is not None:
            for header in additional_headers:
                key, value = header.split(":", 1)
                headers.update({key.strip(): value.strip()})
        return headers


def dispatch_alerts(
    admission_request: AdmissionRequest, admit_event: bool, reason: str = None
) -> None:
    """
    Send out alerts for the admission request.
    If alerts must succeed for the admission to be allowed, do it synchronously,
    otherwise run the alert sending in a different thread to return a webhook response sooner.
    """
    if must_alerting_succeed(admit_event):
        send_alerts(admission_request, admit_event)
    else:
        alert_thread = Thread(
            target=send_alerts, args=[admission_request, admit_event, reason]
        )
        alert_thread.run()


def send_alerts(
    admission_request: AdmissionRequest, admit_event: bool, reason: str = None
) -> None:
    al_config = AlertingConfiguration()
    event_category = (
        AlertingConfiguration.ADMIT_CATEGORY_KEY
        if admit_event
        else AlertingConfiguration.REJECT_CATEGORY_KEY
    )
    if al_config.alerting_required(event_category):
        for receiver in al_config.config[event_category][
            AlertingConfiguration.RECEIVER_KEY
        ]:
            message = (
                "CONNAISSEUR admitted a request."
                if admit_event
                else f"CONNAISSEUR rejected a request: {reason}"
            )
            Alert(message, receiver, admission_request).send_alert()


def must_alerting_succeed(admit_event: bool) -> bool:
    # If image is rejected anyways, failing to send alerts won't change the outcome
    if not admit_event:
        return False
    # If image would be admitted, check whether alerting must succeed to actually admit
    al_config = AlertingConfiguration()
    event_category = AlertingConfiguration.ADMIT_CATEGORY_KEY
    if al_config.alerting_required(event_category):
        for receiver in al_config.config[event_category][
            AlertingConfiguration.RECEIVER_KEY
        ]:
            if receiver.get(AlertingConfiguration.FAIL_IF_SEND_FAILS_KEY, False):
                return True
    return False
