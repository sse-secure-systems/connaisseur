import pytest
import conftest as fix
import connaisseur.util as ut
import connaisseur.exceptions as exc


@pytest.mark.parametrize(
    "delegation_role, out",
    [
        ("phbelitz", "targets/phbelitz"),
        ("chamsen", "targets/chamsen"),
        ("targets/releases", "targets/releases"),
    ],
)
def test_normalize_delegation(delegation_role: str, out: str):
    assert ut.normalize_delegation(delegation_role) == out


@pytest.mark.parametrize(
    "path, exception",
    [
        ("/etc/passwd", fix.no_exc()),
        ("/etc/../etc/passwd", fix.no_exc()),
        ("/root", pytest.raises(exc.PathTraversalError)),
        ("/etc/../root", pytest.raises(exc.PathTraversalError)),
    ],
)
def test_safe_path_func(path, exception):
    with exception:
        assert ut.safe_path_func(str, "/etc", path) == path


admission_review_plain = {
    "apiVersion": "admission.k8s.io/v1beta1",
    "kind": "AdmissionReview",
    "response": {
        "uid": 1,
        "allowed": True,
        "status": {"code": 202},
    },
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
admission_review_msg_dm = {
    "apiVersion": "admission.k8s.io/v1beta1",
    "kind": "AdmissionReview",
    "response": {
        "uid": 1,
        "allowed": True,
        "status": {"code": 202, "message": "Well hello there."},
        "warnings": ["Well hello there."],
    },
}
admission_review_patch = {
    "apiVersion": "admission.k8s.io/v1beta1",
    "kind": "AdmissionReview",
    "response": {
        "uid": 1,
        "allowed": True,
        "status": {"code": 202},
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


@pytest.mark.parametrize(
    "uid, allowed, patch, msg, dm, review",
    [
        (1, True, None, None, False, admission_review_plain),
        (1, True, None, "Well hello there.", False, admission_review_msg),
        (
            1,
            True,
            [{"op": "add", "path": "/spec/replicas", "value": 3}],
            None,
            False,
            admission_review_patch,
        ),
        (
            1,
            False,
            [{"op": "add", "path": "/spec/replicas", "value": 3}],
            "Well hello there.",
            False,
            admission_review_msg_patch,
        ),
        (1, False, None, "Well hello there.", True, admission_review_msg_dm),
        (1, True, None, "Well hello there.", True, admission_review_msg),
    ],
)
def test_get_admission_review(uid, allowed, patch, msg, dm, review):
    assert (
        ut.get_admission_review(
            uid,
            allowed,
            patch=patch,
            msg=msg,
            detection_mode=dm,
        )
        == review
    )
