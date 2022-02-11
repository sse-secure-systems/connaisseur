import os
import re
from connaisseur.trust_root import TrustRoot
import pytest
from aioresponses import aioresponses
from ... import conftest as fix
import connaisseur.validators.notaryv1.notaryv1_validator as nv1
from connaisseur.image import Image
import connaisseur.exceptions as exc


@pytest.mark.parametrize(
    "val_config", [{"name": "nv1", "host": "me", "trust_roots": ["not_empty"]}]
)
def test_init(m_notary, val_config):
    val = nv1.NotaryV1Validator(**val_config)
    assert val.name == val_config["name"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "image, key, delegations, digest, exception",
    [
        (
            "securesystemsengineering/alice-image:test",
            None,
            ["phbelitz", "chamsen"],
            "ac904c9b191d14faf54b7952f2650a4bb21c201bf34131388b851e8ce992a652",
            fix.no_exc(),
        ),
        (
            (
                (
                    "securesystemsengineering/alice-image@sha256"
                    ":ac904c9b191d14faf54b7952f2650a4bb21"
                    "c201bf34131388b851e8ce992a652"
                )
            ),
            None,
            ["phbelitz", "chamsen"],
            "ac904c9b191d14faf54b7952f2650a4bb21c201bf34131388b851e8ce992a652",
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/sample-image:sign",
            None,
            [],
            "a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/sample-image:v1",
            None,
            [],
            "799c0fa8aa4c9fbff5a99aef1b4b5c3abb9c2f34134345005982fad3489893c7",
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/charlie-image:test2",
            "charlie",
            ["del1"],
            "",
            pytest.raises(exc.InsufficientTrustDataError),
        ),
        (
            "securesystmesengineering/dave-image:test",
            "charlie",
            ["del1", "del2"],
            "",
            pytest.raises(exc.AmbiguousDigestError),
        ),
        (
            "securesystemsengineering/alice-image:missingtag",
            None,
            [],
            "ac904c9b191d14faf54b7952f2650a4bb21c201bf34131388b851e8ce992a652",
            pytest.raises(exc.NotFoundException, match=r".*digest.*"),
        ),
    ],
)
async def test_validate(
    sample_nv1,
    m_trust_data,
    m_request,
    m_expiry,
    image: str,
    key: str,
    delegations: list,
    digest: str,
    exception,
):
    with exception:
        with aioresponses() as aio:
            aio.get(re.compile(r".*"), callback=fix.async_callback, repeat=True)
            signed_digest = await sample_nv1.validate(Image(image), key, delegations)
            assert signed_digest == digest


@pytest.mark.parametrize(
    "url, acr, health",
    [
        ("healthy.url", False, True),
        ("unhealthy.url", False, False),
        ("exceptional.url", False, False),
        ("irrelevant.url", True, True),
    ],
)
def test_healthy(m_request, url, acr, health):
    val = nv1.NotaryV1Validator(
        **{"name": "sample", "host": url, "trust_roots": ["not_empty"], "is_acr": acr}
    )
    assert val.healthy is health


@pytest.mark.parametrize(
    "delegation_role, out",
    [
        ("phbelitz", "targets/phbelitz"),
        ("chamsen", "targets/chamsen"),
        ("targets/releases", "targets/releases"),
    ],
)
def test_normalize_delegations(delegation_role: str, out: str):
    assert (
        nv1.NotaryV1Validator._NotaryV1Validator__normalize_delegation(delegation_role)
        == out
    )


