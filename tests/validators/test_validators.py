import pytest

import connaisseur.exceptions as exc
import connaisseur.validators.validator as val

from .. import conftest as fix


@pytest.mark.parametrize(
    "validator_dict, class_, exception",
    [
        (
            {
                "type": "notaryv1",
                "name": "notary1",
                "host": "me",
                "trustRoots": [{"name": "i'm", "key": "not_empty"}],
            },
            val.NotaryV1Validator,
            fix.no_exc(),
        ),
        (
            {"type": "notaryv2", "name": "notary2", "host": "me"},
            val.NotaryV2Validator,
            fix.no_exc(),
        ),
        (
            {
                "type": "cosign",
                "name": "cosigngn",
                "trustRoots": [{"name": "i'm", "key": "not_empty"}],
            },
            val.CosignValidator,
            fix.no_exc(),
        ),
        (
            {"type": "static", "name": "allow", "approve": True},
            val.StaticValidator,
            fix.no_exc(),
        ),
        ({"type": "ayy"}, None, pytest.raises(exc.NoSuchClassError)),
    ],
)
def test_new(validator_dict, class_, exception):
    with exception:
        assert isinstance(val.Validator(**validator_dict), class_)
