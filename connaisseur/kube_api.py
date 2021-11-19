import os
import requests


def request_kube_api(path: str):
    """
    Make an API call to the underlying Kubernetes API server with the given
    `path`.
    """

    token_path = os.environ.get("KUBE_API_TOKEN_PATH")
    ca_path = os.environ.get("KUBE_API_CA_PATH")
    kube_ip = os.environ.get("KUBERNETES_SERVICE_HOST")
    kube_port = os.environ.get("KUBERNETES_SERVICE_PORT")

    token = __get_token(token_path)

    url = f"https://{kube_ip}:{kube_port}/{path}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, verify=ca_path, headers=headers)
    response.raise_for_status()

    return response.json()


def __get_token(path: str):
    """
    Get the API token from the container's file system.
    """
    with open(path, "r", encoding="utf-8") as file:
        return file.read()
