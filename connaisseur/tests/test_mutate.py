import pytest
import json
import re
import requests
import connaisseur.notary_api
import connaisseur.trust_data
import connaisseur.mutate as muta
from connaisseur.exceptions import BaseConnaisseurException, UnknownVersionError
from connaisseur.key_store import KeyStore

request_obj_pod = {
    "kind": "Pod",
    "apiVersion": "v1",
    "metadata": {},
    "spec": {
        "containers": [
            {
                "name": "test-connaisseur",
                "image": "securesystemsengineering/charlie-image:test",
            }
        ]
    },
}
request_obj_pod_with_init_container = {
    "kind": "Pod",
    "apiVersion": "v1",
    "metadata": {},
    "spec": {
        "containers": [
            {
                "name": "test-connaisseur",
                "image": "securesystemsengineering/charlie-image:test",
            }
        ],
        "initContainers": [
            {
                "name": "init-container",
                "image": "docker.io/securesystemsengineering/testing_conny:unsigned",
            }
        ],
    },
}
request_obj_cronjob = {
    "apiVersion": "batch/v1beta1",
    "kind": "CronJob",
    "metadata": {},
    "spec": {
        "schedule": "*/1 * * * *",
        "jobTemplate": {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "test-connaisseur",
                                "image": "securesystemsengineering/charlie-image:test",
                            }
                        ]
                    }
                }
            }
        },
    },
}
request_obj_cronjob_with_init_container = {
    "apiVersion": "batch/v1beta1",
    "kind": "CronJob",
    "metadata": {},
    "spec": {
        "schedule": "*/1 * * * *",
        "jobTemplate": {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "test-connaisseur",
                                "image": "securesystemsengineering/charlie-image:test",
                            }
                        ],
                        "initContainers": [
                            {
                                "name": "init-container",
                                "image": "docker.io/securesystemsengineering/testing_conny:unsigned",
                            }
                        ],
                    }
                }
            }
        },
    },
}
request_obj_deployment = {
    "kind": "Deployment",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ]
            },
        }
    },
}
request_obj_deployment_with_two_init_containers = {
    "kind": "Deployment",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ],
                "initContainers": [
                    {
                        "name": "init-container",
                        "image": "docker.io/securesystemsengineering/testing_conny:unsigned",
                    },
                    {
                        "name": "init-container2",
                        "image": "docker.io/securesystemsengineering/testing_conny:signed",
                    },
                ],
            },
        }
    },
}
request_obj_replicationscontroller = {
    "kind": "ReplicationController",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ]
            },
        }
    },
}
request_obj_replicationcontroller_with_two_init_containers = {
    "kind": "ReplicationController",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ],
                "initContainers": [
                    {
                        "name": "init-container",
                        "image": "docker.io/securesystemsengineering/testing_conny:unsigned",
                    },
                    {
                        "name": "init-container2",
                        "image": "docker.io/securesystemsengineering/testing_conny:signed",
                    },
                ],
            },
        }
    },
}
request_obj_replicatset = {
    "kind": "ReplicaSet",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ]
            },
        }
    },
}
request_obj_replicaset_with_two_init_containers = {
    "kind": "ReplicaSet",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ],
                "initContainers": [
                    {
                        "name": "init-container",
                        "image": "docker.io/securesystemsengineering/testing_conny:unsigned",
                    },
                    {
                        "name": "init-container2",
                        "image": "docker.io/securesystemsengineering/testing_conny:signed",
                    },
                ],
            },
        }
    },
}
request_obj_daemonset = {
    "kind": "DaemonSet",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ]
            },
        }
    },
}
request_obj_daemonset_with_two_init_containers = {
    "kind": "DaemonSet",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ],
                "initContainers": [
                    {
                        "name": "init-container",
                        "image": "docker.io/securesystemsengineering/testing_conny:unsigned",
                    },
                    {
                        "name": "init-container2",
                        "image": "docker.io/securesystemsengineering/testing_conny:signed",
                    },
                ],
            },
        }
    },
}
request_obj_statefulset = {
    "kind": "StatefulSet",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ]
            },
        }
    },
}
request_obj_tuftuf = {
    "kind": "TufTuf",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ]
            },
        }
    },
}
request_obj_statefulset_with_two_init_containers = {
    "kind": "StatefulSet",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ],
                "initContainers": [
                    {
                        "name": "init-container",
                        "image": "docker.io/securesystemsengineering/testing_conny:unsigned",
                    },
                    {
                        "name": "init-container2",
                        "image": "docker.io/securesystemsengineering/testing_conny:signed",
                    },
                ],
            },
        }
    },
}
request_obj_job = {
    "kind": "Job",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ]
            },
        }
    },
}
request_obj_job_with_two_init_containers = {
    "kind": "Job",
    "apiVersion": "apps/v1",
    "metadata": {},
    "spec": {
        "template": {
            "metadata": {},
            "spec": {
                "containers": [
                    {
                        "name": "test-connaisseur",
                        "image": "securesystemsengineering/charlie-image:test",
                    }
                ],
                "initContainers": [
                    {
                        "name": "init-container",
                        "image": "docker.io/securesystemsengineering/testing_conny:unsigned",
                    },
                    {
                        "name": "init-container2",
                        "image": "docker.io/securesystemsengineering/testing_conny:signed",
                    },
                ],
            },
        }
    },
}
request_obj_output = [
    {"name": "test-connaisseur", "image": "securesystemsengineering/charlie-image:test"}
]
request_obj_output_with_init_container = [
    {
        "name": "test-connaisseur",
        "image": "securesystemsengineering/charlie-image:test",
    },
    {
        "name": "init-container",
        "image": "docker.io/securesystemsengineering/testing_conny:unsigned",
    },
]
request_obj_output_with_two_init_containers = [
    {
        "name": "test-connaisseur",
        "image": "securesystemsengineering/charlie-image:test",
    },
    {
        "name": "init-container",
        "image": "docker.io/securesystemsengineering/testing_conny:unsigned",
    },
    {
        "name": "init-container2",
        "image": "docker.io/securesystemsengineering/testing_conny:signed",
    },
]
patch_pod = {
    "op": "replace",
    "path": "/spec/containers/1/image",
    "value": "image@sha256:859b5aad",
}
patch_cronjob = {
    "op": "replace",
    "path": "/spec/jobTemplate/spec/template/spec/containers/1/image",
    "value": "image@sha256:859b5aad",
}
patch_deployment = {
    "op": "replace",
    "path": "/spec/template/spec/containers/1/image",
    "value": "image@sha256:859b5aad",
}
ad_review1 = {
    "apiVersion": "admission.k8s.io/v1beta1",
    "kind": "AdmissionReview",
    "response": {
        "uid": "3a3a7b38-5512-4a85-94bb-3562269e0a6a",
        "allowed": True,
        "status": {"code": 202},
        "patchType": "JSONPatch",
        "patch": (
            "W3sib3AiOiAicmVwbGFjZSIsICJwYXRoIjogIi9zcGVjL3RlbXBsYXRlL3NwZWMvY29udGFpbmVy"
            "cy8wL2ltYWdlIiwgInZhbHVlIjogImRvY2tlci5pby9zZWN1cmVzeXN0ZW1zZW5naW5lZXJpbmcv"
            "YWxpY2UtaW1hZ2VAc2hhMjU2OmFjOTA0YzliMTkxZDE0ZmFmNTRiNzk1MmYyNjUwYTRiYjIxYzIw"
            "MWJmMzQxMzEzODhiODUxZThjZTk5MmE2NTIifV0="
        ),
    },
}
ad_review2 = {
    "apiVersion": "admission.k8s.io/v1beta1",
    "kind": "AdmissionReview",
    "response": {
        "uid": "f8c8b687-fe68-48e2-8e2b-329567556307",
        "allowed": True,
        "status": {"code": 202},
    },
}
policy = {
    "rules": [
        {"pattern": "*:*", "verify": True, "delegations": ["phbelitz", "chamsen"]},
        {"pattern": "docker.io/*:*", "verify": True, "delegations": ["phbelitz"]},
        {"pattern": "k8s.gcr.io/*:*", "verify": False},
        {"pattern": "gcr.io/*:*", "verify": False},
        {
            "pattern": "docker.io/securesystemsengineering/*:*",
            "verify": True,
            "delegations": ["someuserthatdidnotsign"],
        },
        {
            "pattern": "docker.io/securesystemsengineering/alice-image",
            "verify": True,
            "delegations": ["phbelitz", "chamsen"],
        },
        {"pattern": "docker.io/securesystemsengineering/sample:v4", "verify": False},
        {
            "pattern": "docker.io/securesystemsengineering/connaisseur:*",
            "verify": False,
        },
        {
            "pattern": "docker.io/securesystemsengineering/sample-san-sama",
            "verify": True,
        },
    ]
}


