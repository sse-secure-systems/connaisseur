# ADR 8: Transition to Golang

## Status

Accepted

## Context

Connaisseur was orignally written in Python, mostly because of a preference of language in the team.
This was completely fine and worked for many years, but over the time it became more apparent that other programming languages might be better suited for the task, namely Golang.
The main reasons for this are:

- The signature schemes (Cosign, Notary, Notation) are written in Golang, which means that they can be directly used in that language.
For Python, this had to be circumvented by using either a compiled version of the schemes as binaries, which bloat image size and are not as easy to use, or writing an own implementation in Python.
Switching to Golang allows for better and probably faster integration of the schemes, giving a broader choice of signature providers to the community.
- The resulting Connaisseur container will be more secure, as Golang is a compiled language, which means that the resulting binary can be run without any interpreter.
This has implication on the use of base images, as Golang can use scratch images, which are more secure than the Python equivalent bringing OS and runtime.
- Golang is THE Kubernetes language.
Most of the tools in the ecosystem are written in Golang, thus the broader community is a lot more familiar with it.
This will make it easier for people to contribute to Connaisseur.

This ADR discusses whether a transition to Golang is worth the effort and how it would play out.

## Considered Options

### Option 1: Stay with Python

No transition will be made.
The Python code base is kept and continuously developed.
Resources can be spend on improving the existing code base and adding new features.
Adding new signature schemes will be more difficult, as they either have to be implemented in Python, or other workarounds have to be found.


### Option 2: Transition to Golang

The Python code base is abandoned and a new code base is written in Golang.
This will allow for easier integration of new signature schemes and a more secure container image.
It will also open up the project to the Kubernetes/Golang community, while shutting down the Python one.
The transition will require a lot of work and will take some time.

We transition to Golang, which will require an entirely new code base 😥
This comes with all benefits mentioned above, but also with a lot of work.
Additionally, the knowledge of the language in the team is rather limited at the time.

There were some efforts by @phbelitz to transition to Golang, of which the following
parts are still missing (compared to the Python version):

- Rekor support for Cosign
- Unit tests for Notary validator
- Integration tests
- CICD
- Documentation

Also none of the Golang code was yet reviewed by a second pair of eyes.

## Decision Outcome

We develop a Golang version in parallel to continued support of the Python version.
The Golang version should not be a breaking change to ensure we can use existing tests to keep confidence in the new version.
Once the Golang version is developed, we switch it with the Python version in a feature release.
