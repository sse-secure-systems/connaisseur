import pytest
import json
import pytz
import datetime as dt
import connaisseur.trust_data
from connaisseur.exceptions import ValidationError, NotFoundException, NoSuchClassError
from connaisseur.key_store import KeyStore

root_keys = {
    "2cd463575a31cb3184320e889e82fb1f9e3bbebee2ae42b2f825b0c8a734e798": {
        "keytype": "ecdsa-x509",
        "keyval": {
            "private": None,
            "public": (
                "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUJlekNDQVNLZ0F3S"
                "UJBZ0lSQUtDclUxM0pNUzdHTnJMWEk2SjVvRmd3Q2dZSUtvWkl6ajBFQXd"
                "Jd0pERWkKTUNBR0ExVUVBeE1aWkc5amEyVnlMbWx2TDNCb1ltVnNhWFI2T"
                "DNOaGJYQnNaVEFlRncweU1EQXhNVE14TlRVMApORFphRncwek1EQXhNVEF"
                "4TlRVME5EWmFNQ1F4SWpBZ0JnTlZCQU1UR1dSdlkydGxjaTVwYnk5d2FHS"
                "mxiR2wwCmVpOXpZVzF3YkdVd1dUQVRCZ2NxaGtqT1BRSUJCZ2dxaGtqT1B"
                "RTUJCd05DQUFTMUhtVENzTXJiWkxJSzd0WXcKWHkwS05XQjQ1RUJMWTlac"
                "HhGd0UzOVZCMVVyZzlXVFhEaWt4YVhQMEFkQzJFTWFYNWJhVGQ2VWVROXR"
                "INkEyUQpyWThJb3pVd016QU9CZ05WSFE4QkFmOEVCQU1DQmFBd0V3WURWU"
                "jBsQkF3d0NnWUlLd1lCQlFVSEF3TXdEQVlEClZSMFRBUUgvQkFJd0FEQUt"
                "CZ2dxaGtqT1BRUURBZ05IQURCRUFpQnRLN25SMGZmc2oxRlZkNFJXeXRJM"
                "0orVG8KTkxMT0lVMXJkczArQ2IxdjRnSWdiUGt5V21heGlxQW1OeFp5bnF"
                "BVHpuN3JLQ2FWRlZKWW9XZjlqeFg1elRNPQotLS0tLUVORCBDRVJUSUZJQ"
                "0FURS0tLS0tCg=="
            ),
        },
    },
    "7c62922e6be165f1ea08252f77410152b9e4ec0d7bf4e69c1cc43f0e6c73da20": {
        "keytype": "ecdsa",
        "keyval": {
            "private": None,
            "public": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErIGdt5pelfWOSjmY7k+/T"
                "ypV0IFF9XLA+K4swhclLJb79cLoeBBDqkkUrkfhN5gxRnA//"
                "wA3amL4WXkaGsb9zQ=="
            ),
        },
    },
    "7dbacd611d5933ca3f0fad581ed233881c501229343613f63f2d4b5771ee4299": {
        "keytype": "ecdsa",
        "keyval": {
            "private": None,
            "public": (
                "MFkwEwYHKoZIzj0CAQYIKoZ"
                "Izj0DAQcDQgAEzRo/rFtBEAJLvEFU7xem34GpEswxsw6nW9YiBqbA"
                "cba6LWZuem7slTp+List+NKAVK3EzJCjUixooO5ss4Erug=="
            ),
        },
    },
    "f1997e14be3d33c5677282b6a73060d8124f4020f464644e27ab76f703eb6f7e": {
        "keytype": "ecdsa",
        "keyval": {
            "private": None,
            "public": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEMza1"
                "L1+e8vfZ1q7+GA5E0st13g7jWR7fdQSsxkdrpJ6IkUq9D"
                "6f9BUopD83YvLBMEMy20MBvsICJnXMu8IZlYA=="
            ),
        },
    },
}
root_keys_sample5 = {
    "59752a99a56142b0d0af030ed78768f313946fcfe17f153b31f6a4c3e95ba778": {
        "keytype": "ecdsa",
        "keyval": {
            "private": None,
            "public": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEnvvEn/Y3CG9ZqPxKdnPPmM"
                "LsLwc4d7+qIU6gYNC0782kyRZYm8rG2NMi45UsZm+fgrRolBezbPGrmTGT"
                "2j5EbA=="
            ),
        },
    },
    "654647b9543690aafc97f608ec604f265f01fdf05d2d488d4b3cd332a2db9d43": {
        "keytype": "ecdsa-x509",
        "keyval": {
            "private": None,
            "public": (
                "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUJqRENDQVRHZ0F3SU"
                "JBZ0lRU3FrTnV5Zk91RGkybzZ6KzJNTVAvekFLQmdncWhrak9QUVFEQWpB"
                "c01Tb3cKS0FZRFZRUURFeUZ5WldkcGMzUnllUzVsZUdGdGNHeGxMbXh2WT"
                "JGc09qVXdNREF2YzI1aGEyVXdIaGNOTVRjeApNREF4TWpJd01UUTNXaGNO"
                "TWpjd09USTVNakl3TVRRM1dqQXNNU293S0FZRFZRUURFeUZ5WldkcGMzUn"
                "llUzVsCmVHRnRjR3hsTG14dlkyRnNPalV3TURBdmMyNWhhMlV3V1RBVEJn"
                "Y3Foa2pPUFFJQkJnZ3Foa2pPUFFNQkJ3TkMKQUFRTHZpdU5raVFETzNjMU"
                "w4TDlVVU9Xajk3bGRJcEEyaVYzN3dMbFFaQk5YaHNiL0o5Z3MrVWd3aytI"
                "aHFjSApRYk13MlhxYzN0eFZkcWxhby85QzdlTDFvelV3TXpBT0JnTlZIUT"
                "hCQWY4RUJBTUNCYUF3RXdZRFZSMGxCQXd3CkNnWUlLd1lCQlFVSEF3TXdE"
                "QVlEVlIwVEFRSC9CQUl3QURBS0JnZ3Foa2pPUFFRREFnTkpBREJHQWlFQX"
                "lhUHYKcjgzNTBwNzJsQlNrM0dyOTlqTXBOUzczc2UrMlFHQ0pKemtMQTdv"
                "Q0lRRDlwUmt3YnFzemVxNVl4U2Y2YTg4ZQp5aHRXSEpmQ2lkVXFKb3pWSn"
                "diaWV3PT0KLS0tLS1FTkQgQ0VSVElGSUNBVEUtLS0tLQo="
            ),
        },
    },
    "a2ebe51f9399e25ce14fd40a1fde6e2508542d0443b3954bdb4ca5283d1cda6f": {
        "keytype": "ecdsa",
        "keyval": {
            "private": None,
            "public": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEQEg7Lk6JgVgweEaxq4Kebqkh"
                "H7QD65GKdST5I8+mJZyIpPVL+nQGOb2DX6W1Q0AN8Z3Ny/+n5oGqQfWCaXw3"
                "Zw=="
            ),
        },
    },
    "fe3d087fbca4a9f9edd21813e5eb464e7c0dcb3814a5fe21b968744a0f45f027": {
        "keytype": "ecdsa",
        "keyval": {
            "private": None,
            "public": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEN3ILa0E1/P6QB/cauouggwlZ"
                "ZwuvnOBAzAnSLJjyOZnvwIzrfrSp/E0OpoiPcKMhlVQbFQyEkhb874On6Dl1"
                "dQ=="
            ),
        },
    },
}
targets_keys = {
    "6984a67934a29955b3f969835c58ee0dd09158f5bec43726d319515b56b0a878": {
        "keytype": "ecdsa",
        "keyval": {
            "private": None,
            "public": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQ"
                "gAEEchQNiJJt4PTaEeAzaztL+TQZqTa0iM0YSf+w0LjSE"
                "lobVsYgnqIbCWe6pGX3UvcCngNw7N4uGkdVNVMS2Tslg=="
            ),
        },
    },
    "70aa109003a93131c63499c70dcfc8db3ba33ca81bdd1abcd52c067a8acc0492": {
        "keytype": "ecdsa",
        "keyval": {
            "private": None,
            "public": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE"
                "M0xl8F5nwIV3IAru1Pf85WCo4cfTOQ91jhxVaQ3xHMe"
                "W430q7R4H/tJmAXUZBe+nOTX8pgtmrLpT+Hu/H7pUhw=="
            ),
        },
    },
}
snapshot_hashes = {
    "root": {
        "hashes": {
            "sha256": "wlaYz21+0NezlHjqkldQQBf3KWtifimy07A+fOEyCTo=",
            "sha512": (
                "4SIpGMdFn0Qsmoj0lzRTUm3g/KXn6UfUhyC+y/F"
                "JEqB2lUQt4d9kb9ZfFnlxRzdvEo32afJnIDLZGYoCYAbB6g=="
            ),
        },
        "length": 2401,
    },
    "targets": {
        "hashes": {
            "sha256": "QGNOSBnOmZHpn8uefASR1xw9ZrPpr0SMW+xWvY4nSAc=",
            "sha512": (
                "XvK3cyEnTJ5URKl3lL8GYZXrtpk/yxpfZrnBq0IVVNh/"
                "OG+mfHMn9N4umNEqVSSNNjfOXd1bsgdvlAknsDXVvQ=="
            ),
        },
        "length": 1307,
    },
    "targets/chamsen": {
        "hashes": {
            "sha256": "ESFkhp4/3VgYQ4otmcgwLaR4IsmvLIGfo7VJMIxZCwY=",
            "sha512": (
                "FMJYFG6Ub4LQiB8eDF+uFNhEjHQd389F70rFLtek6"
                "K22NW0WGYJ/9W6ckWB/aqBnlI9h3ydMHlUcfc5xlHVNDg=="
            ),
        },
        "length": 521,
    },
    "targets/phbelitz": {
        "hashes": {
            "sha256": "ADiBf7StE9k0mqdAXp0o8SGQuJtXbufSZxNTKZ8hDZc=",
            "sha512": (
                "LWoqYC+44e69zluqZo5V+M77iNDycEejX/5u8FUbvib"
                "GeXDFo9UnjFHspN+kDZ3xEoDqUSq8a1J3Gew+AOn9UQ=="
            ),
        },
        "length": 521,
    },
    "targets/releases": {
        "hashes": {
            "sha256": "pNjHgtwOrSZB5l0bzHZt9u3dUdFpKsPBhWPiVrIMm88=",
            "sha512": (
                "w4IIp9GNVS1bbVRnp9T7JlMbopvuwcPYboVRe9gJW"
                "Mt0C2wUB/LWEgeKjZLyUR/4SmCwqJ4Cw+pYVqVZQycGQA=="
            ),
        },
        "length": 712,
    },
}
timestamp_hashes = {
    "snapshot": {
        "hashes": {
            "sha256": "cNXm5R+rJsc3WNQVH8M1G/cTwkO1doq5n8fQmYpQcfQ=",
            "sha512": (
                "S3w5/5XiL1TjSjxRfQhC23JDGuVn7d4Y9WGPLgucypw"
                "HPABQFEJtSjd514jiV0jjEyBrMFZXlf7MQ+syDqYBEg=="
            ),
        },
        "length": 1286,
    }
}


