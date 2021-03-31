import pytest
import pytest_subprocess
import subprocess

import connaisseur.sigstore_validator as sigstore_validator
from connaisseur.exceptions import (
    NotFoundException,
    ValidationError,
    CosignError,
    CosignTimeout,
    UnexpectedCosignData,
)

cosign_payload = '{"Critical":{"Identity":{"docker-reference":""},"Image":{"Docker-manifest-digest":"sha256:c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"},"Type":"cosign container signature"},"Optional":null}'
cosign_multiline_payload = """
{"Critical":{"Identity":{"docker-reference":""},"Image":{"Docker-manifest-digest":"sha256:2f6d89c49ad745bfd5d997f9b2d253329323da4c500c7fe343e068c0382b8df4"},"Type":"cosign container signature"},"Optional":null}
{"Critical":{"Identity":{"docker-reference":""},"Image":{"Docker-manifest-digest":"sha256:2f6d89c49ad745bfd5d997f9b2d253329323da4c500c7fe343e068c0382b8df4"},"Type":"cosign container signature"},"Optional":{"foo":"bar"}}
"""
cosign_payload_unexpected_json_format = '{"Important":{"Identity":{"docker-reference":""},"Image":{"Docker-manifest-digest":"sha256:c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"},"Type":"cosign container signature"},"Optional":null}'
cosign_payload_unexpected_digest_pattern = '{"Critical":{"Identity":{"docker-reference":""},"Image":{"Docker-manifest-digest":"sha512:c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"},"Type":"cosign container signature"},"Optional":null}'

cosign_nonjson_payload = "This is not json."
cosign_combined_payload = "{}\n{}".format(cosign_payload, cosign_nonjson_payload)

example_pubkey = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXbZhEfTYb4Mnb/LdrtXKTIIbzNBp8mwriocbaxXxzquvbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ=="

with open("tests/data/cosign_error_wrong_key.txt", "r") as readfile:
    cosign_error_message_wrong_pubkey = readfile.read()

with open("tests/data/cosign_error_no_data.txt", "r") as readfile:
    cosign_error_message_no_cosign_signature = readfile.read()

cosign_stderr_at_success = """
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
  - Any certificates were verified against the Fulcio roots.
"""


@pytest.fixture()
def mock_add_kill_fake_process(monkeypatch):
    def mock_kill(self):
        return

    pytest_subprocess.core.FakePopen.kill = mock_kill


@pytest.fixture()
def mock_invoke_cosign(mocker, status_code, stdout, stderr):
    mocker.patch(
        "connaisseur.sigstore_validator.invoke_cosign",
        return_value=(status_code, stdout, stderr),
    )


@pytest.mark.parametrize(
    "status_code, stdout, stderr, image, output",
    [
        (
            0,
            cosign_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            ["c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"],
        ),
        (
            0,
            cosign_combined_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            ["c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7"],
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
        ),
    ],
)
def test_get_cosign_validated_digests(
    mock_invoke_cosign, mocker, status_code, stdout, stderr, image, output
):
    mock_info_log = mocker.patch("logging.info")
    digests = sigstore_validator.get_cosign_validated_digests(image, "sth")
    mock_info_log.assert_has_calls(
        [
            mocker.call(
                "COSIGN output for image: %s; RETURNCODE: %s; STDOUT: %s; STDERR: %s",
                image,
                status_code,
                stdout,
                stderr,
            )
        ]
    )
    if stdout == (cosign_nonjson_payload or cosign_combined_payload):
        mock_info_log.assert_has_calls(
            [
                mocker.call(
                    "non-json signature data from cosign: %s", cosign_nonjson_payload
                )
            ]
        )
    assert digests == output


@pytest.mark.parametrize(
    "status_code, stdout, stderr, image",
    [
        (1, "", cosign_error_message_wrong_pubkey, "testimage:v1"),
    ],
)
def test_get_cosign_validated_digests_validation_error(
    mock_invoke_cosign, status_code, stdout, stderr, image
):
    with pytest.raises(ValidationError) as err:
        sigstore_validator.get_cosign_validated_digests(image, "sth")
    assert "failed to verify signature of trust data." in str(err.value)


