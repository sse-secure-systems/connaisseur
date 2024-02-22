# ADR 3: Multiple Notary Configuration

## Status

Accepted

## Context

Previously Connaisseur only supported the configuration of a single notary, where all signature data had to reside in. Unfortunately this is rather impractical, as one doesn't create all signatures for all images one uses in a cluster. There is a need to access signature data from multiple places, like in a setup where most images come from a private registry + notary and some from Docker Hub and their notary.

There is also the problem that a single notary instance could use multiple root keys, used for creating the signatures, like in the case of Docker Hub. Connaisseur also only supports a single root key to be trust pinned, thus making it impractical.

That's why the decision was made to support more than one notary and multiple keys per notary, which leads to the question how the new configuration should look like. This also has implications on the notary health check, which is important for Connaisseur's own readiness check.

## Considered options

### Choice 1

The overall notary configuration setup in `charts/connaisseur/values.yaml`.

#### Option 1 (Per Notary)

The `notary` field becomes a list and changes to `notaries`. Per to be used notary instance, there will be one entry in this list.

The entry will have the following data fields (**bold** are mandatory):

- **`name`** -- A unique identifier for the notary configuration, which will be used in the image policy.
- **`host`** -- The host address of the notary instance.
- **`pub_root_keys`** -- A list of public root keys, which are to be used for signature verification.
    - **`name`** -- An identifier for a single public root key, which will be used in the image policy.
    - **`key`** -- The actual public root key in PEM format.
- `selfsigned_cert` -- A self-signed certificate in PEM format, for making secure TLS connection to the notary.
- `auth` -- Authentication details, should the notary require some.
    - `user` -- Username to authenticate with.
    - `password` -- Password to authenticate with.
    - `secretName` -- Kubernetes secret reference to use *INSTEAD* of user/password combination.
- `isAcr` -- Marks the notary as being part of an Azure Container Registry.

The image policy will have two additional fields per rule entry (in "quotes" are already present fields):

- "`pattern`" -- Image pattern to match against, for rule to apply.
- "`verify`" -- Whether the images should be verified or not.
- "`delegations`" -- List of required delegation roles.
- `notary` -- Which notary to use for any matching image. This has to correspond to a `name` field of one configured notary. What happens if none is given, is defined by the result of choice 2.
- `key` -- Which key to use for doing the signature verification. This has to correspond to a `name` field of one of the public keys configured for the notary corresponding to the image policy's `notary` field. What happens if none is given, is defined by the result of choice 2.

#### Option 2 (Per Notary + Key)

The `notary` field becomes a list and changes to `notaries`. Per notary + public root key combination, there is one entry. Meaning, for example, there will be one entry for Docker Hub and the public key for all official images and there will be another entry for Docker Hub and the public key for some private images.

The entries will look identical to the one's from option 1, with two exceptions.

1. The `pub_root_keys` field of the notary configurations won't be a list and only has a single entry, without needing to specify a key name.

2. The image policy will only address the notary configuration to be chosen with the `notary` field, without the need for a `key` field.

### Choice 2

Default values for `notary` (and `key`) inside the image policy.

#### Option 1 (First item)

When no `notary` is specified in a image policy rule, the first entry in the `notaries` configuration list is taken. The same goes for the public root key list, should option 1 for choice 1 be chosen.

Problem: Might get inconsistent, should list ordering in python get shuffled around

#### Option 2 (Explicit default)

One of the notary configuration will be given a `default` field, which marks it as the default value.

Problem: No real problems here, just an extra field that the user has to care about.

#### Option 3 (Mandatory Notary)

The `notary` (and potentially `key`) field is mandatory for the image policy.

Problem: Creates configuration overhead if many image policies use the same notary/key combination.

#### Option 4 (Default name)

If no `notary` or `key` are given in the image policy, it is assumed that one of the elements in the notary list or key list has `name: "default"`, which will then be taken. Should the assumption be wrong, an error is raised.

### Choice 3

Previously, the readiness probe for connaisseur also considered the notary's health for its own status. With multiple notary instances configured, this behavior changes.

#### Option 1 (Ignore Notary)

The readiness probe of Connaisseur will no longer be dependent on any notary health checks. The are completely decoupled.

Problem: No knowledge that Connaisseur will automatically fail because of an unreachable notary, before one tries to deploy an image.

#### Option 2 (Health check on all)

In order for connaisseur to be ready, all configured notaries must be healthy and reachable.

Problem: A single unreachable notary will "disable" Connaisseur's access to all others.

#### Option 3 (Log Notary status)

A mix of option 1 and 2, whereas the readiness of Connaisseur is independent of the notaries health check, but they are still being made, so unhealthy notaries can be logged.

Problem: At what interval should be logged?

## Decision outcome

### Choice 1

Option 1 was chosen, to keep configurational duplication at a minimum.

### Choice 2

Option 4 was chosen. If more than one notary configuration or key within a configuration are present, one of those can be called "default" (setting the `name` field). That way it should be obvious enough, which configuration or key will be used, if not further specified within the image policy, while keeping configuration effort low.

### Choice 3

Option 3 was chosen. Notary and Connaisseur will be completely decoupled, with Connaisseur logging all notaries it can't reach. This way Connaisseur can still be operational, even with all notaries being unreachable. Otherwise Connaisseur would have blocked even images that were allowlisted. This is a breaking change, but we agreed that it is better as it allows e.g. deployments for which the respective image policy specifies `verify: false`.
