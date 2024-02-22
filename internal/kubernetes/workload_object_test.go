package kubernetes

import (
	"connaisseur/internal/constants"
	"connaisseur/test/testhelper"
	"context"
	"errors"
	"fmt"
	"slices"
	"testing"

	"github.com/stretchr/testify/assert"
	core "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	meta "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/dynamic/fake"
)

const PRE = "../../test/testdata/admission_requests/"

func TestConsolidatedContainers(t *testing.T) {
	var testCases = []struct {
		wlo      WorkloadObject
		expected map[string][]IdxType
	}{
		{
			WorkloadObject{
				Containers:     []core.Container{{Image: "a"}, {Image: "b"}},
				InitContainers: []core.Container{{Image: "c"}, {Image: "d"}},
				EphemeralContainers: []core.EphemeralContainer{
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "e"}},
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "f"}},
				},
			},
			map[string][]IdxType{
				"a": {{Index: 0, Type: "containers"}},
				"b": {{Index: 1, Type: "containers"}},
				"c": {{Index: 0, Type: "initContainers"}},
				"d": {{Index: 1, Type: "initContainers"}},
				"e": {{Index: 0, Type: "ephemeralContainers"}},
				"f": {{Index: 1, Type: "ephemeralContainers"}},
			},
		},
		{
			WorkloadObject{
				Containers: []core.Container{{Image: "a"}, {Image: "b"}},
				EphemeralContainers: []core.EphemeralContainer{
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "c"}},
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "d"}},
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "e"}},
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "f"}},
				},
			},
			map[string][]IdxType{
				"a": {{Index: 0, Type: "containers"}},
				"b": {{Index: 1, Type: "containers"}},
				"c": {{Index: 0, Type: "ephemeralContainers"}},
				"d": {{Index: 1, Type: "ephemeralContainers"}},
				"e": {{Index: 2, Type: "ephemeralContainers"}},
				"f": {{Index: 3, Type: "ephemeralContainers"}},
			},
		},
		{
			WorkloadObject{
				Containers:     []core.Container{{Image: "a"}, {Image: "b"}},
				InitContainers: []core.Container{{Image: "a"}, {Image: "d"}},
			},
			map[string][]IdxType{
				"a": {{Index: 0, Type: "containers"}, {Index: 0, Type: "initContainers"}},
				"b": {{Index: 1, Type: "containers"}},
				"d": {{Index: 1, Type: "initContainers"}},
			},
		},
		{
			WorkloadObject{
				Containers: []core.Container{{Image: "a"}},
				EphemeralContainers: []core.EphemeralContainer{
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "a"}},
				},
			},
			map[string][]IdxType{
				"a": {{Index: 0, Type: "containers"}, {Index: 0, Type: "ephemeralContainers"}},
			},
		},
	}

	for _, tc := range testCases {
		con := tc.wlo.ConsolidatedContainers()
		assert.Equal(t, len(tc.expected), len(con))
		for k, v := range con {
			vv := tc.expected[k]
			assert.Equal(t, len(vv), len(v))
			for i, idxT := range v {
				assert.Equal(t, vv[i].Index, idxT.Index)
				assert.Equal(t, vv[i].Type, idxT.Type)
			}
		}
	}
}

func TestImageSet(t *testing.T) {
	var testCases = []struct {
		wlo      WorkloadObject
		expected []string
	}{
		{
			WorkloadObject{
				Containers:     []core.Container{{Image: "a"}, {Image: "b"}},
				InitContainers: []core.Container{{Image: "c"}, {Image: "d"}},
				EphemeralContainers: []core.EphemeralContainer{
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "e"}},
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "f"}},
				},
			},
			[]string{"a", "b", "c", "d", "e", "f"},
		},
		{
			WorkloadObject{
				Containers:     []core.Container{{Image: "a"}, {Image: "b"}},
				InitContainers: []core.Container{{Image: "a"}, {Image: "c"}},
				EphemeralContainers: []core.EphemeralContainer{
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "b"}},
					{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "c"}},
				},
			},
			[]string{"a", "b", "c"},
		},
	}

	for _, tc := range testCases {
		is := tc.wlo.ImageSet()
		for _, image := range is {
			assert.True(t, slices.Contains[[]string, string](tc.expected, image))
		}
		for _, image := range tc.expected {
			assert.True(t, slices.Contains[[]string, string](is, image))
		}
	}
}

