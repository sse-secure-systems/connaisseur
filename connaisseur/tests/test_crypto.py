import pytest
import json
import base64
import conftest as fix
import connaisseur.crypto as cr


def get_message(path: str):
    with open(f"tests/data/trust_data/{path}.json", "r") as file:
        msg = json.load(file)

    return json.dumps(msg["signed"], separators=(",", ":"))


root_pub = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu"
    "7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDG"
    "l+W2k3elHkPbR+gNkK2PCA=="
)

targets_pub = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErIGdt5pelfW"
    "OSjmY7k+/TypV0IFF9XLA+K4swhclLJb79cLoeBBDqkkUrk"
    "fhN5gxRnA//wA3amL4WXkaGsb9zQ=="
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


@pytest.mark.parametrize(
    "key, out, exception",
    [
        (
            root_pub,
            (
                b"tR5kwrDK22SyCu"
                b"7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDG"
                b"l+W2k3elHkPbR+gNkK2PCA=="
            ),
            fix.no_exc(),
        ),
        (
            targets_pub,
            (
                b"rIGdt5pelfW"
                b"OSjmY7k+/TypV0IFF9XLA+K4swhclLJb79cLoeBBDqkkUrk"
                b"fhN5gxRnA//wA3amL4WXkaGsb9zQ=="
            ),
            fix.no_exc(),
        ),
        (
            key1,
            (
                b"M0xl8F5nwIV3IAru1Pf85WCo4cfT"
                b"OQ91jhxVaQ3xHMeW430q7R4H/tJmAXUZBe+nOTX8pgtmrLpT+Hu/H7pUhw=="
            ),
            fix.no_exc(),
        ),
        (
            key2,
            (
                b"WGcErqaO7+y3PzNTHt7PVx0+Xtgv"
                b"LV5mFW91CxzN8uQht/Ig6+FAymrn2lOtUz5BqF4pSQizcdqN475t6raTWw=="
            ),
            fix.no_exc(),
        ),
        ("", "", pytest.raises(ValueError)),
    ],
)
def test_load_key(key: str, out: str, exception):
    with exception:
        pub_key = cr.load_key(key)
        assert base64.b64encode(pub_key.to_string()) == out


root_sig = (
    "77lGn17vJPsru39/mO6quh+yuMQvhLyqz4PhvMySLpnpzYu2x+"
    "YIsXfH2gngP8hYzOWvovE6iQPKBoJv3zWMsQ=="
)
targets_sig = (
    "ayUgIwW4LmtW+kuzHuyU7lkn8awoXlymBcXeO8j++JSAUpU"
    "3BSuFsBe7yx3SOOsxh57u+vWkCOzPdLEYVyQrqg=="
)


@pytest.mark.parametrize(
    "public, signature, message",
    [
        (
            cr.load_key(root_pub),
            root_sig,
            get_message("sample_root"),
        ),
        (
            cr.load_key(targets_pub),
            targets_sig,
            get_message("sample_targets"),
        ),
    ],
)
def test_verify_signature(public, signature: str, message: str):
    assert cr.verify_signature(public, signature, message)
