# ADR 6: Dynamic Configuration

## Status

Accepted

## Context

The configuration of validators are mounted into Connaisseur as a configmap, as it is common practice in the Kubernetes ecosystem. When this configmap is upgraded, say with a `helm upgrade`, the resource itself in Kubernetes is updated accordingly, but that doesn't mean it's automatically updated inside the pods which mounted it. That only occurs once the pods are restarted and until they are the pods still have an old version of the configuration lingering around. This is a fairly unintuitive behavior and the reason why Connaisseur doesn't mount the image policy into its pods. Instead, the pods have access to the kube API and get the image policy dynamically from there. The same could be done for the validator configuration, but there is also another solution.

## Problem 1 - Access to configuration

How should Connaisseur get access to its configuration files?

### Solution 1.1 - Dynamic access

This is the same solution as currently employed for the image policy configuration. The validators will get their own CustomResourceDefinition and Connaisseur gets access to this resource via RBAC so it can use the kube API to read the configuration.

**Pros:** Pods don't need to be restarted and the configuration can be changed "on the fly", without using Helm.
**Cons:** Not a very Kubernetes native approach and Connaisseur must always do some network requests to access its config.

### Solution 1.2 - Restart pods

The other solution would be to use ConfigMaps for validators and image policy and then restart the pods, once there were changes in the configurations. This can be achieved by setting the hash of the config files as annotations into the deployment. If there are changes in the configuration, the hash will change and thus a new deployment will be rolled out as it has a new annotation. This corresponds to the [suggestion](https://helm.sh/docs/howto/charts_tips_and_tricks/#automatically-roll-deployments) made by Helm.

**Pros:** Kubernetes native and no more CustomResourceDefinitions!
**Cons:** No more "on the fly" changes.

### Decision Outcome (1)

Solution 1.2 was chosen, going with the more Kubernetes native way.

## Problem 2 - How many configmaps are too many?

When both the image policy and validator configurations are either CustomResourceDefinitions or ConfigMaps, is there still a need to separate them or can they be merged into one file?

### Solution 2.1 - 2 concerns, 2 resources

There will be 2 resources, one for the image policy and one for the validators.

### Solution 2.2 - One to rule them all

One Ring to rule them all, One Ring to find them, One Ring to bring them all and in the darkness bind them.

### Decision Outcome (2)

Solution 2.2 was chosen as it is the more simpler of the two.
