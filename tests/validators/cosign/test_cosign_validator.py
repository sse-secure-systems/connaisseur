import pytest
import pytest_subprocess
import subprocess
from ... import conftest as fix
from connaisseur.image import Image
import connaisseur.validators.cosign.cosign_validator as co
import connaisseur.exceptions as exc
from connaisseur.trust_root import TrustRoot

example_key = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXb"
    "ZhEfTYb4Mnb/LdrtXKTIIbzNBp8mwriocbaxXxzqu"
    "vbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ=="
)
example_key2 = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEOXYta5TgdCwXTCnLU09W5T4M4r9f"
    "QQrqJuADP6U7g5r9ICgPSmZuRHP/1AYUfOQW3baveKsT969EfELKj1lfCA=="
)

static_cosigns = [
    {
        "name": "cosign1",
        "type": "cosign",
        "trust_roots": [
            {
                "name": "default",
                "key": example_key,
            },
            {"name": "test", "key": example_key2},
        ],
    },
    {
        "name": "cosign2",
        "type": "cosign",
        "trust_roots": [
            {
                "name": "test",
                "key": "...",
            },
        ],
        "auth": {"k8s_keychain": True},
        "host": "https://rekor.instance.com",
    },
    {
        "name": "cosign1",
        "type": "cosign",
        "trust_roots": [
            {"name": "megatest", "key": "..."},
            {"name": "test", "key": "..."},
        ],
        "auth": {"k8s_keychain": False},
        "host": "http://foo.bar",
    },
    {
        "name": "cosign1",
        "type": "cosign",
        "trust_roots": [],
        "auth": {"secret_name": "my-secret"},
        "host": "rekor.tlog.xyz",
    },
    {
        "name": "cosign1",
        "type": "cosign",
        "trust_roots": [
            {
                "name": "test1",
                "key": example_key,
            },
            {"name": "test2", "key": example_key2},
            {"name": "test3", "key": example_key2},
        ],
    },
    {
        "name": "cosign1",
        "type": "cosign",
        "host": "rekor.sigstore.dev",
        "trust_roots": [
            {
                "name": "default",
                "key": example_key,
            }
        ],
    },
]

digest1 = "c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"


class testerr:
    message = "some error occurred"


cosign_payload = '{"critical":{"identity":{"docker-reference":""},"image":{"docker-manifest-digest":"sha256:c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"},"Type":"cosign container signature"},"Optional":null}'
cosign_multiline_payload = """
{"critical":{"identity":{"docker-reference":""},"image":{"docker-manifest-digest":"sha256:2f6d89c49ad745bfd5d997f9b2d253329323da4c500c7fe343e068c0382b8df4"},"Type":"cosign container signature"},"Optional":null}
{"critical":{"identity":{"docker-reference":""},"image":{"docker-manifest-digest":"sha256:2f6d89c49ad745bfd5d997f9b2d253329323da4c500c7fe343e068c0382b8df4"},"Type":"cosign container signature"},"Optional":{"foo":"bar"}}
"""
cosign_payload_unexpected_json_format = '{"Important":{"identity":{"docker-reference":""},"image":{"docker-manifest-digest":"sha256:c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"},"Type":"cosign container signature"},"Optional":null}'
cosign_payload_unexpected_digest_pattern = '{"critical":{"identity":{"docker-reference":""},"image":{"docker-manifest-digest":"sha512:c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"},"Type":"cosign container signature"},"Optional":null}'

cosign_nonjson_payload = "This is not json."
cosign_combined_payload = "{}\n{}".format(cosign_payload, cosign_nonjson_payload)

example_pubkey = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXbZhEfTYb4Mnb/LdrtXKTIIbzNBp8mwriocbaxXxzquvbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ=="

cosign_stderr_at_success = """
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
  - Any certificates were verified against the Fulcio roots.
"""


