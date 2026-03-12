# Release Guide

## Release version updates

To update a major or minor version, or patch a release, and publish on PyPI:

1. **Update the CHANGELOG.md**

   - [ ] Generate a list of PRs using [github-activity](https://github.com/executablebooks/github-activity)

   ```bash
   hatch shell release
   github-activity --output github-activity-output.md --since <last tag> 2i2c-org/jupyterhub-usage-quotas
   ```

   - [ ] Visit and label all uncategorised PRs appropriately with: maintenance, enhancement, breaking, bug, or documentation or skip this and next step and categorize them manually in the changelog.
   - [ ] Generate the `github-activity` output again and add it to the [changelog](CHANGELOG.md)
   - [ ] Highlight breaking changes
   - [ ] Summarise the release changes
   - [ ] Open a PR to merge the updated changelog into main

1. **Prepare Your Environment**

   Following the update of the changelog in the main branch, ensure your local repository is up-to-date and install required tools:

   ```bash
   git checkout main
   git fetch origin main
   git reset --hard origin/main
   ```

   Activate the `release` environment if not already activated:

   ```bash
   hatch shell release
   ```

1. **Update Version with tbump**

   ```{note}
   To perform the actions in this step, you will need write access to the GitHub repository.
   ```

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

   - Update `__version__` in `src/jupyterhub_usage_quotas/__init__.py`
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
   - The package is available on PyPI
