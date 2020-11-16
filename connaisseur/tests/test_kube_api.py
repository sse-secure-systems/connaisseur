import os
import pytest
import requests
import json
import connaisseur.kube_api


@pytest.fixture
def api():
    return connaisseur.kube_api


@pytest.fixture
def mock_request(monkeypatch):
    class MockResponse:
        content: dict

        def __init__(self, content: str):
            self.content = content

        def raise_for_status(self):
            if not self.content:
                raise Exception

        def json(self):
            return self.content

    def mock_get_request(url: str, **kwargs):
        role = url.split("/")[-1]

        with open(f"tests/data/{role}", "r") as file:
            file_content = json.load(file)

        return MockResponse(file_content)

    monkeypatch.setattr(requests, "get", mock_get_request)


@pytest.fixture
def mock_get_token(monkeypatch):
    def mock_token(path: str):
        return "token"

    monkeypatch.setattr(connaisseur.kube_api, "get_token", mock_token)


def get_data(path: str):
    with open(path, "r") as file:
        data = json.load(file)
    return data


@pytest.mark.parametrize(
    "path, response",
    [
        ("sample_targets.json", get_data("tests/data/sample_targets.json")),
        ("sample_releases.json", get_data("tests/data/sample_releases.json")),
    ],
)
def test_request_kube_api(
    api, mock_request, mock_get_token, path: str, response: dict, monkeypatch
):
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "127.0.0.1")
    monkeypatch.setenv("KUBERNETES_SERVICE_PORT", "1234")
    assert api.request_kube_api(path) == response
