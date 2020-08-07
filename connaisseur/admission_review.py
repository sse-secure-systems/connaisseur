import base64
import json


def get_admission_review(
    uid: str, allowed: bool, patch: list = None, status_id: int = None, msg: str = None
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
    status_id : int (optional)
        The HTTP status code send back with the response.
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
            "patchType": "JSONPatch",
            "patch":
                "W3sib3AiOiAiYWRkIiwgInBhdGgiOiAiL3NwZWMvcmVwbGljYXMiLCAidmFsdWUiOiAzfV0="
          }
        }
    """
    review = {
        "apiVersion": "admission.k8s.io/v1beta1",
        "kind": "AdmissionReview",
        "response": {"uid": uid, "allowed": allowed},
    }

    if status_id or msg:
        if not status_id:
            status_id = 202 if allowed else 403
        status = {"code": status_id}
        if msg:
            status["message"] = msg
        review["response"]["status"] = status

    if patch:
        review["response"]["patchType"] = "JSONPatch"
        review["response"]["patch"] = base64.b64encode(
            bytearray(json.dumps(patch), "utf-8")
        ).decode("utf-8")

    return review
