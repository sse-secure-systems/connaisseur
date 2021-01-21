import pytest
import connaisseur.image as img
from connaisseur.exceptions import BaseConnaisseurException


@pytest.fixture
def im():
    return img


@pytest.mark.parametrize(
    "image, name, tag, digest, repo, registry",
    [
        (
            "registry.io/path/to/repo/image:tag",
            "image",
            "tag",
            None,
            "path/to/repo",
            "registry.io",
        ),
        (
            "registry.io/path/to/repo/image",
            "image",
            "latest",
            None,
            "path/to/repo",
            "registry.io",
        ),
        (
            (
                "registry.io/path/to/repo/image@sha256:"
                "859b5aada817b3eb53410222e8fc232cf126c9e598390ae61895eb96f52ae46d"
            ),
            "image",
            None,
            "859b5aada817b3eb53410222e8fc232cf126c9e598390ae61895eb96f52ae46d",
            "path/to/repo",
            "registry.io",
        ),
        ("registry.io/image:tag", "image", "tag", None, "", "registry.io"),
        ("path/to/repo/image:tag", "image", "tag", None, "path/to/repo", "docker.io"),
        (
            "reg.com:12345/path/to/repo/image:tag",
            "image",
            "tag",
            None,
            "path/to/repo",
            "reg.com:12345",
        ),
        ("image:tag", "image", "tag", None, "library", "docker.io"),
        (
            "sub.registry.io/path/image:tag",
            "image",
            "tag",
            None,
            "path",
            "sub.registry.io",
        ),
    ],
)
def test_image(
    im, image: str, name: str, tag: str, digest: str, repo: str, registry: str
):
    i = img.Image(image)
    assert i.name == name
    assert i.tag == tag
    assert i.digest == digest
    assert i.repository == repo
    assert i.registry == registry


@pytest.mark.parametrize(
    "image, error",
    [
        ("image/", '"image/" is not a valid image format.'),
        ("registry:", '"registry:" is not a valid image format.'),
        (
            "registry:123456789/repo/image:tag",
            '"registry:123456789/repo/image:tag" is not a valid image format.',
        ),
    ],
)
def test_image_error(im, image: str, error: str):
    with pytest.raises(BaseConnaisseurException) as err:
        img.Image(image)
    assert error in str(err.value)


@pytest.mark.parametrize(
    "image, digest",
    [("image:tag", "859b5aada817b3eb53410222e8fc232cf126c9e598390ae61895eb96f52ae46d")],
)
def test_set_digest(im, image: str, digest: str):
    i = img.Image(image)
    i.set_digest(digest)
    assert i.digest == digest


@pytest.mark.parametrize(
    "image, digest",
    [
        ("image:tag", False),
        (
            (
                "image@sha256:859b5aada817b3eb53410222e8f"
                "c232cf126c9e598390ae61895eb96f52ae46d"
            ),
            True,
        ),
    ],
)
def test_has_digest(im, image: str, digest: bool):
    i = img.Image(image)
    assert i.has_digest() == digest


@pytest.mark.parametrize(
    "image, str_image",
    [
        ("image:tag", "docker.io/library/image:tag"),
        ("registry.io/image:tag", "registry.io/image:tag"),
        ("reg.io/path/image:tag", "reg.io/path/image:tag"),
        ("image", "docker.io/library/image:latest"),
        ("registry.io:42358/path/image:1", "registry.io:42358/path/image:1"),
        ("registry:12", "docker.io/library/registry:12"),
        ("registry.io:8080/image", "registry.io:8080/image:latest"),
        (
            (
                "image@sha256:859b5aada817b3eb53410222"
                "e8fc232cf126c9e598390ae61895eb96f52ae46d"
            ),
            (
                "docker.io/library/image@sha256:859b5aada817b3eb53410"
                "222e8fc232cf126c9e598390ae61895eb96f52ae46d"
            ),
        ),
        ("path/image", "docker.io/path/image:latest"),
    ],
)
def test_str(im, image: str, str_image: str):
    i = img.Image(image)
    assert str(i) == str_image
