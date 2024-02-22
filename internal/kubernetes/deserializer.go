package kubernetes

import (
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/runtime/serializer"
)

var (
	runtimeScheme = runtime.NewScheme()
	codecFactory  = serializer.NewCodecFactory(runtimeScheme)
	Deserializer  = codecFactory.UniversalDeserializer()
)

// Deserializes a given byte array into a runtime.Object.
func Deserialize(raw []byte, kind *schema.GroupVersionKind, obj runtime.Object) (runtime.Object, error) {
	new_obj, _, err := Deserializer.Decode(raw, kind, obj)
	return new_obj, err
}
