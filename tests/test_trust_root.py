import pytest
from . import conftest as fix
import connaisseur.exceptions as exc
import connaisseur.trust_root as trust_root


sample_ecdsa = "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEOXYta5TgdCwXTCnLU09W5T4M4r9f\nQQrqJuADP6U7g5r9ICgPSmZuRHP/1AYUfOQW3baveKsT969EfELKj1lfCA==\n-----END PUBLIC KEY-----"
sample_rsa = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAs5pC7R5OTSTUMJHUniPk\nrLfmGDAUxZtRlvIE+pGPCD6cUXH22advkK87xwpupjxdVYuKTFnWHUIyFJwjI3vu\nsievezcAr0E/xxyeo49tWog9kFoooK3qmXjpETC8OpvNROZ0K3qhlm9PZkGo3gSJ\n/B4rMU/d+jkCI8eiUPpdVQOczdBoD5nzQAF1mfmffWGsbKY+d8/l77Vset0GXExR\nzUtnglMhREyHNpDeQUg5OEn+kuGLlTzIxpIF+MlbzP3+xmNEzH2iafr0ae2g5kX2\n880priXpxG8GXW2ybZmPvchclnvFu4ZfZcM10FpgYJFvR/9iofFeAka9u5z6VZcc\nmQIDAQAB\n-----END PUBLIC KEY-----"
awskms1 = "awskms:///1234abcd-12ab-34cd-56ef-1234567890ab"
awskms2 = "awskms://localhost:4566/1234abcd-12ab-34cd-56ef-1234567890ab"
awskms3 = "awskms:///arn:aws:kms:us-east-2:111122223333:key/1234abcd-12ab-34cd-56ef-1234567890ab"
awskms4 = "awskms://localhost:4566/arn:aws:kms:us-east-2:111122223333:key/1234abcd-12ab-34cd-56ef-1234567890ab"
awskms5 = "awskms:///alias/ExampleAlias"
awskms6 = "awskms://localhost:4566/alias/ExampleAlias"
awskms7 = "awskms:///arn:aws:kms:us-east-2:111122223333:alias/ExampleAlias"
awskms8 = (
    "awskms://localhost:4566/arn:aws:kms:us-east-2:111122223333:alias/ExampleAlias"
)
gcpkms = "gcpkms://projects/example_project/locations/example_location/keyRings/example_keyring/cryptoKeys/example_key/versions/example_keyversion"
azurekms = "azurekms://example_vault_name/example_key"
hashicorpkms = "hashivault://example_keyname"
k8skms = "k8s://example_ns/example_key"
sample_mail = "mail@example.com"

sample_ecdsa2 = "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEi2WD/E/UXF4+yoE5e4cjpJMNgQw\n8PAVALRX+8f8I8B+XneAtnOHDTI8L6wBeFRTzl6G4OmgDyCRYTb5MV3hog==\n-----END PUBLIC KEY-----"


def cb(image, key_args):
    return key_args[:2]


@pytest.mark.parametrize(
    "data, class_, exception",
    [
        (sample_ecdsa, trust_root.ECDSAKey, fix.no_exc()),
        (sample_rsa, trust_root.RSAKey, fix.no_exc()),
        (sample_mail, trust_root.KeyLessTrustRoot, fix.no_exc()),
        ("iamnotakey", None, pytest.raises(exc.InvalidFormatException)),
    ]
    + list(
        map(
            lambda x: (x, trust_root.KMSKey, fix.no_exc()),
            [
                awskms1,
                awskms2,
                awskms3,
                awskms4,
                awskms5,
                awskms6,
                awskms7,
                awskms8,
                gcpkms,
                azurekms,
                hashicorpkms,
                k8skms,
            ],
        )
    ),
)
def test_keys(data, class_, exception):
    with exception:
        key = trust_root.TrustRoot(data)
        assert isinstance(key, class_)


@pytest.mark.parametrize(
    "key, out",
    [
        (
            sample_ecdsa,
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEOXYta5TgdCwXTCnLU09W5T4M4r9fQQrqJuADP6U7g5r9ICgPSmZuRHP/1AYUfOQW3baveKsT969EfELKj1lfCA==",
        ),
        (
            sample_rsa,
            "MIIBCgKCAQEAs5pC7R5OTSTUMJHUniPkrLfmGDAUxZtRlvIE+pGPCD6cUXH22advkK87xwpupjxdVYuKTFnWHUIyFJwjI3vusievezcAr0E/xxyeo49tWog9kFoooK3qmXjpETC8OpvNROZ0K3qhlm9PZkGo3gSJ/B4rMU/d+jkCI8eiUPpdVQOczdBoD5nzQAF1mfmffWGsbKY+d8/l77Vset0GXExRzUtnglMhREyHNpDeQUg5OEn+kuGLlTzIxpIF+MlbzP3+xmNEzH2iafr0ae2g5kX2880priXpxG8GXW2ybZmPvchclnvFu4ZfZcM10FpgYJFvR/9iofFeAka9u5z6VZccmQIDAQAB",
        ),
        (awskms1, awskms1),
        (sample_mail, sample_mail),
    ],
)
def test_str(key, out):
    k = trust_root.TrustRoot(key)
    assert str(k) == out
