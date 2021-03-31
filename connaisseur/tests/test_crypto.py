import pytest
import json
import connaisseur.crypto
from connaisseur.exceptions import InvalidPublicKey

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


@pytest.mark.parametrize(
    "base64encoded_key",
    [
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXbZhEfTYb4Mnb/LdrtXKTIIbzNBp8mw"
        "riocbaxXxzquvbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ==",
        targets_pub,
    ],
)
def test_decode_and_verify_ecdsa_key(base64encoded_key):
    connaisseur.crypto.decode_and_verify_ecdsa_key(base64encoded_key)


@pytest.mark.parametrize(
    "base64encoded_key",
    [
        "somekey==",
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXbZhEfTYb4Mnb/LdrtXKTIIbzNBp8mw"
        "riocbaxXxzquvbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ=",
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXbZhEfTnb/LdrtXKTIIbzNBp8mw"
        "riocbaxXxzquvbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ==",
    ],
)
def test_decode_and_verify_ecdsa_key_invalid_key_error(base64encoded_key):
    with pytest.raises(InvalidPublicKey):
        connaisseur.crypto.decode_and_verify_ecdsa_key(base64encoded_key)
