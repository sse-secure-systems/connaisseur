package kubernetes

import (
	"connaisseur/internal/constants"
	"context"
	"fmt"
	"strings"

	"github.com/sirupsen/logrus"
	apps "k8s.io/api/apps/v1"
	batch "k8s.io/api/batch/v1"
	core "k8s.io/api/core/v1"
	meta "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/dynamic"
)

type WorkloadObject struct {
	// Name of the workload object
	Name string
	// Kind of the workload object
	Kind string
	// Namespace of the workload object
	Namespace string
	// Containers of the workload object
	Containers []core.Container
	// InitContainers of the workload object
	InitContainers []core.Container
	// Ephemeral containers of the workload object
	EphemeralContainers []core.EphemeralContainer
	// OwnerReferences of the workload object
	Owners []meta.OwnerReference
}

type IdxType struct {
	// Index of the container in the pod
	Index int
	// Type of the container (container, init container or ephemeral container)
	Type string
}

// Returns a new WorkloadObject from the given byte array.
func NewWorkloadObjectFromBytes(
	raw []byte,
	kind schema.GroupVersionKind,
	namespace string,
) (*WorkloadObject, error) {
	var (
		name                string
		containers          []core.Container
		initContainers      []core.Container
		ephemeralContainers []core.EphemeralContainer
		owners              []meta.OwnerReference
		err                 error
		obj                 runtime.Object
		ok                  bool
	)
	switch kind.Kind {
	case "Pod":
		pod := &core.Pod{}
		obj, err = Deserialize(raw, &kind, pod)
		pod, ok = obj.(*core.Pod)
		if !ok {
			err = fmt.Errorf("deserialize conversion to \"%s\" has failed", kind.Kind)
			return nil, err
		}
		name = pod.Name
		if name == "" {
			name = pod.GenerateName
		}
		containers = pod.Spec.Containers
		initContainers = pod.Spec.InitContainers
		ephemeralContainers = pod.Spec.EphemeralContainers
		owners = pod.OwnerReferences
	case "Deployment":
		deployment := &apps.Deployment{}
		obj, err = Deserialize(raw, &kind, deployment)
		deployment, ok = obj.(*apps.Deployment)
		if !ok {
			err = fmt.Errorf("deserialize conversion to \"%s\" has failed", kind.Kind)
			return nil, err
		}
		name = deployment.Name
		containers = deployment.Spec.Template.Spec.Containers
		initContainers = deployment.Spec.Template.Spec.InitContainers
		owners = deployment.OwnerReferences
	case "ReplicationController":
		rplc := &core.ReplicationController{}
		obj, err = Deserialize(raw, &kind, rplc)
		rplc, ok = obj.(*core.ReplicationController)
		if !ok {
			err = fmt.Errorf("deserialize conversion to \"%s\" has failed", kind.Kind)
			return nil, err
		}
		name = rplc.Name
		containers = rplc.Spec.Template.Spec.Containers
		initContainers = rplc.Spec.Template.Spec.InitContainers
		owners = rplc.OwnerReferences
	case "ReplicaSet":
		rpls := &apps.ReplicaSet{}
		obj, err = Deserialize(raw, &kind, rpls)
		rpls, ok = obj.(*apps.ReplicaSet)
		if !ok {
			err = fmt.Errorf("deserialize conversion to \"%s\" has failed", kind.Kind)
			return nil, err
		}
		name = rpls.Name
		containers = rpls.Spec.Template.Spec.Containers
		initContainers = rpls.Spec.Template.Spec.InitContainers
		owners = rpls.OwnerReferences
	case "DaemonSet":
		ds := &apps.DaemonSet{}
		obj, err = Deserialize(raw, &kind, ds)
		ds, ok = obj.(*apps.DaemonSet)
		if !ok {
			err = fmt.Errorf("deserialize conversion to \"%s\" has failed", kind.Kind)
			return nil, err
		}
		name = ds.Name
		containers = ds.Spec.Template.Spec.Containers
		initContainers = ds.Spec.Template.Spec.InitContainers
		owners = ds.OwnerReferences
	case "StatefulSet":
		sts := &apps.StatefulSet{}
		obj, err = Deserialize(raw, &kind, sts)
		sts, ok = obj.(*apps.StatefulSet)
		if !ok {
			err = fmt.Errorf("deserialize conversion to \"%s\" has failed", kind.Kind)
			return nil, err
		}
		name = sts.Name
		containers = sts.Spec.Template.Spec.Containers
		initContainers = sts.Spec.Template.Spec.InitContainers
		owners = sts.OwnerReferences
	case "Job":
		job := &batch.Job{}
		obj, err = Deserialize(raw, &kind, job)
		job, ok = obj.(*batch.Job)
		if !ok {
			err = fmt.Errorf("deserialize conversion to \"%s\" has failed", kind.Kind)
			return nil, err
		}
		name = job.Name
		containers = job.Spec.Template.Spec.Containers
		initContainers = job.Spec.Template.Spec.InitContainers
		owners = job.OwnerReferences
	case "CronJob":
		cj := &batch.CronJob{}
		obj, err = Deserialize(raw, &kind, cj)
		cj, ok = obj.(*batch.CronJob)
		if !ok {
			err = fmt.Errorf("deserialize conversion to \"%s\" has failed", kind.Kind)
			return nil, err
		}
		name = cj.Name
		containers = cj.Spec.JobTemplate.Spec.Template.Spec.Containers
		initContainers = cj.Spec.JobTemplate.Spec.Template.Spec.InitContainers
		owners = cj.OwnerReferences
	default:
		err = fmt.Errorf("unknown workload kind \"%s\"", kind.Kind)
	}

	if err != nil {
		return nil, err
	} else if len(containers) == 0 && len(initContainers) == 0 && len(ephemeralContainers) == 0 {
		return nil, fmt.Errorf("no containers found in workload object")
	}

	return &WorkloadObject{
		Name:                name,
		Kind:                kind.Kind,
		Namespace:           namespace,
		Containers:          containers,
		InitContainers:      initContainers,
		EphemeralContainers: ephemeralContainers,
		Owners:              owners,
	}, nil
}

