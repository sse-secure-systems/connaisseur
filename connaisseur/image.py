import re
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
    tag: str
    digest: str

    def __init__(self, image: str):
        # e.g. example.com, super.example.com:3498
        domain_with_dot_re = (
            r"(?:[a-z0-9-]{1,63}\.){1,62}[a-z0-9-]{1,63}(?::[0-9]{1,5})?"
        )
        # e.g. private-registry:30000, localhost:5000
        domain_without_dot_re = r"[a-z0-9-]{1,64}(?::[0-9]{1,5})"
        # e.g. library/, library/alpine/,
        repo_re = r"(?:[\w-]+\/)+"
        # e.g. alpine, nginx, hello-world
        image_re = r"[\w.-]+"
        # e.g. :v1, :3.7-alpine, @sha256:3e7a89...
        tag_re = r"(?:(?:@sha256:([a-f0-9]{64}))|(?:\:([\w.-]+)))"

        # e.g. docker.io/library/python:3.7-alpine
        regex = (
            f"^((?:{domain_with_dot_re}|{domain_without_dot_re})/)?"
            f"({repo_re})?({image_re})({tag_re})?$"
        )

        match = re.search(regex, image)
        if not match:
            msg = "{image} is not a valid image reference."
            raise InvalidImageFormatError(message=msg, image=image)

        self.registry, self.repository, self.name, self.digest, self.tag = (
            match.group(1),
            match.group(2),
            match.group(3),
            match.group(5),
            match.group(6),
        )
        # strip trailing "/" or set to default "docker.io" registry
        self.registry = (self.registry or "docker.io").rstrip("/")
        # strip trailing "/"
        self.repository = (
            self.repository or ("library/" if self.registry == "docker.io" else "/")
        ).rstrip("/")

        if not (self.tag or self.digest):
            self.tag = "latest"

    def set_digest(self, digest):
        """
        Sets the digest to the given `digest`.
        """
        self.digest = digest
        self.tag = None

    def has_digest(self):
        """
        Returns `true` if the image has a digest, `false` otherwise.
        """
        return self.digest is not None

    def __str__(self):
        repo_reg = "".join(
            f"{item}/" for item in [self.registry, self.repository] if item
        )
        tag = f":{self.tag}" if not self.digest else f"@sha256:{self.digest}"
        return f"{repo_reg}{self.name}{tag}"
