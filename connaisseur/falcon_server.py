import os
import logging
import json
import traceback
import asyncio
from connaisseur.admission_request import AdmissionRequest
from connaisseur.alert import send_alerts
from connaisseur.config import Config
from connaisseur.exceptions import (
    BaseConnaisseurException,
    AlertSendingError,
    ConfigurationError,
)
from connaisseur.util import get_admission_review
import falcon


class Health:
    def on_get(self, req, rsp):
        rsp.status = falcon.HTTP_200


class Ready:
    def on_get(self, req, rsp):
        rsp.status = falcon.HTTP_200


class Mutate:
    def __init__(self, config) -> None:
        self.config = config

    def on_post(self, req, rsp):
        content = req.get_media()
        logging.debug(content)

        admission_request = AdmissionRequest(content)
        req.context.ar = admission_request

        response = asyncio.run(self.__admit(admission_request))
        rsp.text = json.dumps(response)
        rsp.content_type = "application/json"
        rsp.status = falcon.HTTP_200
        send_alerts(admission_request, True)

    async def __admit(self, admission_request: AdmissionRequest):
        logging_context = dict(admission_request.context)
        patches = []

        patches = asyncio.gather(
            *[
                self.__validate_image(type_index, image, admission_request)
                for type_index, image in admission_request.wl_object.containers.items()
            ]
        )

        try:
            await patches
        except BaseConnaisseurException as err:
            err.update_context(**logging_context)
            raise err

        return get_admission_review(
            admission_request.uid,
            True,
            patch=[patch for patch in patches.result() if patch],
        )

    async def __validate_image(self, type_index, image, admission_request):
        logging_context = dict(admission_request.context)
        original_image = str(image)
        type_, index = type_index
        logging_context.update(image=original_image)

        # child resources have mutated image names, as their parents got mutated
        # before their creation. this may result in mismatch of rules or duplicate
        # lookups for already approved images. so child resources are automatically
        # approved without further check ups, if their parents were approved
        # earlier.
        child_approval_on = (
            os.environ.get("AUTOMATIC_CHILD_APPROVAL_ENABLED", "1") == "1"
        )

        if child_approval_on & (
            image in admission_request.wl_object.parent_containers.values()
        ):
            msg = f'automatic child approval for "{original_image}".'
            logging.info(self.__create_logging_msg(msg, **logging_context))
            return

        try:
            policy_rule = self.config.get_policy_rule(image)
            validator = self.config.get_validator(policy_rule.validator)

            msg = (
                f'starting verification of image "{original_image}" using rule '
                f'"{str(policy_rule)}" with arguments {str(policy_rule.arguments)}'
                f' and validator "{str(validator)}".'
            )
            logging.debug(
                self.__create_logging_msg(
                    msg, **logging_context, policy_rule=policy_rule, validator=validator
                )
            )

            trusted_digest = await validator.validate(image, **policy_rule.arguments)
        except BaseConnaisseurException as err:
            raise err
        msg = f'successful verification of image "{original_image}"'
        logging.info(self.__create_logging_msg(msg, **logging_context))
        if trusted_digest:
            image.set_digest(trusted_digest)
            return admission_request.wl_object.get_json_patch(image, type_, index)

    def __create_logging_msg(self, msg: str, **kwargs):
        return str({"message": msg, "context": dict(**kwargs)})


def handle_exception(ex, req, rsp, params):
    if isinstance(ex, BaseConnaisseurException):
        err_log = str(ex)
        msg = ex.user_msg  # pylint: disable=no-member
    else:
        err_log = str(traceback.format_exc())
        msg = "unknown error. please check the logs."

    uid = ""
    if req.context.get("ar"):
        send_alerts(req.context.ar, False, msg)
        uid = req.context.ar.uid
    logging.error(err_log)

    dm = os.environ.get("DETECTION_MODE", "0") == "1"
    data = get_admission_review(uid, False, msg=msg, detection_mode=dm)

    rsp.text = json.dumps(data)
    rsp.content_type = "application/json"
    rsp.status = falcon.HTTP_200


APP = falcon.App()
config = Config()

APP.add_route("/health", Health())
APP.add_route("/ready", Ready())
APP.add_route("/mutate", Mutate(config))

APP.add_error_handler(Exception, handle_exception)
