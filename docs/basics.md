# Basics

In the following, we aim to lay the foundation on Connaisseur's core concepts, how to configure and administer it.

## Admission control, validators and image policy

Connaisseur works as a [mutating admission controller](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/).
It intercepts all *CREATE* and *UPDATE* resource requests for *Pods*, *Deployments*, *ReplicationControllers*, *ReplicaSets*, *DaemonSets*, *StatefulSets*, *Jobs*, and *CronJobs* and extracts all image references for validation.

Per default, Connaisseur uses *automatic child approval* by which the child of a Kubernetes resource is automatically admitted without re-verification of the signature in order to avoid duplicate validation and handle inconsistencies with the image policy.
Essentially, this is done since an image that is deployed as part of an already deployed object (e.g. a Pod deployed as a child of a Deployment) has already been validated and potentially mutated during admission of the parent.
More information and configuration options can be found in the [feature documentation for automatic child approval](features/automatic_child_approval.md).

Validation itself relies on two core concepts: image policy and validators.
A validator is a set of configuration options required for validation like the type of signature, public key to use for verification, path to signature data, or authentication.
The image policy defines a set of rules which maps different images to those validators.
This is done via glob matching of the image name which for example allows to use different validators for different registries, repositories, images or even tags.
This is specifically useful when using public or external images from other entities like Docker's official images or different keys in a more complex development team.

> :octicons-light-bulb-16: **Note**: Typically, the public key of a known entity is used to validate the signature over an image's content in order to ensure integrity and provenance.
> However, other ways to implement such trust pinning exist and as a consequence we refer to all types of trust anchors in a generalized form as *trust roots*.

## Using Connaisseur

Some general administration tasks like deployment or uninstallation when using Connaisseur are described in this section.

### Requirements

