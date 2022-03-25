# Releasing

Releasing a new version of Connaisseur includes the following steps:

- check readiness
- adding a new version tag
- creating a changelog from commit messages
- creating a PR from `develop` (new version) to `master` (current version)
- pushing a new version of the Connaisseur image to Docker Hub
- merging in the PR & push tag
- creating release page
- shoot some trouble

## Check readiness

Before starting the release, make sure everything is ready and in order:

- See that all tests are running smoothly.
- Check that documentation changes show up correctly [here](https://sse-secure-systems.github.io/connaisseur/develop/).
- Make sure the Connaisseur version is incremented correctly according to the changes.
- Make sure Connaisseur version in `helm/values.yaml` is matched to the appVersion in `helm/Chart.yaml` and the (chart) version in `helm/Chart.yaml` is increased according to semantic versioning if Helm templates have been touched.
- See if the docs announcements should be adjusted [here](https://github.com/sse-secure-systems/connaisseur/blob/master/docs/overrides/main.html).
- Consider making a [GitHub Discussions *announcement*](https://github.com/sse-secure-systems/connaisseur/discussions).

## Add new tag

Before adding the new tag, make sure the Connaisseur version is updated in the `helm/values.yaml` and applies the semantic versioning guidelines: fixes increment PATCH version, non-breaking features increment MINOR version, breaking features increment MAJOR version.
Then add the tag (on `develop` branch) with `git tag v<new-conny-version>` (e.g. `git tag v1.4.6`).

## Create changelog

A changelog text, including all new commits from one to another version, can be automatically generated using the `scrips/changelogger.py` script.
Run `python scripts/changelogger.py > CHANGELOG.md` to get the changelog between the two latest tags.
If you want to have a diff between certain commits, you have to set the two `ref1` and `ref2` variables.
If you e.g. want to get the changelog from `v1.4.5` to `09fd2379cf2374ba9fdc8a84e56d959a176f1569`, then you have to run `python scripts/changelogger.py --ref1="v1.4.5" --ref2="09fd2379cf2374ba9fdc8a84e56d959a176f1569"> CHANGELOG.md`, storing the changelog in a new file `CHANGELOG.md` (we won't keep this file, it's just for convenient storing purpose).
This file will include all new commits, categorized by their type (e.g. fix, feat, docs, etc.), but may include some mistakes so take a manual look if everything looks in order.

Things to look out for:

- multiple headings for the same category
- broken pull request links
- `None` appended on end of line

## Create PR

Create a PR from `develop` to `master`, putting the changelog text as description and wait for someone to approve it.

## Push new Connaisseur image

When the PR is approved and ready to be merged, first push the new Connaisseur image to Docker Hub, as it will be used in the release pipeline.
Run `make docker` to build the new version of the docker image and then `DOCKER_CONTENT_TRUST=1 docker image push securesystemsengineering/connaisseur:<new-version>` to push and sign it.
You'll obviously need the right private key and passphrase for doing so.
You also need to be in the list of valid signers for Connaisseur.
If not already (you can check with `docker trust inspect securesystemsengineering/connaisseur --pretty`) you'll need to contact [Philipp Belitz](mailto:philipp.belitz@securesystems.de).

## Merge PR

Run `git checkout master` to switch to the `master` branch and then run `git merge develop` to merge `develop` in.
Then run `git push` and `git push --tags` to publish all changes and the new tag.

## Create release page

Finally a release on GitHub should be created.
Go to the [Connaisseur releases page](https://github.com/sse-secure-systems/connaisseur/releases), then click _Draft a new release_.
There you have to enter the new tag version, a title (usually `Version <new-version>`) and the changelog text as description.
Then click _Publish release_ and you're done!
(You can delete the CHANGELOG.md file now. Go and do it.)

![gh_release_flow](assets/gh_release.png)

## Shoot trouble

Be aware that this **isn't** a completely fleshed out, highly available, hyper scalable and fully automated workflow, backed up by state-of-the-art blockchain technology and 24/7 incident response team coverage with global dominance!
Not yet at least.
For now things will probably break, so make sure that in the end everything looks to be in order and the new release can be seen on the GitHub page, tagged with _Latest release_ and pointing to the correct version of Connaisseur.
Good Luck!
