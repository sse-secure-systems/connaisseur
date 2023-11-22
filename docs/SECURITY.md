# Security Policy

## Supported versions

While all known vulnerabilities in the Connaisseur application are listed below and we intent to fix vulnerabilities as soon as we become aware, both, Python and OS packages of the Connaisseur image may become vulnerable over time and we suggest to frequently update to the latest version of Connaisseur or rebuilding the image from source yourself.
At present, we only support the latest version.
We stick to semantic versioning, so unless the major version changes, updating Conaisseur should never break your installation.

## Known vulnerabilities

| Title | Affected versions | Fixed version | Description |
| - | - | - | - |
| initContainers not validated | <span>&#8804;</span> 1.3.0 | 1.3.1 | Prior to version 1.3.1 Connaisseur did not validate initContainers which allowed deploying unverified images to the cluster. |
| Ephemeral containers not validated | <span>&#8804;</span> 3.1.1 | 3.2.0 | Prior to version 3.2.0 Connaisseur did not validate ephemeral containers (introduced in k8s 1.25) which allowed deploying unverified images to the cluster. |
| Regex Denial of Service for Notary delegations | <span>&#8804;</span> 3.3.0 | 3.3.1 | Prior to version 3.3.1 Connaisseur did input validation on the names of delegations in an unsafe manner: An adversary with the ability to alter Notary responses, in particular an evil Notary server, could have provided Connaisseur with an invalid delegation name that would lead to catastrophic backtracking during a regex matching. Only users of type `notaryv1` validators are affected as Connaisseur will only perform this kind of input validation in the context of a Notary validation. If you mistrust the Docker Notary server, the default configuration is vulnerable as it contains a `notaryv1` validator with the root keys of both Connaisseur and the library of official Docker images. |

## Reporting a vulnerability

We are very grateful for reports on vulnerabilities discovered in the project, specifically as it is intended to increase security for the community. We aim to investigate and fix these as soon as possible. Please submit vulnerabilities to [connaisseur@securesystems.dev](mailto:connaisseur@securesystems.dev).
