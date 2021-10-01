import pytest
import pytest_subprocess
import subprocess
from ... import conftest as fix
import connaisseur.validators.cosign.cosign_validator as co
import connaisseur.exceptions as exc

example_key = (
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXb"
    "ZhEfTYb4Mnb/LdrtXKTIIbzNBp8mwriocbaxXxzqu"
    "vbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ=="
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
            {"name": "test", "key": "..."},
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
    },
    {
        "name": "cosign1",
        "type": "cosign",
        "trust_roots": [
            {"name": "megatest", "key": "..."},
            {"name": "test", "key": "..."},
        ],
    },
    {
        "name": "cosign1",
        "type": "cosign",
        "trust_roots": [],
    },
]

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

    pytest_subprocess.core.FakePopen.kill = mock_kill


@pytest.mark.parametrize("index", [0, 1, 2])
def test_init(index: int):
    val = co.CosignValidator(**static_cosigns[index])
    assert val.name == static_cosigns[index]["name"]
    assert val.trust_roots == static_cosigns[index]["trust_roots"]


@pytest.mark.parametrize(
    "index, key_name, key, exception",
    [
        (0, "test", "...", fix.no_exc()),
        (0, None, example_key, fix.no_exc()),
        (
            0,
            "non_existing",
            None,
            pytest.raises(exc.NotFoundException, match=r'.*Trust root "non_existing.*'),
        ),
        (
            2,
            None,
            None,
            pytest.raises(exc.NotFoundException, match=r'.*Trust root "default".*'),
        ),
    ],
)
def test_get_key(index: int, key_name: str, key: str, exception):
    with exception:
        val = co.CosignValidator(**static_cosigns[index])
        assert val._CosignValidator__get_key(key_name) == key


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code, stdout, stderr, image, digest",
    [
        (
            0,
            cosign_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            "c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7",
        ),
        (
            0,
            cosign_multiline_payload,
            cosign_stderr_at_success,
            "",
            "2f6d89c49ad745bfd5d997f9b2d253329323da4c500c7fe343e068c0382b8df4",
        ),
    ],
)
async def test_validate(mock_invoke_cosign, status_code, stdout, stderr, image, digest):
    assert await co.CosignValidator(**static_cosigns[0]).validate(image) == digest


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
            "",
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
            "",
            pytest.raises(exc.ValidationError),
        ),
        (
            0,
            cosign_payload_unexpected_json_format,
            cosign_stderr_at_success,
            "testimage:v1",
            "",
            pytest.raises(exc.UnexpectedCosignData, match=r".*KeyError.*"),
        ),
        (
            0,
            cosign_payload_unexpected_digest_pattern,
            cosign_stderr_at_success,
            "testimage:v1",
            "",
            pytest.raises(exc.UnexpectedCosignData, match=r".*Exception.*"),
        ),
        (
            0,
            cosign_nonjson_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            "",
            pytest.raises(exc.UnexpectedCosignData, match=r".*extract.*"),
        ),
        (
            1,
            "",
            fix.get_cosign_err_msg("no_data"),
            "testimage:v1",
            "",
            pytest.raises(exc.NotFoundException),
        ),
        (
            1,
            "",
            "Hm. Something weird happened.",
            "testimage:v1",
            "",
            pytest.raises(exc.CosignError),
        ),
    ],
)
def test_get_cosign_validated_digests(
    mock_invoke_cosign, status_code, stdout, stderr, image, output, exception
):
    with exception:
        val = co.CosignValidator(**static_cosigns[0])
        digests = val._CosignValidator__get_cosign_validated_digests(image, "sth")
        assert digests == output


@pytest.mark.parametrize(
    "image, process_input, input_type",
    [
        (
            "testimage:v1",
            (
                "-----BEGIN PUBLIC KEY-----\n"
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXbZhEfTYb4Mnb/LdrtXKTIIbz\n"
                "NBp8mwriocbaxXxzquvbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ==\n"
                "-----END PUBLIC KEY-----\n"
            ),
            "key",
        ),
        ("testimage:v1", "k8s://connaisseur/test_key", "ref"),
    ],
)
def test_invoke_cosign(fake_process, image, process_input, input_type):
    def stdin_function(input):
        return {"stderr": input.decode(), "stdout": input}

    # as we are mocking the subprocess the output doesn't change with the input. To check that the
    # <process>.communicate() method is invoked with the correct input, we append it to stderr as explained in the docs
    # https://pytest-subprocess.readthedocs.io/en/latest/usage.html#passing-input
    # It seems there is a bug that, when appending the input to a data stream (e.g. stderr),
    # eats the other data stream (stdout in that case). Thus, simply appending to both.
    fake_process_calls = [
        "/app/cosign/cosign",
        "verify",
        "-output",
        "text",
        "-key",
        "/dev/stdin" if input_type == "key" else process_input,
        image,
    ]
    fake_process.register_subprocess(
        fake_process_calls,
        stderr=cosign_stderr_at_success,
        stdout=bytes(cosign_payload, "utf-8"),
        stdin_callable=stdin_function,
    )
    val = co.CosignValidator(**static_cosigns[0])
    returncode, stdout, stderr = val._CosignValidator__invoke_cosign(
        "testimage:v1", process_input
    )
    assert fake_process_calls in fake_process.calls
    assert (returncode, stdout, stderr) == (
        0,
        "{}{}".format(cosign_payload, process_input if input_type == "key" else ""),
        "{}{}".format(
            cosign_stderr_at_success, process_input if input_type == "key" else ""
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
            "-output",
            "text",
            "-key",
            "/dev/stdin",
            image,
        ],
        stdin_callable=callback_function,
    )

    mock_kill = mocker.patch("pytest_subprocess.core.FakePopen.kill")

    with pytest.raises(exc.CosignTimeout) as err:

        co.CosignValidator(**static_cosigns[0])._CosignValidator__invoke_cosign(
            image, example_pubkey
        )

    mock_kill.assert_has_calls([mocker.call()])
    assert "Cosign timed out." in str(err.value)