@pytest.fixture
def td():
    return connaisseur.trust_data


@pytest.fixture
def mock_schema_path(monkeypatch):
    def trust_init(self, data: dict, role: str):
        self.schema_path = "res/targets_schema.json"
        self.kind = role
        self._validate_schema(data)
        self.signed = data["signed"]
        self.signatures = data["signatures"]

    monkeypatch.setattr(connaisseur.trust_data.TargetsData, "__init__", trust_init)
    connaisseur.trust_data.TrustData.schema_path = "res/{}_schema.json"


@pytest.fixture
def mock_keystore(monkeypatch):
    def init(self):
        self.keys = {
            "root": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu7WMF8tCjVgeORA"
                "S2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA=="
            ),
            "7dbacd611d5933ca3f0fad581ed233881c501229343613f63f2d4b5771ee4299": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEzRo/rFtBEAJLvEFU7xem34GpEswx"
                "sw6nW9YiBqbAcba6LWZuem7slTp+List+NKAVK3EzJCjUixooO5ss4Erug=="
            ),
            "f1997e14be3d33c5677282b6a73060d8124f4020f464644e27ab76f703eb6f7e": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEMza1L1+e8vfZ1q7+GA5E0st13g7j"
                "WR7fdQSsxkdrpJ6IkUq9D6f9BUopD83YvLBMEMy20MBvsICJnXMu8IZlYA=="
            ),
            "7c62922e6be165f1ea08252f77410152b9e4ec0d7bf4e69c1cc43f0e6c73da20": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErIGdt5pelfWOSjmY7k+/TypV0IF"
                "F9XLA+K4swhclLJb79cLoeBBDqkkUrkfhN5gxRnA//wA3amL4WXkaGsb9zQ=="
            ),
            "6984a67934a29955b3f969835c58ee0dd09158f5bec43726d319515b56b0a878": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEchQNiJJt4PTaEeAzaztL+TQZqTa"
                "0iM0YSf+w0LjSElobVsYgnqIbCWe6pGX3UvcCngNw7N4uGkdVNVMS2Tslg=="
            ),
            "70aa109003a93131c63499c70dcfc8db3ba33ca81bdd1abcd52c067a8acc0492": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEM0xl8F5nwIV3IAru1Pf85WCo4cf"
                "TOQ91jhxVaQ3xHMeW430q7R4H/tJmAXUZBe+nOTX8pgtmrLpT+Hu/H7pUhw=="
            ),
            "a2ebe51f9399e25ce14fd40a1fde6e2508542d0443b3954bdb4ca5283d1cda6f": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEQEg7Lk6JgVgweEaxq4KebqkhH7Q"
                "D65GKdST5I8+mJZyIpPVL+nQGOb2DX6W1Q0AN8Z3Ny/+n5oGqQfWCaXw3Zw=="
            ),
            "fb77b27209b581031fa11e548a56bcacb617ce3ca9b15846fb146d786a6ce29c": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAExK/3GbTTNE6qG3/rByaDurVQ41D"
                "PqkYN4ge13exMeGZzRtv5fcaEHEyt4zK/bPyXpc2laxLiIHEZMU6WQYVD2A=="
            ),
        }
        self.hashes = {
            "root": ("wlaYz21+0NezlHjqkldQQBf3KWtifimy07A+fOEyCTo=", 2401),
            "snapshot": ("cNXm5R+rJsc3WNQVH8M1G/cTwkO1doq5n8fQmYpQcfQ=", 1286),
            "targets": ("QGNOSBnOmZHpn8uefASR1xw9ZrPpr0SMW+xWvY4nSAc=", 1307),
            "targets/releases": ("pNjHgtwOrSZB5l0bzHZt9u3dUdFpKsPBhWPiVrIMm88=", 712),
        }

    monkeypatch.setattr(KeyStore, "__init__", init)


