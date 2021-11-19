import re

from connaisseur.exceptions import InvalidFormatException


class TUFRole:
    """
    Represent a TUF role ('root', 'snapshot', 'timestamp', 'targets') and
    make sure only a valid `role` can be used.

    Raise an `InvalidFormatException` should an invalid `role` be given.
    """

    role: str

    def __init__(self, role: str):
        regex = "^(root|(targets(/[^/\\s]+)?)|snapshot|timestamp)$"
        match = re.match(regex, role)

        if not match:
            msg = "{role} is not a valid TUF role."
            raise InvalidFormatException(message=msg, role=str(role))

        self.role = role

    def __str__(self):
        return self.role
