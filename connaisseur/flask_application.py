import asyncio
import logging
import traceback

import aiohttp
from flask import Flask, jsonify, request
from prometheus_flask_exporter import NO_PREFIX, PrometheusMetrics

import connaisseur.constants as const
from connaisseur.admission_request import AdmissionRequest
from connaisseur.alert import dispatch_alerts
from connaisseur.config import Config
from connaisseur.exceptions import (
    AlertSendingError,
    BaseConnaisseurException,
    ConfigurationError,
)
from connaisseur.util import feature_flag_on, get_admission_review

APP = Flask(__name__)
"""
Flask application that admits the request send to the k8s cluster, validates it and
sends its response back.
"""
CONFIG = Config()

metrics = PrometheusMetrics(
    APP,
    defaults_prefix=NO_PREFIX,
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0, 15.0, 20, 30.0, float("inf")),
)
"""
Provides metrics for the Flask application
"""


@APP.errorhandler(AlertSendingError)
def handle_alert_sending_failure(err):
    logging.error(err.message)
    return "Alert could not be sent. Check the logs for more details!", 500


@APP.errorhandler(ConfigurationError)
def handle_alert_config_error(err):
    logging.error(err.message)
    return (
        "Alerting configuration is not valid. Check the logs for more details!",
        500,
    )


@APP.route("/mutate", methods=["POST"])
@metrics.counter(
    "mutate_requests_total",
    "Total number of mutate requests",
    labels={
        "allowed": lambda r: metrics_label(r, "allowed"),
        "status_code": lambda r: metrics_label(r, "status_code"),
        "warnings": lambda r: metrics_label(r, "warnings"),
    },
)
def mutate():
    """
    Handle the '/mutate' path and accept CREATE and UPDATE requests.
    Send a response back, which either denies or allows the request.
    """
    result = asyncio.get_event_loop().run_until_complete(__async_mutate())
    return result


def metrics_label(response, label):
    json_response = response.get_json(silent=True)
    if json_response:
        if label == "allowed":
            return json_response["response"]["allowed"]
        elif label == "status_code":
            return json_response["response"]["status"]["code"]
        elif label == "warnings":
            return "warnings" in json_response["response"]
    return json_response


# health probe
@APP.route("/health", methods=["GET", "POST"])
@metrics.do_not_track()
def healthz():
    """
    Handle the '/health' endpoint and check the health status of the web server.
    Send back '200' status code.
    """

    return "", 200


# readiness probe
@APP.route("/ready", methods=["GET", "POST"])
@metrics.do_not_track()
def readyz():
    return "", 200