def trust_data(path: str):
    with open(path, "r") as file:
        return json.load(file)


@pytest.mark.parametrize(
    "data, role, class_",
    [
        (trust_data("tests/data/sample_root.json"), "root", "RootData"),
        (trust_data("tests/data/sample_snapshot.json"), "snapshot", "SnapshotData"),
        (trust_data("tests/data/sample_timestamp.json"), "timestamp", "TimestampData"),
        (trust_data("tests/data/sample_targets.json"), "targets", "TargetsData"),
        (
            trust_data("tests/data/sample_releases.json"),
            "targets/releases",
            "TargetsData",
        ),
    ],
)
def test_trust_data(td, mock_schema_path, data: dict, role: str, class_: str):
    trust_data_ = td.TrustData(data, role)

    assert trust_data_.signed == data["signed"]
    assert trust_data_.signatures == data["signatures"]
    assert trust_data_.kind == role
    assert class_ in str(type(trust_data_))


def test_trust_data_error(td):
    with pytest.raises(NoSuchClassError) as err:
        td.TrustData({}, "trust")
    assert str(err.value) == "could not find class with name trust."


@pytest.mark.parametrize(
    "trustdata, role",
    [
        (trust_data("tests/data/sample6_root.json"), "root"),
        ([], "root"),
        ({}, "targets"),
        (trust_data("tests/data/sample3_timestamp.json"), "timestamp"),
    ],
)
def test_validate_schema_error(td, mock_schema_path, trustdata: dict, role: str):
    with pytest.raises(ValidationError) as err:
        td.TrustData(trustdata, role)
    assert "trust data has invalid format." in str(err.value)