@pytest.fixture
def mutate():
    return muta


@pytest.fixture
def mock_kube_request(monkeypatch):
    def m_request(path: str):
        kind = path.split("/")[-2]
        return get_ad_request(f"tests/data/{kind.lower()}.json")

    monkeypatch.setattr(muta, "request_kube_api", m_request)


@pytest.fixture
def mock_request(monkeypatch):
    class MockResponse:
        content: dict
        status_code: int = 200

        def __init__(self, content: dict):
            self.content = content

        def raise_for_status(self):
            pass

        def json(self):
            return self.content

    def mock_get_request(**kwargs):
        regex = (
            r"https:\/\/([^\/]+)\/v2\/([^\/]+)\/([^\/]+\/)?"
            r"([^\/]+)\/_trust\/tuf\/(.+)\.json"
        )
        m = re.search(regex, kwargs["url"])

        if m:
            host, registry, repo, image, role = (
                m.group(1),
                m.group(2),
                m.group(3),
                m.group(4),
                m.group(5),
            )

        if "health" in kwargs["url"]:
            return MockResponse(None)

        with open(f"tests/data/{image}/{role}.json", "r") as file:
            file_content = json.load(file)

        return MockResponse(file_content)

    monkeypatch.setattr(requests, "get", mock_get_request)


