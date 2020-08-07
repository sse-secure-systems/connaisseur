import pytest
import connaisseur.util


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
