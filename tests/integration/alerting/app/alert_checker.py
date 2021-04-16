from flask import Flask, request
import json

APP = Flask(__name__)

endpoint_hits = {}
opsgenie_endpoint_hits = 0
slack_endpoint_hits = 0
keybase_endpoint_hits = 0


@APP.route("/")
def show_endpoint_hits():
    return endpoint_hits


@APP.route("/opsgenie", methods=["POST"])
def opsgenie_payload_verification():
    with open("/app/opsgenie_payload.json", "r") as readfile:
        opsgenie_test_payload = json.load(readfile)
    if request.is_json is False:
        return ("", 500)
    payload = request.json
    if (
        payload.keys() != opsgenie_test_payload.keys()
        or payload.get("details").keys() != opsgenie_test_payload.get("details").keys()
    ):
        APP.logger.error("Received payload differs from expected payload.")
        return ("", 500)
    global opsgenie_endpoint_hits
    opsgenie_endpoint_hits += 1
    endpoint_hits.update(
        {"successful_requests_to_opsgenie_endpoint": opsgenie_endpoint_hits}
    )
    return ("", 200)


@APP.route("/slack", methods=["POST"])
def slack_payload_verification():
    with open("/app/slack_payload.json", "r") as readfile:
        slack_test_payload = json.load(readfile)
    payload = request.json
    if (
        payload.keys() != slack_test_payload.keys()
        or payload["blocks"][1].keys() != slack_test_payload["blocks"][1].keys()
    ):
        APP.logger.error("Received payload differs from expected payload.")
        return ("", 500)
    global slack_endpoint_hits
    slack_endpoint_hits += 1
    endpoint_hits.update({"successful_requests_to_slack_endpoint": slack_endpoint_hits})
    return ("", 200)


@APP.route("/keybase", methods=["POST"])
def keybase_payload_verification():
    with open("/app/keybase_payload.json", "r") as readfile:
        keybase_test_payload = json.load(readfile)
    payload = request.json
    if payload.keys() != keybase_test_payload.keys():
        APP.logger.error("Received payload differs from expected payload.")
        return ("", 500)
    global keybase_endpoint_hits
    keybase_endpoint_hits += 1
    endpoint_hits.update(
        {"successful_requests_to_keybase_endpoint": keybase_endpoint_hits}
    )
    return ("", 200)


if __name__ == "__main__":
    APP.run(host="0.0.0.0", port=56243)