@pytest.fixture
def mock_keystore(monkeypatch):
    def init(self):
        self.keys = {
            "root": (
                "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu7WMF8tCjVgeORA"
                "S2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA=="
            )
        }
        self.hashes = {}

    monkeypatch.setattr(KeyStore, "__init__", init)


@pytest.fixture
def mock_policy(monkeypatch):
    def get_policy():
        return policy

    muta.ImagePolicy.get_image_policy = staticmethod(get_policy)
    muta.ImagePolicy.JSON_SCHEMA_PATH = "res/policy_schema.json"


@pytest.fixture
def mock_trust_data(monkeypatch):
    def validate_expiry(self):
        pass

    def trust_init(self, data: dict, role: str):
        self.schema_path = "res/targets_schema.json"
        self.kind = role
        self._validate_schema(data)
        self.signed = data["signed"]
        self.signatures = data["signatures"]

    monkeypatch.setattr(
        connaisseur.trust_data.TrustData, "validate_expiry", validate_expiry
    )
    monkeypatch.setattr(connaisseur.trust_data.TargetsData, "__init__", trust_init)
    connaisseur.trust_data.TrustData.schema_path = "res/{}_schema.json"


def get_ad_request(path: str):
    with open(path, "r") as file:
        return json.load(file)


@pytest.mark.parametrize(
    "request_obj, output",
    [
        (request_obj_pod, request_obj_output),
        (request_obj_cronjob, request_obj_output),
        (request_obj_deployment, request_obj_output),
        (request_obj_replicationscontroller, request_obj_output),
        (request_obj_replicatset, request_obj_output),
        (request_obj_daemonset, request_obj_output),
        (request_obj_statefulset, request_obj_output),
        (request_obj_job, request_obj_output),
        (request_obj_tuftuf, None),
        (request_obj_pod_with_init_container, request_obj_output_with_init_container),
        (
            request_obj_cronjob_with_init_container,
            request_obj_output_with_init_container,
        ),
        (
            request_obj_deployment_with_two_init_containers,
            request_obj_output_with_two_init_containers,
        ),
        (
            request_obj_replicationcontroller_with_two_init_containers,
            request_obj_output_with_two_init_containers,
        ),
        (
            request_obj_replicaset_with_two_init_containers,
            request_obj_output_with_two_init_containers,
        ),
        (
            request_obj_daemonset_with_two_init_containers,
            request_obj_output_with_two_init_containers,
        ),
        (
            request_obj_statefulset_with_two_init_containers,
            request_obj_output_with_two_init_containers,
        ),
        (
            request_obj_job_with_two_init_containers,
            request_obj_output_with_two_init_containers,
        ),
    ],
)
def test_get_container_specs(mutate, request_obj: dict, output: dict):
    assert muta.get_container_specs(request_obj) == output


