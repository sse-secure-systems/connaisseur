import os
import pytest
import connaisseur.exceptions


@pytest.fixture
def excep():
    return connaisseur.exceptions


def test_exceptions(excep):
    ex = excep.BaseConnaisseurException("Hello", {"you": "there"})
    assert ex.message == "Hello"
    assert ex.context == {"you": "there"}
    assert ex.detection_mode == False


def test_exception_str(excep):
    ex = excep.BaseConnaisseurException("Hello", {"you": "there"})
    assert str(ex) == str(
        {"message": "Hello", "context": {"you": "there"}, "detection_mode": False}
    )


@pytest.mark.parametrize(
    "msg, dm, out",
    [
        ("Hello", "0", "Hello"),
        ("Hello", "1", "Hello (not denied due to DETECTION_MODE)"),
    ],
)
def test_exception_user_msg(monkeypatch, excep, msg, dm, out):
    monkeypatch.setenv("DETECTION_MODE", dm)
    ex = excep.BaseConnaisseurException(msg, {"you": "there"})
    assert ex.user_msg == out
