# CI/CD Pipeline

## Overview

The pipeline is defined in the `.github/workflows` directory. It is structured as follows:

- all `0*.yml` files are the main pipeline definitions, that are triggered by either pushing code, creating a pull request, manually running a job, or a scheduled job.
- all `1*.yml` files are part of a reusable pipeline definition, that is included in the main pipeline definitions.
- all `2*.yml` files are part of miscellaneous job definitions, also included in the main pipeline definitions.

Additionally there are custom actions defined in the `.github/actions` directory, that are used in the pipeline definitions.

## Pipeline Definitions

The main pipeline definitions are as follows:

- `01_pr.yaml`: Triggered by creating a pull request against master and develop. It runs the reusable CI pipeline.
- `02_push.yaml`: Triggered by pushing code to master or develop and is otherwise identical to the `00_pr.yaml` pipeline.
- `03_release.yaml:`: Triggered by pushing a tag prefixed with `v` and builds the Connaisseur image, checks that the image tag matches the git tag, runs the integration tests, publishes the helm chart to ArtifactHub and updates the Connaisseur documentation.
- `04_publish.yaml`: Triggered manually and publishes the helm chart to ArtifactHub and updates the Connaisseur documentation. This is meant to be used in case the `03_release.yaml` pipeline fails and the helm chart needs to be published manually.
- `05_nightly.yaml`: Triggered by a scheduled job that runs every night, which runs the reusable CI pipeline but without unit tests, sast jobs, documentation publishing and integration tests. This pipeline also cleans up old images from the GitHub container registry.
- `06_dockerhub_check.yaml`: Triggered by a scheduled job that runs weekly, which pulls all test images from DockerHub to make sure they are still available and don't get deleted because of inactivity.

## Reusable Pipeline Definitions

The reusable pipeline definitions are as follows:

- `100_ci.yaml`: This is the combined pipeline definition that includes all other jobs in this section and can be configured to skip certain jobs.
- `101_build.yaml`: Builds the Connaisseur image and pushes it to the GitHub container registry. Also prints a summary to the GitHub Actions summary.
- `102_compliance.yaml`: Does a dependency review, looks for invalid licenses and check that the commit message follows the conventional commit format.
- `103_unit-tests.yaml`: Runs the unit tests.
- `104_sast.yaml`: Runs static application security testing.
- `105_sca.yaml`: Runs software composition analysis.
- `106_docs.yaml`: Updates the Connaisseur documentation.
- `107_integration-tests.yaml`: Runs the integration tests.

## Miscellaneous Job Definitions

The miscellaneous job definitions are as follows:

- `200_publish.yaml`: Publishes the helm chart to ArtifactHub and updates the Connaisseur documentation.
- `201_cleanup-registry.yaml`: Cleans up old images from the GitHub container registry.

## Custom Actions

The custom actions are as follows:

- `integration-test`: Sets up a k3s Kubernetes cluster, if necessary, deploys an alerting service, runs the integration tests and displays various information in the GitHub Actions summary.
- `notary-service`: Starts up either a notary signer or a notary server service, depending on the input.
