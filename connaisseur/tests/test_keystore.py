import pytest
import json
import ecdsa
import base64
from connaisseur.trust_data import TrustData, TargetsData
import connaisseur.key_store as ks
from connaisseur.exceptions import BaseConnaisseurException

sample_key = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu"
    "7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDG"
    "l+W2k3elHkPbR+gNkK2PCA=="
)

root_keys = {
    "7c62922e6be165f1ea08252f77410152b9e4ec0d7bf4e69c1cc43f0e6c73da20": (
        ks.KeyStore.load_key_string(
            "7c62922e6be165f1ea08252f77410152b9e4ec0d7bf4e69c1cc43f0e6c73da20",
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErIGdt5pelfWOSjmY7k+/TypV0IFF"
                "9XLA+K4swhclLJb79cLoeBBDqkkUrkfhN5gxRnA//wA3amL4WXkaGsb9zQ=="
            ),
        )
    ),
    "7dbacd611d5933ca3f0fad581ed233881c501229343613f63f2d4b5771ee4299": (
        ks.KeyStore.load_key_string(
            "7dbacd611d5933ca3f0fad581ed233881c501229343613f63f2d4b5771ee4299",
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEzRo/rFtBEAJLvEFU7xem34GpEsw"
                "xsw6nW9YiBqbAcba6LWZuem7slTp+List+NKAVK3EzJCjUixooO5ss4Erug=="
            ),
        )
    ),
    "f1997e14be3d33c5677282b6a73060d8124f4020f464644e27ab76f703eb6f7e": (
        ks.KeyStore.load_key_string(
            "f1997e14be3d33c5677282b6a73060d8124f4020f464644e27ab76f703eb6f7e",
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEMza1L1+e8vfZ1q7+GA5E0st13g7j"
                "WR7fdQSsxkdrpJ6IkUq9D6f9BUopD83YvLBMEMy20MBvsICJnXMu8IZlYA=="
            ),
        )
    ),
}

target_keys = {
    "6984a67934a29955b3f969835c58ee0dd09158f5bec43726d319515b56b0a878": (
        ks.KeyStore.load_key_string(
            "6984a67934a29955b3f969835c58ee0dd09158f5bec43726d319515b56b0a878",
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEchQNiJJt4PTaEeAzaztL+TQZqTa"
                "0iM0YSf+w0LjSElobVsYgnqIbCWe6pGX3UvcCngNw7N4uGkdVNVMS2Tslg=="
            ),
        )
    ),
    "70aa109003a93131c63499c70dcfc8db3ba33ca81bdd1abcd52c067a8acc0492": (
        ks.KeyStore.load_key_string(
            "70aa109003a93131c63499c70dcfc8db3ba33ca81bdd1abcd52c067a8acc049",
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEM0xl8F5nwIV3IAru1Pf85WCo4cfT"
                "OQ91jhxVaQ3xHMeW430q7R4H/tJmAXUZBe+nOTX8pgtmrLpT+Hu/H7pUhw=="
            ),
        )
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


@pytest.fixture
def key_store():
    return ks


@pytest.fixture
def mock_trust_data(monkeypatch):
    def _validate_expiry(self):
        pass

    def trust_init(self, data: dict, role: str):
        self.schema_path = "res/targets_schema.json"
        self.kind = role
        self._validate_schema(data)
        self.signed = data["signed"]
        self.signatures = data["signatures"]

    monkeypatch.setattr(TrustData, "_validate_expiry", _validate_expiry)
    monkeypatch.setattr(TargetsData, "__init__", trust_init)
    TrustData.schema_path = "res/{}_schema.json"


def trust_data(path: str):
    with open(path, "r") as file:
        data = json.load(file)
    return data


@pytest.mark.parametrize(
    "pub_key",
    [
        (
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu"
                "7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDG"
                "l+W2k3elHkPbR+gNkK2PCA=="
            )
        ),
        (
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErIGdt5pelfWOSjmY7k+/TypV0IFF"
                "9XLA+K4swhclLJb79cLoeBBDqkkUrkfhN5gxRnA//wA3amL4WXkaGsb9zQ=="
            )
        ),
    ],
)
def test_key_store(key_store, pub_key: str):
    k = ks.KeyStore(pub_key)
    key = ecdsa.VerifyingKey.from_der(base64.b64decode(pub_key))
    assert k.keys == {"root": key}
    assert k.hashes == {}


