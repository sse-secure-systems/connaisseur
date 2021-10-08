import pytest
from . import conftest as fix
import connaisseur.util as ut
import connaisseur.exceptions as exc


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
    "apiVersion": "admission.k8s.io/v1",
    "kind": "AdmissionReview",
    "response": {
        "uid": 1,
        "allowed": True,
        "status": {"code": 202},
    },
}
admission_review_msg = {
    "apiVersion": "admission.k8s.io/v1",
    "kind": "AdmissionReview",
    "response": {
        "uid": 1,
        "allowed": True,
        "status": {"code": 202, "message": "Well hello there."},
    },
}
admission_review_msg_dm = {
    "apiVersion": "admission.k8s.io/v1",
    "kind": "AdmissionReview",
    "response": {
        "uid": 1,
        "allowed": True,
        "status": {"code": 202, "message": "Well hello there."},
        "warnings": ["Well hello there."],
    },
}
admission_review_patch = {
    "apiVersion": "admission.k8s.io/v1",
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
    "apiVersion": "admission.k8s.io/v1",
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
def test_get_admission_review(monkeypatch, uid, allowed, patch, msg, dm, review):
    monkeypatch.setenv("KUBE_VERSION", "v1.20.0")
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


@pytest.mark.parametrize(
    "data, schema_path, kind, exception_kind, exception",
    [
        (
            fix.get_admreq("deployments"),
            "connaisseur/res/ad_request_schema.json",
            None,
            None,
            fix.no_exc(),
        ),
        (
            fix.get_admreq("err"),
            "connaisseur/res/ad_request_schema.json",
            "AdmissionRequest",
            exc.InvalidFormatException,
            pytest.raises(exc.InvalidFormatException, match=r".*AdmissionRequest.*"),
        ),
    ],
)
def test_validate_schema(
    data: dict, schema_path: str, kind: str, exception_kind, exception
):
    with exception:
        assert ut.validate_schema(data, schema_path, kind, exception_kind) is None


@pytest.mark.parametrize(
    "major, minor, patch, set_version",
    [
        ("1", "20", "0", "v1.20.0"),
        ("0", "0", "0", "wrong_input"),
        ("0", "0", "0", ""),
        ("1", "20", "11-34+7402e007632498", "v1.20.11-34+7402e007632498"),
    ],
)
def test_get_kube_version(monkeypatch, major, minor, patch, set_version):
    monkeypatch.setenv("KUBE_VERSION", set_version)
    assert ut.get_kube_version() == (major, minor, patch)