def gen_vals(static_cosign, root_no: list = None, digest=None, error=None):
    if root_no is None:
        root_no = range(len(static_cosign["trust_roots"]))

    if not isinstance(digest, list):
        digest = [digest] * len(static_cosign["trust_roots"])

    return {
        static_cosign["trust_roots"][num]["name"]: {
            "name": static_cosign["trust_roots"][num]["name"],
            "trust_root": TrustRoot("".join(static_cosign["trust_roots"][num]["key"])),
            "digest": digest[num],
            "error": error,
        }
        for num in root_no
    }


def str_vals(vals):
    for k in vals.keys():
        vals[k]["trust_root"] = str(vals[k]["trust_root"])
    return vals


@pytest.fixture()
def mock_invoke_cosign(mocker, status_code, stdout, stderr):
    mocker.patch(
        (
            "connaisseur.validators.cosign.cosign_validator."
            "CosignValidator._CosignValidator__invoke_cosign"
        ),
        return_value=(status_code, stdout, stderr),
    )


@pytest.fixture()
def mock_add_kill_fake_process(monkeypatch):
    def mock_kill(self):
        return

    pytest_subprocess.fake_popen.FakePopen.kill = mock_kill


@pytest.mark.parametrize(
    "index, kchain, host",
    [
        (0, False, None),
        (1, True, "https://rekor.instance.com"),
        (2, False, "http://foo.bar"),
        (3, False, "https://rekor.tlog.xyz"),
    ],
)
def test_init(index: int, kchain: bool, host: str):
    val = co.CosignValidator(**static_cosigns[index])
    assert val.name == static_cosigns[index]["name"]
    assert val.trust_roots == static_cosigns[index]["trust_roots"]
    assert val.k8s_keychain == kchain
    assert val.rekor_url == host


@pytest.mark.parametrize(
    "index, key_name, required, threshold, key, exception",
    [
        (
            0,
            None,
            [],
            1,
            gen_vals(static_cosigns[0], [0]),
            fix.no_exc(),
        ),
        (
            0,
            "test",
            [],
            1,
            gen_vals(static_cosigns[0], [1]),
            fix.no_exc(),
        ),
        (
            0,
            "non_existing",
            [],
            1,
            None,
            pytest.raises(
                exc.NotFoundException, match=r'.*Trust roots "non_existing.*'
            ),
        ),
        (
            2,
            None,
            [],
            1,
            None,
            pytest.raises(exc.NotFoundException, match=r'.*Trust roots "default".*'),
        ),
        (
            4,
            "*",
            [],
            len(static_cosigns[4]["trust_roots"]),
            gen_vals(static_cosigns[4], range(3)),
            fix.no_exc(),
        ),
        (
            4,
            "*",
            ["test1", "non_existent"],
            1,
            None,
            pytest.raises(
                exc.NotFoundException, match=r'.*Trust roots "non_existent".*'
            ),
        ),
        (
            4,
            "*",
            ["test1", "non_existent", "another_nonexistent"],
            1,
            None,
            pytest.raises(
                exc.NotFoundException,
                match=r'.*Trust roots "(another_nonexistent, non_existent|non_existent, another_nonexistent)".*',
            ),
        ),
    ],
)
def test_get_pinned_keys(
    index: int, key_name: str, required: list, threshold: int, key: str, exception
):
    with exception:
        val = co.CosignValidator(**static_cosigns[index])
        assert str_vals(
            val._CosignValidator__get_pinned_trust_roots(key_name, required, threshold)
        ) == str_vals(key)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "index, status_code, stdout, stderr, image, trust_root, digest, exception",
    [
        (
            0,
            0,
            cosign_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            None,
            "c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7",
            fix.no_exc(),
        ),
        (
            0,
            0,
            cosign_multiline_payload,
            cosign_stderr_at_success,
            "",
            None,
            "2f6d89c49ad745bfd5d997f9b2d253329323da4c500c7fe343e068c0382b8df4",
            fix.no_exc(),
        ),
        (
            4,
            0,
            cosign_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            "*",
            "c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7",
            fix.no_exc(),
        ),
        (
            0,
            1,
            cosign_payload,
            "raises unexpected cosign exception",
            "testimage:v1",
            None,
            "2f6d89c49ad745bfd5d997f9b2d253329323da4c500c7fe343e068c0382b8df4",
            pytest.raises(exc.CosignError),
        ),
    ],
)
async def test_validate(
    mock_invoke_cosign,
    index,
    status_code,
    stdout,
    stderr,
    image,
    trust_root,
    digest,
    exception,
):
    with exception:
        assert (
            await co.CosignValidator(**static_cosigns[index]).validate(
                image, trust_root
            )
            == digest
        )


