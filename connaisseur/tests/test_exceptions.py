import os
import pytest
import connaisseur.exceptions


@pytest.fixture
def excep():
    return connaisseur.exceptions


def test_exceptions(excep):
    ex = excep.BaseConnaisseurException("Hallo", {"du": "da"})
    assert ex.message == "Hallo"
    assert ex.context == {"du": "da"}
    assert ex.detection_mode == False


def test_exception_str(excep):
    ex = excep.BaseConnaisseurException("Hallo", {"du": "da"})
    assert str(ex) == str(
        {"message": "Hallo", "context": {"du": "da"}, "detection_mode": False}
    )


@pytest.mark.parametrize(
    "msg, dm, out",
    [
        ("Hallo", "0", "Hallo"),
        ("Hallo", "1", "Hallo (not denied due to DETECTION_MODE)"),
    ],
)
def test_exception_user_msg(excep, msg, dm, out):
    os.environ["DETECTION_MODE"] = dm
    ex = excep.BaseConnaisseurException(msg, {"du": "da"})
    assert ex.user_msg == out
