import pytest
import connaisseur.admission_review

admission_review_plain = {
    "apiVersion": "admission.k8s.io/v1beta1",
    "kind": "AdmissionReview",
    "response": {"uid": 1, "allowed": True},
}
admission_review_msg = {
    "apiVersion": "admission.k8s.io/v1beta1",
    "kind": "AdmissionReview",
    "response": {
        "uid": 1,
        "allowed": True,
        "status": {"code": 202, "message": "Well hello there."},
    },
}
admission_review_patch = {
    "apiVersion": "admission.k8s.io/v1beta1",
    "kind": "AdmissionReview",
    "response": {
        "uid": 1,
        "allowed": True,
        "patchType": "JSONPatch",
        "patch": (
            "W3sib3AiOiAiYWRkIiwgInBhdGgiOiAi"
            "L3NwZWMvcmVwbGljYXMiLCAidmFsdWUiOiAzfV0="
        ),
    },
}
admission_review_msg_patch = {
    "apiVersion": "admission.k8s.io/v1beta1",
    "kind": "AdmissionReview",
    "response": {
        "uid": 1,
        "allowed": False,
        "status": {"code": 403, "message": "Well hello there."},
        "patchType": "JSONPatch",
        "patch": (
            "W3sib3AiOiAiYWRkIiwgInBhdGgiOiAi"
            "L3NwZWMvcmVwbGljYXMiLCAidmFsdWUiOiAzfV0="
        ),
    },
}


@pytest.fixture
def adm_rev():
    return connaisseur.admission_review


@pytest.mark.parametrize(
    "uid, allowed, patch, status_id, msg, review",
    [
        (1, True, None, None, None, admission_review_plain),
        (1, True, None, None, "Well hello there.", admission_review_msg),
        (
            1,
            True,
            [{"op": "add", "path": "/spec/replicas", "value": 3}],
            None,
            None,
            admission_review_patch,
        ),
        (
            1,
            False,
            [{"op": "add", "path": "/spec/replicas", "value": 3}],
            None,
            "Well hello there.",
            admission_review_msg_patch,
        ),
    ],
)
def test_get_admission_review(adm_rev, uid, allowed, patch, status_id, msg, review):
    assert (
        adm_rev.get_admission_review(
            uid, allowed, patch=patch, status_id=status_id, msg=msg
        )
        == review
    )
