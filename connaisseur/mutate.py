import logging
from connaisseur.image import Image
from connaisseur.validate import get_trusted_digest
from connaisseur.admission_review import get_admission_review
from connaisseur.kube_api import request_kube_api
from connaisseur.exceptions import BaseConnaisseurException, UnknownVersionError
from connaisseur.policy import ImagePolicy
from connaisseur.config import Config

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


def get_container_specs(request_object: dict):
    """
    Returns the container specifications of the `request_object`, based on its
    type.
    """
    object_kind = request_object["kind"]
    if object_kind == "Pod":
        relevant_spec = request_object["spec"]
        init_containers = relevant_spec.get("initContainers", [])
        return relevant_spec["containers"] + init_containers
    elif object_kind == "CronJob":
        relevant_spec = request_object["spec"]["jobTemplate"]["spec"]["template"][
            "spec"
        ]
        init_containers = relevant_spec.get("initContainers", [])
        return relevant_spec["containers"] + init_containers
    elif object_kind in (
        "Deployment",
        "ReplicationController",
        "ReplicaSet",
        "DaemonSet",
        "StatefulSet",
        "Job",
    ):
        relevant_spec = request_object["spec"]["template"]["spec"]
        init_containers = relevant_spec.get("initContainers", [])
        return relevant_spec["containers"] + init_containers


def get_json_patch(object_kind: str, index: int, image_name: str):
    """
    Gives different JSONPatches as a `dict`, depending on the `object_kind`.

    The JSONPatch replaces the image at index `index` with
    `image_name`.
    """
    if object_kind == "Pod":
        return {
            "op": "replace",
            "path": f"/spec/containers/{str(index)}/image",
            "value": image_name,
        }
    elif object_kind == "CronJob":
        return {
            "op": "replace",
            "path": (
                f"/spec/jobTemplate/spec/template/spec/containers/"
                f"{str(index)}/image"
            ),
            "value": image_name,
        }
    else:
        return {
            "op": "replace",
            "path": f"/spec/template/spec/containers/{str(index)}/image",
            "value": image_name,
        }


def get_parent_images(request: dict, index: int, namespace: str):
    """
    Requests the kube API for the parent object, found in the `request` at
    `index` and searches for all image name references in there.

    Return the found image references as a `list`. The list is empty if none
    were found.
    """
    owner = request["request"]["object"]["metadata"]["ownerReferences"][index]
    api_version = owner["apiVersion"]
    kind = owner["kind"]
    name = owner["name"]
    uid = owner["uid"]

    # get parent object
    parent = request_kube_api(
        f"apis/{api_version}/namespaces/{namespace}/{kind.lower()}s/{name}"
    )

    if parent["metadata"]["uid"] != uid:
        msg = "owner uid and found parent uid do not match."
        raise BaseConnaisseurException(msg, create_logging_context(request))

    # search parent object for image references
    acceptable_images = []
    parent_containers = get_container_specs(parent)
    for container in parent_containers:
        acceptable_images.append(container["image"])
    return acceptable_images


def create_logging_context(request: dict, image: str = None):
    """
    Creates a default logging context `dict` of useful information to log from
    the current `request` and currently view `image`, if present.

    """
    user = request.get("request", {}).get("userInfo", {}).get("username")
    operation = request.get("request", {}).get("operation")
    namespace = request.get("request", {}).get("namespace")
    kind = request.get("request", {}).get("kind", {}).get("kind")

    context = {
        "user": user,
        "operation": operation,
        "kind": kind,
        "namespace": namespace,
    }

    try:
        context["name"] = request["request"]["object"]["metadata"]["name"]
    except KeyError:
        pass

    if image:
        context["image"] = image

    return context


def validate(request: dict):
    request_version = request.get("apiVersion")

    if request_version not in ("admission.k8s.io/v1beta1", "admission.k8s.io/v1"):
        raise UnknownVersionError(f"API version {request_version} unknown.")

    request_object = request.get("request", {}).get("object", {})
    request_object_kind = request_object.get("kind")
    request_object_version = request_object.get("apiVersion")

    try:
        if request_object_version not in SUPPORTED_API_VERSIONS[request_object_kind]:
            raise UnknownVersionError(
                (
                    f"unsupported version {request_object_version} "
                    f"for resource {request_object_kind}."
                )
            )
    except KeyError as err:
        raise BaseConnaisseurException(
            f"unknown request object kind {request_object_kind}",
            create_logging_context(request),
        ) from err


def admit(request: dict, config: Config):  # pylint: disable=too-many-locals
    """
    Admits a request, parses all image names from it, validates the images,
    optionally mutates the request and sends back a response. The request is
    only allowed, if all images are successfully validated.
    """
    uid = request["request"]["uid"]
    request_object = request["request"]["object"]
    object_kind = request_object["kind"]

    # container specifications differ from deployment objects,
    # Pod/Deployment/Job/...
    containers = get_container_specs(request_object)
    patches = []

    # child resources have mutated image names, as their parents got mutated
    # before their creation. this may result in mismatch of rules or duplicate
    # lookups for already approved images. so child resources are automatically
    # approved without further check ups, when their parents were approved
    # earlier.
    acceptable_images = []
    owner_references = request_object["metadata"].get("ownerReferences", [])
    namespace = request_object["metadata"].get(
        "namespace", request["request"]["namespace"]
    )
    if owner_references:
        for index, owner in enumerate(owner_references):
            if owner["kind"] in (
                "Pod",
                "Deployment",
                "ReplicationController",
                "ReplicaSet",
                "DaemonSet",
                "StatefulSet",
                "Job",
                "CronJob",
            ):
                acceptable_images += get_parent_images(request, index, namespace)

    policy = ImagePolicy()

    # validate all images from the request
    for index, container in enumerate(containers):
        try:
            logging_context = create_logging_context(request, container["image"])

            # child approval
            if container["image"] in acceptable_images:
                msg = 'automatic child approval for "{}".'.format(container["image"])
                logging.info(str({"message": msg, "context": logging_context}))
                continue

            image = Image(container["image"])

            policy_rule = policy.get_matching_rule(image)
            verify = policy_rule.get("verify", True)
            notary_name = policy_rule.get("notary")
            notary = config.get_notary(notary_name)

            # if image doesn't need verification, continue
            if not verify:
                msg = 'no verification for image "{}".'.format(str(image))
                logging.info(str({"message": msg, "context": logging_context}))
                continue

            msg = 'start verification of image "{}".'.format(str(image))
            logging.debug(
                str(
                    {
                        "message": msg,
                        "context": dict(
                            logging_context,
                            matching_rule=policy_rule.get("pattern"),
                            host_config=notary.name,
                        ),
                    }
                )
            )

            # get signed digest and update image reference with the digest
            trusted_digest = get_trusted_digest(notary, image, policy_rule)
            image.set_digest(trusted_digest)
            patches += [
                get_json_patch(
                    object_kind=object_kind, index=index, image_name=str(image)
                )
            ]

            msg = 'successful verification of image "{}"'.format(str(image))
            logging.info(str({"message": msg, "context": logging_context}))
        except BaseConnaisseurException as err:
            err.context.update(logging_context)
            raise err

    return get_admission_review(uid, True, patch=patches)