@pytest.mark.parametrize(
    "status_code, stdout, stderr, image, output, exception",
    [
        (
            0,
            cosign_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            ["c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"],
            fix.no_exc(),
        ),
        (
            0,
            cosign_combined_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            ["c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"],
            fix.no_exc(),
        ),
        (
            0,
            cosign_multiline_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            [
                "2f6d89c49ad745bfd5d997f9b2d253329323da4c500c7fe343e068c0382b8df4",
                "2f6d89c49ad745bfd5d997f9b2d253329323da4c500c7fe343e068c0382b8df4",
            ],
            fix.no_exc(),
        ),
        (
            1,
            "",
            fix.get_cosign_err_msg("wrong_key"),
            "testimage:v1",
            [],
            pytest.raises(exc.ValidationError, match=r".*signature of trust data.*"),
        ),
        (
            0,
            cosign_payload_unexpected_json_format,
            cosign_stderr_at_success,
            "testimage:v1",
            [],
            pytest.raises(exc.UnexpectedCosignData, match=r".*KeyError.*"),
        ),
        (
            0,
            cosign_payload_unexpected_digest_pattern,
            cosign_stderr_at_success,
            "testimage:v1",
            [],
            pytest.raises(exc.UnexpectedCosignData, match=r".*Exception.*"),
        ),
        (
            0,
            cosign_nonjson_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            [],
            pytest.raises(exc.UnexpectedCosignData, match=r".*extract.*"),
        ),
        (
            1,
            "",
            fix.get_cosign_err_msg("no_data"),
            "testimage:v1",
            [],
            pytest.raises(exc.NotFoundException),
        ),
        (
            1,
            "",
            fix.get_cosign_err_msg("does_not_exist"),
            "testimage:v1",
            [],
            pytest.raises(exc.NotFoundException),
        ),
        (
            1,
            "",
            "Hm. Something weird happened.",
            "testimage:v1",
            [],
            pytest.raises(exc.CosignError),
        ),
        (
            1,
            "",
            fix.get_cosign_err_msg("notfound_in_tl"),
            "testimage:v1",
            [],
            pytest.raises(exc.ValidationError, match=r".*transparency log.*"),
        ),
    ],
)
def test_get_cosign_validated_digests(
    mock_invoke_cosign, status_code, stdout, stderr, image, output, exception
):
    with exception:
        val = co.CosignValidator(**static_cosigns[0])
        digest = val._CosignValidator__get_cosign_validated_digests(
            image, gen_vals(static_cosigns[0], [0])["default"]
        )
        assert digest == output.pop()


