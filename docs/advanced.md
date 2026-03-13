# Advanced information

There are some edge cases or considerations for Connaisseur, which most people won't notice or care about, but which we still want to document.
Below those are listed.

## Finalizer removal

Connaisseur used to run every single CREATE and UPDATE adminission request through its validators.
However, in some cases this is not desired as highlighted by [Issue #2053](https://github.com/sse-secure-systems/connaisseur/issues/2053).
Once a pod is marked for deletion, it's attributes cannot be changed anymore, except for [removal of finalizers](https://kubernetes.io/docs/concepts/overview/working-with-objects/finalizers/#:~:text=Kubernetes%20adds%20the%20deletion%20timestamp%20for%20that%20object%20and%20then%20immediately%20starts%20to%20restrict%20changes).
If finalizers cannot be removed (e.g., because the operation would be blocked by Connaisseur), resources may be kept alive indefinitely.

Since no meaningful attributes (with respect to Connaisseur's mission) can be changed, it is safe for Connaisseur to allow updates to resources marked for deletion.
This is also in line with Connaisseur allowing all DELETE admission request.
Therefore, if Connaisseur receives an UPDATE admission request, where the previous object was already marked for deletion, we allow it without verifying image signatures according to the policy.

## Starting a cluster with Connaisseur installed

Connaisseur is a Mutating Admission Controller and as such has a `MutatingWebhookConfiguration` which specifies where requests are to be sent for mutation and admission review.
By default, Connaisseur is configured to be a fail-closed service: If anything goes wrong, including service unavailability, resource admission will be blocked.
This works well if Connaisseur is installed into a running cluster.
Then the actual Connaisseur resources are deployed and then the `MutatingWebhookConfiguration` is installed, routing to the Connaisseur pods and subsequent verification can start.
If however, the cluster is restarted with all of Connaisseur's resources in place, the `MutatingWebhookConfiguration` will require all starting resources to be verified by Connaisseur, which itself hasn't been deployed yet.
A not-yet-running Connaisseur would need to allow itself to be started, a classical chicken-and-egg problem.

There is unfortunately no good way around it, so you'll have to uninstall and reinstall Connaisseur when restarting the cluster.
If you want all other resources properly validated, make sure that Connaisseur is deployed before restoring the remaining resources.
