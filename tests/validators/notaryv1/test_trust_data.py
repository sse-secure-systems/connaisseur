import pytest
import json
import pytz
import datetime as dt
from ... import conftest as fix
import connaisseur.validators.notaryv1.trust_data as td
import connaisseur.exceptions as exc
from connaisseur.trust_root import TrustRoot

pub_root_keys = {
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
pub_root_keys_sample5 = {
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


@pytest.mark.parametrize(
    "data, role, class_, exception",
    [
        (fix.get_td("sample_root"), "root", "RootData", fix.no_exc()),
        (fix.get_td("sample_snapshot"), "snapshot", "SnapshotData", fix.no_exc()),
        (fix.get_td("sample_timestamp"), "timestamp", "TimestampData", fix.no_exc()),
        (fix.get_td("sample_targets"), "targets", "TargetsData", fix.no_exc()),
        (
            fix.get_td("sample_releases"),
            "targets/releases",
            "TargetsData",
            fix.no_exc(),
        ),
        ({}, "noclass", "", pytest.raises(exc.NoSuchClassError)),
        (
            fix.get_td("missing_keys_root"),
            "root",
            "RootData",
            pytest.raises(exc.InvalidTrustDataFormatError),
        ),
        ([], "root", "RootData", pytest.raises(exc.InvalidTrustDataFormatError)),
        ({}, "targets", "TargetsData", pytest.raises(exc.InvalidTrustDataFormatError)),
        (
            fix.get_td("wrong_time_timestamp"),
            "timestamp",
            "TimestampData",
            pytest.raises(exc.InvalidTrustDataFormatError),
        ),
        (fix.get_td("sample3_targets"), "targets", "TargetsData", fix.no_exc()),
        (fix.get_td("sample4_targets"), "targets", "TargetsData", fix.no_exc()),
        (fix.get_td("sample7_targets"), "targets", "TargetsData", fix.no_exc()),
        (fix.get_td("sample7_snapshot"), "snapshot", "SnapshotData", fix.no_exc()),
    ],
)
def test_trust_data_init(m_trust_data, data: dict, role: str, class_: str, exception):
    with exception:
        trust_data_ = td.TrustData(data, role)
        assert trust_data_.signed == data["signed"]
        assert trust_data_.signatures == data["signatures"]
        assert trust_data_.kind == role
        assert class_ in str(type(trust_data_))


@pytest.mark.parametrize(
    "data, role, exception",
    [
        (fix.get_td("sample_root"), "root", fix.no_exc()),
        (fix.get_td("sample_snapshot"), "snapshot", fix.no_exc()),
        (fix.get_td("sample_timestamp"), "timestamp", fix.no_exc()),
        (fix.get_td("sample_targets"), "targets", fix.no_exc()),
        (fix.get_td("sample_releases"), "targets/releases", fix.no_exc()),
        (fix.get_td("wrong_signature"), "root", pytest.raises(exc.ValidationError)),
        (
            fix.get_td("sample3_targets"),
            "targets",
            pytest.raises(exc.NotFoundException),
        ),
    ],
)
def test_validate_signature(
    m_trust_data, sample_key_store, data: dict, role: str, exception
):
    with exception:
        trust_data_ = td.TrustData(data, role)
        assert trust_data_.validate_signature(sample_key_store) is None


@pytest.mark.parametrize(
    "signature, payload, key, exception",
    [
        (
            (
                "hx/VtTJT2r1nmkHtPZacncvosKca4XnLbMxNmeuH0cw5sTsUsznRuZ"
                "mgd4vKPaQUbnCA3RMQpNlaGRWz1TR8CQ=="
            ),
            "iliketurtles",
            TrustRoot(
                (
                    "-----BEGIN PUBLIC KEY-----\n"
                    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEi2WD/E/UXF4+yoE5e4cjpJMNgQw\n"
                    "8PAVALRX+8f8I8B+XneAtnOHDTI8L6wBeFRTzl6G4OmgDyCRYTb5MV3hog==\n"
                    "-----END PUBLIC KEY-----"
                )
            ),
            fix.no_exc(),
        ),
        (
            "",
            "",
            TrustRoot("mail@example.com"),
            pytest.raises(exc.WrongKeyError),
        ),
    ],
)
def test_validate_signature_with_key(
    signature: str, payload: str, key: TrustRoot, exception
):
    with exception:
        assert (
            td.TrustData._TrustData__validate_signature_with_key(
                signature, payload, key
            )
            is True
        )


@pytest.mark.parametrize(
    "signature, payload, key, exception",
    [
        (
            (
                "hx/VtTJT2r1nmkHtPZacncvosKca4XnLbMxNmeuH0cw5sTsUsznRuZ"
                "mgd4vKPaQUbnCA3RMQpNlaGRWz1TR8CQ=="
            ),
            "iliketurtles",
            TrustRoot(
                (
                    "-----BEGIN PUBLIC KEY-----\n"
                    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEi2WD/E/UXF4+yoE5e4cjpJMNgQw\n"
                    "8PAVALRX+8f8I8B+XneAtnOHDTI8L6wBeFRTzl6G4OmgDyCRYTb5MV3hog==\n"
                    "-----END PUBLIC KEY-----"
                )
            ),
            fix.no_exc(),
        ),
        (
            (
                "hx/VtTJT2r1nmkHtPZacncvosKca4XnLbMxNmeuH0cw5sTsUsznRuZ"
                "mgd4vKPaQUbnCA3RMQpNlaGRWz1TR8CM=="
            ),
            "iliketurtles",
            TrustRoot(
                (
                    "-----BEGIN PUBLIC KEY-----\n"
                    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEi2WD/E/UXF4+yoE5e4cjpJMNgQw\n"
                    "8PAVALRX+8f8I8B+XneAtnOHDTI8L6wBeFRTzl6G4OmgDyCRYTb5MV3hog==\n"
                    "-----END PUBLIC KEY-----"
                )
            ),
            pytest.raises(Exception),
        ),
    ],
)
def test_validate_signature_with_ecdsa(
    signature: str, payload: str, key: TrustRoot, exception
):
    with exception:
        assert (
            td.TrustData._TrustData__validate_signature_with_ecdsa(
                signature, payload, key
            )
            is True
        )


@pytest.mark.parametrize(
    "data, role, exception",
    [
        (fix.get_td("sample_root"), "root", fix.no_exc()),
        (fix.get_td("sample_snapshot"), "snapshot", fix.no_exc()),
        (fix.get_td("sample_timestamp"), "timestamp", fix.no_exc()),
        (fix.get_td("sample_targets"), "targets", fix.no_exc()),
        (fix.get_td("sample_releases"), "targets/releases", fix.no_exc()),
        (fix.get_td("sample3_targets"), "targets", pytest.raises(exc.ValidationError)),
    ],
)
def test_validate_hash(
    m_trust_data, sample_key_store, data: dict, role: str, exception
):
    with exception:
        trust_data_ = td.TrustData(data, role)
        assert trust_data_.validate_hash(sample_key_store) is None


@pytest.mark.parametrize(
    "data, role, delta, exception",
    [
        (fix.get_td("sample_snapshot"), "snapshot", 1, fix.no_exc()),
        (fix.get_td("sample_timestamp"), "timestamp", 1, fix.no_exc()),
        (fix.get_td("sample4_targets"), "targets", 1, fix.no_exc()),
        (
            fix.get_td("sample4_targets"),
            "targets",
            -1,
            pytest.raises(exc.ValidationError),
        ),
    ],
)
def test_validate_trust_data_expiry(m_trust_data, data, role, delta, exception):
    with exception:
        trust_data_ = td.TrustData(data, role)
        time = dt.datetime.now(pytz.utc) + dt.timedelta(hours=delta)
        time_format = "%Y-%m-%dT%H:%M:%S.%f%z"
        trust_data_.signed["expires"] = time.strftime(time_format)

        assert trust_data_.validate_expiry() is None


@pytest.mark.parametrize(
    "data, role, keys",
    [
        (fix.get_td("sample_root"), "root", pub_root_keys),
        (fix.get_td("sample_snapshot"), "snapshot", {}),
        (fix.get_td("sample_timestamp"), "timestamp", {}),
        (fix.get_td("sample_targets"), "targets", targets_keys),
        (fix.get_td("sample_releases"), "targets/releases", {}),
        (fix.get_td("sample5_root"), "root", pub_root_keys_sample5),
    ],
)
def test_get_keys(m_trust_data, data: dict, role: str, keys: dict):
    trust_data_ = td.TrustData(data, role)
    assert trust_data_.get_keys() == keys


@pytest.mark.parametrize(
    "data, role, hashes",
    [
        (fix.get_td("sample_root"), "root", {}),
        (fix.get_td("sample_snapshot"), "snapshot", snapshot_hashes),
        (fix.get_td("sample_timestamp"), "timestamp", timestamp_hashes),
        (fix.get_td("sample_targets"), "targets", {}),
        (fix.get_td("sample_releases"), "targets/releases", {}),
    ],
)
def test_get_hashes(m_trust_data, data: dict, role: str, hashes: dict):
    trust_data_ = td.TrustData(data, role)
    assert trust_data_.get_hashes() == hashes


@pytest.mark.parametrize(
    "data, out",
    [
        (fix.get_td("sample_targets"), True),
        (fix.get_td("sample2_targets"), False),
    ],
)
def test_has_delegation(m_trust_data, data: dict, out: bool):
    trust_data_ = td.TrustData(data, "targets")
    assert trust_data_.has_delegations() == out


@pytest.mark.parametrize(
    "data, out",
    [
        (
            fix.get_td("sample_targets"),
            ["targets/phbelitz", "targets/releases", "targets/chamsen"],
        ),
        (fix.get_td("sample2_targets"), []),
    ],
)
def test_get_delegations(m_trust_data, data: dict, out: list):
    trust_data = td.TrustData(data, "targets")
    assert trust_data.get_delegations() == out


@pytest.mark.parametrize(
    "data, out",
    [
        (fix.get_td("sample_targets"), []),
        (fix.get_td("sample2_targets"), ["hai"]),
        (
            fix.get_td("sample3_targets"),
            ["v1.0.9", "v1.0.9-slim-fat_image", "v382"],
        ),
    ],
)
def test_get_tags(m_trust_data, data: dict, out: list):
    trust_data = td.TrustData(data, "targets")
    assert list(trust_data.get_tags()) == out


@pytest.mark.parametrize(
    "data, tag, digest, exception",
    [
        (
            fix.get_td("sample2_targets"),
            "hai",
            "kZGRnKhqiPDULOLq2jx8VFuSvl7n+x8jpWHoFNx4uMI=",
            fix.no_exc(),
        ),
        (
            fix.get_td("sample_releases"),
            "v1",
            "E4irx6ElMoNsOoG9sAh0CbFSCPWuunqHrtz9VtY3wUU=",
            fix.no_exc(),
        ),
        (
            fix.get_td("sample_releases"),
            "v2",
            "uKOFIodqniVQ1YLOUaHYfr3GxXDl5YXQhWC/1kb3+AQ=",
            fix.no_exc(),
        ),
        (
            fix.get_td("sample3_targets"),
            "v1.0.9-slim-fat_image",
            "VI55/vvzrpsAqPDn1nClK32rr5DYwz41SF7TsoFnGbQ=",
            fix.no_exc(),
        ),
        (
            fix.get_td("sample2_targets"),
            "missingtag",
            "",
            pytest.raises(exc.NotFoundException),
        ),
    ],
)
def test_get_digest(m_trust_data, data: dict, tag: str, digest: str, exception):
    with exception:
        trust_data = td.TrustData(data, "targets")
        assert trust_data.get_digest(tag) == digest


# # This test will fail in January 2023 due to the expiry date in the test data
# # TODO: Autogenerate test data with "up-to-date" expiry dates
@pytest.mark.parametrize("data, role", [(fix.get_td("sample_snapshot"), "snapshot")])
def test_validate(m_trust_data, sample_key_store, data: dict, role: str):
    _trust_data = td.TrustData(data, role)
    _trust_data.validate(sample_key_store)
