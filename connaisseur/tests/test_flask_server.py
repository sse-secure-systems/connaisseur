import os
import pytest
import json
import connaisseur.flask_server as fs
import connaisseur.kube_api as api
from requests.exceptions import HTTPError


@pytest.fixture
def mock_kube_request(monkeypatch):
    def m_request(path: str):
        name = path.split("/")[-1]
        try:
            return get_file(f"tests/data/{name}.json")
        except FileNotFoundError:
            raise HTTPError

    monkeypatch.setattr(api, "request_kube_api", m_request)


@pytest.fixture
def mock_notary_health(monkeypatch):
    def m_health_check(path: str):
        if path == "healthy":
            return True
        return False

    monkeypatch.setattr(fs, "health_check", m_health_check)


def get_file(path: str):
    with open(path, "r") as file:
        return json.load(file)


def test_healthz():
    assert fs.healthz() == ("", 200)


@pytest.mark.parametrize(
    "sentinel_name, webhook, notary_health, status",
    [
        ("sample_sentinel_run", "", "healthy", 200),
        ("sample_sentinel_fin", "", "healthy", 500),
        ("sample_sentinel_err", "", "healthy", 500),
        ("", "", "", 500),
        ("sample_sentinel_fin", "sample_webhook", "healthy", 200),
        ("sample_sentinel_fin", "", "healthy", 500),
        ("sample_sentinel_fin", "sample_webhook", "unhealthy", 500),
    ],
)
def test_readyz(
    mock_kube_request,
    mock_notary_health,
    monkeypatch,
    sentinel_name,
    webhook,
    notary_health,
    status,
):
    monkeypatch.setenv("CONNAISSEUR_NAMESPACE", "conny")
    monkeypatch.setenv("CONNAISSEUR_SENTINEL", sentinel_name)
    monkeypatch.setenv("CONNAISSEUR_WEBHOOK", webhook)
    monkeypatch.setenv("NOTARY_SERVER", notary_health)

    assert fs.readyz() == ("", status)
