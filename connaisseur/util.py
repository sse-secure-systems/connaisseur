import os
import base64
import json
import yaml
from jsonschema import validate, ValidationError, FormatChecker
from connaisseur.exceptions import PathTraversalError


def safe_path_func(callback: callable, base_dir: str, path: str, *args, **kwargs):
    if os.path.commonprefix((os.path.realpath(path), base_dir)) != base_dir:
        msg = "Potential path traversal in {path}."
        raise PathTraversalError(message=msg, path=path)
    return callback(path, *args, **kwargs)


def safe_json_open(base_dir: str, path: str):
    with safe_path_func(open, base_dir, path, "r") as file:
        return json.load(file)


def safe_yaml_open(base_dir: str, path: str):
    with safe_path_func(open, base_dir, path, "r") as file:
        return yaml.safe_load(file)


def get_admission_review(
    uid: str,
    allowed: bool,
    patch: list = None,
    msg: str = None,
    detection_mode: bool = False,
):
    """
    Get a standardized response object with patching instructions for the
    request and error message.

    Parameters
    ----------
    uid : str
        The uid of the request that was sent to the Admission Controller.
    allowed : bool
        The decision, whether the request will be accepted or denied.
    patch : list (optional)
        A list with JSON patch instruction, that will modify the original
        request, send to the Admission Controller. The list is Base64
        encoded.
    msg : str (optional)
        The error message, which will be displayed, should allowed be
        'False'.

    Return
    ----------
    AdmissionReview : dict
        Response is an AdmissionReview with following structure:

        {
          "apiVersion": "admission.k8s.io/v1beta1",
          "kind": "AdmissionReview",
          "response": {
            "uid": uid,
            "allowed": allowed,
            "status": {
                "code": 200,
                "message": "All gucci, my boi."
            },
            "warnings": ["detection_mode ON"]
            "patchType": "JSONPatch",
            "patch":
                "W3sib3AiOiAiYWRkIiwgInBhdGgiOiAiL3NwZWMvcmVwbGljYXMiLCAidmFsdWUiOiAzfV0="
          }
        }
    """
    review = {
        "apiVersion": "admission.k8s.io/v1beta1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": allowed or detection_mode,
            "status": {"code": 202 if allowed or detection_mode else 403},
        },
    }

    if msg:
        review["response"]["status"]["message"] = msg
        if detection_mode and not allowed:
            review["response"]["warnings"] = [msg]

    if patch:
        review["response"]["patchType"] = "JSONPatch"
        review["response"]["patch"] = base64.b64encode(
            bytearray(json.dumps(patch), "utf-8")
        ).decode("utf-8")

    return review


def validate_schema(data: dict, schema_path: str, kind: str, exception):
    with open(schema_path, "r") as schema_file:
        schema = json.load(schema_file)

    try:
        validate(instance=data, schema=schema, format_checker=FormatChecker())
    except ValidationError as err:
        msg = "{validation_kind} has an invalid format: {validation_err}."
        raise exception(
            message=msg,
            validation_kind=kind,
            validation_err=str(err),
        ) from err