@pytest.mark.parametrize("k_id, k_value", [("1", "1"), ("2", "2")])
def test_get_key(key_store, k_id: str, k_value: str):
    k = ks.KeyStore(sample_key)
    k.keys = {"1": "1", "2": "2"}
    assert k.get_key(k_id) == k_value


def test_get_key_error(key_store):
    k = ks.KeyStore(sample_key)
    with pytest.raises(BaseConnaisseurException) as err:
        k.get_key("1")
    assert 'could not find key id "1" in keystore.' in str(err.value)


@pytest.mark.parametrize(
    "role, _hash, _len",
    [
        ("root", "wlaYz21+0NezlHjqkldQQBf3KWtifimy07A+fOEyCTo=", 2401),
        ("targets", "QGNOSBnOmZHpn8uefASR1xw9ZrPpr0SMW+xWvY4nSAc=", 1307),
        ("targets/releases", "pNjHgtwOrSZB5l0bzHZt9u3dUdFpKsPBhWPiVrIMm88=", 712),
    ],
)
def test_get_hash(key_store, role: str, _hash: str, _len: int):
    k = ks.KeyStore(sample_key)
    k.hashes = snapshot_hashes
    assert k.get_hash(role) == (_hash, _len)


def test_get_hash_error(key_store):
    k = ks.KeyStore(sample_key)
    with pytest.raises(BaseConnaisseurException) as err:
        k.get_hash("timestamp")
    assert 'could not find hash for role "timestamp" in keystore.' in str(err.value)


@pytest.mark.parametrize(
    "data, role, keys, hashes",
    [
        (
            trust_data("tests/data/sample_root.json"),
            "root",
            dict(
                **{"root": ks.KeyStore.load_key_string("root", sample_key)}, **root_keys
            ),
            {},
        ),
        (
            trust_data("tests/data/sample_targets.json"),
            "targets",
            dict(
                **{"root": ks.KeyStore.load_key_string("root", sample_key)},
                **target_keys
            ),
            {},
        ),
        (
            trust_data("tests/data/sample_snapshot.json"),
            "snapshot",
            {"root": ks.KeyStore.load_key_string("root", sample_key)},
            snapshot_hashes,
        ),
        (
            trust_data("tests/data/sample_timestamp.json"),
            "timestamp",
            {"root": ks.KeyStore.load_key_string("root", sample_key)},
            timestamp_hashes,
        ),
    ],
)
def test_update(
    key_store,
    mock_trust_data,
    data: dict,
    role: str,
    keys: dict,
    hashes: dict,
):
    k = ks.KeyStore(sample_key)
    trust_data_ = TrustData(data, role)
    k.update(trust_data_)
    assert k.keys == keys
    assert k.hashes == hashes


@pytest.mark.parametrize(
    "key_base64, key_out",
    [
        (
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEOXY"
                "ta5TgdCwXTCnLU09W5T4M4r9fQQrqJuADP6U7g5r9I"
                "CgPSmZuRHP/1AYUfOQW3baveKsT969EfELKj1lfCA=="
            ),
            (
                b"OXYta5TgdCwXTCnLU09W5T4M4r9fQQrqJuADP6U"
                b"7g5r9ICgPSmZuRHP/1AYUfOQW3baveKsT969EfELKj1lfCA=="
            ),
        ),
        (
            (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEsx28WV7BsQfnHF1kZmpdCTTLJaWe"
                "d0CA+JOi8H4REuBaWSZ5zPDe468WuOJ6f71E7WFg3CVEVYHuoZt2UYbN/Q=="
            ),
            (
                b"sx28WV7BsQfnHF1kZmpdCTTLJaWed0CA+JOi8H4REu"
                b"BaWSZ5zPDe468WuOJ6f71E7WFg3CVEVYHuoZt2UYbN/Q=="
            ),
        ),
    ],
)
def test_load_key_string(key_store, key_base64: str, key_out: str):
    key = ks.KeyStore.load_key_string("", key_base64)
    assert base64.b64encode(key.to_string()) == key_out


@pytest.mark.parametrize(
    "key_base64", [("wellhollothere"), (None), ("d2VsbGhlbGxvdGhlcmUK")]
)
def test_load_key_string_error(key_store, key_base64: str):
    with pytest.raises(BaseConnaisseurException) as err:
        ks.KeyStore.load_key_string("id", key_base64)
    assert "error loading key id." in str(err.value)
