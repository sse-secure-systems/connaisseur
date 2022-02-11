import os


class BaseConnaisseurException(Exception):
    """
    Base exception that can take an error message and context information.
    """

    message: str
    context: dict
    detection_mode: bool
    default_message = "An error occurred."

    def __init__(self, message: str = default_message, **kwargs):
        self.message = message.format(**kwargs)
        self.detection_mode = os.environ.get("DETECTION_MODE", "0") == "1"
        self.context = dict(**kwargs, detection_mode=self.detection_mode)
        super().__init__()

    def __str__(self):
        return str(dict(message=self.message, context=self.context))

    @property
    def user_msg(self):
        msg = self.message
        if self.detection_mode:
            msg += " (not denied due to DETECTION_MODE)"
        return msg

    def update_context(self, **kwargs):
        self.context.update(dict(**kwargs))


class ValidationError(BaseConnaisseurException):
    pass


class InvalidFormatException(ValidationError):
    pass


class InvalidImageFormatError(InvalidFormatException):
    pass


class InvalidKeyFormatError(InvalidFormatException):
    pass


class InvalidPolicyFormatError(InvalidFormatException):
    pass


class InvalidConfigurationFormatError(InvalidFormatException):
    pass


class InvalidTrustDataFormatError(InvalidFormatException):
    pass


class PathTraversalError(InvalidFormatException):
    pass


class NotFoundException(BaseConnaisseurException):
    pass


class NoSuchClassError(NotFoundException):
    pass


class NoMatchingPolicyRuleError(NotFoundException):
    pass


class ParentNotFoundError(NotFoundException):
    pass


class InsufficientTrustDataError(NotFoundException):
    pass


class UnknownTypeException(BaseConnaisseurException):
    pass


class UnknownAPIVersionError(UnknownTypeException):
    pass


class WrongKeyError(UnknownTypeException):
    pass


class AmbiguousDigestError(BaseConnaisseurException):
    pass


class CosignError(BaseConnaisseurException):
    pass


class CosignTimeout(BaseConnaisseurException):
    pass


class UnexpectedCosignData(BaseConnaisseurException):
    pass


class UnreachableError(BaseConnaisseurException):
    pass


class AlertingException(Exception):

    message: str

    def __init__(self, message: str):
        self.message = message
        super().__init__()

    def __str__(self):
        return str(self.message)


class ConfigurationError(AlertingException):
    pass


class AlertSendingError(AlertingException):
    pass
