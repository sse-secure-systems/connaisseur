import json
import sys
import pytest
import traceback
import re
from falcon import testing
from . import conftest as fix
from aioresponses import aioresponses
import connaisseur.exceptions as exc
import connaisseur.config as co
from connaisseur.validators.static.static_validator import StaticValidator


@pytest.fixture
def client(monkeypatch, sample_nv1):
    def mock_init(self):
        self.validators = [sample_nv1, StaticValidator("allow", True)]
        self.policy = [
            {
                "pattern": "*:*",
                "validator": "",
                "with": {"delegations": ["phbelitz", "chamsen"]},
            },
            {
                "pattern": "docker.io/*:*",
                "validator": "dockerhub",
                "with": {"delegations": ["phbelitz"]},
            },
            {"pattern": "k8s.gcr.io/*:*", "validator": "allow"},
            {"pattern": "gcr.io/*:*", "validator": "allow"},
            {
                "pattern": "docker.io/securesystemsengineering/*:*",
                "validator": "dockerhub",
                "with": {"delegations": ["someuserthatdidnotsign"]},
            },
            {
                "pattern": "docker.io/securesystemsengineering/sample",
                "validator": "dockerhub",
                "with": {"delegations": ["phbelitz", "chamsen"]},
            },
            {
                "pattern": "docker.io/securesystemsengineering/sample:v4",
                "validator": "allow",
            },
            {
                "pattern": "docker.io/securesystemsengineering/connaisseur:*",
                "validator": "allow",
            },
            {
                "pattern": "docker.io/securesystemsengineering/sample-san-sama",
                "validator": "allow",
            },
            {
                "pattern": "docker.io/securesystemsengineering/alice-image",
                "validator": "dockerhub",
            },
        ]

    monkeypatch.setattr(co.Config, "__init__", mock_init)
    monkeypatch.setenv("KUBE_VERSION", "v1.20.0")

    from connaisseur.falcon_server import APP

    return testing.TestClient(APP)


def test_health(client):
    assert client.simulate_get("/health").status_code == 200


def test_ready(client):
    assert client.simulate_get("/ready").status_code == 200


@pytest.mark.parametrize(
    "index, allowed, status_code, detection_mode",
    [(0, True, 202, 0), (5, False, 403, 0)],
)
def test_mutate(
    monkeypatch,
    client,
    adm_req_samples,
    index,
    m_request,
    m_trust_data,
    m_alerting,
    m_expiry,
    allowed,
    status_code,
    detection_mode,
):
    with aioresponses() as aio:
        aio.get(re.compile(r".*"), callback=fix.async_callback, repeat=True)
        response = client.simulate_post("/mutate", json=adm_req_samples[index])

        assert response.status_code == 200
        assert response.json["response"]["allowed"] == allowed
        assert response.json["response"]["status"]["code"] == status_code
