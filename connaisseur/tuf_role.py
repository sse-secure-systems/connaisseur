import re
from connaisseur.exceptions import InvalidFormatException


class TUFRole:
    """
    Represents a TUF role ('root', 'snapshot', 'timestamp', 'targets') and
    makes sure, only a valid `role` can be used.

    Raises an `InvalidFormatException` should an invalid `role` be given.
    """

    role: str

    def __init__(self, role: str):
        regex = "^(root|(targets(/[^/\\s]+)?)|snapshot|timestamp)$"
        match = re.match(regex, role)

        if not match:
            raise InvalidFormatException('"{}" is not a valid TUF role.'.format(role))

        self.role = role