Using Connaisseur requires a [Kubernetes](https://kubernetes.io/) cluster, [Helm](https://helm.sh/) and, if installing from source, [Git](https://git-scm.com/) to be installed and set up.

### Get the code/chart

Download the Connaisseur resources required for installation either by cloning the source code via Git or directly add the chart repository via Helm.

=== "Clone via Git"

    The Connaisseur source code can be cloned directly from GitHub and includes the application and Helm charts in a single repository:

    ```bash
    git clone https://github.com/sse-secure-systems/connaisseur.git
    ```

=== "Add via Helm"

    The Helm chart can be added by:

    ```bash
    helm repo add connaisseur https://sse-secure-systems.github.io/connaisseur/charts
    ```

### Configure

The configuration of Connaisseur is completely done in the `helm/values.yaml`.
The upper `deployment` section offers some general Kubernetes typical configurations like image version or resources.
Noteworthy configurations are:

- `deployment.failurePolicy`: Failure policy allows configuration whether the mutating admission webhook should fail closed (`Fail`, *default*) or open (`Ignore`) should the Connaisseur service become unavailable. While Connaisseur is configured to be secure by default, setting the [failure policy](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#failure-policy) to `Ignore` allows to prioritize cluster access[^1].
- `deployment.reinvocationPolicy`: [Reinvocation Policy](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#reinvocation-policy) defines whether Connaisseur is called again as part of the admission evaluation if the object being admitted is modified by other admission plugins after the initial webhook call (`IfNeeded`) or not (`Never`, *default*). Note that if Connaisseur is invoked a second time, the policy to be applied might change in between[^2]. Make sure, your Connaisseur policies are set up to handle multiple mutations of the image originally specified in the manifest, e.g. `my.private.registry/image:1.0.0` and `my.private.registry/image@sha256:<hash-of-1.0.0-image>`.
- `deployment.securityContext`: Connaisseur ships with secure defaults. However, some keys are not supported by all versions or flavors of Kubernetes and might need adjustment[^3]. This is mentioned in the comments to the best of our knowledge.
- `deployment.podSecurityPolicy`: Some clusters require a PSP. A secure default PSP for Connaisseur is available.

[^1]: This is not to be confused with the [detection mode](features/detection_mode.md) feature: In detection mode, Conaisseur service admits all requests to the cluster independent of the validation result while the failure policy only takes effect when the service itself becomes unavailable.

[^2]: During the first mutation, Connaisseur converts the image tag to its digests. Read more in the [overview of Connaisseur](https://sse-secure-systems.github.io/connaisseur/v2.4.1/#trusted-digests)

[^3]: In those cases, consider using security annotations via `deployment.annotations` or pod security policies `deployment.podSecurityPolicy` if available.

The actual configuration consists of the `validators` and image `policy` sections.
These are described in detail [below](#detailed-configuration) and for initials steps it is instructive to follow the [getting started guide](getting_started.md).
Other features are described on the [respective pages](features/README.md).

Connaisseur ships with a pre-configuration that does not need any adjustments for testing.
However, validating your own images requires additional configuration.

### Deploy

Install Connaisseur via Helm:

=== "Cloned via Git"

    Install Connaisseur by using the Helm template definition files in the `helm` directory:

    ```bash
    helm install connaisseur helm --atomic --create-namespace --namespace connaisseur
    ```

=== "Added via Helm"

    Install Connaisseur using the default configuration from the chart repository:

    ```bash
    helm install connaisseur connaisseur/connaisseur --atomic --create-namespace --namespace connaisseur
    ```

    To customize Connaisseur, craft a `values.yaml` according to your needs and apply:

    ```bash
    helm install connaisseur connaisseur/connaisseur --atomic --create-namespace --namespace connaisseur -f values.yaml
    ```

This deploys Connaisseur to its own namespace called `connaisseur`.
The installation itself may take a moment, as the installation order of the Connaisseur components is critical:
The admission webhook for intercepting requests can only be applied when the Connaisseur pods are up and ready to receive admission requests.

### Check

Once everything is installed, you can check whether all the pods are up by running `kubectl get all -n connaisseur`:

```bash
kubectl get all -n connaisseur
> NAME                                          READY   STATUS    RESTARTS   AGE
> pod/connaisseur-deployment-78d8975596-42tkw   1/1     Running   0          22s
> pod/connaisseur-deployment-78d8975596-5c4c6   1/1     Running   0          22s
> pod/connaisseur-deployment-78d8975596-kvrj6   1/1     Running   0          22s
>
> NAME                      TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
> service/connaisseur-svc   ClusterIP   10.108.220.34   <none>        443/TCP   22s
>
> NAME                                     READY   UP-TO-DATE   AVAILABLE   AGE
> deployment.apps/connaisseur-deployment   3/3     3            3           22s
>
> NAME                                                DESIRED   CURRENT   READY   AGE
> replicaset.apps/connaisseur-deployment-78d8975596   3         3         3       22s
```

### Use

To use Connaisseur, simply try running some images or apply a deployment.
In case you use the pre-configuration, you could for example run the following commands:

```bash
kubectl run demo --image=docker.io/securesystemsengineering/testimage:unsigned
> Error from server: admission webhook "connaisseur-svc.connaisseur.svc" denied the request (...).

kubectl run hello-world --image=docker.io/hello-world
> pod/hello-world created
```

### Upgrade

A running Connaisseur instance can be updated by a Helm upgrade of the current release:

=== "Cloned via Git"

    Adjust configuration in `helm/values.yaml` as required and upgrade via:

    ```bash
    helm upgrade connaisseur helm -n connaisseur --wait
    ```

=== "Added via Helm"

    Adjust your local configuration file (e.g. `values.yaml`) as required and upgrade via:

    ```bash
    helm upgrade connaisseur connaisseur/connaisseur -n connaisseur --wait -f values.yaml
    ```



### Delete

Just like for installation, Helm can also be used to delete Connaisseur from your cluster:

```bash
helm uninstall connaisseur -n connaisseur
```

In case uninstallation fails or problems occur during subsequent installation, you can manually remove all resources:

```bash
kubectl delete all,mutatingwebhookconfigurations,clusterroles,clusterrolebindings,configmaps,imagepolicies,secrets,serviceaccounts,customresourcedefinitions -lapp.kubernetes.io/instance=connaisseur
kubectl delete namespaces connaisseur
```

Connaisseur for example also installs a *CutstomResourceDefinition* `imagepolicies.connaisseur.policy` that validates its configuration.
In case of major releases, the configuration structure might change which can cause installation to fail and you might have to delete it manually.

### Makefile

Alternatively to using Helm, you can also run the Makefile for installing, deleting and more. Here the available commands:

- `make install` -- Install Connaisseur.
- `make upgrade` -- Upgrade Connaisseur.
- `make uninstall` -- Uninstall Connaisseur and delete the namespace.
- `make annihilate` -- Remove all Connaisseur Kubernetes resources including its namespace. This command is usually helpful, should the normal `make uninstall` not work.
- `make docker` -- Builds the *connaisseur* container image.

## Detailed configuration

All configuration is done in the `helm/values.yaml`.
The configuration of features is only described in the [corresponding section](features/README.md).

### Validators

The validators are configured in the `validators` field, which defines a list of validator objects.

A validator defines what kind of signatures are to be expected, how signatures are to be validated, against which trust root and how to access the signature data.
For example, images might be signed with Docker Content Trust and reside in a private registry.
Thus the validator would need to specify `notaryv1` as type, the notary host and the required credentials.

The specific validator type should be chosen based on the use case.
A list of supported validator types can be found [here](validators/README.md).
All validators share a similar structure for configuration.
For specifics and additional options, please review the dedicated page of the validator type.

There is a special behavior, when a validator or one of the trust roots is named `default`.
In this case, should an image policy rule not specify a validator or trust root to use, the one named `default` will be used instead.
This also means there can only be one validator named `default` and for the trust roots, there can only be one called `default` within a single validator.

Connaisseur comes with a few validators pre-configured including one for Docker's official images.
The pre-configured validators can be removed.
However to avoid Connaisseur failing its own validation in case you remove the `securesystemsengineering_official` key, make sure to also exclude Connaisseur from validation either via the static `allow` validator or [namespaced validation](features/namespaced_validation.md).
The special case of static validators used to simply allow or deny images without verification is described below.

#### Configuration options

`.validators[*]` in `helm/values.yaml` supports the following keys:

| Key | Default | Required | Description |
| - | - | - | - |
| `name` | - | :heavy_check_mark: | Name of the validator, which is referenced in the image policy. It must consist of lower case alphanumeric characters or '-'. If the name is `default`, it will be used if no validator is specified. |
| `type` | - | :heavy_check_mark: | Type of the validator, e.g. `notaryv1` or `cosign`, which is dependent on the [signing solution in use](validators/README.md). |
| `trust_roots` | - | :heavy_check_mark: | List of trust anchors to validate the signatures against. In practice, this is typically a list of public keys. |
| `trust_roots[*].name` | - | :heavy_check_mark: | Name of the trust anchor, which is referenced in the image policy. If the name is `default`, it will be used if no key is specified. |
| `trust_roots[*].key` | - | :heavy_check_mark: | Value of the trust anchor, most commonly a PEM encoded public key. |
| `auth`| - | | Credentials that should be used in case authentication is required for validation. Details are provided on validator-specific pages. |

*Further configuration fields specific to the validator type are described in the [respective section](validators/README.md).*

#### Example

```yaml
validators:
- name: default
  type: notaryv1
  host: notary.docker.io
  trust_roots:
  - name: default
    key: |
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEsx28WV7BsQfnHF1kZmpdCTTLJaWe
      d0CA+JOi8H4REuBaWSZ5zPDe468WuOJ6f71E7WFg3CVEVYHuoZt2UYbN/Q==
      -----END PUBLIC KEY-----
  auth:
    username: superuser
    password: lookatmeimjumping
- name: myvalidator
  type: cosign
  trust_roots:
  - name: mykey
    key: |
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEIFXO1w6oj0oI2Fk9SiaNJRKTiO9d
      ksm6hFczQAq+FDdw0istEdCwcHO61O/0bV+LC8jqFoomA28cT+py6FcSYw==
      -----END PUBLIC KEY-----
```

#### Static validators

Static validators are a special type of validator that does not validate any signatures.
Depending on the `approve` value being `true` or `false`, they either allow or deny all images for which they are specified as validator.
This for example allows to implement an *allowlist* or *denylist*.

##### Configuration options

| Key | Default | Required | Description |
| - | - | - | - |
| `name` | - | :heavy_check_mark: | Name of the validator, which will be used to reference it in the image policy. |
| `type` | - | :heavy_check_mark: | `static`; value has to be `static` for a static validator. |
| `approve` | - | :heavy_check_mark: | `true` or `false` to admit or deny all images.|

##### Example

```yaml
validators:
- name: allow
  type: static
  approve: true
- name: deny
  type: static
  approve: false
```

### Image policy

The image policy is defined in the `policy` field and acts as a list of rule objects to determine which image should be validated by which validator (and potentially some further configurations).

For each image in the admission request, only a single rule in the image policy will apply: the one with the *most specific* matching `pattern` field.
This is determined by the following algorithm:

1. A given image is matched against all rule patterns.
2. All matching patterns are compared to one another to determine the most specific one (see below). Only two patterns are compared at a time; the more specific one then is compared to the next one and so forth. Specificity is determined as follows:
    1. Patterns are split into components (delimited by "/"). The pattern that has a higher number of components wins (is considered more specific).
    2. Should the two patterns that are being compared have equal number of components, the longest common prefix between each pattern component and corresponding image component are calculated (for this purpose, image identifiers are also split into components). The pattern with the longest common prefix in one component, starting from the leftmost, wins.
    3. Should all longest common prefixes of all components between the two compared patterns be equal, the pattern with a longer component, starting from the leftmost, wins.
    4. The rule whose pattern has won all comparisons is considered the most specific rule.
3. Return the most specific rule.

Should an image match none of the rules, Connaisseur will deny the request and raise an error.
This *deny per default* behavior can be changed via a *catch-all* rule `*:*` and for example using the static `allow` validator in order to admit otherwise unmatched images.

In order to perform the actual validation, Connaisseur will call the validator specified in the selected rule and pass the image name and potential further configuration to it.
The reference to validator and exact trust root is resolved in the following way:

1. The validator with name (`validators[*].name`) equal to the `validator` value in the selected rule is chosen. If no validator is specified, the validator with name `default` is used if it exists.
2. Of that validator, the trust root (e.g. public key) is chosen which name (`.validators.trust_roots[*].name`) matches the policies trust root string (`with.trust_root`). If no trust root is specified, the trust root with name `default` is used if it exists.

Let's review the pattern and validator matching at a minimal example.
We consider the following validator and policy configuration (most fields have been omitted for clarity):

```yaml
validators:
- name: default     # validator 1
  trust_roots:
  - name: default   # key 1
    key: |
      ...
- name: myvalidator # validator 2
  trust_roots:
  - name: default   # key 2
    key: |
      ...
  - name: mykey     # key 3
    key: |
      ...

policy:
- pattern: "*:*"                      # rule 1
- pattern: "docker.io/myrepo/*:*"     # rule 2
  validator: myvalidator
- pattern: "docker.io/myrepo/myimg:*" # rule 3
  validator: myvalidator
  with:
    trust_root: mykey
```

Now deploying the following images we would get the matchings:

- `docker.io/superrepo/myimg:v1` &rarr; *rule 1* &rarr; *validator 1*(*key 1*): The image matches none of the more specific rules 2 and 3, so rule 1 is applied. As that rule neither specifies a validator nor a trust root, the `default` validator (validator 1) with trust root `default` (key 1) is used.
- `docker.io/myrepo/superimg:v1` &rarr; *rule 2* &rarr; *validator 2*(*key 2*): The image only matches rules 1 and 2 and thus 2 is chosen as it is more specific. That rule specifies `myvalidator` as validator but no trust root and thus validator 2 with trust root `default` (key 2) is used.
- `docker.io/myrepo/myimg:v1` &rarr; *rule 3* &rarr; *validator 2*(*key 3*): The image matches all rules and thus 3 is chosen as it is most specific. The rule specifies `myvalidator` as validator with `mykey` as trust root and thus validator 2 with key 2 is used.

Connaisseur ships with a few rules pre-configured.
There is two rules that should remain intact in some form in order to not brick the Kubernetes cluster:

- `k8s.gcr.io`: This is an `allow` rule for Kubernetes images (`k8s.gcr.io`) in order to not block cluster relevant images. These cannot be validated currently.
- `docker.io/securesystemsengineering/*:*`: This rule is used to validate the Connaisseur images with the respective validator and removal can break the Connaisseur deployment. It is, however, possible to use the static `allow` validator.

#### Configuration options

`.policy[*]` in `helm/values.yaml` supports the following keys:

| Key  | Default | Required | Description |
| - | - | - | - |
| `pattern` | - | :heavy_check_mark: | Globbing pattern to match an image name against. |
| `validator` | `default` | | Name of a validator in the `validators` list. If not provided, the validator with name `default` is used if it exists. |
| `with` | - | | Additional parameters to use for a validator. See more specifics in [validator section](validators/README.md). |
|`with.trust_root`| `default` | | Name of a trust root, which is specified within the referenced validator. If not provided, the trust root with name `default` is used if it exists. |

#### Example

```yaml
policy:
- pattern: "*:*"
- pattern: "docker.io/myrepo/*:*"
  validator: myvalidator
  with:
    trust_root: mykey
- pattern: "docker.io/myrepo/deniedimage:*"
  validator: deny
- pattern: "docker.io/myrepo/allowedimage:v*"
  validator: allow
```

### Common examples

Let's look at some useful examples for the `validators` and `policy` configuration.
These can serve as a first template beyond the pre-configuration or might just be instructive to understand validators and policies.

We assume your repository is `docker.io/myrepo` and a public key has been created.
In case this repository is private, authentication would have to be added to the respective validator for example via:

```yaml
  auth:
    secret_name: k8ssecret
```

The Kubernetes secret would have to be created separately according to the validator documentation.

#### Case: Only validate own images and deny all others

This is likely the most common case in simple settings by which only self-built images are used and validated against your own public key:

```yaml
validators:
- name: allow
  type: static
  approve: true
- name: default
  type: notaryv1  # or e.g. 'cosign'
  host: notary.docker.io  # only required in case of notaryv1
  trust_roots:
  - name: default
    key: |  # your public key below
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvtc/qpHtx7iUUj+rRHR99a8mnGni
      qiGkmUb9YpWWTS4YwlvwdmMDiGzcsHiDOYz6f88u2hCRF5GUCvyiZAKrsA==
      -----END PUBLIC KEY-----
- name: dockerhub_basics
  type: notaryv1
  host: notary.docker.io
  trust_roots:
  - name: securesystemsengineering_official
    key: |
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEsx28WV7BsQfnHF1kZmpdCTTLJaWe
      d0CA+JOi8H4REuBaWSZ5zPDe468WuOJ6f71E7WFg3CVEVYHuoZt2UYbN/Q==
      -----END PUBLIC KEY-----

policy:
- pattern: "*:*"
- pattern: "k8s.gcr.io/*:*"
  validator: allow
- pattern: "docker.io/securesystemsengineering/*:*"
  validator: dockerhub_basics
  with:
    trust_root: securesystemsengineering_official
```


#### Case: Only validate own images and deny all others (faster)

This configuration achieves the same as the one above, but is faster as trust data only needs to be requested for images in your repository:

```yaml
validators:
- name: allow
  type: static
  approve: true
- name: deny
  type: static
  approve: false
- name: default
  type: notaryv1  # or e.g. 'cosign'
  host: notary.docker.io  # only required in case of notaryv1
  trust_roots:
  - name: default
    key: |  # your public key below
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvtc/qpHtx7iUUj+rRHR99a8mnGni
      qiGkmUb9YpWWTS4YwlvwdmMDiGzcsHiDOYz6f88u2hCRF5GUCvyiZAKrsA==
      -----END PUBLIC KEY-----
- name: dockerhub_basics
  type: notaryv1
  host: notary.docker.io
  trust_roots:
  - name: securesystemsengineering_official
    key: |
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEsx28WV7BsQfnHF1kZmpdCTTLJaWe
      d0CA+JOi8H4REuBaWSZ5zPDe468WuOJ6f71E7WFg3CVEVYHuoZt2UYbN/Q==
      -----END PUBLIC KEY-----

policy:
- pattern: "*:*"
  validator: deny
- pattern: "docker.io/myrepo/*:*"
- pattern: "k8s.gcr.io/*:*"
  validator: allow
- pattern: "docker.io/securesystemsengineering/*:*"
  validator: dockerhub_basics
  with:
    trust_root: securesystemsengineering_official
```

The `*:*` rule could also have been omitted as Connaisseur denies unmatched images.
However, explicit is better than implicit.

#### Case: Only validate Docker Hub official images and deny all others

In case only validated Docker Hub official images should be admitted to the cluster:

```yaml
validators:
- name: allow
  type: static
  approve: true
- name: deny
  type: static
  approve: false
- name: dockerhub_basics
  type: notaryv1
  host: notary.docker.io
  trust_roots:
  - name: docker_official
    key: |
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEOXYta5TgdCwXTCnLU09W5T4M4r9f
      QQrqJuADP6U7g5r9ICgPSmZuRHP/1AYUfOQW3baveKsT969EfELKj1lfCA==
      -----END PUBLIC KEY-----
  - name: securesystemsengineering_official
    key: |
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEsx28WV7BsQfnHF1kZmpdCTTLJaWe
      d0CA+JOi8H4REuBaWSZ5zPDe468WuOJ6f71E7WFg3CVEVYHuoZt2UYbN/Q==
      -----END PUBLIC KEY-----

policy:
- pattern: "*:*"
  validator: deny
- pattern: "docker.io/library/*:*"
  validator: dockerhub_basics
  with:
    trust_root: docker_official
- pattern: "k8s.gcr.io/*:*"
  validator: allow
- pattern: "docker.io/securesystemsengineering/*:*"
  validator: dockerhub_basics
  with:
    trust_root: securesystemsengineering_official
```

#### Case: Only validate Docker Hub official images and allow all others

In case only Docker Hub official images should be validated while all others are simply admitted:

```yaml
validators:
- name: allow
  type: static
  approve: true
- name: deny
  type: static
  approve: false
- name: dockerhub_basics
  type: notaryv1
  host: notary.docker.io
  trust_roots:
  - name: docker_official
    key: |
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEOXYta5TgdCwXTCnLU09W5T4M4r9f
      QQrqJuADP6U7g5r9ICgPSmZuRHP/1AYUfOQW3baveKsT969EfELKj1lfCA==
      -----END PUBLIC KEY-----
  - name: securesystemsengineering_official
    key: |
      -----BEGIN PUBLIC KEY-----
      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEsx28WV7BsQfnHF1kZmpdCTTLJaWe
      d0CA+JOi8H4REuBaWSZ5zPDe468WuOJ6f71E7WFg3CVEVYHuoZt2UYbN/Q==
      -----END PUBLIC KEY-----

policy:
- pattern: "*:*"
  validator: allow
- pattern: "docker.io/library/*:*"
  validator: dockerhub_basics
  with:
    trust_root: docker_official
- pattern: "k8s.gcr.io/*:*"
  validator: allow
- pattern: "docker.io/securesystemsengineering/*:*"
  validator: dockerhub_basics
  with:
    trust_root: securesystemsengineering_official
```

#### Case: Directly admit own images and deny all others

As a matter of fact, Connaisseur can also be used to restrict the allowed registries and repositories without signature validation:

```yaml
validators:
- name: allow
  type: static
  approve: true
- name: deny
  type: static
  approve: false

policy:
- pattern: "*:*"
  validator: deny
- pattern: "docker.io/myrepo/*:*"
  validator: allow
- pattern: "k8s.gcr.io/*:*"
  validator: allow
- pattern: "docker.io/securesystemsengineering/*:*"
  validator: allow
```

