import pytest
import connaisseur.tuf_role as tuf_role
from connaisseur.exceptions import BaseConnaisseurException


@pytest.fixture
def tuf():
    return tuf_role


@pytest.mark.parametrize(
    "role", [("root"), ("targets"), ("targets/images"), ("snapshot"), ("timestamp")]
)
def test_tuf_role(tuf, role: str):
    t = tuf.TUFRole(role)
    assert t.role == role


def test_tuf_role_error(tuf):
    role = "attacka-bonanza"
    with pytest.raises(BaseConnaisseurException) as err:
        assert tuf.TUFRole(role)
    assert f'"{role}" is not a valid TUF role.' in str(err.value)
