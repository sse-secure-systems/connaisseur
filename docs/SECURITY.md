# Security Policy

## Supported versions

While all known vulnerabilities are listed below and we intent to fix vulnerabilities as soon as we become aware, both, Python and OS packages of the Connaisseur image may become vulnerable over time and we suggest to frequently update to the latest version of Connaisseur or rebuilding the image from source yourself.
At present, we only support the latest version.
We stick to semantic versioning, so unless the major version changes, updating Conaisseur should never break your installation.

## Known vulnerabilities

| Title | Affected versions | Fixed version | Description |
| - | - | - | - |
| initContainers not validated | <span>&#8804;</span> 1.3.0 | 1.3.1 | Prior to version 1.3.1 Connaisseur did not validate initContainers which allowed deploying unverified images to the cluster. |

## Reporting a vulnerability

We are very grateful for reports on vulnerabilities discovered in the project, specifically as it is intended to increase security for the community. We aim to investigate and fix these as soon as possible. Please submit vulnerabilities to [connaisseur@securesystems.dev](mailto:connaisseur@securesystems.dev).
