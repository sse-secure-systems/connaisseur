import pytest

import connaisseur.logging as lw

from . import conftest as fix


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


@pytest.mark.parametrize(
    "log_level",
    [
        ("INFO"),
        ("DEBUG"),
        ("CRITICAL"),
        ("WARNING"),
        ("NOTSET"),
    ],
)
def test_is_debug_level(log_level):
    lw.ConnaisseurLoggingWrapper("SOME_NAME", log_level)
    assert lw.ConnaisseurLoggingWrapper.is_debug_level() == (log_level == "DEBUG")


# don't know how to properly test the logging :(
# pytest supports a fixture (caplog), but this only captures
# the input for the log call, but not the resulting string/JSON
# object. the result is actually printed to stderr, according to
# pytest, but when reading stderr, it's empty. skipping the test
# for now.
# def test_json_log():
#     pass
