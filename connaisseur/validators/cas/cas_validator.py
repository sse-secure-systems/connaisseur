# import asyncio
from cas_pip.casclient.casclient import CASClient, ArtifactStatus
from connaisseur.exceptions import ValidationError
from connaisseur.image import Image
from connaisseur.validators.interface import ValidatorInterface


class CASValidator(ValidatorInterface):

    def __init__(
        self,
        name: str,
        signerId: str = None,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.signerId = signerId
        self.client = CASClient(signerId=self.signerId)

    async def validate(
        self, image: Image, **kwargs
    ):  # pylint: disable=arguments-differ
        if(image.has_digest()):
            package_name, status = self.client.authenticateHash(image.digest)
            if(status and status == ArtifactStatus.TRUSTED):
                return True
            raise ValidationError(message="Artifact is not trusted.")
        raise ValidationError(message="Deployment has no digest")