@pytest.mark.parametrize(
    "image, key, process_input, exception",
    [
        (
            "testimage:v1",
            example_key,
            {
                "option_kword": "--key",
                "inline_tr": "/dev/stdin",
                "trust_root": (
                    b"-----BEGIN PUBLIC KEY-----\n"
                    b"MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXbZhEfTYb4Mnb/LdrtXKTIIbz\n"
                    b"NBp8mwriocbaxXxzquvbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ==\n"
                    b"-----END PUBLIC KEY-----\n"
                ),
            },
            fix.no_exc(),
        ),
        (
            "testimage:v1",
            "k8s://example_ns/example_key",
            {
                "option_kword": "--key",
                "inline_tr": "k8s://example_ns/example_key",
            },
            fix.no_exc(),
        ),
        (
            "testimage:v1",
            "mail@example.com",
            {"option_kword": "", "inline_tr": ""},
            pytest.raises(exc.WrongKeyError),
        ),
    ],
)
def test_validate_using_key(fake_process, image, key, process_input, exception):
    def stdin_function(input):
        return {"stderr": input.decode(), "stdout": input}

    # as we are mocking the subprocess the output doesn't change with the input. To check that the
    # <process>.communicate() method is invoked with the correct input, we append it to stderr as explained in the docs
    # https://pytest-subprocess.readthedocs.io/en/latest/usage.html#passing-input
    # It seems there is a bug that, when appending the input to a data stream (e.g. stderr),
    # eats the other data stream (stdout in that case). Thus, simply appending to both.

    im = Image(image)
    fake_process_calls = [
        "/app/cosign/cosign",
        "verify",
        "--output",
        "text",
        process_input["option_kword"],
        process_input["inline_tr"],
        *[],
        str(im),
    ]
    fake_process.register_subprocess(
        fake_process_calls,
        stderr=cosign_stderr_at_success,
        stdout=bytes(cosign_payload, "utf-8"),
        stdin_callable=stdin_function,
    )
    config = static_cosigns[0].copy()
    val = co.CosignValidator(**config)
    with exception:
        returncode, stdout, stderr = val._CosignValidator__validate_using_trust_root(
            im, TrustRoot(key)
        )
        assert fake_process_calls in fake_process.calls
        assert (returncode, stdout, stderr) == (
            0,
            "{}{}".format(
                cosign_payload, process_input.get("trust_root", b"").decode()
            ),
            "{}{}".format(
                cosign_stderr_at_success, process_input.get("trust_root", b"").decode()
            ),
        )


@pytest.mark.parametrize(
    "image, process_input, k8s_keychain, host",
    [
        (
            "testimage:v1",
            {
                "option_kword": "--key",
                "inline_tr": "/dev/stdin",
                "trust_root": (
                    b"-----BEGIN PUBLIC KEY-----\n"
                    b"MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXbZhEfTYb4Mnb/LdrtXKTIIbz\n"
                    b"NBp8mwriocbaxXxzquvbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ==\n"
                    b"-----END PUBLIC KEY-----\n"
                ),
            },
            False,
            None,
        ),
        (
            "testimage:v1",
            {
                "option_kword": "--key",
                "inline_tr": "k8s://connaisseur/test_key",
            },
            False,
            None,
        ),
        (
            "testimage:v1",
            {
                "option_kword": "--key",
                "inline_tr": "k8s://connaisseur/test_key",
            },
            False,
            "https://rekor.sigstore.dev",
        ),
    ],
)
def test_invoke_cosign(fake_process, image, process_input, k8s_keychain, host):
    def stdin_function(input):
        return {"stderr": input.decode(), "stdout": input}

    # as we are mocking the subprocess the output doesn't change with the input. To check that the
    # <process>.communicate() method is invoked with the correct input, we append it to stderr as explained in the docs
    # https://pytest-subprocess.readthedocs.io/en/latest/usage.html#passing-input
    # It seems there is a bug that, when appending the input to a data stream (e.g. stderr),
    # eats the other data stream (stdout in that case). Thus, simply appending to both.
    im = Image(image)
    fake_process_calls = [
        "/app/cosign/cosign",
        "verify",
        "--output",
        "text",
        process_input["option_kword"],
        process_input["inline_tr"],
        *(["--k8s-keychain"] if k8s_keychain else []),
        *(["--rekor-url", host] if host else []),
        str(im),
    ]
    fake_process.register_subprocess(
        fake_process_calls,
        stderr=cosign_stderr_at_success,
        stdout=bytes(cosign_payload, "utf-8"),
        stdin_callable=stdin_function,
    )
    config = static_cosigns[0].copy()
    config["auth"] = {"k8s_keychain": k8s_keychain}
    if host:
        config["host"] = host
    val = co.CosignValidator(**config)
    returncode, stdout, stderr = val._CosignValidator__invoke_cosign(im, process_input)
    assert fake_process_calls in fake_process.calls
    assert (returncode, stdout, stderr) == (
        0,
        "{}{}".format(cosign_payload, process_input.get("trust_root", b"").decode()),
        "{}{}".format(
            cosign_stderr_at_success, process_input.get("trust_root", b"").decode()
        ),
    )


