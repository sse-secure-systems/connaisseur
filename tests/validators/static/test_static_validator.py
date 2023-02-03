import pytest

import connaisseur.exceptions as exc
import connaisseur.validators.static.static_validator as st
from connaisseur.image import Image

from ... import conftest as fix


@pytest.mark.parametrize("name, approve", [("sample", True), ("sample", False)])
def test_init(name, approve):
    val = st.StaticValidator(name, approve)
    assert val.name == name
    assert val.approve == approve


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "approve, out, exception",
    [(True, None, fix.no_exc()), (False, None, pytest.raises(exc.ValidationError))],
)
async def test_validate(approve, out, exception):
    with exception:
        val = st.StaticValidator("sample", approve)
        assert await val.validate(Image("sample")) == out