func TestContainerPath(t *testing.T) {
	var testCases = []struct {
		wlo      WorkloadObject
		expected string
	}{
		{
			WorkloadObject{
				Kind: "Deployment",
			},
			"/spec/template/spec/%s/%d/image",
		},
		{
			WorkloadObject{
				Kind: "Pod",
			},
			"/spec/%s/%d/image",
		},
		{
			WorkloadObject{
				Kind: "ReplicaSet",
			},
			"/spec/template/spec/%s/%d/image",
		},
		{
			WorkloadObject{
				Kind: "CronJob",
			},
			"/spec/jobTemplate/spec/template/spec/%s/%d/image",
		},
	}

	for _, tc := range testCases {
		assert.Equal(t, tc.expected, tc.wlo.ContainerPathFormatString())
	}
}

func TestNewWorkloadObjectFromBytes(t *testing.T) {
	trueVar := true
	var testCases = []struct {
		admissionReview string
		kind            string
		namespace       string
		expectedWLO     *WorkloadObject
		expectedErr     error
	}{
		{ // 1: Deployment
			"01_deployment",
			"Deployment",
			"test-connaisseur",
			&WorkloadObject{
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
			nil,
		},
		{ // 2: Pod
			"02_pod",
			"Pod",
			"test-connaisseur",
			&WorkloadObject{
				"charlie-deployment-76fbf58b7d-",
				"Pod",
				"test-connaisseur",
				[]core.Container{{
					Name:  "test-connaisseur",
					Image: "securesystemsengineering/charlie-image@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
					Ports: []core.ContainerPort{{
						ContainerPort: 5000,
						Protocol:      "TCP",
					}},
					Resources: core.ResourceRequirements{},
					VolumeMounts: []core.VolumeMount{{
						Name:      "default-token-hn7nn",
						ReadOnly:  true,
						MountPath: "/var/run/secrets/kubernetes.io/serviceaccount",
					}},
					TerminationMessagePath:   "/dev/termination-log",
					TerminationMessagePolicy: "File",
					ImagePullPolicy:          "Always",
				}},
				nil,
				nil,
				[]meta.OwnerReference{{
					APIVersion:         "apps/v1",
					Kind:               "ReplicaSet",
					Name:               "charlie-deployment-76fbf58b7d",
					UID:                "090d26f8-1812-11ea-b3fc-02897404852e",
					Controller:         &trueVar,
					BlockOwnerDeletion: &trueVar,
				}},
			},
			nil,
		},
		{ // 3: ReplicaSet
			"03_replicaset",
			"ReplicaSet",
			"test-connaisseur",
			&WorkloadObject{
				"charlie-deployment-558576bf6c",
				"ReplicaSet",
				"test-connaisseur",
				[]core.Container{{
					Name:  "test-connaisseur",
					Image: "securesystemsengineering/sample-san-sama:hai",
					Ports: []core.ContainerPort{{
						ContainerPort: 5000,
						Protocol:      "TCP",
					}},
					Resources:                core.ResourceRequirements{},
					VolumeMounts:             nil,
					TerminationMessagePath:   "/dev/termination-log",
					TerminationMessagePolicy: "File",
					ImagePullPolicy:          "Always",
				}},
				nil,
				nil,
				[]meta.OwnerReference{{
					APIVersion:         "apps/v1",
					Kind:               "Deployment",
					Name:               "charlie-deployment",
					UID:                "3a3a7b38-5512-4a85-94bb-3562269e0a6a",
					Controller:         &trueVar,
					BlockOwnerDeletion: &trueVar,
				}},
			},
			nil,
		},
		{ // 4: CronJob
			"04_cronjob",
			"CronJob",
			"connaisseur",
			&WorkloadObject{
				"yooob",
				"CronJob",
				"connaisseur",
				[]core.Container{{
					Name:                     "yooob",
					Image:                    "busybox",
					Ports:                    nil,
					Resources:                core.ResourceRequirements{},
					VolumeMounts:             nil,
					TerminationMessagePath:   "/dev/termination-log",
					TerminationMessagePolicy: "File",
					ImagePullPolicy:          "Always",
				}},
				nil,
				nil,
				nil,
			},
			nil,
		},
		{ // 5: ReplicationController
			"05_replication_controller",
			"ReplicationController",
			"connaisseur",
			&WorkloadObject{
				"nginx",
				"ReplicationController",
				"connaisseur",
				[]core.Container{{
					Name:  "nginx",
					Image: "nginx",
					Ports: []core.ContainerPort{
						{
							ContainerPort: 80,
							Protocol:      "TCP",
						},
					},
					Resources:                core.ResourceRequirements{},
					VolumeMounts:             nil,
					TerminationMessagePath:   "/dev/termination-log",
					TerminationMessagePolicy: "File",
					ImagePullPolicy:          "Always",
				}},
				nil,
				nil,
				nil,
			},
			nil,
		},
		{ // 6: DaemonSet
			"06_daemonset",
			"DaemonSet",
			"kube-system",
			&WorkloadObject{
				"fluentd-elasticsearch",
				"DaemonSet",
				"kube-system",
				[]core.Container{{
					Name:  "fluentd-elasticsearch",
					Image: "quay.io/fluentd_elasticsearch/fluentd:v2.5.2",
					Ports: nil,
					Resources: core.ResourceRequirements{
						Limits: core.ResourceList{
							"memory": resource.MustParse("200Mi"),
						},
						Requests: core.ResourceList{
							"memory": resource.MustParse("200Mi"),
							"cpu":    resource.MustParse("100m"),
						},
					},
					VolumeMounts: []core.VolumeMount{
						{
							Name:      "varlog",
							MountPath: "/var/log",
						},
					},
					TerminationMessagePath:   "/dev/termination-log",
					TerminationMessagePolicy: "File",
					ImagePullPolicy:          "IfNotPresent",
				}},
				nil,
				nil,
				nil,
			},
			nil,
		},
		{ // 7: StatefulSet
			"07_statefulset",
			"StatefulSet",
			"connaisseur",
			&WorkloadObject{
				"web",
				"StatefulSet",
				"connaisseur",
				[]core.Container{{
					Name:  "nginx",
					Image: "registry.k8s.io/nginx-slim:0.8",
					Ports: []core.ContainerPort{
						{
							Name:          "web",
							ContainerPort: 80,
							Protocol:      "TCP",
						},
					},
					Resources: core.ResourceRequirements{},
					VolumeMounts: []core.VolumeMount{
						{
							Name:      "www",
							MountPath: "/usr/share/nginx/html",
						},
					},
					TerminationMessagePath:   "/dev/termination-log",
					TerminationMessagePolicy: "File",
					ImagePullPolicy:          "IfNotPresent",
				}},
				nil,
				nil,
				nil,
			},
			nil,
		},
		{ // 8: Job
			"08_job",
			"Job",
			"connaisseur",
			&WorkloadObject{
				"pi",
				"Job",
				"connaisseur",
				[]core.Container{{
					Name:  "pi",
					Image: "perl:5.34.0",
					Ports: nil,
					Command: []string{
						"perl",
						"-Mbignum=bpi",
						"-wle",
						"print bpi(2000)",
					},
					Resources:                core.ResourceRequirements{},
					VolumeMounts:             nil,
					TerminationMessagePath:   "/dev/termination-log",
					TerminationMessagePolicy: "File",
					ImagePullPolicy:          "IfNotPresent",
				}},
				nil,
				nil,
				nil,
			},
			nil,
		},
		{ // 9: invlid Pod
			"12_err_pod",
			"",
			"",
			nil,
			errors.New("unknown workload kind \"\""),
		},
		{ // 10:
			"19_pod_initcontainer",
			"Pod",
			"test-connaisseur",
			&WorkloadObject{
				"charlie-deployment-76fbf58b7d-",
				"Pod",
				"test-connaisseur",
				[]core.Container{{
					Name:  "test-connaisseur",
					Image: "securesystemsengineering/charlie-image@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
					Ports: []core.ContainerPort{{
						ContainerPort: 5000,
						Protocol:      "TCP",
					}},
					Resources: core.ResourceRequirements{},
					VolumeMounts: []core.VolumeMount{{
						Name:      "default-token-hn7nn",
						ReadOnly:  true,
						MountPath: "/var/run/secrets/kubernetes.io/serviceaccount",
					}},
					TerminationMessagePath:   "/dev/termination-log",
					TerminationMessagePolicy: "File",
					ImagePullPolicy:          "Always",
				}},
				[]core.Container{{
					Image:           "nginx",
					ImagePullPolicy: "Always",
					Name:            "my-initcontainer",
					Ports: []core.ContainerPort{
						{
							ContainerPort: 5000,
							Protocol:      "TCP",
						},
					},
					Resources:                core.ResourceRequirements{},
					TerminationMessagePath:   "/dev/termination-log",
					TerminationMessagePolicy: "File",
					VolumeMounts: []core.VolumeMount{
						{
							MountPath: "/var/run/secrets/kubernetes.io/serviceaccount",
							Name:      "kube-api-access-ndgq4",
							ReadOnly:  true,
						},
					},
				}},
				nil,
				[]meta.OwnerReference{{

					APIVersion:         "apps/v1",
					Kind:               "ReplicaSet",
					Name:               "charlie-deployment-76fbf58b7d",
					UID:                "090d26f8-1812-11ea-b3fc-02897404852e",
					Controller:         &trueVar,
					BlockOwnerDeletion: &trueVar,
				}},
			},
			nil,
		},
		{ //11:
			"20_pod_ephemeralcontainer",
			"Pod",
			"test-connaisseur",
			&WorkloadObject{
				"charlie-deployment-76fbf58b7d-",
				"Pod",
				"test-connaisseur",
				[]core.Container{{
					Name:  "test-connaisseur",
					Image: "securesystemsengineering/charlie-image@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
					Ports: []core.ContainerPort{{
						ContainerPort: 5000,
						Protocol:      "TCP",
					}},
					Resources: core.ResourceRequirements{},
					VolumeMounts: []core.VolumeMount{{
						Name:      "default-token-hn7nn",
						ReadOnly:  true,
						MountPath: "/var/run/secrets/kubernetes.io/serviceaccount",
					}},
					TerminationMessagePath:   "/dev/termination-log",
					TerminationMessagePolicy: "File",
					ImagePullPolicy:          "Always",
				}},
				nil,
				[]core.EphemeralContainer{{
					EphemeralContainerCommon: core.EphemeralContainerCommon{
						Image:                    "nginx",
						ImagePullPolicy:          "Always",
						Name:                     "my-initcontainer",
						Resources:                core.ResourceRequirements{},
						TerminationMessagePath:   "/dev/termination-log",
						TerminationMessagePolicy: "File",
					},
				}},
				[]meta.OwnerReference{{

					APIVersion:         "apps/v1",
					Kind:               "ReplicaSet",
					Name:               "charlie-deployment-76fbf58b7d",
					UID:                "090d26f8-1812-11ea-b3fc-02897404852e",
					Controller:         &trueVar,
					BlockOwnerDeletion: &trueVar,
				}},
			},
			nil,
		},
		// This test should cover the case when a workload resource has a mislabled kind
		{ // 12:
			"04_cronjob",
			"Pod",
			"connaisseur",
			nil,
			fmt.Errorf("no containers found in workload object"),
		},
	}

	for idx, tc := range testCases {
		ar := testhelper.RetrieveAdmissionReview(PRE + tc.admissionReview + ".json")
		wl, err := NewWorkloadObjectFromBytes(ar.Request.Object.Raw, schema.GroupVersionKind{Kind: tc.kind}, tc.namespace)
		assert.Equal(t, tc.expectedWLO, wl, "test case %d", idx+1)
		assert.Equal(t, tc.expectedErr, err, "test case %d", idx+1)
	}
}

func TestParentContainerImagesFromKubeAPI(t *testing.T) {
	var testCases = []struct {
		child                    WorkloadObject
		api                      string
		namespace                string
		name                     string
		uid                      string
		containerImages          []string
		initContainerImages      []string
		ephemeralContainerImages []string
		expected                 []string
	}{
		{ // 1: Normal owner
			WorkloadObject{
				"childName",
				"Pod",
				"childNamespace",
				nil,
				nil,
				nil,
				[]meta.OwnerReference{{
					APIVersion: "apps/v1",
					Kind:       "ReplicaSet",
					Name:       "ownerName",
					UID:        "090d26f8-1812-11ea-b3fc-02897404852e",
				}},
			},
			"apps/v1",
			"childNamespace",
			"ownerName",
			"090d26f8-1812-11ea-b3fc-02897404852e",
			[]string{"ownerImage"},
			[]string{},
			[]string{},
			[]string{"ownerImage"},
		},
		{ // 2: Owner with multiple images
			WorkloadObject{
				"childName",
				"Pod",
				"childNamespace",
				nil,
				nil,
				nil,
				[]meta.OwnerReference{{
					APIVersion: "apps/v1",
					Kind:       "ReplicaSet",
					Name:       "ownerName",
					UID:        "090d26f8-1812-11ea-b3fc-02897404852e",
				}},
			},
			"apps/v1",
			"childNamespace",
			"ownerName",
			"090d26f8-1812-11ea-b3fc-02897404852e",
			[]string{"ownerImage1", "ownerImage2"},
			[]string{},
			[]string{},
			[]string{"ownerImage1", "ownerImage2"},
		},
		{ // 3: Owner with init container
			WorkloadObject{
				"childName",
				"Pod",
				"childNamespace",
				nil,
				nil,
				nil,
				[]meta.OwnerReference{{
					APIVersion: "apps/v1",
					Kind:       "ReplicaSet",
					Name:       "ownerName",
					UID:        "090d26f8-1812-11ea-b3fc-02897404852e",
				}},
			},
			"apps/v1",
			"childNamespace",
			"ownerName",
			"090d26f8-1812-11ea-b3fc-02897404852e",
			[]string{"ownerImage1"},
			[]string{"ownerImage2"},
			nil,
			[]string{"ownerImage1", "ownerImage2"},
		},
		{ // 4: Owner with ephemeral container usually doesn't work (invalid spec)
			WorkloadObject{
				"childName",
				"Pod",
				"childNamespace",
				nil,
				nil,
				nil,
				[]meta.OwnerReference{{
					APIVersion: "apps/v1",
					Kind:       "ReplicaSet",
					Name:       "ownerName",
					UID:        "090d26f8-1812-11ea-b3fc-02897404852e",
				}},
			},
			"apps/v1",
			"childNamespace",
			"ownerName",
			"090d26f8-1812-11ea-b3fc-02897404852e",
			[]string{"ownerImage1"},
			nil,
			[]string{"ownerImage2"},
			[]string{"ownerImage1"},
		},
		{ // 5: Owner Pod(!) with ephemeral container works (it is possible, though maybe not terribly useful)
			WorkloadObject{
				"childName",
				"Pod",
				"childNamespace",
				nil,
				nil,
				nil,
				[]meta.OwnerReference{{
					APIVersion: "v1",
					Kind:       "Pod",
					Name:       "ownerName",
					UID:        "090d26f8-1812-11ea-b3fc-02897404852e",
				}},
			},
			"v1",
			"childNamespace",
			"ownerName",
			"090d26f8-1812-11ea-b3fc-02897404852e",
			[]string{"ownerImage1"},
			nil,
			[]string{"ownerImage2"},
			[]string{"ownerImage1", "ownerImage2"},
		},
		{ // 6: Owner with smaller API group
			WorkloadObject{
				"childName",
				"Pod",
				"childNamespace",
				nil,
				nil,
				nil,
				[]meta.OwnerReference{{
					APIVersion: "itsJustAppsNoSlash",
					Kind:       "ReplicaSet",
					Name:       "ownerName",
					UID:        "090d26f8-1812-11ea-b3fc-02897404852e",
				}},
			},
			"itsJustAppsNoSlash",
			"childNamespace",
			"ownerName",
			"090d26f8-1812-11ea-b3fc-02897404852e",
			[]string{"ownerImage"},
			[]string{},
			[]string{},
			[]string{"ownerImage"},
		},
		{ // 7: Owner in different namespace
			WorkloadObject{
				"childName",
				"Pod",
				"childNamespace",
				nil,
				nil,
				nil,
				[]meta.OwnerReference{{
					APIVersion: "apps/v1",
					Kind:       "ReplicaSet",
					Name:       "ownerName",
					UID:        "090d26f8-1812-11ea-b3fc-02897404852e",
				}},
			},
			"apps/v1",
			"ownerNamespace",
			"ownerName",
			"090d26f8-1812-11ea-b3fc-02897404852e",
			[]string{"ownerImage"},
			[]string{},
			[]string{},
			nil,
		},
		{ // 8: Owner with unexpected UID
			WorkloadObject{
				"childName",
				"Pod",
				"childNamespace",
				nil,
				nil,
				nil,
				[]meta.OwnerReference{{
					APIVersion: "apps/v1",
					Kind:       "ReplicaSet",
					Name:       "ownerName",
					UID:        "090d26f8-1812-11ea-b3fc-02897404852e",
				}},
			},
			"apps/v1",
			"childNamespace",
			"ownerName",
			"definitely the wrong UID",
			[]string{"ownerImage"},
			[]string{},
			[]string{},
			nil,
		},
	}

	for idx, tc := range testCases {
		objects := []runtime.Object{
			newUnstructured(
				tc.api,
				tc.child.Owners[0].Kind,
				tc.namespace,
				tc.name,
				tc.uid,
				tc.containerImages,
				tc.initContainerImages,
				tc.ephemeralContainerImages,
			),
		}
		scheme := runtime.NewScheme()
		client := fake.NewSimpleDynamicClient(scheme, objects...)
		ctx := context.Background()
		ctx = context.WithValue(ctx, constants.KubeAPI, client)

		parentImages := tc.child.ParentContainerImagesFromKubeAPI(ctx)
		assert.Equal(t, tc.expected, parentImages, idx+1)
	}
}

func TestParentContainerImagesFromKubeAPIMissingAPI(t *testing.T) {
	wlo := WorkloadObject{
		"childName",
		"Pod",
		"childNamespace",
		nil,
		nil,
		nil,
		[]meta.OwnerReference{{
			APIVersion: "apps/v1",
			Kind:       "ReplicaSet",
			Name:       "ownerName",
			UID:        "090d26f8-1812-11ea-b3fc-02897404852e",
		}},
	}

	parentImages := wlo.ParentContainerImagesFromKubeAPI(context.Background())

	assert.Equal(t, []string{}, parentImages)
}

func TestParentContainerImagesFromKubeAPIMultipleOwners(t *testing.T) {
	child := WorkloadObject{
		"childName",
		"Pod",
		"someNs",
		nil,
		nil,
		nil,
		[]meta.OwnerReference{
			{
				APIVersion: "apps/v1",
				Kind:       "ReplicaSet",
				Name:       "ownerName1",
				UID:        "090d26f8-1812-11ea-b3fc-02897404852e",
			},
			{
				APIVersion: "apps/v1",
				Kind:       "Deployment",
				Name:       "ownerName2",
				UID:        "deadbeef-1812-11ea-b3fc-02897404852e",
			}},
	}

	objects := []runtime.Object{
		newUnstructured( // owner1
			"apps/v1",
			"ReplicaSet",
			"someNs",
			"ownerName1",
			"090d26f8-1812-11ea-b3fc-02897404852e",
			[]string{"ownerImage1"},
			nil,
			nil,
		),
		newUnstructured( // owner2
			"apps/v1",
			"Deployment",
			"someNs",
			"ownerName2",
			"deadbeef-1812-11ea-b3fc-02897404852e",
			[]string{"ownerImage2"},
			nil,
			nil,
		),
	}
	scheme := runtime.NewScheme()
	client := fake.NewSimpleDynamicClient(scheme, objects...)
	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.KubeAPI, client)

	parentImages := child.ParentContainerImagesFromKubeAPI(ctx)
	assert.Equal(t, []string{"ownerImage1", "ownerImage2"}, parentImages)
}
