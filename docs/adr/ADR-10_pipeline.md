# ADR 10: Pipeline

## Status

Undecided.

Author: @phbelitz

## Context

The pipeline grew into a complicated construct that is, at times, confusing to work with (at least for me). So let's take the time to reconsider certain parts of it, trying to remove clutter and maybe even speed up runtime :tada:

## Current Setup

The current setup uses a reusable CI definition (`.reusable-ci.yaml`), which itself consists of reusable parts. Occasionally, self-written actions are used which are found in the `action` directory. The CI looks something like this:

- ci
    - conditionals [prints summary + pass-through for args]
    - build
        - context **action** [yq metadata for build]
        - build **action** [build the app + push to ghcr]
            - install cosign
            - setup docker
            - login registry
            - generate tags
            - build + push
            - sbom
            - sign
            - verify
            - upload pub key
            - print summary
    - compliance
        - ossf [scoring for open source projects]
        - dependency review [dependency scanning]
        - check-commit-message [linting for commit messages]
    - unit-test [unit tests :shrug:]
    - sast
        - checkov [helm chart scanning]
        - codeql [GitHub's "industry-leading" semantic code analysis engine]
        - golangci-lint [linting]
        - gosec [go security checker]
        - hadolint [dockerfile linter]
        - kubelinter [helm chart linting]
        - semgrep [some scanning :shrug:]
        - trivy-config-scan
            - trivy-config **action** [scan helm chart and dockerfile]
    - sca
        - trivy-image-scan
            - trivy-image **action** [vulnerability scanning of docker image]
        - grype
            - grype **action** [vulnerabiliy scanning]
        - dependency-submission [sbom generation ...? ran into issues]
    - docs
        - deploy [creates documentation and deploys it]
    - integration-test
        - functional-tests [uses **action** for setting up k8s cluster and alerting endpoint]
        - optional-tests
        - k8s-versions
        - old-k8s-versions
        - self-hosted-notary

## Issues

Issues I see with this setup are as follows:

- confusing file structure: the actual workflows and their moving parts, but not all of them, only the reusables that are not actions reside next to each other, while the actions reside somewhere else ... what? Also most of the actions are used ONCE, resulting is just tearing apart code that is supposed to be together, without any upsides.
- redundant jobs: scanning of the helm chart is done at least thrice. why? 
- unnecessary jobs: signing images inside the pipeline is nice and all, but adds a lot of complexity for very little gains. same is true for creating sboms, especially during development pipelines. 

## Considered Options

### Option 1

Some general things first.

1. ~~Let the workflows be in the `workflow` directory and put the reusable parts into it's own (e.g. `reusable` or `components` :shrug:).~~ Technically not possible because of [reasons](https://docs.github.com/en/actions/sharing-automations/reusing-workflows#creating-a-reusable-workflow)
2. Get rid of all actions that are not being reused and put their code to where it belongs.
3. Create an action for the integration tests. The one place where these actions make sense, we are not using them :facepalm:

For the actual CI definition I propose:

- ci
    - conditionals [prints summary + pass through for args]
    - build
        - context [yq metadata for build]  *// get rid of action*
        - build [build the app + push to ghcr]  *// get rid of action*
            - ~~install cosign~~  *// not worth the effort*
            - setup docker
            - login registry
            - generate tags
            - build + push
            - ~~sbom~~  *// not worth the effort*
            - ~~sign~~  *// not worth the effort*
            - ~~verify~~  *// not worth the effort*
            - ~~upload pub key~~  *// not worth the effort*
            - print summary
    - compliance
        - ~~ossf [scoring for open source projects]~~  *// largely pseudo findings that create clutter*
        - dependency review [dependency scanning]
        - check-commit-message [linting for commit messages]
    - unit-test [unit tests :shrug:]
    - sast
        - ~~checkov [helm chart scanning]~~  *// we have enough helm scanning*
        - codeql [GitHub's "industry-leading" semantic code analysis engine]
        - golangci-lint [linting]
        - gosec [go security checker]
        - hadolint [dockerfile linter]
        - kubelinter [helm chart linting]
        - ~~semgrep [some scanning :shrug:]~~  *// we have enough SCANNING*
        - trivy-config-scan [scan helm chart and dockerfile]  *// get rid of action*
    - sca
        - trivy-image-scan [vulnerability scanning of docker image]  *// get rid of action*
        - ~~grype~~  *// go with trivy scan*
            - ~~grype **action** [vulnerabiliy scanning]~~
        - dependency-submission [sbom generation ...? ran into issues]
    - docs
        - deploy [creates documentation and deploys it]
    - integration-test
        - functional-tests [uses **action** for setting up k8s cluster and alerting endpoint]
        - optional-tests
        - k8s-versions
        - old-k8s-versions
        - self-hosted-notary

### Option 2

Leave things as they are.

### Option X

...?

## Decision

Tbd.