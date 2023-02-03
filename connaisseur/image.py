import re
from typing import Optional

import connaisseur.constants as const
from connaisseur.exceptions import InvalidImageFormatError


class Image:
    """
    Class to store image information.

    Input:
        'registry.io/path/to/repo/image:tag'

    Output:
        name = 'image'
        repo = 'path/to/repo'
        registry = 'registry.io'
        tag = 'tag'
        digest = None

    Default registry is 'docker.io' and default tag is 'latest'.
    """

    registry: str
    repository: str
    name: str
    tag: Optional[str]
    digest: Optional[str]
    digest_algo: Optional[str]

    def __init__(self, image: str):  # pylint: disable=too-many-locals
        # implements https://github.com/distribution/distribution/blob/main/reference/regexp.go
        digest_hex = r"[0-9a-fA-F]{32,}"
        digest_algorithm_component = r"[A-Za-z][A-Za-z0-9]*"
        digest_algorithm_separator = r"[+._-]"
        digest_algorithm = (
            rf"{digest_algorithm_component}(?:{digest_algorithm_separator}"
            rf"{digest_algorithm_component})*"
        )
        digest = rf"{digest_algorithm}:{digest_hex}"
        tag = r"[\w][\w.-]{0,127}"
        separator = r"[_.]|__|[-]*"
        alpha_numeric = r"[a-z0-9]+"
        path_component = rf"{alpha_numeric}(?:{separator}{alpha_numeric})*"
        port = r"[0-9]+"
        domain_component = r"(?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])"
        domain_name = rf"{domain_component}(?:\.{domain_component})*"
        ipv6 = r"\[(?:[a-fA-F0-9:]+)\]"
        host = rf"(?:{domain_name}|{ipv6})"
        domain = rf"{host}(?::{port})?"
        name = rf"(?:{domain}/)?{path_component}(?:/{path_component})*"
        reference = rf"^(?P<name>{name})(?::(?P<tag>{tag}))?(?:@(?P<digest>{digest}))?$"

        match = re.search(reference, image)
        if (not match) or (len(match.group("name")) > 255):
            msg = "{image} is not a valid image reference."
            raise InvalidImageFormatError(message=msg, image=image)

        name, tag, digest = match.groups()
        components = name.split("/")
        self.name = components[-1]
        self.digest_algo, self.digest = digest.split(":") if digest else (None, None)
        self.tag = tag or ("latest" if not self.digest else None)

        if self.digest_algo and self.digest_algo != const.SHA256:
            raise InvalidImageFormatError(
                message="A digest algorithm of {digest_algo} is not supported. Use sha256 instead.",
                digest_algo=self.digest_algo,
            )

        registry_repo = components[:-1]
        try:
            registry = registry_repo[0]
            self.registry = (
                registry
                if re.search(r"[.:]", registry)
                or registry == "localhost"
                or any(ele.isupper() for ele in registry)
                else "docker.io"
            )
            self.repository = "/".join(registry_repo).removeprefix(
                f"{self.registry}"
            ).removeprefix("/") or ("library" if self.registry == "docker.io" else None)
        except IndexError:
            self.registry = "docker.io"
            self.repository = "library"

    def __str__(self):
        repo_reg = "/".join(item for item in [self.registry, self.repository] if item)
        tag = f":{self.tag}" if self.tag else ""
        digest = f"@{self.digest_algo}:{self.digest}" if self.digest else ""
        return f"{repo_reg}/{self.name}{tag}{digest}"

    def __eq__(self, other):
        return str(self) == str(other)
