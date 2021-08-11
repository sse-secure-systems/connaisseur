# ADR 5: No More Bootstrap Pods

## Status

Accepted

## Context

Installing Connaisseur isn't as simple as one might think. There is more to it then just applying some yaml files, all due to the nature of being an admission controller, which might block itself in various ways. This ADR depicts some issues during installation of Connaisseur and shows solutions, that try make the process simpler and easier to understand.

## Problem 1 - Installation order

Connaisseur's installation order is fairly critical. The webhook responsible for intercepting all requests is dependent on the Connaisseur pods and can only work, if those pods are available and ready. If not and  `FailurePolicy` is set to `Fail`, the webhook will block anything and everything, including the Connaisseur pods themselves. This means, the webhook must be installed *after* the Connaisseur pods are ready. This was previously solved using the `post-install` Helm hook, which installs the webhook configuration after all other resources have been applied and are considered ready. Just for installation purposes, this solution suffices. A downside of this is, every resource installed via a Helm hook isn't natively considered to be part of the chart, meaning a `helm uninstall` would completely ignore those resources and leave the webhook configuration in place. Then the situation of everything and anything being blocked arises again. Additionally, upgrading won't be possible, since you can't tell Helm to temporarily delete resources and then reapply them. That's why the `helm-hook` image and `bootstrap-sentinel` where introduced. They were used to temporarily delete the webhook and reapply it before and after installations, in order to beat the race conditions. Unfortunately, this solution always felt a bit clunky and added a lot of complexity for a seemingly simple problem.

### Solution 1.1 - Empty webhook as part of Helm release

The `bootstrap sentinel` and `helm-hook` image won't be used anymore. Instead, an empty webhook configuration (a configuration without any rules) will be applied along all other resources during the normal Helm installation phase. This way the webhook can be normally deleted with the `helm uninstall` command. Additionally, during the `post-install` (and `post-upgrade`/`post-rollback`) Helm hook, the webhook will be updated so it can actually intercept incoming request. So in a sense an unloaded webhook gets installed, which then gets "armed" during `post-install`. This also works during an upgrade, since the now "armed" webhook will be overwritten by the empty one when trying to apply the chart again! This will obviously be reverted back again after upgrading, with a `post-upgrade` Helm hook.

**Pros:** Less clunky and more k8s native.
**Cons:** Connaisseur will be deactivated for a short time during upgrading.

### Solution 1.2 - Bootstrap Sentinel and Helm hook

Everything stays as is! The Helm hook image is still used to (un)install the webhook, while the bootstrap sentinel is there to mark the Connaisseur pods as ready for initial installation.

**Pros:** Never change a running system.
**Cons:** Clunky, at times confusing for anyone not familiar with the Connaisseur installation order problem, inactive webhook during upgrade.

### Solution 1.3 - (Un)installation of webhook during Helm hooks

The webhook can be easily installed during the `post-install` step of the Helm installation, but then it isn't part of the Helm release and can't be uninstalled, as mentioned above. With a neat little trick this is still possible: in the `post-delete` step the webhook can be reapplied in an empty ("unarmed") form, while setting the `hook-delete-policy` to delete the resource in either way (no matter if the Helm hook step fails or not). So in a way the webhook gets reapplied and then immediately deleted. This still works with upgrading Connaisseur if a rolling update strategy is pursued, meaning the old pods will still be available for admitting the new ones, while with more and more new pods being ready, the old ones get deleted.

**Pros:** Less clunky and more k8s native, no inactivity of the webhook during upgrade.
**Cons:** Slower upgrade of Connaisseur compared to solution 1.

### Decision outcome (1)

Solution 1.3 was chosen, as it is the more Kubernetes native way of doing things and Connaisseur will be always available, even during its own upgrade.

### Problem 2

All admission webhooks must use TLS for communication purposes or they won't be accepted by Kubernetes. That is why Connaisseur creates its own self signed certificate, which it uses for communication between the webhook and its pods. This certificate is created within the Helm chart, using the native `genSelfSignedCert` function, which makes Connaisseur pipeline friendly as there is no need for additional package installation such as OpenSSL. Unfortunately, this certificate gets created every time Helm is used, whether that being a `helm install` or `helm upgrade`. Especially during an upgrade, the webhook will get a new certificate, while the pods will get their new one written into a secret. The problem is that the pods will only capitalize on the new certificate inside the secret once they are restarted. If no restart happens, the pods and webhook will have different certificates and any validation will fail.

### Solution 2.1 - Lookup

Instead of always generating a new certificate, the `lookup` function for Helm templates could be used to see whether there already is a secret defined that contains a certificate and then use this one. This way the same certificate is reused the whole time so no pod restarts are necessary. Should there be no secret with certificate to begin with, a new one can be generated within the Helm chart.

**Pros:** No need for restarts and changing of TLS certificates.
**Cons:** The lookup function takes some time to gather the current certs.

### Solution 2.2 - Restart

On each upgrade of the Helm release, all pods will be restarted so they incorporate the new TLS secrets.

**Pros:** -
**Cons:** Restarting takes time and may break if too many Connaisseur pods are unavailable at the same time.

### Solution 2.3 - External TLS

Go back to using an external TLS certificate which is not being generated within the Helm chart, but by pre-configuring it or using OpenSSL.

**Pros:** Fastest solution.
**Cons:** More configurational effort and/or not pipeline friendly (may need OpenSSL).

### Decision outcome (2)

Solution 2.1 is being implemented, as it is important that Connaisseur works with as little configuration effort as possible from the get-go. Nonetheless an external configuration of TLS certificates is still considered for later development.

--
