from connaisseur.exceptions import NoSuchClassError
from connaisseur.validators.cosign.cosign_validator import CosignValidator
from connaisseur.validators.notaryv1.notaryv1_validator import NotaryV1Validator
from connaisseur.validators.notaryv2.notaryv2_validator import NotaryV2Validator
from connaisseur.validators.static.static_validator import StaticValidator


class Validator:
    class_map = {
        "notaryv1": NotaryV1Validator,
        "notaryv2": NotaryV2Validator,
        "cosign": CosignValidator,
        "static": StaticValidator,
    }

    def __new__(cls, **kwargs):
        validator_type = kwargs.pop("type")
        try:
            return cls.class_map[validator_type](**kwargs)
        except KeyError:
            msg = f"{validator_type} is not a supported validator."
            raise NoSuchClassError(message=msg)  # pylint: disable=raise-missing-from