@pytest.mark.parametrize(
    "trustdata, role",
    [
        (trust_data("tests/data/sample_root.json"), "root"),
        (trust_data("tests/data/sample_snapshot.json"), "snapshot"),
        (trust_data("tests/data/sample_timestamp.json"), "timestamp"),
        (trust_data("tests/data/sample3_targets.json"), "targets"),
        (trust_data("tests/data/sample4_targets.json"), "targets"),
        (trust_data("tests/data/sample7_targets.json"), "targets"),
        (trust_data("tests/data/sample7_snapshot.json"), "snapshot"),
    ],
)
def test_validate_schema(td, mock_schema_path, trustdata: dict, role: str):
    data = td.TrustData(trustdata, role)


@pytest.mark.parametrize(
    "data, role",
    [
        (trust_data("tests/data/sample_root.json"), "root"),
        (trust_data("tests/data/sample_snapshot.json"), "snapshot"),
        (trust_data("tests/data/sample_timestamp.json"), "timestamp"),
        (trust_data("tests/data/sample_targets.json"), "targets"),
        (trust_data("tests/data/sample_releases.json"), "targets/releases"),
    ],
)
def test_validate_signature(td, mock_schema_path, mock_keystore, data: dict, role: str):
    ks = KeyStore()
    trust_data_ = td.TrustData(data, role)
    assert trust_data_.validate_signature(ks) is None