@pytest.mark.parametrize(
    "status_code, stdout, stderr, image, error_message",
    [
        (
            0,
            cosign_payload_unexpected_json_format,
            cosign_stderr_at_success,
            "testimage:v1",
            "could not retrieve valid and unambiguous digest from data received by cosign: KeyError: 'Critical'",
        ),
        (
            0,
            cosign_payload_unexpected_digest_pattern,
            cosign_stderr_at_success,
            "testimage:v1",
            "could not retrieve valid and unambiguous digest from data received by cosign: "
            "Exception: digest 'sha512:c5327b291d702719a26c6cf8cc93f72e7902df46547106a9930feda2c002a4a7' "
            "does not match expected digest pattern.",
        ),
        (
            0,
            cosign_nonjson_payload,
            cosign_stderr_at_success,
            "testimage:v1",
            "could not extract any digest from data received by cosign "
            "despite successful image verification.",
        ),
    ],
)
def test_get_cosign_validated_digests_unexpected_cosign_data_error(
    mock_invoke_cosign, mocker, status_code, stdout, stderr, image, error_message
):
    with pytest.raises(UnexpectedCosignData) as err:
        sigstore_validator.get_cosign_validated_digests(image, "sth")
    assert error_message in str(err.value)


@pytest.mark.parametrize(
    "status_code, stdout, stderr, image",
    [
        (1, "", cosign_error_message_no_cosign_signature, "testimage:v1"),
    ],
)
def test_get_cosign_validated_digests_not_found_exception(
    mock_invoke_cosign, status_code, stdout, stderr, image
):
    with pytest.raises(NotFoundException) as err:
        sigstore_validator.get_cosign_validated_digests(image, "sth")
    assert 'no trust data for image "testimage:v1"' in str(err.value)


@pytest.mark.parametrize(
    "status_code, stdout, stderr, image",
    [
        (1, "", "Hm. Something weird happened.", "testimage:v1"),
    ],
)
def test_get_cosign_validated_digests_cosign_error(
    mock_invoke_cosign, status_code, stdout, stderr, image
):
    with pytest.raises(CosignError) as err:
        sigstore_validator.get_cosign_validated_digests(image, "sth")
    assert (
        'unexpected cosign exception for image "testimage:v1": Hm. Something weird happened.'
        in str(err.value)
    )


@pytest.mark.parametrize(
    "image, process_input",
    [
        (
            "testimage:v1",
            "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6uuXbZhEfTYb4Mnb/LdrtXKTIIbzNBp8mwriocbaxXxzquvbZpv4QtOTPoIw+0192MW9dWlSVaQPJd7IaiZIIQ==\n-----END PUBLIC KEY-----",
        )
    ],
)
def test_invoke_cosign(fake_process, image, process_input):
    def stdin_function(input):
        return {"stderr": input.decode(), "stdout": input}

    # as we are mocking the subprocess the output doesn't change with the input. To check that the
    # <process>.communicate() method is invoked with the correct input, we append it to stderr as explained in the docs
    # https://pytest-subprocess.readthedocs.io/en/latest/usage.html#passing-input
    # It seems there is a bug that, when appending the input to a data stream (e.g. stderr),
    # eats the other data stream (stdout in that case). Thus, simply appending to both.
    fake_process.register_subprocess(
        ["/app/cosign/cosign", "verify", "-key", "/dev/stdin", image],
        stderr=cosign_stderr_at_success,
        stdout=bytes(cosign_payload, "utf-8"),
        stdin_callable=stdin_function,
    )
    returncode, stdout, stderr = sigstore_validator.invoke_cosign(
        "testimage:v1", example_pubkey
    )
    assert [
        "/app/cosign/cosign",
        "verify",
        "-key",
        "/dev/stdin",
        image,
    ] in fake_process.calls
    assert (returncode, stdout, stderr) == (
        0,
        "{}{}".format(cosign_payload, process_input),
        "{}{}".format(cosign_stderr_at_success, process_input),
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
        ["/app/cosign/cosign", "verify", "-key", "/dev/stdin", image],
        stdin_callable=callback_function,
    )

    mock_kill = mocker.patch("pytest_subprocess.core.FakePopen.kill")

    with pytest.raises(CosignTimeout) as err:
        sigstore_validator.invoke_cosign(image, example_pubkey)

    mock_kill.assert_has_calls([mocker.call()])
    assert "cosign timed out." in str(err.value)
