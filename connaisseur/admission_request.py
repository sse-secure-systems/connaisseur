import json
from jsonschema import validate, ValidationError
from connaisseur.k8s_object import K8sObject
from connaisseur.exceptions import InvalidFormatException


class AdmissionRequest:
    def __init__(self, ad_request: dict):
        self.__validate(ad_request)

        request = ad_request["request"]
        self.uid = request["uid"]
        self.kind = request["kind"]["kind"]
        self.namespace = request["namespace"]
        self.operation = request["operation"]
        self.user = request["userInfo"]["username"]
        self.k8s_object = K8sObject(request["object"], self.namespace)

    def __validate(self, request: dict):
        with open("/app/connaisseur/res/ad_request_schema.json", "r") as schemafile:
            schema = json.load(schemafile)

        try:
            validate(instance=request, schema=schema)
        except ValidationError as err:
            msg = "{validation_kind} has an invalid format: {validation_err}."
            raise InvalidFormatException(
                message=msg,
                validation_kind="AdmissionRequest",
                validation_err=str(err),
                request=request,
            ) from err

    @property
    def context(self):
        return {
            "user": self.user,
            "operation": self.operation,
            "kind": self.kind,
            "name": self.k8s_object.name,
            "namespace": self.namespace,
        }
