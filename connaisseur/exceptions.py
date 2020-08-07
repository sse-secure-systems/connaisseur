# pylint: disable=dangerous-default-value
class BaseConnaisseurException(Exception):
    """
    Base exception that can take an error message and context information as a
    dict.
    """

    message: str
    context: dict

    def __init__(self, message: str, context: dict = {}):
        self.message = message
        self.context = context
        super().__init__()

    def __str__(self):
        return str({"message": self.message, "context": self.context})


class InvalidFormatException(BaseConnaisseurException):
    pass


class ValidationError(BaseConnaisseurException):
    pass


class NotFoundException(BaseConnaisseurException):
    pass


class NoSuchClassError(Exception):
    pass


class UnsupportedTypeException(BaseConnaisseurException):
    pass


class UnknownVersionError(Exception):
    pass


class AmbiguousDigestError(BaseConnaisseurException):
    pass