@pytest.mark.parametrize(
    "object_kind, index, name, patch",
    [
        ("Pod", 1, "image@sha256:859b5aad", patch_pod),
        ("CronJob", 1, "image@sha256:859b5aad", patch_cronjob),
        ("Deployment", 1, "image@sha256:859b5aad", patch_deployment),
    ],
)
def test_get_json_patch(mutate, object_kind: str, index: int, name: str, patch: dict):
    assert (
        muta.get_json_patch(object_kind=object_kind, index=index, image_name=name)
        == patch
    )


@pytest.mark.parametrize(
    "ad_request, index, acc_images",
    [
        (
            get_ad_request("tests/data/ad_request_replicasets.json"),
            0,
            ["securesystemsengineering/sample-san-sama:hai"],
        )
    ],
)
def test_get_parent_images(
    mutate, mock_kube_request, ad_request: dict, index: int, acc_images: list
):
    assert mutate.get_parent_images(ad_request, index, "namespace") == acc_images


def test_get_parent_images_error(mutate, mock_kube_request):
    with pytest.raises(BaseConnaisseurException) as err:
        ad_request = get_ad_request("tests/data/ad_request_pods.json")
        muta.get_parent_images(ad_request, 0, "namespace")
    assert "owner uid and found parent uid do not match." in str(err.value)


@pytest.mark.parametrize(
    "ad_request, review",
    [
        (get_ad_request("tests/data/ad_request_deployments.json"), ad_review1),
        (get_ad_request("tests/data/ad_request_replicasets.json"), ad_review2),
    ],
)
def test_admit(
    mutate,
    mock_kube_request,
    mock_request,
    mock_keystore,
    mock_policy,
    mock_trust_data,
    ad_request: dict,
    review: dict,
):
    assert mutate.admit(ad_request) == review


@pytest.mark.parametrize(
    "ad_request",
    [
        (get_ad_request("tests/data/ad_request_deployments.json")),
        (get_ad_request("tests/data/ad_request_replicasets.json")),
        (get_ad_request("tests/data/ad_request_pods.json")),
    ],
)
def test_validate(mutate, ad_request: dict):
    assert mutate.validate(ad_request) is None


def test_validate_error_ad(mutate):
    ad_request = get_ad_request("tests/data/ad_request_pods.json")
    ad_request["apiVersion"] = "v2"
    with pytest.raises(UnknownVersionError) as err:
        mutate.validate(ad_request)
    assert "API version v2 unknown." in str(err.value)


def test_validate_error_obj(mutate):
    ad_request = get_ad_request("tests/data/ad_request_pods.json")
    ad_request["request"]["object"]["apiVersion"] = "v2"
    with pytest.raises(UnknownVersionError) as err:
        mutate.validate(ad_request)
    assert "unsupported version v2 for resource Pod." in str(err.value)


def test_validate_error_kind(mutate):
    ad_request = get_ad_request("tests/data/ad_request_pods.json")
    ad_request["request"]["object"]["kind"] = "MisterX"
    with pytest.raises(BaseConnaisseurException) as err:
        mutate.validate(ad_request)
    assert "unknown request object kind MisterX" in str(err.value)
