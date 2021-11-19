import re
from typing import Optional

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

    def __init__(self, image: str):
        separator = r"[-._:@+]|--"
        alphanum = r"[A-Za-z0-9]+"
        component = f"{alphanum}(?:(?:{separator}){alphanum})*"
        ref = f"^{component}(?:/{component})*$"

        # e.g. :v1, :3.7-alpine, @sha256:3e7a89...
        tag_re = r"(?:(?:@sha256:([a-f0-9]{64}))|(?:\:([\w.-]+)))"

        match = re.search(ref, image)
        if not match:
            msg = "{image} is not a valid image reference."
            raise InvalidImageFormatError(message=msg, image=image)

        name_tag = image.split("/")[-1]
        search = re.search(tag_re, name_tag)
        self.digest, self.tag = search.groups() if search else (None, "latest")
        self.name = name_tag.removesuffix(":" + str(self.tag)).removesuffix(
            "@sha256:" + str(self.digest)
        )

        first_comp = image.removesuffix(name_tag).split("/")[0]
        self.registry = (
            first_comp
            if re.search(r"[.:]", first_comp)
            or first_comp == "localhost"
            or any(ele.isupper() for ele in first_comp)
            else "docker.io"
        )
        self.repository = (
            image.removesuffix(name_tag).removeprefix(self.registry)
        ).strip("/") or ("library" if self.registry == "docker.io" else "")

        if (self.repository + self.name).lower() != self.repository + self.name:
            msg = "{image} is not a valid image reference."
            raise InvalidImageFormatError(message=msg, image=image)

    def set_digest(self, digest):
        """
        Set the digest to the given `digest`.
        """
        self.digest = digest
        self.tag = None

    def has_digest(self) -> bool:
        """
        Return `True` if the image has a digest, `False` otherwise.
        """
        return self.digest is not None

    def __str__(self):
        repo_reg = "".join(
            f"{item}/" for item in [self.registry, self.repository] if item
        )
        tag = f":{self.tag}" if not self.digest else f"@sha256:{self.digest}"
        return f"{repo_reg}{self.name}{tag}"

    def __eq__(self, other):
        return str(self) == str(other)
