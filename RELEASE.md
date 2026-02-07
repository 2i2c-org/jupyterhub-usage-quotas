# Release Guide

We publish images on [quay.io](https://quay.io/repository/2i2c/jupyterhub-usage-quotas) and [Helm charts](https://2i2c.org/jupyterhub-usage-quotas/) for every tag, including development versions.

## Build image and release publish Helm charts

The GitHub Actions workflow [`publish-helm-chart.yaml`](https://github.com/2i2c-org/jupyterhub-usage-quotas/blob/main/.github/workflows/publish-helm-chart.yaml)) uses [chartpress](https://github.com/jupyterhub/chartpress) to automatically:

- Build the image
- Push the image to the Quay registry (quay.io)
- Update the Helm chart with the new image tags
- Package and publish the Helm chart to [https://2i2c.org/jupyterhub-usage-quotas/](https://2i2c.org/jupyterhub-usage-quotas/)

## Release version updates

To update a major or minor version, or patch a release, and publish on PyPI:

1. **Update the CHANGELOG.md**

   - [ ] Generate a list of PRs using [github-activity](https://github.com/executablebooks/github-activity)

   ```bash
   pip install github-activity
   github-activity --output github-activity-output.md --since <last tag> 2i2c-org/jupyterhub-usage-quotas
   ```

   - [ ] Visit and label all uncategorised PRs appropriately with: maintenance, enhancement, breaking, bug, or documentation or skip this and next step and categorize them manually in the changelog.
   - [ ] Generate the `github-activity` output again and add it to the [changelog](CHANGELOG.md)
   - [ ] Highlight breaking changes
   - [ ] Summarise the release changes

1. **Prepare Your Environment**

   Ensure your local repository is up-to-date and install required tools:

   ```bash
   git checkout main
   git fetch origin main
   git reset --hard origin/main
   ```

   Install tbump if not already installed:

   ```bash
   pip install tbump
   ```

1. **Update Version with tbump**

   To perform the actions in this step, you will need write access to the GitHub repository.

   Use `tbump` to update the version numbers in the codebase:

   - Perform a dry run to see what will change:

   ```bash
   tbump --dry-run ${VERSION}
   ```

   - If you are happy, run the actual update:

   ```bash
   VERSION=x.y.z
   tbump ${VERSION}
   ```

   This will:

   - Update `__version__` in `jupyterhub_home_nfs/__init__.py`
   - Update `version` and `appVersion` in `helm/jupyterhub-usage-quotas/Chart.yaml`
   - Create a git commit
   - Create a git tag

1. **CI Automation**

   TODO: Once we create a tag, the GitHub Actions workflow [`release.yaml`](https://github.com/2i2c-org/jupyterhub-usage-quotas/blob/main/.github/workflows/release.yaml)) will automatically:

   - Package and publish the library to PyPI

1. **Reset the version back to dev, e.g. 4.0.1-0.dev after releasing 4.0.0.**

   ```bash
   NEXT_VERSION=x.y.z1-0.dev
   tbump --no-tag ${NEXT_VERSION}-0.dev
   ```

## Verification

After pushing your changes:

1. Check the GitHub Actions [workflow status](https://github.com/2i2c-org/jupyterhub-usage-quotas/actions)
1. Verify that:
   - The workflow completed successfully
   - The image is available [on quay.io](https://quay.io/repository/2i2c/jupyterhub-usage-quotas)
   - The Helm chart is published on [https://2i2c.org/jupyterhub-usage-quotas/](https://2i2c.org/jupyterhub-usage-quotas/)
   - The package is available on PyPI
