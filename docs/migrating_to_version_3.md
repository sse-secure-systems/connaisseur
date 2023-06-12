# Migrate to Connaisseur version 3.0

It's been a while since our last major update, but it is time again :tada:
Connaisseur version 3.0 is out and brings along many new features, but also breaking changes :boom:
For those breaking changes, we've set up a [script](../scripts/upgrade_to_version_3.py) that migrates your existing Connaisseur configuration.
Read on for the list of most interesting changes.

## Major changes

- NEW: Support for Cosign 2.0
    - :boom: This is a breaking change, because Connaisseur now supports transparency log verification by default.
    If all your Cosign signature artifacts are already part of Rekor's default transparency log (or part of your configured Rekor host) or you don't use Cosign, this is not breaking for you.
- [Changes](#api-changes) to the Helm `values.yaml` file
    - :boom: This is a breaking change as we touched quite a bunch of configuration keys to make the configuration API more consistent and more intuitive
    - :robot: We've prepared a [script](../scripts/upgrade_to_version_3.py) that migrates your existing Connaisseur configuration to the new format. Limitation: It won't migrate your comments :cry: Simply run `python3 scripts/upgrade_to_version_3.py` and your `helm/values.yaml` will be updated (and we'll store a backup of your previous config in `helm/values.yaml.old`)

## Minor changes

- Changed the log format to JSON :sunglasses:
    - The logging format of Connaisseur is now fully transformed into JSON. It includes a `timestamp` and a `message` field, next to additional fields depending on the context. Logs of the HTTP request do not contain a `message` field.

## API changes

Here's the list of changes we made to the Helm `values.yaml`:

- Top-level `kubernetes` key
    - Previously, there were top-level `deployment` and `service` keys, both of which concerned themselves with the respective<sup>*</sup> Kubernetes resources.
    We moved them below a common `kubernetes` key.
- Split `kubernetes` keys by resource
    - Previously, `deployment` contained mostly keys that could be applied to Connaisseur's Kubernetes Deployment resource.
    Notable exceptions were the configuration keys `failurePolicy` and `reinvocationPolicy`, which pertain to the admission controllers webhook.
    We moved them below a `webhook` key below `kubernetes`.
- Split image repository and tag
    - Previously, we had a `deployment.image` key, which held the fully qualified reference of the Connaisseur image. Since not every application logic works with every Helm chart version, we now default to using the tag equal to the chart's `appVersion` (prepended with `v`) and explicitly discourage setting (and do not support arbitrary combinations of) `kubernetes.deployment.image.tag`. However, having this key, and taking into account the top-level `kubernetes` key, the repository (or more correctly, registry, namespace and repository) are configured as `kubernetes.deployment.image.repository`.
- Top-level `application` key
    - Previously, we had a host of configuration keys that pertained to the actual configuration of the Connaisseur application, e.g. the log level, which validators were configured and which features are enabled.
    We moved them below a common `application` key.
- Remove `debug` key
    - The `debug` key was made redundant by the `logLevel` key, which could be set to `DEBUG`.
- Consistent naming of variables
    - Previously, due to some configuration keys being directly used within our Python application, we named them according to pythonic snake_case.
    Since the main interaction of users is through the Helm `values.yaml`, having inconsistent casing there is worse than dealing with a few misnamed keys in our Python stack.
    Accordingly, we migrated all configuration keys_with_snake_case to dromedaryKeys.
- Group features in `features` key
    - Previously, we had top-level configurations for all features changing Connaisseur's verification behavior.
    We grouped them below a common `features` key below the new `application` key.
- Consistent feature toggles
    - Previously, some features had an `enable` key, while others simply featured a boolean.
    The idea was based around whether the feature would have further configuration or not.
    However, having configuration for a disabled feature doesn't really make sense, so we changed it to be the following:
        - If a feature has configuration, i.e. `<featureName>.<someConfigKey>` is set, it is enabled.
        - If a feature is set, i.e. `<featureName>: true`  it is enabled and an error is thrown if it needed configuration but doesn't have any.
        - If a feature is false, i.e. `<featureName>: false`  it is disabled.
        - If a feature is not set at all, i.e. `features` doesn't have a `<featureName>` key, its default configuration is chosen.
- Alerting `receivers`
    - We renamed `alerting.templates` to `alerting.receivers` as each receiver has inherently a template and multiple receivers can have the same template.
    As such `templates` wasn't a fitting name.
- Cosign validator `host.rekor` key
    - Previously, a Cosign validator could have a `host` key, which determined the remote host of a Rekor transparency log to validate against.
    Since `host` is both imprecise for this use and may be used in the future for other hosts (e.g. keyless) for the same validator, we moved this value to a subkey `host.rekor`.
