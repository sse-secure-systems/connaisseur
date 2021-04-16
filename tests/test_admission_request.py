import pytest
from . import conftest as fix
import connaisseur.admission_request as admreq
import connaisseur.exceptions as exc


static_adm_req = [
    {
        "uid": "3a3a7b38-5512-4a85-94bb-3562269e0a6a",
        "kind": "Deployment",
        "namespace": "test-connaisseur",
        "operation": "CREATE",
        "user": "admin",
    },
    {
        "uid": "0c3331b6-1812-11ea-b3fc-02897404852e",
        "kind": "Pod",
        "namespace": "test-connaisseur",
        "operation": "CREATE",
        "user": "system:serviceaccount:kube-system:replicaset-controller",
    },
    {
        "uid": "f8c8b687-fe68-48e2-8e2b-329567556307",
        "kind": "ReplicaSet",
        "namespace": "test-connaisseur",
        "operation": "CREATE",
        "user": "system:serviceaccount:kube-system:deployment-controller",
    },
    {
        "uid": "1d5c9e9a-a985-41ef-b87f-4bc6057e94a2",
        "kind": "CronJob",
        "namespace": "connaisseur",
        "operation": "CREATE",
        "user": "minikube-user",
    },
]


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_admission_request_init(adm_req_samples, index):
    adm = admreq.AdmissionRequest(adm_req_samples[index])
    assert adm.uid == static_adm_req[index]["uid"]
    assert adm.kind == static_adm_req[index]["kind"]
    assert adm.namespace == static_adm_req[index]["namespace"]
    assert adm.operation == static_adm_req[index]["operation"]
    assert adm.user == static_adm_req[index]["user"]


@pytest.mark.parametrize(
    "index, exception",
    [(0, fix.no_exc()), (4, pytest.raises(exc.InvalidFormatException))],
)
def test_validate(adm_req_samples, index, exception):
    with exception:
        assert admreq.AdmissionRequest(adm_req_samples[index])


static_context = [
    {
        "user": "admin",
        "operation": "CREATE",
        "kind": "Deployment",
        "name": "charlie-deployment",
        "namespace": "test-connaisseur",
    },
    {
        "user": "system:serviceaccount:kube-system:replicaset-controller",
        "operation": "CREATE",
        "kind": "Pod",
        "name": "charlie-deployment-76fbf58b7d-",
        "namespace": "test-connaisseur",
    },
]


@pytest.mark.parametrize("index", [0, 1])
def test_context(adm_req_samples, index):
    adm = admreq.AdmissionRequest(adm_req_samples[index])
    assert adm.context == static_context[index]
