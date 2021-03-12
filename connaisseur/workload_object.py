import connaisseur.kube_api as k_api
from connaisseur.exceptions import UnknownAPIVersionError, ParentNotFoundError


SUPPORTED_API_VERSIONS = {
    "Pod": ["v1"],
    "Deployment": ["apps/v1", "apps/v1beta1", "apps/v1beta2"],
    "ReplicationController": ["v1"],
    "ReplicaSet": ["apps/v1", "apps/v1beta1", "apps/v1beta2"],
    "DaemonSet": ["apps/v1", "apps/v1beta1", "apps/v1beta2"],
    "StatefulSet": ["apps/v1", "apps/v1beta1", "apps/v1beta2"],
    "Job": ["batch/v1"],
    "CronJob": ["batch/v1beta1", "batch/v2alpha1"],
}


class WorkloadObject:
    container_path = "/spec/template/spec/containers/{}/image"

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
    def parent_images(self):
        parent_images = []
        for owner in self._owner:
            api_version = owner["apiVersion"]
            kind = owner["kind"].lower() + "s"
            name = owner["name"]
            uid = owner["uid"]

            parent = k_api.request_kube_api(
                f"apis/{api_version}/namespaces/{self.namespace}/{kind}/{name}"
            )

            if parent["metadata"]["uid"] != uid:
                msg = (
                    "Couldn't find the right parent"
                    " resource {parent_kind} {parent_name}."
                )
                raise ParentNotFoundError(
                    message=msg, parent_kind=kind, parent_name=name, parent_uid=uid
                )

            parent_images += WorkloadObject(parent, self.namespace).container_images
        return parent_images

    @property
    def container_images(self):
        spec = self._spec["template"]["spec"]
        return [
            container["image"]
            for container in (spec["containers"] + spec.get("initContainers", []))
        ]


class Pod(WorkloadObject):
    container_path = "/spec/containers/{}/image"

    @property
    def container_images(self):
        return [
            container["image"]
            for container in (
                self._spec["containers"] + self._spec.get("initContainers", [])
            )
        ]


class CronJob(WorkloadObject):
    container_path = "/spec/jobTemplate/spec/template/spec/containers/{}/image"

    @property
    def container_images(self):
        spec = self._spec["jobTemplate"]["spec"]["template"]["spec"]
        return [
            container["image"]
            for container in (spec["containers"] + spec.get("initContainers", []))
        ]
