import os
import pytest
import connaisseur.exceptions as exc


@pytest.mark.parametrize(
    "message, kwargs, detection_mode, ex_msg",
    [
        ("Error.", {"reason": "fate"}, 0, "Error."),
        (
            "How the {tables} have {turned}.",
            {"tables": "turns", "turned": "tabled"},
            0,
            "How the turns have tabled.",
        ),
        ("", {}, 0, "An error occurred."),
        ("", {"bad": "guy"}, 0, "An error occurred."),
        ("", {}, 1, "An error occurred."),
    ],
)
def test_exceptions(monkeypatch, message, kwargs, detection_mode, ex_msg):
    monkeypatch.setenv("DETECTION_MODE", str(detection_mode))
    if message and kwargs:
        ex = exc.BaseConnaisseurException(message=message, **kwargs)
    else:
        ex = exc.BaseConnaisseurException(**kwargs)
    assert ex.message == ex_msg
    assert ex.context == dict(**kwargs, detection_mode=ex.detection_mode)
    assert ex.detection_mode is bool(detection_mode)


def test_exception_str():
    ex = exc.BaseConnaisseurException("hello there.", general="kenobi")
    assert str(ex) == str(
        {
            "message": "hello there.",
            "context": {"general": "kenobi", "detection_mode": False},
        }
    )


@pytest.mark.parametrize(
    "msg, dm, out",
    [
        ("hello there.", "0", "hello there."),
        ("hello there.", "1", "hello there. (not denied due to DETECTION_MODE)"),
    ],
)
def test_exception_user_msg(monkeypatch, msg, dm, out):
    monkeypatch.setenv("DETECTION_MODE", dm)
    ex = exc.BaseConnaisseurException(msg, general="kenobi")
    assert ex.user_msg == out


def test_update_context():
    ex = exc.BaseConnaisseurException(general="kenobi")
    ex.update_context(general="grievous", hello="there")
    assert ex.context == {
        "detection_mode": False,
        "general": "grievous",
        "hello": "there",
    }
