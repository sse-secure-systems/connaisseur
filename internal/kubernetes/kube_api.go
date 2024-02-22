package kubernetes

import (
	"context"
	"fmt"
	"strings"

	meta "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/dynamic"
)

// Returns a kubernetes resource.
func fetchKubeResource(
	client dynamic.Interface,
	ctx context.Context,
	group string,
	version string,
	resource string,
	namespace string,
	name string,
) (*unstructured.Unstructured, error) {
	resource = fmt.Sprintf("%ss", strings.ToLower(resource))

	resourceId := schema.GroupVersionResource{
		Group:    group,
		Version:  version,
		Resource: resource,
	}
	res, err := client.Resource(resourceId).Namespace(namespace).Get(ctx, name, meta.GetOptions{})
	if err != nil {
		return nil, fmt.Errorf("error getting resource: %s", err)
	}
	return res, nil
}
