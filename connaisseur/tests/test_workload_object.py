import pytest
import conftest as fix
import connaisseur.workload_object as wl
import connaisseur.exceptions as exc


static_k8s = [
    {
        "kind": "Deployment",
        "apiVersion": "apps/v1",
        "namespace": "default",
        "name": "charlie-deployment",
    },
    {
        "kind": "Pod",
        "apiVersion": "v1",
        "namespace": "default",
        "name": "charlie-deployment-76fbf58b7d-",
    },
    {
        "kind": "ReplicaSet",
        "apiVersion": "apps/v1",
        "namespace": "default",
        "name": "charlie-deployment-558576bf6c",
    },
    {
        "kind": "CronJob",
        "apiVersion": "batch/v1beta1",
        "namespace": "default",
        "name": "yooob",
    },
]


@pytest.fixture()
def adm_req_sample_objects():
    return [
        fix.get_admreq(t)["request"]["object"]
        for t in ("deployments", "pods", "replicasets", "cronjob", "wrong_version")
    ]


@pytest.mark.parametrize(
    "index, wl_class",
    [
        (0, wl.WorkloadObject),
        (1, wl.Pod),
        (2, wl.WorkloadObject),
        (3, wl.CronJob),
    ],
)
def test_k8s_object_new(adm_req_sample_objects, index, wl_class):
    obj = wl.WorkloadObject(adm_req_sample_objects[index], "default")
    assert isinstance(obj, wl_class)


@pytest.mark.parametrize(
    "index, exception",
    [
        (0, fix.no_exc()),
        (1, fix.no_exc()),
        (2, fix.no_exc()),
        (3, fix.no_exc()),
        (4, pytest.raises(exc.UnknownAPIVersionError)),
    ],
)
def test_k8s_object_init(adm_req_sample_objects, index, exception):
    with exception:
        obj = wl.WorkloadObject(adm_req_sample_objects[index], "default")
        assert obj.kind == static_k8s[index]["kind"]
        assert obj.api_version == static_k8s[index]["apiVersion"]
        assert obj.namespace == static_k8s[index]["namespace"]
        assert obj.name == static_k8s[index]["name"]


@pytest.mark.parametrize(
    "index, parent_list, exception",
    [
        (0, [], fix.no_exc()),
        (
            1,
            [
                (
                    "securesystemsengineering/charlie-image@sha256"
                    ":91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff"
                )
            ],
            fix.no_exc(),
        ),
        (2, [], pytest.raises(exc.ParentNotFoundError)),
        (3, [], fix.no_exc()),
    ],
)
def test_k8s_object_parent_images(
    adm_req_sample_objects, m_request, index, parent_list, exception
):
    obj = wl.WorkloadObject(adm_req_sample_objects[index], "default")
    with exception:
        assert obj.parent_images == parent_list


@pytest.mark.parametrize(
    "index, images",
    [
        (0, ["securesystemsengineering/alice-image:test"]),
        (
            1,
            [
                (
                    "securesystemsengineering/charlie-image@sha256:"
                    "91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff"
                )
            ],
        ),
        (2, ["securesystemsengineering/sample-san-sama:hai"]),
        (3, ["busybox"]),
    ],
)
def test_k8s_object_container_images(adm_req_sample_objects, index, images):
    obj = wl.WorkloadObject(adm_req_sample_objects[index], "default")
    assert obj.container_images == images
