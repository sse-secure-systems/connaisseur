# Contributing
We hope to steer development of Connaisseur from demand of the community and are excited about direct contributions to improve the tool!

The following guide is meant to help you get started with contributing to Connaisseur.
In case of questions or feedback, feel free to [reach out to us](https://github.com/sse-secure-systems/connaisseur/discussions).

We are committed to positive interactions between all contributors of the project. To ensure this, please follow the [Code of Conduct](CODE_OF_CONDUCT.md) in all communications.

## Discuss problems, raise bugs and propose feature ideas
We are happy you made it here!
In case you want to share your feedback, need support, want to discuss issues from using Connaisseur in your own projects, have ideas for new features or just want to connect with us, please reach out via [GitHub Discussions](https://github.com/sse-secure-systems/connaisseur/discussions).
If you want to raise any bugs you found or make a feature request, feel free to [create an issue](https://github.com/sse-secure-systems/connaisseur/issues/new) with an informative title and description.

While issues are a great way to discuss problems, bugs and new features, a direct proposal via a pull request can sometimes say more than a thousand words.
So be bold and contribute to the code as described in the [next section](#contribute-to-source-code)!

In case you require a more private communication, you can reach us via [connaisseur@securesystems.dev](mailto:connaisseur@securesystems.dev).

## Contribute to source code
The following steps will help you make code contributions to Connaisseur and ensure good code quality and workflow.
This includes the following steps:

1. **Set up your environment**:
   Set up up your local environment to best interact with the code.
   Further information is given [below](#set-up-the-environment).
2. **Make atomic changes**:
   Changes should be atomic.
   As such, pull requests should contain only few commits, and each commit should only fix one issue or implement one feature, with a concise commit message.
3. **Test your changes**:
   Test any changes locally for code quality and functionality and add new tests for any additional code.
   How to test is described [below](#test-changes).
4. **Create semantic, conventional and signed commits**:
   Any commits should follow a simple semantic convention to help structure the work on Connaisseur. The convention is described [below](#semantic-and-conventional-commits). For security reasons and since integrity is at the core of this project, code merged into master must be signed.
   How we achieve this is described [below](#signed-commits-and-pull-requests).
5. **Create pull requests**:
   We consider code review central to quality and security of code.
   Therefore, a pull request (PR) to the `develop` branch should be created for each contribution. It will be reviewed, and potential improvements may be discussed within the PR. After approval, changes will be merged and moved to the `master` branch with the next release.

### Set up the environment
To start contributing, you will need to set up your local environment.
First step is to get the source code by cloning this repository:

```bash
git clone git@github.com:sse-secure-systems/connaisseur.git
```
In order to review the effects of your changes, you should create your own Kubernetes cluster and install Connaisseur.
This is described in the [getting started](getting_started.md).
A simple starting point may be a minikube cluster with e.g. a [Docker Hub](https://hub.docker.com/) repository for maintaining your test images and trust data.

In case you make changes to the Connaisseur container image itself or code for that matter, you need to re-build the image and install it locally for testing.
This requires a few steps:

1. In `helm/values.yaml`, set `imagePullPolicy` to `IfNotPresent`.
2. Configure your local environment to use the Kubernetes Docker daemon. In minikube, this can be done via `eval (minikube docker-env)`.
3. Build the Connaisseur container image via `make docker`.
4. Install Connaisseur as usual via `make install`.

### Test changes
Tests and linting are important to ensure code quality, functionality and security.
We therefore aim to keep the code coverage high.
We are running several automated tests in the [CI pipeline](https://github.com/sse-secure-systems/connaisseur/blob/master/.github/workflows/cicd.yaml).
Application code is tested via [pytest](https://docs.pytest.org/) and linted via [pylint](https://pylint.org/).
When making changes to the application code, please directly provide tests for your changes.

We recommend using [black](https://pypi.org/project/black/) for autoformatting to simplify linting and reduce review effort. It can be installed via:
```
pip3 install black
```
To autoformat the code:
```
black <path-to-repository>/connaisseur
```

Changes can also be tested locally.
We recommend the following approach for running pytest in a container:
```
docker run -it --rm -v <path-to-repository>:/data --entrypoint=ash python:alpine
cd data
YARL_NO_EXTENSIONS=1 MULTIDICT_NO_EXTENSIONS=1 pip3 install -r requirements_dev.txt
pytest --cov=connaisseur --cov-report=xml tests/
```

This helps identify bugs in changes before pushing.

> :information_source: **INFO** We believe that testing should not only ensure functionality, but also aim to test for expected security issues like injections and appreciate if security tests are added with new functionalities.

Besides the unit testing and before any PR can be merged, an integration test is carried out whereby:

- Connaisseur is successfully installed in a test cluster
- a non-signed image is deployed to the cluster and denied
- an image signed with an unrelated key is denied
- a signed image is deployed to the cluster and passed
- Connaisseur is successfully uninstalled

You can also run this integration test on a local cluster. There is a more [detailed guided](https://github.com/sse-secure-systems/connaisseur/blob/master/tests/integration/README.md) on how to do that.

If you are changing documentation, you can simply inspect your changes locally via:

```bash
docker run --rm -it -p 8000:8000 -v ${PWD}:/docs squidfunk/mkdocs-material
```


### Signed commits and pull requests
All changes to the `develop` and `master` branch must be signed which is enforced via [branch protection](https://docs.github.com/en/free-pro-team@latest/github/administering-a-repository/about-required-commit-signing).
This can be achieved by only fast-forwarding signed commits or signing of merge commits by a contributor.
Consequently, we appreciate but do not require that commits in PRs are signed.

A general introduction into signing commits can for example be found in the [With Blue Ink blog](https://withblue.ink/2020/05/17/how-and-why-to-sign-git-commits.html). For details on setting everything up for GitHub, please follow the steps in the [Documentation](https://docs.github.com/en/github/authenticating-to-github/managing-commit-signature-verification).

Once you have generated your local GPG key, added it to your GitHub account and informed Git about it, you are set up to create signed commits.
We recommend to configure Git to sign commits by default via:
```bash
git config commit.gpgsign true
```
This avoids forgetting to use the `-S` flag when committing changes.
In case it happens anyways, you can always rebase to sign earlier commits:
```bash
git rebase -i master
```
You can then mark all commits that need to be signed as `edit` and sign them without any other changes via:
```bash
git commit -S --amend --no-edit
```
Finally, you force push to overwrite the unsigned commits via `git push -f`.

### Semantic and conventional commits
For Connaisseur, we want to use semantic and conventional commits to ensure good readability of code changes.
A good introduction to the topic can be found in [this blog post](https://nitayneeman.com/posts/understanding-semantic-commit-messages-using-git-and-angular/).

Commit messages should consist of header, body and footer.
Such a commit message takes the following form:

```
git commit -m "<header>" -m "<body>" -m "<footer>"
```
The three parts should consist of the following:

- _header_: Comprises of a commit type (common types are described below) and a concise description of the actual change, e.g. `fix: extend registry validation regex to custom ports`.
- _body_ (optional): Contains information on the motivation behind the change and considerations for the resolution, `The current regex used for validation of the image name does not allow using non-default ports for the image repository name. The regex is extended to optionally provide a port number.`.
- _footer_ (optional): Used to reference PRs, issues or contributors and mark consequences such as breaking changes, e.g. `Fix #<issue-number>`

We want to use the following common types in the header:

- _build_: changes to development and building
- _ci_: CI related changes
- _docs_: changes in the documentation
- _feat_: adding of new features
- _fix_: fixing an issue or bug
- _refactor_: adjustment of code base to improve code quality or performance but not adding a feature or fixing a bug
- _test_: testing related changes
- _update_: updating a dependency

A complete commit message could therefore look as follows:
```
git commit -m "fix: extend registry validation regex to custom ports" -m "The current regex used for validation of the image name does not allow using non-default ports for the image repository name. The regex is extended to optionally provide a port number." -m "Fix #3"
```

## Enjoy!
Please be __bold__ and contribute!
