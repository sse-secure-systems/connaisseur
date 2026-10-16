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

## Admission webhook connectivity

The Kubernetes API server must be able to connect to Connaisseur's admission webhook.
Depending on the cluster provider and network configuration, infrastructure firewalls, security groups, or network ACLs can restrict traffic from the control plane to Connaisseur pods.

If the Connaisseur port is blocked, admission requests time out.
Connaisseur does not log the admission request in this case because the request never reaches the pod.
Changing Kubernetes NetworkPolicies does not resolve the issue when an infrastructure firewall blocks the connection.

There are two possible remediations:

1. Allow the configured Pod port through the relevant firewall or security rule. Restrict ingress to the control plane source range or security group and the cluster nodes on `kubernetes.deployment.port`; do not expose the port publicly.
For example, GKE's automatically created control plane firewall rules allow connections to nodes and pods on TCP ports `443` and `10250` by default, whereas Connaisseur's default port is 5000.
See [discussion #481](https://github.com/sse-secure-systems/connaisseur/discussions/481) for community solutions.
2. Run Connaisseur on a port, which is already allowlisted, like `443`.
Since `443` is a privileged port, you will need to reconfigure the default `podSecurityContext`:

    ```yaml
    kubernetes:
        deployment:
            port: 443
            podSecurityContext:
                sysctls:
                    - name: net.ipv4.ip_unprivileged_port_start
                        value: "0"
    ```

    Connaisseur runs as a non-root user and drops all Linux capabilities.
    The namespaced safe sysctl allows the process to bind port `443` without granting `CAP_NET_BIND_SERVICE` or running as root.
    This configuration requires `hostNetwork: false`.
    See the Kubernetes documentation on [safe and unsafe sysctls](https://kubernetes.io/docs/tasks/administer-cluster/sysctl-cluster/#safe-and-unsafe-sysctls).
