import pytest
from ... import conftest as fix
import connaisseur.validators.static.static_validator as st
import connaisseur.exceptions as exc
from connaisseur.image import Image


@pytest.mark.parametrize("name, approve", [("sample", True), ("sample", False)])
def test_init(name, approve):
    val = st.StaticValidator(name, approve)
    assert val.name == name
    assert val.approve == approve


@pytest.mark.parametrize(
    "approve, out, exception",
    [(True, None, fix.no_exc()), (False, None, pytest.raises(exc.ValidationError))],
)
def test_validate(approve, out, exception):
    with exception:
        val = st.StaticValidator("sample", approve)
        assert val.validate(Image("sample")) == out
