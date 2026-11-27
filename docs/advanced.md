# Advanced information

There are some edge cases or considerations for Connaisseur, which most people won't notice or care about, but which we still want to document.
Below those are listed.

## Finalizer removal

If finalizers cannot be removed (e.g., because an existing image is no longer trusted and the operation would be blocked by Connaisseur), resources may be kept alive indefinitely; see [Issue #2053](https://github.com/sse-secure-systems/connaisseur/issues/2053).
Kubernetes restricts some resource changes, but does not generally prevent updates, in particular image updates; see [Finalizers](https://kubernetes.io/docs/concepts/overview/working-with-objects/finalizers/).

For an UPDATE whose previous object was already marked for deletion, Connaisseur skips validation only if container, init container, and ephemeral container image references are unchanged by type and name.
This allows finalizer removal without revalidating existing images.
If an image reference is added, removed, or changed, Connaisseur processes all images through its normal validation path, including any configured automatic approvals and caching.
If an image fails validation during such an update, remove the finalizer in a separate update without image changes.

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
