from connaisseur.image import Image


class ValidatorInterface:
    def __init__(self, name: str, **kwargs):  # pylint: disable=unused-argument
        self.name = name

    async def validate(self, image: Image, **kwargs) -> str:
        """
        Validate an admission request, using the extra arguments from the image policy.

        Return a list of trusted digests.
        """
        raise NotImplementedError

    @property
    def healthy(self):
        raise NotImplementedError

    def __str__(self):
        return self.name
