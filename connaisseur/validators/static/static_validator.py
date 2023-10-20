from connaisseur.exceptions import ValidationError
from connaisseur.image import Image
from connaisseur.validators.interface import ValidatorInterface
from connaisseur.timing import timing


class StaticValidator(ValidatorInterface):
    name: str
    approve: bool

    def __init__(self, name: str, approve: bool, **kwargs):
        super().__init__(name, **kwargs)
        self.approve = approve

    @timing(capture_args=["image"])
    async def validate(self, image: Image, **kwargs):
        if not self.approve:
            msg = "Static deny."
            raise ValidationError(message=msg)

    @property
    def healthy(self):
        return True
