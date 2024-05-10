# Caching

Connaisseur utilizes [Redis](https://github.com/redis/redis) as a cache.
For each image reference the resolved digest or validation error is cached.
This drastically boosts the performance of Connaisseur compared to older non-caching variants.
The expiration for keys in the cache defaults to 30 seconds, but can be tweaked.
If set to 0, no caching will be performed and the cache will not be deployed as part of Connaisseur.

## Configuration options

`cache` in `charts/connaisseur/values.yaml` under `application.features` supports the following configuration:

| Key | Default | Required | Description |
| - | - | - | - |
| `expirySeconds` | `30` | - | Number of seconds for which validation results are cached. If set to 0, the Connaisseur deployment will omit the caching infrastructure in its entirety. |
| `cacheErrors` | `true` | - | Whether validation failures are cached. If set to false, Connaisseur will only cache successfully validated image digests instead of also caching errors. |

## Example

In `charts/connaisseur/values.yaml`:

```yaml
application:
  features:
    cache:
      expirySeconds: 15
      cacheErrors: false
```
