package kubernetes

import (
	"connaisseur/internal/constants"
	"connaisseur/test/testhelper"
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
	core "k8s.io/api/core/v1"
	meta "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func TestNewAdmissionRequestObjects(t *testing.T) {
	trueVar := true
	const PRE = "../../test/testdata/admission_requests/"
	var testCases = []struct {
		admissionReview         string
		automaticUpdateApproval string
		expectedAro             *AdmissionRequestObjects
		expectedErr             error
	}{
		{
			"01_deployment",
			"false",
			&AdmissionRequestObjects{
				NewObj: &WorkloadObject{
					"charlie-deployment",
					"Deployment",
					"test-connaisseur",
					[]core.Container{{
						Name:  "test-connaisseur",
						Image: "securesystemsengineering/alice-image:test",
						Ports: []core.ContainerPort{{
							ContainerPort: 5000,
							Protocol:      "TCP",
						}},
						Resources:                core.ResourceRequirements{},
						TerminationMessagePath:   "/dev/termination-log",
						TerminationMessagePolicy: "File",
						ImagePullPolicy:          "Always",
					}},
					nil,
					nil,
					nil,
				},
				OldObj: &WorkloadObject{
					Containers:     []core.Container{},
					InitContainers: []core.Container{},
				},
				Kind:      "Deployment",
				Namespace: "test-connaisseur",
				Operation: "CREATE",
			},
			nil,
		},
		{
			"10_update",
			"true",
			&AdmissionRequestObjects{
				NewObj: &WorkloadObject{
					"test-58d59c69bf",
					"ReplicaSet",
					"default",
					[]core.Container{{
						Name:                     "nginx",
						Image:                    "docker.io/library/redis:latest@sha256:1111111111111111111111111111111111111111111111111111111111111111",
						Resources:                core.ResourceRequirements{},
						TerminationMessagePath:   "/dev/termination-log",
						TerminationMessagePolicy: "File",
						ImagePullPolicy:          "Always",
					}},
					nil,
					nil,
					[]meta.OwnerReference{{

						APIVersion:         "apps/v1",
						Kind:               "Deployment",
						Name:               "test",
						UID:                "8d8adb16-b1fc-487d-a778-3b6f556a9050",
						Controller:         &trueVar,
						BlockOwnerDeletion: &trueVar,
					}},
				},
				OldObj: &WorkloadObject{
					"test-58d59c69bf",
					"ReplicaSet",
					"default",
					[]core.Container{{
						Name:                     "nginx",
						Image:                    "docker.io/library/redis:latest@sha256:1111111111111111111111111111111111111111111111111111111111111111",
						Resources:                core.ResourceRequirements{},
						TerminationMessagePath:   "/dev/termination-log",
						TerminationMessagePolicy: "File",
						ImagePullPolicy:          "Always",
					}},
					nil,
					nil,
					[]meta.OwnerReference{{

						APIVersion:         "apps/v1",
						Kind:               "Deployment",
						Name:               "test",
						UID:                "8d8adb16-b1fc-487d-a778-3b6f556a9050",
						Controller:         &trueVar,
						BlockOwnerDeletion: &trueVar,
					}},
				},
				Kind:      "ReplicaSet",
				Namespace: "default",
				Operation: "UPDATE",
			},
			nil,
		},
		{
			"21_broken_admission_request",
			"false",
			nil,
			errors.New("error decoding new workload object: unknown workload kind \"\""),
		},
		{
			"21_broken_admission_request",
			"true",
			nil,
			errors.New("error decoding old workload object: unknown workload kind \"\""),
		},
	}

	for _, tc := range testCases {
		t.Setenv(constants.AutomaticUnchangedApproval, tc.automaticUpdateApproval)
		ar := testhelper.RetrieveAdmissionReview(PRE + tc.admissionReview + ".json")
		aro, err := NewAdmissionRequestObjects(ar.Request)
		assert.Equal(t, tc.expectedAro, aro)
		assert.Equal(t, tc.expectedErr, err)
	}
}
