package kubernetes

import (
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
		admissionReview string
		expectedAro     *AdmissionRequestObjects
		expectedErr     error
	}{
		{
			"01_deployment",
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
					false,
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
					false,
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
					false,
				},
				Kind:      "ReplicaSet",
				Namespace: "default",
				Operation: "UPDATE",
			},
			nil,
		},
		{
			"21_broken_admission_request",
			nil,
			errors.New("error decoding new workload object: unknown workload kind \"\""),
		},
		{
			"26_broken_update_admission_request",
			nil,
			errors.New("error decoding old workload object: unknown workload kind \"\""),
		},
	}

	for _, tc := range testCases {
		ar := testhelper.RetrieveAdmissionReview(PRE + tc.admissionReview + ".json")
		aro, err := NewAdmissionRequestObjects(ar.Request)
		assert.Equal(t, tc.expectedAro, aro)
		assert.Equal(t, tc.expectedErr, err)
	}
}
