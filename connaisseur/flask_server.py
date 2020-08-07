import os
import traceback
import logging
from flask import Flask, request, jsonify
from connaisseur.exceptions import BaseConnaisseurException, UnknownVersionError
from connaisseur.mutate import admit, validate
from connaisseur.notary_api import health_check
from connaisseur.admission_review import get_admission_review

APP = Flask(__name__)
"""
Flask Server that admits the request send to the k8s cluster, validates it and
sends its response back.
"""


@APP.route("/mutate", methods=["POST"])
def mutate():
    """
    Handles the '/mutate' path and accepts CREATE and UPDATE requests.
    Sends its response back, which either denies or allows the request.
    """
    admission_request = request.json
    try:
        validate(admission_request)
        response = admit(admission_request)
    except BaseConnaisseurException as err:
        logging.error(str(err))
        msg = err.message
        return jsonify(
            get_admission_review(admission_request["request"]["uid"], False, msg=msg)
        )
    except UnknownVersionError as err:
        logging.error(str(err))
        return jsonify(
            get_admission_review(
                admission_request["request"]["uid"], False, msg=str(err)
            )
        )
    except Exception:
        logging.error(traceback.format_exc())
        return jsonify(
            get_admission_review(
                admission_request["request"]["uid"],
                False,
                msg="unknown error. please check the logs.",
            )
        )
    return jsonify(response)


@APP.route("/health", methods=["GET", "POST"])
def healthz():
    """
    Handles the '/health' path and checks the health status of the flask and
    the notary server. Sends back either '200' for a healthy status or '500'
    otherwise.
    """
    health = health_check(os.environ.get("NOTARY_SERVER"))
    return ("", 200) if health else ("", 500)