// ConsolidatedContainers consolidates containers, initContainers and ephemeralContainers from
// the WorkloadObject struct into a single map.
//
// The returned map has the container image as the key and a list of IdxType structs as the value.
// Each IdxType struct contains the index of the container and its type (either "containers",
// "initContainers" or "ephemeralContainers").
func (wlo *WorkloadObject) ConsolidatedContainers() map[string][]IdxType {
	consolidated := map[string][]IdxType{}

	for _, item := range []struct {
		containerList []core.Container
		type_         string
	}{
		{wlo.Containers, "containers"},
		{wlo.InitContainers, "initContainers"},
	} {
		for idx, container := range item.containerList {
			newEntry := IdxType{Index: idx, Type: item.type_}
			idxTypeList, ok := consolidated[container.Image]

			if ok {
				consolidated[container.Image] = append(idxTypeList, newEntry)
			} else {
				consolidated[container.Image] = []IdxType{newEntry}
			}
		}
	}

	// Also include ephemeralContainers into the consolidated map
	for idx, container := range wlo.EphemeralContainers {
		newEntry := IdxType{Index: idx, Type: "ephemeralContainers"}
		idxTypeList, ok := consolidated[container.Image]

		if ok {
			consolidated[container.Image] = append(idxTypeList, newEntry)
		} else {
			consolidated[container.Image] = []IdxType{newEntry}
		}
	}

	return consolidated
}

// ImageSet returns a list of unique container images from the WorkloadObject struct.
func (wlo *WorkloadObject) ImageSet() []string {
	imageSet := []string{}
	imageMap := map[string]struct{}{}

	for _, c := range wlo.Containers {
		imageMap[c.Image] = struct{}{}
	}

	for _, ic := range wlo.InitContainers {
		imageMap[ic.Image] = struct{}{}
	}

	for _, ec := range wlo.EphemeralContainers {
		imageMap[ec.Image] = struct{}{}
	}

	for i := range imageMap {
		imageSet = append(imageSet, i)
	}
	return imageSet
}

// Returns the container path, used for the JSON patch, which
// differs from the WorkLoadObject kind.
func (wlo *WorkloadObject) ContainerPathFormatString() string {
	switch wlo.Kind {
	case "Pod":
		return "/spec/%s/%d/image"
	case "CronJob":
		return "/spec/jobTemplate/spec/template/spec/%s/%d/image"
	default:
		return "/spec/template/spec/%s/%d/image"
	}
}

// Returns all containers the parent workload object has approved
// for automatic child approval from the Kubernetes API.
func (wlo WorkloadObject) ParentContainerImagesFromKubeAPI(ctx context.Context) []string {
	client, ok := ctx.Value(constants.KubeAPI).(dynamic.Interface)
	if !ok || client == nil {
		logrus.Warnf("missing expected reference to kube API, unable to get parent container images")
		return []string{}
	}

	var containers []string
	for _, owner := range wlo.Owners {
		var group string
		var version string

		groupVersion := strings.Split(owner.APIVersion, "/")
		if len(groupVersion) > 1 {
			group = groupVersion[0]
			version = groupVersion[1]
		} else {
			group = ""
			version = groupVersion[0]
		}

		parent, err := fetchKubeResource(
			client,
			ctx,
			group,
			version,
			owner.Kind,
			wlo.Namespace,
			owner.Name,
		)
		if err != nil {
			logrus.Infof("error getting kube resource: %s", err)
			continue
		}

		if parent.GetUID() != owner.UID {
			logrus.Warnf("non matching UIDs")
			continue
		}

		parentBytes, err := parent.MarshalJSON()
		if err != nil {
			logrus.Warnf("can't marshal parent: %s", err)
			continue
		}

		parentWLO, err := NewWorkloadObjectFromBytes(parentBytes, parent.GroupVersionKind(), wlo.Namespace)
		if err != nil {
			logrus.Warnf("error creating parent workload object: %s", err)
			continue
		}

		for _, c := range parentWLO.Containers {
			containers = append(containers, c.Image)
		}
		for _, c := range parentWLO.InitContainers {
			containers = append(containers, c.Image)
		}
		for _, c := range parentWLO.EphemeralContainers {
			containers = append(containers, c.Image)
		}
	}
	return containers
}
