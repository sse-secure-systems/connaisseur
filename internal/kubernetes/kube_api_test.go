package kubernetes

import (
	"context"
	"fmt"
	"testing"

	"github.com/stretchr/testify/assert"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/client-go/dynamic/fake"
)

func TestFetchKubeResource(t *testing.T) {
	objects := []runtime.Object{
		newUnstructured(
			"apps/v1",
			"ReplicaSet",
			"test-connaisseur",
			"charlie-deployment-76fbf58b7d",
			"090d26f8-1812-11ea-b3fc-02897404852e",
			[]string{"image"},
			nil,
			nil,
		),
	}
	scheme := runtime.NewScheme()
	client := fake.NewSimpleDynamicClient(scheme, objects...)
	ctx := context.Background()

	res, err := fetchKubeResource(
		client,
		ctx,
		"apps",
		"v1",
		"ReplicaSet",
		"test-connaisseur",
		"charlie-deployment-76fbf58b7d",
	)
	assert.Nil(t, err)
	assert.Equal(t, "charlie-deployment-76fbf58b7d", res.GetName())

	res, err = fetchKubeResource(
		client,
		ctx,
		"apps",
		"v1",
		"ReplicaSet",
		"test-connaisseur",
		"non-existing",
	)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "error getting resource")
	assert.Nil(t, res)
}

func newUnstructured(
	apiVersion, kind, namespace, name, uid string,
	containerImages, initContainerImages, ephemeralContainerImages []string,
) *unstructured.Unstructured {
	var spec map[string]interface{}

	containers := []interface{}{}
	for i := range containerImages {
		containers = append(containers, map[string]interface{}{
			"name":  fmt.Sprintf("container%d", i),
			"image": containerImages[i],
		})
	}
	initContainers := []interface{}{}
	for i := range initContainerImages {
		initContainers = append(initContainers, map[string]interface{}{
			"name":  fmt.Sprintf("initContainer%d", i),
			"image": initContainerImages[i],
		})
	}
	ephemeralContainers := []interface{}{}
	for i := range ephemeralContainerImages {
		ephemeralContainers = append(ephemeralContainers, map[string]interface{}{
			"name":  fmt.Sprintf("ephemeralContainer%d", i),
			"image": ephemeralContainerImages[i],
		})
	}

	switch kind {
	case "Pod":
		spec = map[string]interface{}{
			"containers":          containers,
			"initContainers":      initContainers,
			"ephemeralContainers": ephemeralContainers,
		}
	case "Deployment":
		spec = map[string]interface{}{
			"template": map[string]interface{}{
				"spec": map[string]interface{}{
					"containers":          containers,
					"initContainers":      initContainers,
					"ephemeralContainers": ephemeralContainers,
				},
			},
		}
	case "ReplicaSet":
		spec = map[string]interface{}{
			"template": map[string]interface{}{
				"spec": map[string]interface{}{
					"containers":          containers,
					"initContainers":      initContainers,
					"ephemeralContainers": ephemeralContainers,
				},
			},
		}
	}

	return &unstructured.Unstructured{
		Object: map[string]interface{}{
			"apiVersion": apiVersion,
			"kind":       kind,
			"metadata": map[string]interface{}{
				"namespace": namespace,
				"name":      name,
				"uid":       uid,
			},
			"spec": spec,
		},
	}
}