async def __async_mutate():
    # Maximum timeout for admission control is 30s
    # If Connaisseur issues requests that timeout after the webhook times out
    # k8s will report that Connaisseur was unresponsive, which isn't quite true
    # thus we timeout slightly earlier
    # https://github.com/sse-secure-systems/connaisseur/issues/448
    timeout = aiohttp.ClientTimeout(total=const.AIO_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        admission_request = None
        try:
            logging.debug(request.json)
            admission_request = AdmissionRequest(request.json)
            response = await __admit(admission_request, session)
            # Depending on whether alerting must succeed, run it synchronously or in the background
            dispatch_alerts(admission_request, True)
            return jsonify(response)
        except Exception as err:
            if isinstance(err, BaseConnaisseurException):
                err_log = str(err)
                msg = err.user_msg  # pylint: disable=no-member
            elif isinstance(err, asyncio.TimeoutError):
                err_log = str(traceback.format_exc())
                msg = (
                    "couldn't retrieve the necessary trust data for verification within 30s. most likely"
                    + " there was a network failure. check connectivity to external servers or retry"
                )
            else:
                err_log = str(traceback.format_exc())
                msg = "unknown error. please check the logs."
            dispatch_alerts(admission_request, False, msg)
            logging.error(err_log)
            uid = admission_request.uid if admission_request else ""
            return jsonify(get_admission_review(uid, False, msg=msg))


async def __admit(admission_request: AdmissionRequest, session: aiohttp.ClientSession):
    patches = asyncio.gather(
        *[
            __validate_image(type_and_index, image, admission_request, session)
            for type_and_index, image in admission_request.wl_object.containers.items()
        ]
    )

    try:
        await patches
    except BaseConnaisseurException as err:
        logging_context = dict(admission_request.context)
        err.update_context(**logging_context)
        raise err

    return get_admission_review(
        admission_request.uid,
        True,
        patch=[patch for patch in patches.result() if patch],
    )


async def __validate_image(
    type_index, image, admission_request, session: aiohttp.ClientSession
):
    logging_context = dict(admission_request.context)
    original_image = str(image)
    type_, index = type_index
    logging_context.update(image=original_image)

    # if automatic_unchanged_approval is enabled, admit resource updates
    # if they do not alter the resource's image reference(s)
    # https://github.com/sse-secure-systems/connaisseur/issues/820
    # exception: if a resource increases its replicas from 0 to >0, it is
    # not automatically approved, even if the image reference is unchanged.
    # this is because the resource may have previously been set to 0 and
    # also changed its image reference, which would have been skipped (see
    # below). if the replicas are now increased, the image reference would
    # not be checked, which is not desired.
    if (
        feature_flag_on(const.AUTOMATIC_UNCHANGED_APPROVAL)
        and admission_request.operation.upper() == "UPDATE"
        and not (
            admission_request.wl_object.kind in ["ReplicaSet", "Deployment"]
            and admission_request.wl_object.replicas > 0
            and admission_request.old_wl_object.replicas == 0
        )
        and image in admission_request.old_wl_object.containers.values()
    ):
        logging.info(
            'automatic approval for unchanged image "%s".',
            original_image,
            extra=logging_context,
        )
        return

    # child resources have mutated image names, as their parents got mutated
    # before their creation. this may result in mismatch of rules or duplicate
    # lookups for already approved images. so child resources are automatically
    # approved without further check ups, if their parents were approved
    # earlier.
    if feature_flag_on(const.AUTOMATIC_CHILD_APPROVAL) and (
        image in admission_request.wl_object.parent_containers.values()
    ):
        logging.info(
            'automatic child approval for "%s".', original_image, extra=logging_context
        )
        return

    # if replicas are set to 0, skip verification, since no pods will be created.
    # otherwise we might run into problems with replicasets having an image
    # without signature. then reducing the replicas to 0 will never be allowed
    # by Connaisseur.
    if (
        admission_request.operation.upper() == "UPDATE"
        and admission_request.kind in ["ReplicaSet", "Deployment"]
        and admission_request.wl_object.replicas == 0
    ):
        logging.info(
            'replicas set to 0. skipping verification of "%s".',
            original_image,
            extra=logging_context,
        )
        return

    try:
        policy_rule = CONFIG.get_policy_rule(image)
        validator = CONFIG.get_validator(policy_rule.validator)
        logging.debug(
            'starting verification of image "%s" using rule "%s" with arguments %s and validator "%s".',
            original_image,
            str(policy_rule),
            str(policy_rule.arguments),
            str(validator),
            extra={
                "policy_rule": policy_rule,
                "validator": validator,
                **logging_context,
            },
        )

        validator_arguments = policy_rule.arguments.copy()
        validator_arguments.update({"session": session})
        trusted_digest = await validator.validate(image, **validator_arguments)
    except BaseConnaisseurException as err:
        # add contextual information to all errors
        err.update_context(**logging_context)
        raise err
    logging.info(
        'successful verification of image "%s"', original_image, extra=logging_context
    )
    if trusted_digest:
        image.digest, image.digest_algo = trusted_digest, const.SHA256
        return admission_request.wl_object.get_json_patch(image, type_, index)
