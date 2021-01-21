# pylint: disable=dangerous-default-value
import os


class BaseConnaisseurException(Exception):
    """
    Base exception that can take an error message and context information as a
    dict.
    """

    message: str
    context: dict
    detection_mode: bool

    def __init__(self, message: str, context: dict = {}):
        self.message = message
        self.context = context
        self.detection_mode = os.environ.get("DETECTION_MODE", "0") == "1"
        super().__init__()

    def __str__(self):
        return str(self.__dict__)

    @property
    def user_msg(self):
        msg = self.message
        if self.detection_mode:
            msg += " (not denied due to DETECTION_MODE)"
        return msg


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


class UnreachableError(BaseConnaisseurException):
    pass
