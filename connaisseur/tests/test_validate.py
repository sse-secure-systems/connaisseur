import pytest
import pytest_subprocess
import conftest as fix
import connaisseur.validate as val
import connaisseur.exceptions as exc
from connaisseur.image import Image
from connaisseur.policy import Rule


policy_rule1 = Rule(
    **{
        "pattern": "docker.io/securesystemsengineering/alice-image",
        "verify": True,
        "delegations": ["phbelitz", "chamsen"],
        "notary": "dockerhub",
    }
)
policy_rule2 = Rule(
    **{
        "pattern": "docker.io/securesystemsengineering/*:*",
        "verify": True,
        "notary": "dockerhub",
    }
)
policy_rule3 = Rule(
    **{
        "pattern": "docker.io/securesystemsengineering/*:*",
        "verify": True,
        "delegations": ["del1"],
        "key": "charlie",
    }
)
policy_rule4 = Rule(
    **{
        "pattern": "docker.io/securesystemsengineering/*:*",
        "verify": True,
        "key": "charlie",
        "delegations": ["del1", "del2"],
    }
)
policy_rule5 = Rule(
    **{
        "pattern": "docker.io/securesystemsengineering/*:*",
        "verify": True,
        "key": "missingkey",
    }
)

req_delegations1 = ["targets/phbelitz", "targets/chamsen"]
req_delegations2 = []
req_delegations3 = ["targets/someuserthatdidnotsign"]
req_delegations4 = ["targets/del1"]
req_delegations5 = ["targets/del2"]
req_delegations6 = ["targets/phbelitz", "targets/someuserthatdidnotsign"]

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

cosign_trust_data = '{"Critical":{"Identity":{"docker-reference":""},"Image":{"Docker-manifest-digest":"sha256:c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"},"Type":"cosign container signature"},"Optional":null}'


pub_root_keys = [
    {
        "name": "default",
        "key": (
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu7WMF8tCjVgeORA"
            "S2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA=="
        ),
    },
    {
        "name": "charlie",
        "key": (
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtkQuBJ/wL1MEDy/6kgfSBls04MT1"
            "aUWM7eZ19L2WPJfjt105PPieCM1CZybSZ2h3O4+E4hPz1X5RfmojpXKePg=="
        ),
    },
    {"name": "cosign"},
]


@pytest.mark.parametrize(
    "image, policy_rule, digest, exception",
    [
        (
            "securesystemsengineering/alice-image:test",
            policy_rule1,
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
            policy_rule1,
            "ac904c9b191d14faf54b7952f2650a4bb21c201bf34131388b851e8ce992a652",
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/sample-image:sign",
            policy_rule2,
            "a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/sample-image:v1",
            policy_rule2,
            "799c0fa8aa4c9fbff5a99aef1b4b5c3abb9c2f34134345005982fad3489893c7",
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/charlie-image:test2",
            policy_rule3,
            "",
            pytest.raises(exc.InsufficientTrustDataError),
        ),
        (
            "securesystmesengineering/dave-image:test",
            policy_rule4,
            "",
            pytest.raises(exc.AmbiguousDigestError),
        ),
        (
            "securesystemsengineering/alice-image:test",
            policy_rule5,
            "",
            pytest.raises(exc.NotFoundException, match=r".*public root key.*"),
        ),
        (
            "securesystemsengineering/alice-image:missingtag",
            policy_rule2,
            "ac904c9b191d14faf54b7952f2650a4bb21c201bf34131388b851e8ce992a652",
            pytest.raises(exc.NotFoundException, match=r".*digest.*"),
        ),
    ],
)
def test_get_trusted_digest(
    m_trust_data,
    m_request,
    m_expiry,
    sample_notary,
    image: str,
    policy_rule: dict,
    digest: str,
    exception,
):
    with exception:
        assert (
            val.get_trusted_digest(sample_notary, Image(image), policy_rule) == digest
        )


@pytest.mark.parametrize(
    "image, policy_rule, digest",
    [
        (
            "docker.io/securesystemsengineering/testimage:co-signed",
            policy_rule2,
            "c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7",
        ),
    ],
)
def test_get_trusted_digest_cosigned(
    fake_process, sample_notary, image: str, policy_rule: dict, digest: str
):
    sample_notary.host = "host"
    sample_notary.is_cosign = True
    fake_process.register_subprocess(
        ["/app/cosign/cosign", "verify", "-key", "/dev/stdin", image],
        stdout=bytes(cosign_trust_data, "utf-8"),
    )
    assert val.get_trusted_digest(sample_notary, Image(image), policy_rule) == digest


@pytest.mark.parametrize(
    "image, req_delegations, root_key, targets, exception",
    [
        (
            "securesystemsengineering/alice-image",
            req_delegations1,
            pub_root_keys[0]["key"],
            targets1,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/sample-image",
            req_delegations2,
            pub_root_keys[0]["key"],
            targets2,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/bob-image",
            req_delegations2,
            pub_root_keys[1]["key"],
            targets3,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/charlie-image",
            req_delegations2,
            pub_root_keys[1]["key"],
            targets4,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations2,
            pub_root_keys[1]["key"],
            targets5,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations4,
            pub_root_keys[1]["key"],
            targets5,
            fix.no_exc(),
        ),
        (
            "securesystemsengineering/dave-image",
            req_delegations5,
            pub_root_keys[1]["key"],
            targets6,
            fix.no_exc(),
        ),
    ],
)
def test_process_chain_of_trust(
    sample_notary,
    m_request,
    m_trust_data,
    m_expiry,
    image: str,
    req_delegations: dict,
    root_key: str,
    targets: list,
    exception,
):
    with exception:
        assert (
            val.__process_chain_of_trust(
                sample_notary, Image(image), req_delegations, root_key
            )
            == targets
        )


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
def test_search_image_targets_for_digest(image: str, digest: str):
    data = fix.get_td("sample_releases")["signed"]["targets"]
    assert val.__search_image_targets_for_digest(data, Image(image)) == digest


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
def test_search_image_targets_for_tag(image: str, digest: str):
    data = fix.get_td("sample_releases")["signed"]["targets"]
    assert val.__search_image_targets_for_tag(data, Image(image)) == digest


@pytest.mark.parametrize(
    "delegations",
    [
        ([]),
        (["targets/phbelitz"]),
        (["targets/phbelitz", "targets/chamsen"]),
        (["targets/daugustin"]),
    ],
)
def test_update_with_delegation_trust_data(
    m_request,
    m_trust_data,
    m_expiry,
    alice_key_store,
    sample_notary,
    delegations,
):
    assert (
        val.__update_with_delegation_trust_data(
            {}, delegations, alice_key_store, sample_notary, Image("alice-image")
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
def test_validate_all_required_delegations_present(req_del, pre_del, exception):
    with exception:
        assert val.__validate_all_required_delegations_present(req_del, pre_del) is None
