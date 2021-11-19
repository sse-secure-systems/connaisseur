from connaisseur.image import Image
from connaisseur.validators.interface import ValidatorInterface


class NotaryV2Validator(ValidatorInterface):
    async def validate(self, image: Image, **kwargs):
        raise NotImplementedError
