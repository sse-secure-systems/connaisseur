# ADR 9: Multi Pod Architecture

## Status

Undecided

## Context

The core functionality of Connaisseur always has been centered around a standalone pod in which a web server is running and where all validation takes place.
There can be multiple pods of Connaisseur, which follows the purpose of redundancy, so that Connaisseur may always be available and that load can be better balanced.
Only recently, with the addition of a caching mechanism using an external Redis store, an additional pod was introduced to a core Connaisseur deployment.

The idea of this ADR is to discuss further distribution of functionalities into separate modules, away from the centralized standalone pod approach.

## Considered Options

### Option 1: Validator Pods

#### Architecture Idea

The different types of supported validators are split into their own pods, with a centralized management service that coordinates incoming requests to the right validator pods.
The validator pods of the same type have their own service, so that multiple pods of the same validator can be run, in case of high load.

The management service will take over the following functionalities:

- Read Connaisseur config
- Run web server
- Accept and parse admission requests
- Image caching
- Send image validation requests to corresponding validator service
- Generate and send back admission response
- Metrics
- Send alerts

The validator pods/service will take over the following functionalities:

- Run web server
- Specific image validation
- Metrics

#### Advantages

- Users only deploy modules they actually need -> smaller footprint
- Embraces the Kubernetes microservice architecture
- Issues in single modules do not affect the others
- No longer bound to a single language
- Public interface would allow proprietary or community-maintained validators

#### Disadvantages

- Maintenance of multiple images (management-image, Notary-image, Cosign-image, etc.)
- (Potentially maintenance of multiple charts or subcharts)
- More complexity
    - TLS between management service and validators (💡: Redis solution can be reused)
    - Upgrade edge cases (how to validate a validator image, if corresponding validator does not exist?)

### Option 2: Alerting Pods

The alerting functionality is split from the main Connaisseur service, into its own.
The management service will contact the alerting service, should alerts need to be sent out.
The alerting service will take over the following functionalities:

- Run web server
- Sending alerts
- Metrics

Similar advantages and disadvantages apply as for option 1.

### Option 3: Single Pod

Everything stays as is.
One pod for web server+validation and one pod for caching.

## Decision Outcome

- We like the idea, but it's a huge change with significant attached effort
- Let's consider a PoC
