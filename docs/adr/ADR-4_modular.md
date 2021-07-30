# ADR 4: Modular Validation

## Status

Accepted

## Context

With the upcoming of [notaryv2](https://github.com/notaryproject/nv2) and similar projects like [Cosign](https://github.com/sigstore/cosign) the opportunity for Connaisseur arises to support multiple signing mechanisms, and combine all into a single validation tool. For that to work, the internal validation mechanism of connaisseur needs to be more modular, so we can easily swap in and out different methods.

## Considered options

### Configuration changes (Choice 1)

Obviously some changes have to be made to the configuration of Connaisseur, but this splits into changes for the previous notary configurations and the image policy.

#### "Notary" configuration (1.1)

With notaryv1 all trust data always resided in a notary server for which Connaisseur needed the URL, authentication credentials, etc. This isn't true anymore for notaryv2 or Cosign. Here Connaisseur may need other data, meaning the configuration is dependent on the type of validation method used here. Also other mechanisms such as digest whitelisting which doesn't even include cryptographic material might be considered in the future.

##### 1.1.1 Structure

##### Option 1.1.1.1

The previous `notaries` section in the _values.yaml_ changes to `validators`, in which different validation methods (validators) can be defined. The least required fields a validator needs are a `name` for later referencing and a `type` for knowing its correct kind.

```yaml
validators:
- name: "dockerhub-nv2"
  type: "notaryv2"
  ...
- name: "harbor-nv1"
  type: "notaryv1"
  host: "notary.harbor.io"
  root_keys:
    - name: "default"
      key: "..."
- name: "cosign"
  type: "cosign"
  ...
```

Depending on the type, additional fields might be required, e.g. the notaryv1 type requires a `host` and `root_keys` field.

NB: JSON schema validation works for the above and can easily handle various configurations based on type in there.

##### Decision

We are going with this structure (**option 1.1.1.1**) due to the lack of other alternatives. It provides all needed information and the flexibility to use multiple validation methods, as needed.

##### 1.1.2 Sensitive values

If we allow multiple validators that may contain different forms of sensitive values, i.e. notary credentials, symmetric keys, service principals, ..., they need to be properly handled within the Helm chart with respect to ConfigMaps and Secrets. Currently, the distinction is hard-coded.

##### Option 1.1.2.1

Add an optional `sensitive([-_]fields)` field at the validator config top level. Any sensitive values go in there and will be handled by the Helm chart to go into a secret. Any other values are treated as public and go into the ConfigMap.

Advantages:
- Generic configuration
  - Could be used by potential plugin validators to have their data properly handled (potential future)
- Hard to forget the configuration for newly implemented validators

Disadvantage: If implemented in a `config = merge(secret, configmap)` way, might allow sensitive values in configmap and Connaisseur still working

##### Option 1.1.2.2

Hard-code sensitive values based on validator type

Advantages: Can do very strict validation on fields without extra work

Disadvantages:
- Helm chart change might be forgotten for new validator
- Helm chart release required for new validator
- Does not "natively" allow plugins

##### Decision

We are going with **option 1.1.2.2** and hard code the sensitive fields, to prevent users from misconfigure and accidentally but sensitive parts into configmaps.

#### Image policy (1.2)

For the image policy similar changes to the notary configuration have to be made.

##### Proposition

The previous `notary` field in the image policy will be changed to `validator`, referencing a `name` field of one item in the validators list. Any additional fields, e.g. required delegation roles for a notaryv1 validator will be given in a `with` field. This will look similar to this:

```yaml
policy:
- pattern: "docker.harbor.io/*:*"
  validator: "harbor-nv1"
  with:
    key: "default"
    delegations:
    - lou
    - max
- pattern: "docker.io/*:*"
  validator: "dockerhub-nv2"
```

##### Option 1.2.1.1

Besides the self configured validator, two additional validators will be available: _allow_ and _deny_. The allow validator will allow any image and the deny validator will deny anything.

Advantages: More powerful than `verify` flag, i.e. has explicit deny option.

Disadvantages: More config changes for users

##### Option 1.2.1.2

Stick with current `verify` flag.

Advantages: Config known for current users

Disadvantages: No explicit deny option

##### Decision

We are going with **option 1.2.1.1**, as we don't have to use additional fields and offer more powerful configuration options.

##### Option 1.2.2.1

When no validator given, default to deny validator.

Advantages: Easy

Disadvantages: Not explicit

##### Option 1.2.2.2

Require validator in policy config.

Advantages: Explicit configuration, no accidental denying images

Disadvantages: ?

#### Decision

We are going with **option 1.2.2.1** as it reduces configurational effort and is consistent with the key selection behavior.

#### Option 1.2.3.1

The validators from option 1.2.1.1 (_allow_ and _deny_) will be purely internal, and additional validator can not be named "allow" or "deny".

Advantages: Less configurational effort

Disadvantage: A bit obscure for users

#### Option 1.2.3.2

The _allow_ and _deny_ validator will be added to the default configuration as `type: static` with an extra argument (name up for discussion) that specifies whether everything should be denied or allowed. E.g.:

```yaml
validators:
- name: allow
  type: static
  approve: true
- name: deny
  type: static
  approve: false
- ...
```

Advantages: No obscurity, if user don't need these they can delete them.

Disadvantage: Bigger config file ...?

#### Decision

We are going with **option 1.2.3.2** as we favor less obscurity over the "bigger" configurational "effort".

### Validator interface (Choice 2)

See [validator interface](https://github.com/sse-secure-systems/connaisseur/blob/master/connaisseur/validators/validator.py)

Should validation return JSON patch or digest?

#### Option 2.1.1

`Validator.validate` creates a JSON patch for the k8s request. Hence, different validators might make changes in addition to transforming tag to digest.

Advantages: More flexibility in the future

Disadvantages: We open the door to changes that are not core to Connaisseur functionality

#### Option 2.1.2

`Validator.validate` returns a digest and Connaisseur uses the digest in a "standardized" way to create a JSON patch for the k8s request.

Advantage: No code duplication and we stay with core feature of translating input data to trusted digest

Disadvantages: Allowing additional changes would require additional work if we wanted to allow them in the future

#### Decision

We are going with **option 2.1.2** as all current and upcoming validation methods return a digest.
