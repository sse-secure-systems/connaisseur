import pytest
import json
import base64
import connaisseur.crypto
from connaisseur.exceptions import BaseConnaisseurException


root_pub = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu"
    "7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDG"
    "l+W2k3elHkPbR+gNkK2PCA=="
)
root_sig = (
    "77lGn17vJPsru39/mO6quh+yuMQvhLyqz4PhvMySLpnpzYu2x+"
    "YIsXfH2gngP8hYzOWvovE6iQPKBoJv3zWMsQ=="
)
targets_pub = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErIGdt5pelfW"
    "OSjmY7k+/TypV0IFF9XLA+K4swhclLJb79cLoeBBDqkkUrk"
    "fhN5gxRnA//wA3amL4WXkaGsb9zQ=="
)
targets_sig = (
    "ayUgIwW4LmtW+kuzHuyU7lkn8awoXlymBcXeO8j++JSAUpU"
    "3BSuFsBe7yx3SOOsxh57u+vWkCOzPdLEYVyQrqg=="
)
key1 = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEM0xl8F5nwIV3IAru1Pf85WCo4cfT\n"
    "OQ91jhxVaQ3xHMeW430q7R4H/tJmAXUZBe+nOTX8pgtmrLpT+Hu/H7pUhw==\n"
    "-----END PUBLIC KEY-----\n"
)
key2 = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEWGcErqaO7+y3PzNTHt7PVx0+Xtgv\n"
    "LV5mFW91CxzN8uQht/Ig6+FAymrn2lOtUz5BqF4pSQizcdqN475t6raTWw==\n"
    "-----END PUBLIC KEY-----\n"
)


@pytest.fixture
def crypto():
    return connaisseur.crypto


def get_message(path: str):
    with open(path, "r") as file:
        msg = json.load(file)

    return json.dumps(msg["signed"], separators=(",", ":"))


@pytest.mark.parametrize(
    "key, out",
    [
        (
            root_pub,
            (
                b"tR5kwrDK22SyCu"
                b"7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDG"
                b"l+W2k3elHkPbR+gNkK2PCA=="
            ),
        ),
        (
            targets_pub,
            (
                b"rIGdt5pelfW"
                b"OSjmY7k+/TypV0IFF9XLA+K4swhclLJb79cLoeBBDqkkUrk"
                b"fhN5gxRnA//wA3amL4WXkaGsb9zQ=="
            ),
        ),
        (
            key1,
            (
                b"M0xl8F5nwIV3IAru1Pf85WCo4cfT"
                b"OQ91jhxVaQ3xHMeW430q7R4H/tJmAXUZBe+nOTX8pgtmrLpT+Hu/H7pUhw=="
            ),
        ),
        (
            key2,
            (
                b"WGcErqaO7+y3PzNTHt7PVx0+Xtgv"
                b"LV5mFW91CxzN8uQht/Ig6+FAymrn2lOtUz5BqF4pSQizcdqN475t6raTWw=="
            ),
        ),
    ],
)
def test_load_key(crypto, key: str, out: str):
    pub_key = crypto.load_key(key)
    assert base64.b64encode(pub_key.to_string()) == out


@pytest.mark.parametrize(
    "public, signature, message",
    [
        (
            connaisseur.crypto.load_key(root_pub),
            root_sig,
            get_message("tests/data/sample_root.json"),
        ),
        (
            connaisseur.crypto.load_key(targets_pub),
            targets_sig,
            get_message("tests/data/sample_targets.json"),
        ),
    ],
)
def test_verify_signature(crypto, public, signature: str, message: str):
    assert crypto.verify_signature(public, signature, message)
