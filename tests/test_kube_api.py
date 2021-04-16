import pytest
from . import conftest as fix
import connaisseur.kube_api as k_api


@pytest.mark.parametrize(
    "url, response",
    [
        (
            "https://samplenotray.io/apis/v1/namespaces/default/pods/sample-pod",
            fix.get_k8s_res("pods"),
        ),
        (
            "https://samplenotray.io/apis/v1/namespaces/default/deployments/sample-dpl",
            fix.get_k8s_res("deployments"),
        ),
    ],
)
def test_request_kube_api(monkeypatch, m_request, url: str, response: dict):
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "127.0.0.1")
    monkeypatch.setenv("KUBERNETES_SERVICE_PORT", "1234")
    assert k_api.request_kube_api(url) == response
