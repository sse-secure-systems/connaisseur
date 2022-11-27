import json
import logging
import os
from datetime import datetime
from typing import Optional

import requests
from jinja2 import StrictUndefined, Template

from connaisseur.util import safe_json_open, validate_schema
from connaisseur.exceptions import (
    AlertSendingError,
    ConfigurationError,
    InvalidConfigurationFormatError,
    InvalidImageFormatError,
)
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


class AlertReceiverAuthentication:
    """
    Class to store authentication information for securely sending events to the alert receiver.
    """

    authentication_config: dict = None
    authentication_scheme: str = None

    class AlertReceiverAuthenticationInterface:
        def __init__(self, alert_receiver_config: dict, authentication_config_key: str):
            if authentication_config_key is not None:
                try:
                    self.authentication_config = alert_receiver_config[
                        authentication_config_key
                    ]
                except KeyError as err:
                    raise ConfigurationError(
                        "No authentication configuration found for dictionary key:"
                        f"{authentication_config_key}."
                    ) from err

                self.authentication_scheme = self.authentication_config.get(
                    "authentication_scheme", self.authentication_scheme
                )
                self._validate_authentication_scheme()

        def _validate_authentication_scheme(self) -> None:
            if not self.authentication_scheme:
                raise ConfigurationError(
                    "The authentication scheme cannot be null or empty."
                )

            if not self.authentication_scheme.isalpha():
                raise ConfigurationError(
                    "The authentication scheme must contain only letters."
                )

        def get_header(self) -> dict:
            return {}

    class AlertReceiverNoneAuthentication(AlertReceiverAuthenticationInterface):
        """
        Placeholder class for AlertReceiver without authentication.
        """

        def __init__(self, alert_receiver_config: dict):
            super().__init__(alert_receiver_config, None)

    class AlertReceiverBasicAuthentication(AlertReceiverAuthenticationInterface):
        """
        Class to store authentication information for basic authentication type
        with username and password.
        """

        username: str
        password: str
        authentication_scheme: str = "Basic"

        def __init__(self, alert_receiver_config: dict):
            super().__init__(alert_receiver_config, "receiver_authentication_basic")

            try:
                username_env = self.authentication_config["username_env"]
                password_env = self.authentication_config["password_env"]
            except KeyError as err:
                raise ConfigurationError(
                    "No username_env or password_env configuration found."
                ) from err

            try:
                self.username = os.environ[username_env]
                self.password = os.environ[password_env]
            except KeyError as err:
                raise ConfigurationError(
                    "No username or password found from environmental variables "
                    f"{username_env} and {password_env}."
                ) from err

        def get_header(self) -> dict:
            return {
                "Authorization": f"{self.authentication_scheme} {self.username}:{self.password}"
            }

    class AlertReceiverBearerAuthentication(AlertReceiverAuthenticationInterface):
        """
        Class to store authentication information for bearer authentication type which uses a token.
        """

        token: str
        authentication_scheme: str = "Bearer"  # default is bearer

        def __init__(self, alert_receiver_config: dict):
            super().__init__(alert_receiver_config, "receiver_authentication_bearer")

            token_env = self.authentication_config.get("token_env")
            token_file = self.authentication_config.get("token_file")

            if (
                token_env is None and token_file is None
            ):  # This should not happen since it is included in the json validation
                raise ConfigurationError(
                    "No token_env and token_file configuration found."
                )

            if (
                token_env is not None and token_file is not None
            ):  # This should not happen since it is included in the json validation
                raise ConfigurationError(
                    "Both token_env and token_file configuration found. Only one can be given."
                )

            if token_env is not None:
                try:
                    self.token = os.environ[token_env]
                except KeyError as err:
                    raise ConfigurationError(
                        f"No token found from environmental variable {token_env}."
                    ) from err
            else:
                try:
                    with open(token_file, "r", encoding="utf-8") as token_file_handler:
                        self.token = token_file_handler.read()
                except FileNotFoundError as err:
                    raise ConfigurationError(
                        f"No token file found at {token_file}."
                    ) from err
                except Exception as err:
                    raise ConfigurationError(
                        f"An error occurred while loading the token file {token_file}: {str(err)}"
                    ) from err

        def get_header(self) -> dict:
            return {"Authorization": f"{self.authentication_scheme} {self.token}"}

    init_map = {
        "basic": AlertReceiverBasicAuthentication,
        "bearer": AlertReceiverBearerAuthentication,
        "none": AlertReceiverNoneAuthentication,
    }

    _authentication_instance = None

    def __init__(self, alert_receiver_config: dict):
        self.authentication_type = alert_receiver_config.get(
            "receiver_authentication_type", "none"
        )
        self.__init_authentication_instance(alert_receiver_config)

    def __init_authentication_instance(self, alert_receiver_config: dict):
        try:
            self._authentication_instance = self.init_map[self.authentication_type](
                alert_receiver_config
            )
        except KeyError as err:
            raise ConfigurationError(
                "No authentication type found. Valid values are "
                f"{list(AlertReceiverAuthentication.init_map.keys())}"
            ) from err  # hopefully this never happens

    def get_auth_header(self) -> dict:
        return self._authentication_instance.get_header()


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
    receiver_authentication: AlertReceiverAuthentication
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
            "priority": str(receiver_config.get("priority", 3)),
            "connaisseur_pod_id": os.getenv("POD_NAME"),
            "cluster": os.getenv("CLUSTER_NAME"),
            "namespace": namespace,
            "timestamp": datetime.now(),
            "request_id": request_id or "No given UID",
            "images": images,
        }
        self.receiver_url = receiver_config["receiver_url"]
        self.receiver_authentication = AlertReceiverAuthentication(receiver_config)
        self.template = receiver_config["template"]
        self.throw_if_alert_sending_fails = receiver_config.get(
            "fail_if_alert_sending_fails", False
        )
        self.payload = self.__construct_payload(receiver_config)
        self.headers = self.__get_headers(receiver_config, self.receiver_authentication)

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
    def __get_headers(
        receiver_config: dict, receiver_authentication: AlertReceiverAuthentication
    ) -> dict:
        headers = {"Content-Type": "application/json"}
        additional_headers = receiver_config.get("custom_headers")
        if additional_headers is not None:
            for header in additional_headers:
                key, value = header.split(":", 1)
                headers.update({key.strip(): value.strip()})
        auth_header = receiver_authentication.get_auth_header()
        if auth_header:  # not None and not empty
            headers.update(auth_header)
        return headers


def send_alerts(
    admission_request: AdmissionRequest, admit_event: bool, reason: str = None
) -> None:
    al_config = AlertingConfiguration()
    event_category = "admit_request" if admit_event else "reject_request"
    if al_config.alerting_required(event_category):
        for receiver in al_config.config[event_category]["templates"]:
            message = (
                "CONNAISSEUR admitted a request."
                if admit_event
                else f"CONNAISSEUR rejected a request: {reason}"
            )
            Alert(message, receiver, admission_request).send_alert()