req_delegations1 = ["targets/phbelitz", "targets/chamsen"]
req_delegations2 = []
req_delegations3 = ["targets/someuserthatdidnotsign"]
req_delegations4 = ["targets/del1"]
req_delegations5 = ["targets/del2"]
req_delegations6 = ["targets/phbelitz"]
root_keys = [
    (
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu7WMF8tCjVgeORA"
        "S2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA=="
    ),
    (
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtkQuBJ/wL1MEDy/6kgfSBls04MT1"
        "aUWM7eZ19L2WPJfjt105PPieCM1CZybSZ2h3O4+E4hPz1X5RfmojpXKePg=="
    ),
]
targets1 = [
    {
        "test": {
            "hashes": {"sha256": "rJBMmxkdFPr1S3lS8mUKS7IcIBvzQTE4i4UejOmSplI="},
            "length": 1993,
        }
    },
    {
        "test": {
            "hashes": {"sha256": "rJBMmxkdFPr1S3lS8mUKS7IcIBvzQTE4i4UejOmSplI="},
            "length": 1993,
        }
    },
]
targets2 = [
    {
        "sign": {
            "hashes": {"sha256": "oVR5e4MAFllW7h8W2Y86FCYwHBFo8EYsc86bwDNhyr8="},
            "length": 1994,
        },
        "v1": {
            "hashes": {"sha256": "eZwPqKpMn7/1qZrvG0tcOrucLzQTQ0UAWYL600iYk8c="},
            "length": 1994,
        },
    }
]
targets3 = [
    {
        "test": {
            "hashes": {"sha256": "TgYbzUu1pMskoZbfWdcj2RF0HVUg+J4034p5LVa97j4="},
            "length": 528,
        }
    }
]
targets4 = [
    {
        "test": {
            "hashes": {"sha256": "pkeg+cgtxfPnxL1kg7SWpJ1XC0/bH+rL/VfpZdKh1mI="},
            "length": 528,
        }
    }
]
targets5 = [
    {
        "test": {
            "hashes": {"sha256": "K3tQZXLk87nedST/hCh9uI7SSwz5RIp7BK0GZOze9xs="},
            "length": 528,
        }
    }
]
targets6 = [
    {
        "test": {
            "hashes": {"sha256": "qCXo6VDc64HH2G9tNOTkcwfpjzVQXRgNQE4ZR0KigHk="},
            "length": 528,
        }
    }
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "image, delegations, key, targets, delegation_count, exception",
    [
        (
            "securesystemsengineering/alice-image",
            req_delegations1,
            root_keys[0],
            targets1,
            2,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/sample-image",
            req_delegations2,
            root_keys[0],
            targets2,
            0,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/bob-image",
            req_delegations2,
            root_keys[1],
            targets3,
            0,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/charlie-image",
            req_delegations2,
            root_keys[1],
            targets4,
            1,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations2,
            root_keys[1],
            targets5,
            1,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations4,
            root_keys[1],
            targets5,
            1,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations5,
            root_keys[1],
            targets6,
            1,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/alice-image",
            req_delegations6,
            root_keys[0],
            [targets1[0]],
            1,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/alice-image",
            req_delegations5,
            root_keys[0],
            None,
            0,
            pytest.raises(exc.NotFoundException, match=r"Unable to find.*"),
        ),
        (
            "securesystemsengineering/eve-image",
            req_delegations5,
            root_keys[1],
            None,
            0,
            pytest.raises(exc.NotFoundException, match=r"Unable to find.*"),
        ),
        (
            "securesystemsengineering/eve-image",
            req_delegations2,
            root_keys[1],
            targets3,
            1,
            fix.no_exc(),
        ),
    ],
)
async def test_process_chain_of_trust(
    monkeypatch,
    sample_nv1,
    m_request,
    m_trust_data,
    m_expiry,
    count_loaded_delegations,
    image: str,
    delegations: list,
    key: str,
    targets: list,
    delegation_count: int,
    exception,
):
    monkeypatch.setenv("DELEGATION_COUNT", "0")
    with exception:
        with aioresponses() as aio:
            aio.get(re.compile(r".*"), callback=fix.async_callback, repeat=True)
            signed_targets = (
                await sample_nv1._NotaryV1Validator__process_chain_of_trust(
                    Image(image), delegations, TrustRoot(key)
                )
            )

            assert signed_targets == targets
            assert delegation_count == int(os.getenv("DELEGATION_COUNT"))


@pytest.mark.parametrize(
    "image, digest",
    [
        (
            (
                "image@sha256:1388abc7a12532836c3a81"
                "bdb0087409b15208f5aeba7a87aedcfd56d637c145"
            ),
            "1388abc7a12532836c3a81bdb0087409b15208f5aeba7a87aedcfd56d637c145",
        ),
        (
            (
                "image@sha256:b8a38522876a9e2550d582"
                "ce51a1d87ebdc6c570e5e585d08560bfd646f7f804"
            ),
            "b8a38522876a9e2550d582ce51a1d87ebdc6c570e5e585d08560bfd646f7f804",
        ),
        (
            (
                "image@sha256:b8a38522876a9e2550d582"
                "ce51a1d87ebdc6c570e5e585d08560bfd646f7f805"
            ),
            None,
        ),
    ],
)
def test_search_image_targets_for_digest(sample_nv1, image: str, digest: str):
    data = fix.get_td("sample_releases")["signed"]["targets"]
    assert (
        sample_nv1._NotaryV1Validator__search_image_targets_for_digest(
            data, Image(image)
        )
        == digest
    )


@pytest.mark.parametrize(
    "image, digest",
    [
        (
            "image:v1",
            "1388abc7a12532836c3a81bdb0087409b15208f5aeba7a87aedcfd56d637c145",
        ),
        (
            "image:v2",
            "b8a38522876a9e2550d582ce51a1d87ebdc6c570e5e585d08560bfd646f7f804",
        ),
        ("image:v3", None),
    ],
)
def test_search_image_targets_for_tag(sample_nv1, image: str, digest: str):
    data = fix.get_td("sample_releases")["signed"]["targets"]
    assert (
        sample_nv1._NotaryV1Validator__search_image_targets_for_tag(data, Image(image))
        == digest
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "delegations",
    [
        ([]),
        (["targets/phbelitz"]),
        (["targets/phbelitz", "targets/chamsen"]),
        (["targets/daugustin"]),
    ],
)
async def test_update_with_delegation_trust_data(
    m_request,
    m_trust_data,
    m_expiry,
    alice_key_store,
    sample_nv1,
    delegations,
):
    assert (
        await sample_nv1._NotaryV1Validator__update_with_delegation_trust_data(
            {}, delegations, alice_key_store, Image("alice-image")
        )
        is None
    )


@pytest.mark.parametrize(
    "req_del, pre_del, exception",
    [
        (["phb"], ["phb", "cha"], fix.no_exc()),
        (["phb", "cha"], ["phb", "cha"], fix.no_exc()),
        (["phb"], ["cha"], pytest.raises(exc.NotFoundException, match=r".*phb.*")),
        ([], [], fix.no_exc()),
        (["phb"], [], pytest.raises(exc.NotFoundException)),
    ],
)
def test_validate_all_required_delegations_present(
    sample_nv1, req_del, pre_del, exception
):
    with exception:
        assert (
            sample_nv1._NotaryV1Validator__validate_all_required_delegations_present(
                req_del, pre_del
            )
            is None
        )
