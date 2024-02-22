package kubernetes

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/utils"
	"fmt"

	admission "k8s.io/api/admission/v1"
	core "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/runtime/schema"
)

type AdmissionRequestObjects struct {
	// The new to be deployed WorkloadObject
	NewObj *WorkloadObject
	// The old to be updated WorkloadObject, should the request
	// be an UPDATE one.
	OldObj *WorkloadObject
	// Kind of both the workload objects
	Kind string
	// Namespace of both the workload objects
	Namespace string
	// Type of AdmissionRequest
	Operation admission.Operation
}

func NewAdmissionRequestObjects(ar *admission.AdmissionRequest) (*AdmissionRequestObjects, error) {
	var err error
	oldWLO := &WorkloadObject{Containers: []core.Container{}, InitContainers: []core.Container{}}

	// the old obj has empty containers, init containers and ephemeral containers per default and is
	// only
	// filled if the request is an UPDATE one and the automatic unchanged approval
	// feature flag is on.
	if utils.FeatureFlagOn(constants.AutomaticUnchangedApproval) &&
		ar.Operation == admission.Update {
		oldWLO, err = NewWorkloadObjectFromBytes(ar.OldObject.Raw, (schema.GroupVersionKind)(ar.Kind), ar.Namespace)
		if err != nil {
			return nil, fmt.Errorf("error decoding old workload object: %s", err)
		}
	}

	wlo, err := NewWorkloadObjectFromBytes(ar.Object.Raw, (schema.GroupVersionKind)(ar.Kind), ar.Namespace)
	if err != nil {
		return nil, fmt.Errorf("error decoding new workload object: %s", err)
	}
	return &AdmissionRequestObjects{
		NewObj:    wlo,
		OldObj:    oldWLO,
		Kind:      ar.Kind.Kind,
		Namespace: ar.Namespace,
		Operation: ar.Operation,
	}, err
}