@pytest.mark.parametrize(
    "image",
    [
        "testimage:v1",
    ],
)
def test_invoke_cosign_timeout_expired(
    mocker, mock_add_kill_fake_process, fake_process, image
):
    def callback_function(input):
        fake_process.register_subprocess(["test"], wait=0.5)
        fake_process_raising_timeout = subprocess.Popen(["test"])
        fake_process_raising_timeout.wait(timeout=0.1)

    fake_process.register_subprocess(
        [
            "/app/cosign/cosign",
            "verify",
            "--output",
            "text",
            "--key",
            "/dev/stdin",
            image,
        ],
        stdin_callable=callback_function,
    )

    mock_kill = mocker.patch("pytest_subprocess.fake_popen.FakePopen.kill")

    with pytest.raises(exc.CosignTimeout) as err:
        co.CosignValidator(**static_cosigns[0])._CosignValidator__invoke_cosign(
            image,
            {
                "option_kword": "--key",
                "inline_tr": "/dev/stdin",
                "trust_root": example_pubkey,
            },
        )

    mock_kill.assert_has_calls([mocker.call()])
    assert "Cosign timed out." in str(err.value)


@pytest.mark.parametrize(
    "index, COSIGN_EXPERIMENTAL",
    [
        (0, 0),
        (5, 1),
    ],
)
def test_get_envs(monkeypatch, index, COSIGN_EXPERIMENTAL):
    env = co.CosignValidator(**static_cosigns[index])._CosignValidator__get_envs()
    assert env["DOCKER_CONFIG"] == "/app/connaisseur-config/cosign1/.docker/"
    if COSIGN_EXPERIMENTAL:
        assert env["COSIGN_EXPERIMENTAL"] == f"{COSIGN_EXPERIMENTAL}"
    else:
        assert "COSIGN_EXPERIMENTAL" not in env.keys()


@pytest.mark.parametrize(
    "index, digest, err, threshold, required, exception",
    [
        (0, [digest1] * 2, testerr(), 1, [], fix.no_exc()),
        (4, [digest1] * 4, testerr(), 3, [], fix.no_exc()),
        (
            4,
            None,
            testerr(),
            2,
            [],
            pytest.raises(
                exc.ValidationError,
                match=r".*Image not compliant with validation policy \(threshold of \'2\' not reached\).*",
            ),
        ),
        (4, [digest1] * 3, testerr(), 2, ["test1", "test2"], fix.no_exc()),
        (
            4,
            [digest1, None, digest1],
            testerr(),
            2,
            ["test1", "test2"],
            pytest.raises(
                exc.ValidationError,
                match=r".*Image not compliant with validation policy \(missing signatures for required trust roots: test2\).*",
            ),
        ),
    ],
)
def test_apply_policy(index, digest, err, threshold, required, exception):
    with exception:
        vals = gen_vals(static_cosigns[index], None, digest, err)
        assert (
            co.CosignValidator._CosignValidator__apply_policy(vals, threshold, required)
            == set(digest).pop()
        )


def test_healthy():
    co.CosignValidator(**static_cosigns[0]).healthy == True
