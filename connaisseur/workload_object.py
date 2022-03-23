import connaisseur.kube_api as k_api
from connaisseur.exceptions import ParentNotFoundError, UnknownAPIVersionError
from connaisseur.image import Image


SUPPORTED_API_VERSIONS = {
    "Pod": ["v1"],
    "Deployment": ["apps/v1", "apps/v1beta1", "apps/v1beta2"],
    "ReplicationController": ["v1"],
    "ReplicaSet": ["apps/v1", "apps/v1beta1", "apps/v1beta2"],
    "DaemonSet": ["apps/v1", "apps/v1beta1", "apps/v1beta2"],
    "StatefulSet": ["apps/v1", "apps/v1beta1", "apps/v1beta2"],
    "Job": ["batch/v1"],
    "CronJob": ["batch/v1", "batch/v1beta1", "batch/v2alpha1"],
}


class WorkloadObject:
    container_path = "/spec/template/spec/{container_type}/{index}/image"

    def __new__(
        cls, request_object: dict, namespace: str
    ):  # pylint: disable=unused-argument
        if request_object["kind"] == "Pod":
            return super(WorkloadObject, cls).__new__(Pod)
        elif request_object["kind"] == "CronJob":
            return super(WorkloadObject, cls).__new__(CronJob)
        return super(WorkloadObject, cls).__new__(WorkloadObject)

    def __init__(self, request_object: dict, namespace: str):
        self.kind = request_object["kind"]
        self.api_version = request_object["apiVersion"]
        self.namespace = namespace
        self.name = request_object["metadata"].get("name") or request_object[
            "metadata"
        ].get("generateName")
        self._spec = request_object["spec"]
        self._owner = request_object["metadata"].get("ownerReferences", [])

        if self.api_version not in SUPPORTED_API_VERSIONS[self.kind]:
            msg = (
                "{wl_obj_version} is not in the supported API version list "
                "for {wl_obj_kind} {wl_obj_name}."
            )
            raise UnknownAPIVersionError(
                message=msg,
                wl_obj_version=self.api_version,
                wl_obj_kind=self.kind,
                wl_obj_name=self.name,
            )

    @property
    def parent_containers(self):
        parent_containers = {}
        for owner in self._owner:
            api_version = owner["apiVersion"]
            kind = owner["kind"]
            kinds = kind.lower() + "s"
            name = owner["name"]
            uid = owner["uid"]

            # k8s API has core at /api/v1 and names groups at /apis/$GROUP_NAME/$VERSION
            # see https://kubernetes.io/docs/reference/using-api/#api-groups
            if api_version == "v1":
                rest_path = "api"
            else:
                rest_path = "apis"

            if (
                kind not in SUPPORTED_API_VERSIONS
                or api_version not in SUPPORTED_API_VERSIONS[kind]
            ):
                return {}

            parent = k_api.request_kube_api(
                f"{rest_path}/{api_version}/namespaces/{self.namespace}/{kinds}/{name}"
            )

            if parent["metadata"]["uid"] != uid:
                msg = (
                    "Couldn't find the right parent"
                    " resource {parent_kind} {parent_name}."
                )
                raise ParentNotFoundError(
                    message=msg, parent_kind=kinds, parent_name=name, parent_uid=uid
                )

            parent_containers.update(WorkloadObject(parent, self.namespace).containers)
        return parent_containers

    @property
    def spec(self):
        return self._spec["template"]["spec"]

    @property
    def containers(self):
        return {
            (container_type, index): Image(container["image"])
            for container_type in ["containers", "initContainers"]
            for index, container in enumerate(self.spec.get(container_type, []))
        }

    def get_json_patch(self, image: Image, type_: str, index: int):
        return {
            "op": "replace",
            "path": self.container_path.format(container_type=type_, index=index),
            "value": str(image),
        }


class Pod(WorkloadObject):
    container_path = "/spec/{container_type}/{index}/image"

    @property
    def spec(self):
        return self._spec


class CronJob(WorkloadObject):
    container_path = (
        "/spec/jobTemplate/spec/template/spec/{container_type}/{index}/image"
    )

    @property
    def spec(self):
        return self._spec["jobTemplate"]["spec"]["template"]["spec"]
