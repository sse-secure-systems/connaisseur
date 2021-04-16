import pytest
from ... import conftest as fix
import connaisseur.validators.notaryv1.tuf_role as tuf
import connaisseur.exceptions as exc


@pytest.mark.parametrize(
    "role, exception",
    [
        ("root", fix.no_exc()),
        ("targets", fix.no_exc()),
        ("targets/images", fix.no_exc()),
        ("snapshot", fix.no_exc()),
        ("timestamp", fix.no_exc()),
        ("notufrole", pytest.raises(exc.InvalidFormatException)),
    ],
)
def test_tuf_role(role: str, exception):
    with exception:
        t = tuf.TUFRole(role)
        assert t.role == role


@pytest.mark.parametrize("role", ["root", "targets"])
def test_str(role):
    assert str(tuf.TUFRole(role)) == role
