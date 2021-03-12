import os
import base64
import json
from connaisseur.exceptions import PathTraversalError


def normalize_delegation(delegation_role: str):
    prefix = "targets/"
    if not delegation_role.startswith(prefix):
        delegation_role = prefix + delegation_role
    return delegation_role


def safe_path_func(callback: callable, base_dir: str, path: str, *args, **kwargs):
    if os.path.commonprefix((os.path.realpath(path), base_dir)) != base_dir:
        msg = "Potential path traversal in {path}."
        raise PathTraversalError(message=msg, path=path)
    return callback(path, *args, **kwargs)


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
        The uid of the request, that was send to the Admission Controller.
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