def test_validate_signature_error(td, mock_schema_path, mock_keystore):
    data = trust_data("tests/data/sample_root.json")
    data["signatures"][0]["sig"] = "Q" + data["signatures"][0]["sig"][1:]
    trust_data_ = td.TrustData(data, "root")
    ks = KeyStore()

    with pytest.raises(ValidationError) as err:
        trust_data_.validate_signature(ks)
    assert "failed to verify signature of trust data." in str(err.value)


@pytest.mark.parametrize(
    "data, role",
    [
        (trust_data("tests/data/sample_root.json"), "root"),
        (trust_data("tests/data/sample_snapshot.json"), "snapshot"),
        (trust_data("tests/data/sample_timestamp.json"), "timestamp"),
        (trust_data("tests/data/sample_targets.json"), "targets"),
        (trust_data("tests/data/sample_releases.json"), "targets/releases"),
    ],
)
def test_validate_hash(td, mock_schema_path, mock_keystore, data: dict, role: str):
    ks = KeyStore()
    trust_data_ = td.TrustData(data, role)
    assert trust_data_.validate_hash(ks) is None


def test_validate_hash_error(td, mock_schema_path, mock_keystore):
    data = trust_data("tests/data/sample_root.json")
    data["signatures"][0]["sig"] = "Q" + data["signatures"][0]["sig"][1:]
    trust_data_ = td.TrustData(data, "root")
    ks = KeyStore()

    with pytest.raises(ValidationError) as err:
        trust_data_.validate_hash(ks)
    assert "failed validating trust data hash." in str(err.value)


