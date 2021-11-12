from connaisseur.validators.interface import ValidatorInterface
from connaisseur.image import Image


class NotaryV2Validator(ValidatorInterface):
    async def validate(self, image: Image, **kwargs):
        raise NotImplementedError