# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

## Example Contributions

You can contribute in many ways, for example:

- [Report bugs](#report-bugs)
- [Fix Bugs](#fix-bugs)
- [Implement Features](#implement-features)
- [Write Documentation](#write-documentation)
- [Submit Feedback](#submit-feedback)

(report-bugs)=

### Report Bugs

Report bugs at [https://github.com/2i2c-org/jupyterhub-usage-quotas/issues](https://github.com/2i2c-org/jupyterhub-usage-quotas/issues).

**If you are reporting a bug, please follow the template guidelines. The more
detailed your report, the easier and thus faster we can help you.**

(fix-bugs)=

### Fix Bugs

Look through the GitHub issues for bugs. Anything labelled with `bug` and
`help wanted` is open to whoever wants to implement it. When you decide to work on such an issue, please assign yourself to it and add a comment that you'll be working on that, too. If you see another issue without the `help wanted` label, just post a comment, the maintainers are usually happy for any support that they can get.

(implement-features)=

### Implement Features

Look through the GitHub issues for features. Anything labelled with
`enhancement` and `help wanted` is open to whoever wants to implement it. As
for [fixing bugs](#fix-bugs), please assign yourself to the issue and add a comment that you'll be working on that, too. If another enhancement catches your fancy, but it doesn't have the `help wanted` label, just post a comment, the maintainers are usually happy for any support that they can get.

(write-documentation)=

### Write Documentation

The project could always use more documentation, whether as
part of the official documentation, in docstrings, an update to our Contributing or Development guide. To contribute, [open an issue](https://github.com/2i2c-org/jupyterhub-usage-quotas/issues) to let us know what you will be working on so that we can provide you with guidance.

(submit-feedback)=

### Submit Feedback

The best way to send feedback is to file an issue at [https://github.com/2i2c-org/jupyterhub-usage-quotas/issues](https://github.com/2i2c-org/jupyterhub-usage-quotas/issues). If your feedback fits the format of one of the issue templates, please use that. Remember that this is a volunteer-driven project and everybody has limited time.

## Get Started!

Ready to contribute? Here's how to set up for
local development.

1. Fork the [repository](https://github.com/2i2c-org/jupyterhub-usage-quotas) on GitHub.

1. Clone your fork locally

   ```shell
   git clone https://github.com/<your_username>/jupyterhub-usage-quotas.git
   ```

1. See [DEVELOPMENT](DEVELOPMENT.md) for guidance on how to set up your local development environment.

1. Create a branch for local development using the default branch (typically `main`) as a starting point. Use `fix` or `feat` as a prefix for your branch name (see [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)).

   ```shell
   git checkout main
   git checkout -b fix-name-of-your-bugfix
   ```

   Now you can make your changes locally.

1. When you're done making changes, apply the quality assurance tools and check
   that your changes pass our test suite. This is all included with hatch

   ```shell
   hatch run test:run
   ```

1. Commit your changes and push your branch to GitHub. Please use [semantic commit messages](https://www.conventionalcommits.org/).

   ```shell
   git add .
   git commit -m "fix: summarize your changes"
   git push -u origin fix-name-of-your-bugfix
   ```

1. Open the link displayed in the message when pushing your new branch in order
   to submit a pull request.

### Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests or test modifications as needed.
1. If needed, please add documentation around a change that you make by updating our DEVELOPMENT.md file.
1. Your pull request will automatically be checked by the full test suite.
   It needs to pass all tests before it can be considered for merging.

## Local development

See the [DEVELOPMENT guide](DEVELOPMENT.md) for more information on local development.