@pytest.mark.parametrize(
    "data, role",
    [
        (trust_data("tests/data/sample_snapshot.json"), "snapshot"),
        (trust_data("tests/data/sample_timestamp.json"), "timestamp"),
        (trust_data("tests/data/sample4_targets.json"), "targets"),
    ],
)
def test_validate_trust_data_expiry(td, mock_schema_path, data: dict, role: str):
    trust_data_ = td.TrustData(data, role)
    time = dt.datetime.now(pytz.utc) + dt.timedelta(hours=1)
    time_format = "%Y-%m-%dT%H:%M:%S.%f%z"
    trust_data_.signed["expires"] = time.strftime(time_format)

    assert trust_data_.validate_expiry() is None


@pytest.mark.parametrize(
    "data, role",
    [(trust_data("tests/data/sample_timestamp.json"), "timestamp")],
)
def test_validate_trust_data_expiry_error(td, mock_schema_path, data: dict, role: str):
    trust_data_ = td.TrustData(data, role)
    time = dt.datetime.now(pytz.utc) - dt.timedelta(hours=1)
    time_format = "%Y-%m-%dT%H:%M:%S.%f%z"
    trust_data_.signed["expires"] = time.strftime(time_format)

    with pytest.raises(ValidationError) as err:
        trust_data_.validate_expiry()
    assert "trust data expired." in str(err.value)


@pytest.mark.parametrize(
    "data, role, keys",
    [
        (trust_data("tests/data/sample_root.json"), "root", root_keys),
        (trust_data("tests/data/sample_snapshot.json"), "snapshot", {}),
        (trust_data("tests/data/sample_timestamp.json"), "timestamp", {}),
        (trust_data("tests/data/sample_targets.json"), "targets", targets_keys),
        (trust_data("tests/data/sample_releases.json"), "targets/releases", {}),
        (trust_data("tests/data/sample5_root.json"), "root", root_keys_sample5),
    ],
)
def test_get_keys(td, mock_schema_path, data: dict, role: str, keys: dict):
    trust_data_ = td.TrustData(data, role)
    assert trust_data_.get_keys() == keys


@pytest.mark.parametrize(
    "data, role, hashes",
    [
        (trust_data("tests/data/sample_root.json"), "root", {}),
        (trust_data("tests/data/sample_snapshot.json"), "snapshot", snapshot_hashes),
        (trust_data("tests/data/sample_timestamp.json"), "timestamp", timestamp_hashes),
        (trust_data("tests/data/sample_targets.json"), "targets", {}),
        (trust_data("tests/data/sample_releases.json"), "targets/releases", {}),
    ],
)
def test_get_hashes(td, mock_schema_path, data: dict, role: str, hashes: dict):
    trust_data_ = td.TrustData(data, role)
    assert trust_data_.get_hashes() == hashes


@pytest.mark.parametrize(
    "data, out",
    [
        (trust_data("tests/data/sample_targets.json"), True),
        (trust_data("tests/data/sample2_targets.json"), False),
    ],
)
def test_has_delegation(td, mock_schema_path, data: dict, out: bool):
    trust_data_ = td.TrustData(data, "targets")
    assert trust_data_.has_delegations() == out


@pytest.mark.parametrize(
    "data, out",
    [
        (
            trust_data("tests/data/sample_targets.json"),
            ["targets/phbelitz", "targets/releases", "targets/chamsen"],
        ),
        (trust_data("tests/data/sample2_targets.json"), []),
    ],
)
def test_get_delegations(td, mock_schema_path, data: dict, out: list):
    trust_data = td.TrustData(data, "targets")
    assert trust_data.get_delegations() == out


