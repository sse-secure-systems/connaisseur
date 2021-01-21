import pytest
import connaisseur.util
from connaisseur.exceptions import InvalidFormatException


@pytest.mark.parametrize(
    "delegation_role, out",
    [
        ("phbelitz", "targets/phbelitz"),
        ("chamsen", "targets/chamsen"),
        ("targets/releases", "targets/releases"),
    ],
)
def test_normalize_delegation(delegation_role: str, out: str):
    assert connaisseur.util.normalize_delegation(delegation_role) == out


def test_safe_path_func():
    assert connaisseur.util.safe_path_func(str, "/", "/root") == "/root"


@pytest.mark.parametrize("path", [("/root"), ("/etc/../root")])
def test_safe_path_func_error(path: str):
    with pytest.raises(InvalidFormatException) as err:
        connaisseur.util.safe_path_func(str, "/etc", path)
    assert "potential path traversal." in str(err.value)
