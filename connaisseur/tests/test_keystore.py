import pytest
import ecdsa
import conftest as fix
import connaisseur.key_store as ks
import connaisseur.exceptions as exc
from connaisseur.trust_data import TrustData
from connaisseur.crypto import load_key

sample_key = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu"
    "7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDG"
    "l+W2k3elHkPbR+gNkK2PCA=="
)
pub_root_keys = {
    "7c62922e6be165f1ea08252f77410152b9e4ec0d7bf4e69c1cc43f0e6c73da20": load_key(
        (
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErIGdt5pelfWOSjmY7k+/TypV0IFF"
            "9XLA+K4swhclLJb79cLoeBBDqkkUrkfhN5gxRnA//wA3amL4WXkaGsb9zQ=="
        ),
    ),
    "7dbacd611d5933ca3f0fad581ed233881c501229343613f63f2d4b5771ee4299": load_key(
        (
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEzRo/rFtBEAJLvEFU7xem34GpEsw"
            "xsw6nW9YiBqbAcba6LWZuem7slTp+List+NKAVK3EzJCjUixooO5ss4Erug=="
        ),
    ),
    "f1997e14be3d33c5677282b6a73060d8124f4020f464644e27ab76f703eb6f7e": load_key(
        (
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEMza1L1+e8vfZ1q7+GA5E0st13g7j"
            "WR7fdQSsxkdrpJ6IkUq9D6f9BUopD83YvLBMEMy20MBvsICJnXMu8IZlYA=="
        ),
    ),
}

target_keys = {
    "6984a67934a29955b3f969835c58ee0dd09158f5bec43726d319515b56b0a878": load_key(
        (
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEchQNiJJt4PTaEeAzaztL+TQZqTa"
            "0iM0YSf+w0LjSElobVsYgnqIbCWe6pGX3UvcCngNw7N4uGkdVNVMS2Tslg=="
        ),
    ),
    "70aa109003a93131c63499c70dcfc8db3ba33ca81bdd1abcd52c067a8acc0492": load_key(
        (
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEM0xl8F5nwIV3IAru1Pf85WCo4cfT"
            "OQ91jhxVaQ3xHMeW430q7R4H/tJmAXUZBe+nOTX8pgtmrLpT+Hu/H7pUhw=="
        ),
    ),
}

snapshot_hashes = {
    "root": ("wlaYz21+0NezlHjqkldQQBf3KWtifimy07A+fOEyCTo=", 2401),
    "targets": ("QGNOSBnOmZHpn8uefASR1xw9ZrPpr0SMW+xWvY4nSAc=", 1307),
    "targets/chamsen": ("ESFkhp4/3VgYQ4otmcgwLaR4IsmvLIGfo7VJMIxZCwY=", 521),
    "targets/phbelitz": ("ADiBf7StE9k0mqdAXp0o8SGQuJtXbufSZxNTKZ8hDZc=", 521),
    "targets/releases": ("pNjHgtwOrSZB5l0bzHZt9u3dUdFpKsPBhWPiVrIMm88=", 712),
}

timestamp_hashes = {
    "snapshot": ("cNXm5R+rJsc3WNQVH8M1G/cTwkO1doq5n8fQmYpQcfQ=", 1286),
}


