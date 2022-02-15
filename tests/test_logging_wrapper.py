import pytest
import time

from . import conftest as fix

import connaisseur.logging_wrapper as lw


@pytest.fixture
def mock_time(monkeypatch):
    monkeypatch.setattr(time, "strftime", lambda X, y: "1/1/1970 00:00:00")


@pytest.mark.parametrize(
    "status_code, environ, out",
    [
        (
            200,
            {
                "REMOTE_ADDR": "127.0.0.1",
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/straight/outta/compton",
                "QUERY_STRING": "who_let_out=dogs",
                "SERVER_PROTOCOL": "HTTP",
            },
            '127.0.0.1 - - [1/1/1970 00:00:00] "POST /straight/outta/compton?who_let_out=dogs HTTP" 200 -',
        ),
        (500, {}, ' - - [1/1/1970 00:00:00] "  " 500 -'),
    ],
)
def test_format_log(mock_time, status_code, environ, out):
    assert lw._format_log(status_code, environ) == out


@pytest.mark.parametrize(
    "app, log_level, exp_level, exception",
    [
        ("TEST", "INFO", 20, fix.no_exc()),
        ("FEST", "DEBUG", 10, fix.no_exc()),
        ("PEST", "CRITICAL", 50, fix.no_exc()),
        ("BEST", "WARNING", 30, fix.no_exc()),
        ("NEST", "NOTSET", 0, fix.no_exc()),
        ("REST", "this_isnt_a_log_level", 20, pytest.raises(ValueError)),
    ],
)
def test_init(app, log_level, exp_level, exception):
    with exception:
        lo = lw.ConnaisseurLoggingWrapper(app, log_level)
        assert lo.logger.level == exp_level
        assert lo.app == app


def test_call():
    def test_app(dict: dict, start_func2):
        return start_func2("200 OK", {}, None)

    def start_func(status, rsp_headers, exc_info=None):
        return "wayne"

    lo = lw.ConnaisseurLoggingWrapper(test_app, "INFO")
    assert lo.__call__({}, start_func) == "wayne"
