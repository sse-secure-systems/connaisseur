import pytest
import base64
import json
import ecdsa
import connaisseur.crypto

root_pub_string = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu"
    "7WMF8tCjVgeORAS2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDG"
    "l+W2k3elHkPbR+gNkK2PCA=="
)
root_pub = ecdsa.VerifyingKey.from_der(base64.b64decode(root_pub_string))
root_sig = (
    "77lGn17vJPsru39/mO6quh+yuMQvhLyqz4PhvMySLpnpzYu2x+"
    "YIsXfH2gngP8hYzOWvovE6iQPKBoJv3zWMsQ=="
)
targets_pub_string = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErIGdt5pelfW"
    "OSjmY7k+/TypV0IFF9XLA+K4swhclLJb79cLoeBBDqkkUrk"
    "fhN5gxRnA//wA3amL4WXkaGsb9zQ=="
)
targets_pub = ecdsa.VerifyingKey.from_der(base64.b64decode(targets_pub_string))
targets_sig = (
    "ayUgIwW4LmtW+kuzHuyU7lkn8awoXlymBcXeO8j++JSAUpU"
    "3BSuFsBe7yx3SOOsxh57u+vWkCOzPdLEYVyQrqg=="
)


@pytest.fixture
def crypto():
    return connaisseur.crypto


def get_message(path: str):
    with open(path, "r") as file:
        msg = json.load(file)

    return json.dumps(msg["signed"], separators=(",", ":"))


@pytest.mark.parametrize(
    "public, signature, message",
    [
        (root_pub, root_sig, get_message("tests/data/sample_root.json")),
        (targets_pub, targets_sig, get_message("tests/data/sample_targets.json")),
    ],
)
def test_verify_signature(crypto, public: str, signature: str, message: str):
    assert crypto.verify_signature(public, signature, message)
