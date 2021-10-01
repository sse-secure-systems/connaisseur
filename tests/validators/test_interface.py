import pytest
import connaisseur.validators.interface as vi


def test_init():
    assert vi.ValidatorInterface("")


@pytest.mark.asyncio
async def test_validate():
    with pytest.raises(NotImplementedError):
        assert await vi.ValidatorInterface("").validate(None)


def test_healthy():
    with pytest.raises(NotImplementedError):
        assert vi.ValidatorInterface("").healthy is True


def test_str():
    assert str(vi.ValidatorInterface("test")) == "test"
