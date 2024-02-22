# Caching

Connaisseur utilizes [Redis](https://github.com/redis/redis) as a cache.
For each image reference the resolved digest or validation error is cached.
This drastically boosts the performance of Connaisseur compared to older non-caching variants.
The expiration for keys in the cache is set to 30 seconds.
