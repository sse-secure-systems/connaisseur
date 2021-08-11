# ADR 1: Bootstrap Sentinel

## Status

Amended in [ADR-3](ADR-3_multi_notary_config.md).
Deprecated as of [ADR-5](ADR-5_no-more-bootstrap.md).

## Context

Connaisseur's main components are a MutatingWebhookConfiguration and the Connaisseur Pods. The MutatingWebhookConfiguration intercepts requests to create or update Kubernetes resources and forwards them to the Connaisseur Pods tasked, on a high level, with verifying trust data. The order of deploying both components matters, since a blocking MutatingWebhookConfiguration without the Connaisseur Pods to answer its requests would also block the deployment of said Pods.

In [#3](https://github.com/sse-secure-systems/connaisseur/issues/3) it was noted that prior to version 1.1.5 of Connaisseur when looking at the `Ready` status of Connaisseur Pods, they could report `Ready` while being non-functional due to the MutatingWebhookConfiguration missing. However, as stated above the MutatingWebhookConfiguration can only be deployed _after_ the Connaisseur Pods, which was solved by checking the `Ready` state of said Pods. If one were to add a dependency to this `Ready` state, such that it only shows `Ready` when the MutatingWebhookConfiguration exists, we run into a deadlock, where the MutatingWebhookConfiguration waits for the Pods and the Pods wait for the MutatingWebhookConfiguration.

## Considered options

### Option 1

At the start of the Helm deployment, one can create a Pod named `connaisseur-bootstrap-sentinel` that will run for 5 minutes (which is also the installation timeout by Helm). Connaisseur Pods will report `Ready` if they can 1) access notary AND 2) the MutatingWebhookConfiguration exists OR 3) the `connaisseur-bootstrap-sentinel` Pod is still running. If 1)  AND 2) both hold true, the sentinel is killed even if the 5 minutes have not passed yet.

### Option 2

Let Connaisseur's Pod readiness stay non-indicative of Connaisseur functioning and advertise that someone running Connaisseur has to monitor the MutatingWebhookConfiguration in order to ensure proper working.

### Option 3

Deploy MutatingWebhookConfiguration through Helm when Connaisseur Pods are healthy instead of when ready. Require Pod started and working notary connection for health and require additionally the existence of the MutatingWebhookConfiguration for readiness.

## Decision outcome

We chose option 1 over option 2, because it was important to us that a brief glance at Connaisseur's Namespace allows one to judge whether it is running properly. Option 3 was not chosen as the readiness status of Pods can be easily seen from the Service, whereas the health status would require querying every single Pod individually. We deemed that to be a very ugly, non-kubernetes-y solution and hence decided against it.

### Positive consequences

If the Connaisseur Pods report `Ready` during the `connaisseur-bootstrap-sentinel`'s runtime, the MutatingWebhookConfiguration will be deployed by Helm. Otherwise, the Helm deployment will fail after its timeout period (default: 5min), since there won't be a running `connaisseur-bootstrap-sentinel` Pod anymore that resolves the installation deadlock. The Connaisseur Pods will never reach the `Ready` state and the MutatingWebhookConfiguration never gets deployed. This means, we get consistent deployment failures after the inital waiting period if something did not work out. Additionally, if the MutatingWebhookConfiguration gets removed for whatever reason during operation, Connaisseur Pods will be failing, indicating their failed dependency. Hence, monitoring the Connaisseur Pods is sufficient to ensure their working.

### Negative consequences

On the other hand, if an adversary can deploy a Pod named `connaisseur-bootstrap-sentinel` to Connaisseur's Namespace, the Connaisseur Pods will always show `Ready` regardless of the MutatingWebhookConfiguration. However, if an adversary can deploy to Connaisseur's Namespace, chances are Connaisseur can be compromised anyways. More importantly, if not a single Connaisseur Pod is successfully deployed or if the notary healthcheck fails during the sentinel's lifetime, then the deployment will fail regardless of possible recovery at a later time. Another issue would be the `connaisseur-bootstrap-sentinel` Pod being left behind, however since it has a very limited use case we can also clean it up during the deployment, so apart from the minimal additional complexity of the deployment this is a non-issue.