@pytest.mark.parametrize(
    "data, out",
    [
        (trust_data("tests/data/sample_targets.json"), []),
        (trust_data("tests/data/sample2_targets.json"), ["hai"]),
        (
            trust_data("tests/data/sample3_targets.json"),
            ["v1.0.9", "v1.0.9-slim-fat_image", "v382"],
        ),
    ],
)
def test_get_tags(td, mock_schema_path, data: dict, out: list):
    trust_data = td.TrustData(data, "targets")
    assert list(trust_data.get_tags()) == out


@pytest.mark.parametrize(
    "data, tag, digest",
    [
        (
            trust_data("tests/data/sample2_targets.json"),
            "hai",
            "kZGRnKhqiPDULOLq2jx8VFuSvl7n+x8jpWHoFNx4uMI=",
        ),
        (
            trust_data("tests/data/sample_releases.json"),
            "v1",
            "E4irx6ElMoNsOoG9sAh0CbFSCPWuunqHrtz9VtY3wUU=",
        ),
        (
            trust_data("tests/data/sample_releases.json"),
            "v2",
            "uKOFIodqniVQ1YLOUaHYfr3GxXDl5YXQhWC/1kb3+AQ=",
        ),
        (
            trust_data("tests/data/sample3_targets.json"),
            "v1.0.9-slim-fat_image",
            "VI55/vvzrpsAqPDn1nClK32rr5DYwz41SF7TsoFnGbQ=",
        ),
    ],
)
def test_get_digest(td, mock_schema_path, data: dict, tag: str, digest: str):
    trust_data = td.TrustData(data, "targets")
    assert trust_data.get_digest(tag) == digest


def test_get_digest_error(td, mock_schema_path):
    _trust_data = td.TrustData(trust_data("tests/data/sample2_targets.json"), "targets")
    with pytest.raises(NotFoundException) as err:
        _trust_data.get_digest("hurr")
    assert 'could not find digest for tag "hurr".' in str(err.value)


# This test will fail in January 2023 due to the expiry date in the test data
# TODO: Autogenerate test data with "up-to-date" expiry dates
@pytest.mark.parametrize(
    "data, role", [(trust_data("tests/data/sample_snapshot.json"), "snapshot")]
)
def test_validate(td, mock_schema_path, mock_keystore, data: dict, role: str):
    ks = KeyStore()
    _trust_data = td.TrustData(data, role)
    _trust_data.validate(ks)


@pytest.mark.parametrize(
    "data, role",
    [
        (trust_data("tests/data/sample_timestamp.json"), "timestamp"),
        (trust_data("tests/data/sample5_targets.json"), "targets"),
    ],
)
def test_validate_for_expiry_error(
    td, mock_schema_path, mock_keystore, data: dict, role: str
):
    ks = KeyStore()
    _trust_data = td.TrustData(data, role)
    with pytest.raises(ValidationError) as err:
        _trust_data.validate(ks)
    assert "trust data expired." in str(err.value)


@pytest.mark.parametrize(
    "data, role", [(trust_data("tests/data/sample4_targets.json"), "targets")]
)
def test_validation_for_missing_key_error(
    td, mock_schema_path, mock_keystore, data: dict, role: str
):
    ks = KeyStore()
    _trust_data = td.TrustData(data, role)
    with pytest.raises(NotFoundException) as err:
        _trust_data.validate(ks)
    assert "could not find key id" in str(err.value)


@pytest.mark.parametrize(
    "data, role", [(trust_data("tests/data/sample3_targets.json"), "targets")]
)
def test_validation_for_signature_validation_error(
    td, mock_schema_path, mock_keystore, data: dict, role: str
):
    ks = KeyStore()
    _trust_data = td.TrustData(data, role)
    with pytest.raises(ValidationError) as err:
        _trust_data.validate(ks)
    assert "failed to verify signature of trust data." in str(err.value)
