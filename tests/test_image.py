import pytest

import connaisseur.exceptions as exc
import connaisseur.image as img

from . import conftest as fix


@pytest.mark.parametrize(
    "image, name, tag, digest, repo, registry, exception",
    [
        (
            "registry.io/path/to/repo/image:tag",
            "image",
            "tag",
            None,
            "path/to/repo",
            "registry.io",
            fix.no_exc(),
        ),
        (
            "registry.io/path/to/repo/image",
            "image",
            "latest",
            None,
            "path/to/repo",
            "registry.io",
            fix.no_exc(),
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
            fix.no_exc(),
        ),
        (
            "registry.io/image:tag",
            "image",
            "tag",
            None,
            None,
            "registry.io",
            fix.no_exc(),
        ),
        (
            "path/to/repo/image:tag",
            "image",
            "tag",
            None,
            "path/to/repo",
            "docker.io",
            fix.no_exc(),
        ),
        (
            "reg.com:12345/path/to/repo/image:tag",
            "image",
            "tag",
            None,
            "path/to/repo",
            "reg.com:12345",
            fix.no_exc(),
        ),
        ("image:tag", "image", "tag", None, "library", "docker.io", fix.no_exc()),
        (
            "sub.registry.io/path/image:tag",
            "image",
            "tag",
            None,
            "path",
            "sub.registry.io",
            fix.no_exc(),
        ),
        ("image/", "", "", None, "", "", pytest.raises(exc.InvalidImageFormatError)),
        ("registry:", "", "", None, "", "", pytest.raises(exc.InvalidImageFormatError)),
        (
            "registry:1234/repo/image:tag",
            "image",
            "tag",
            None,
            "repo",
            "registry:1234",
            fix.no_exc(),
        ),
        (
            "master-node:5000/k8s.gcr.io/library/kube-apiserver:v1.18.6",
            "kube-apiserver",
            "v1.18.6",
            None,
            "k8s.gcr.io/library",
            "master-node:5000",
            fix.no_exc(),
        ),
        ("Test/test:v1", "test", "v1", None, None, "Test", fix.no_exc()),
        (
            "docker.io/library/image:Tag",
            "image",
            "Tag",
            None,
            "library",
            "docker.io",
            fix.no_exc(),
        ),
        (
            "ghcr.io/repo/test/image-with-tag-and-digest:v1.2.3@sha256:f8816ada742348e1adfcec5c2a180b675bf6e4a294e0feb68bd70179451e1242",
            "image-with-tag-and-digest",
            "v1.2.3",
            "f8816ada742348e1adfcec5c2a180b675bf6e4a294e0feb68bd70179451e1242",
            "repo/test",
            "ghcr.io",
            fix.no_exc(),
        ),
        (
            "image@sha:859b5aada817b3eb53410222e8fc232cf126c9e598390ae61895eb96f52ae46d",
            None,
            None,
            None,
            None,
            None,
            pytest.raises(exc.InvalidImageFormatError, match=r".*is not supported.*"),
        ),
        (
            (
                "what/a/long/path/to/an/image/that/is/quite/unnecessarily/long/if/you/ask/me/this/shouldnt"
                "/be/as/long/as/this/is/but/in/order/to/test/this/i/see/no/other/way/that/using/such/a"
                "ridiculous/long/name/that/may/or/may/not/make/it/into/the/book/from/this/guiness/person/"
                "the/one/with/the/beer/you/know/image:tag"
            ),
            None,
            None,
            None,
            None,
            None,
            pytest.raises(exc.InvalidImageFormatError, match=r".*not a valid.*"),
        ),
    ],
)
def test_image(
    image: str, name: str, tag: str, digest: str, repo: str, registry: str, exception
):
    with exception:
        i = img.Image(image)
        assert i.name == name
        assert i.tag == tag
        assert i.digest == digest
        assert i.repository == repo
        assert i.registry == registry


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
        (
            (
                "ghcr.io/repo/test/image-with-tag-and-digest:v1.2.3"
                "@sha256:859b5aada817b3eb53410222e8fc232cf126c9e598390ae61895eb96f52ae46d"
            ),
            (
                "ghcr.io/repo/test/image-with-tag-and-digest:v1.2.3"
                "@sha256:859b5aada817b3eb53410222e8fc232cf126c9e598390ae61895eb96f52ae46d"
            ),
        ),
    ],
)
def test_str(image: str, str_image: str):
    i = img.Image(image)
    assert str(i) == str_image