@pytest.mark.parametrize(
    "pub_key, exception",
    [
        (
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu"
                "7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDG"
                "l+W2k3elHkPbR+gNkK2PCA=="
            ),
            fix.no_exc(),
        ),
        (
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErIGdt5pelfWOSjmY7k+/TypV0IFF"
                "9XLA+K4swhclLJb79cLoeBBDqkkUrkfhN5gxRnA//wA3amL4WXkaGsb9zQ=="
            ),
            fix.no_exc(),
        ),
        (None, fix.no_exc()),
        (
            (
                "-----BEGIN PUBLIC KEY-----"
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEWGcErqaO7+y3PzNTHt7PVx0+Xtgv"
                "LV5mFW91CxzN8uQht/Ig6+FAymrn2lOtUz5BqF4pSQizcdqN475t6raTWw=="
                "-----END PUBLIC KEY-----"
            ),
            pytest.raises(exc.InvalidKeyFormatError),
        ),
        (
            (
                "-----BEGIN PUBLIC KEY-----\n"
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEWGcErqaO7+y3PzNTHt7PVx0+Xtgv\n"
                "LV5mFW91CxzN8uQht/Ig6+FAymrn2lOtUz5BqF4pSQizcdqN475t6raTWwthismakesnosense==C\n"
                "-----END PUBLIC KEY-----\n"
            ),
            pytest.raises(exc.InvalidKeyFormatError),
        ),
        ("hello! i'm happy to be here.", pytest.raises(exc.InvalidKeyFormatError)),
    ],
)
def test_key_store(pub_key: str, exception):
    with exception:
        k = ks.KeyStore(pub_key)
        if pub_key:
            key = ecdsa.VerifyingKey.from_pem(pub_key)
            assert k.keys == {"root": key}
        else:
            assert k.keys == {}
        assert k.hashes == {}


@pytest.mark.parametrize(
    "k_id, k_value, exception",
    [
        ("root", load_key(sample_key), fix.no_exc()),
        (
            "7c62922e6be165f1ea08252f77410152b9e4ec0d7bf4e69c1cc43f0e6c73da20",
            load_key(
                (
                    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErIGdt5pelfWOSjmY7k+/TypV0IFF"
                    "9XLA+K4swhclLJb79cLoeBBDqkkUrkfhN5gxRnA//wA3amL4WXkaGsb9zQ=="
                )
            ),
            fix.no_exc(),
        ),
        ("3", "", pytest.raises(exc.NotFoundException)),
    ],
)
def test_get_key(sample_key_store, k_id, k_value, exception):
    with exception:
        assert sample_key_store.get_key(k_id) == k_value


@pytest.mark.parametrize(
    "role, _hash, _len, exception",
    [
        ("root", "wlaYz21+0NezlHjqkldQQBf3KWtifimy07A+fOEyCTo=", 2401, fix.no_exc()),
        ("targets", "QGNOSBnOmZHpn8uefASR1xw9ZrPpr0SMW+xWvY4nSAc=", 1307, fix.no_exc()),
        (
            "targets/releases",
            "pNjHgtwOrSZB5l0bzHZt9u3dUdFpKsPBhWPiVrIMm88=",
            712,
            fix.no_exc(),
        ),
        ("timestamp", "", None, pytest.raises(exc.NotFoundException)),
    ],
)
def test_get_hash(sample_key_store, role: str, _hash: str, _len: int, exception):
    with exception:
        assert sample_key_store.get_hash(role) == (_hash, _len)


@pytest.mark.parametrize(
    "data, role, keys, hashes, exception",
    [
        (
            fix.get_td("sample_root"),
            "root",
            dict(**{"root": load_key(sample_key)}, **pub_root_keys),
            {},
            fix.no_exc(),
        ),
        (
            fix.get_td("sample_targets"),
            "targets",
            dict(**{"root": load_key(sample_key)}, **target_keys),
            {},
            fix.no_exc(),
        ),
        (
            fix.get_td("sample_snapshot"),
            "snapshot",
            {"root": load_key(sample_key)},
            snapshot_hashes,
            fix.no_exc(),
        ),
        (
            fix.get_td("sample_timestamp"),
            "timestamp",
            {"root": load_key(sample_key)},
            timestamp_hashes,
            fix.no_exc(),
        ),
        (
            fix.get_td("wrong_key_format"),
            "targets",
            {},
            {},
            pytest.raises(exc.InvalidKeyFormatError),
        ),
    ],
)
def test_update(
    m_trust_data, sample_key_store, data, role, keys: dict, hashes: dict, exception
):
    with exception:
        k = ks.KeyStore(sample_key)
        trust_data = TrustData(data, role)
        k.update(trust_data)
        assert k.keys == keys
        assert k.hashes == hashes
