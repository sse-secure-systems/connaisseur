# ADR 2: Release Management

## Status

Proposed

## Context

During its initial development Connaisseur was more or less maintained by a single person and not released frequently. Hence, the easiest option was to just have the maintainer build and push at certain stages of development. With the influx of more team members, the number of contributions and hence the number of needed/reasonable releases went up. Also since publication, it is more important that the uploaded Connaisseur image corresponds to the most recent version referenced in the Helm chart.

A single person having to build, sign and push the images whenever a new pull request is accepted is hence unpractical for both development and agility.

## Considered options

### Choice 1

What branches to maintain

#### Option 1

Continue with PRs from personal feature branches to `master`.

#### Option 2

Have a development branch against which to create pull requests (during usual development, hotfixes may be different).

Sub-options:
- a `develop` (or similar) branch that will exist continuously
- a `v.1.5.0_dev` (or similar) branch for each respective version

### Choice 2

Where to sign the images

#### Option 1

Have the pipeline build, sign and push the images.

#### Option 2

Have a maintainer build, sign and push the images.

## Decision outcome

For choice 1, we decided to go for two branches. On the one hand, `master` being the branch that contains the code of the latest release and will be tagged with release versions. On the other hand, there will be a `develop` branch that hosts the current state of development and will be merged to `master` whenever we want to create a new release.

This way we get rid of the current pain of releasing with every pull request at the cost a some overhead during release.

In the process of automating most of the release process, we will run an integration test with locally built images for pull requests to `master`. Regarding choice 2, whenever a pull request is merged, whoever merged the PR has to tag this commit on the `master` branch with the most recent version. Right after the merge, whoever merged the PR builds, signs and pushes the new Connaisseur release and creates a tag on the `master` branch referencing the new release version.

After the image is pushed and the new commit tagged, the pipeline will run the integration test with the image pulled from Docker Hub to ensure that the released version is working.

We decided for this option as it does not expose credentials to GitHub Actions, which we wanted to avoid especially in light of the [recent GitHub Actions injection attacks](https://bugs.chromium.org/p/project-zero/issues/detail?id=2070) and as it would also prevent us from opening up the repository to Pull Requests. To alleviate the work required for doing the steps outside the pipeline we use a shell script that will automate these steps given suitable environment, i.e. Docker context and DCT keys.

### Positive consequences

- We can develop without having to ship changes immediatly.
- Release process does not expose credentials to GitHub Actions.
- Code gets Git tags.

### Negative consequences

- Process from code to release for a single change is more cumbersome than right now.
- Release still requires human intervention.
