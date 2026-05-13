# Changelog

## v0.1.1 2026-05-13

([full changelog](https://github.com/2i2c-org/jupyterhub-usage-quotas/compare/v0.1.0b1...e084a6fd31f6c3a24818490269fd2f9833b6a580))

### Enhancements made

- feat: Add tests and docs for usage viewer [#46](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/46) ([@jnywong](https://github.com/jnywong))
- feat: update usage viewer [#45](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/45) ([@jnywong](https://github.com/jnywong))
- feat: update usage viewer frontend to show compute [#42](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/42) ([@jnywong](https://github.com/jnywong), [@sunu](https://github.com/sunu))
- feat: Add Prometheus exporter to update usage viewer backend with compute usage and quota limits [#37](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/37) ([@jnywong](https://github.com/jnywong))
- feat: config prometheus creds [#35](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/35) ([@jnywong](https://github.com/jnywong))

### Maintenance and upkeep improvements

- refactor: port usage viewer service from FastAPI to Tornado [#43](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/43) ([@sunu](https://github.com/sunu), [@jnywong](https://github.com/jnywong))
- patch: remove duplicate config [#41](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/41) ([@jnywong](https://github.com/jnywong))
- fix: Pass Prometheus credentials to client queries [#36](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/36) ([@jnywong](https://github.com/jnywong), [@sunu](https://github.com/sunu))
- fix: include templates directory in python package build [#34](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/34) ([@sunu](https://github.com/sunu))
- fix: preserve existing config values [#33](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/33) ([@sunu](https://github.com/sunu))

### Contributors to this release

The following people contributed discussions, new ideas, code and documentation contributions, and review.
See [our definition of contributors](https://github-activity.readthedocs.io/en/latest/use/#how-does-this-tool-define-contributions-in-the-reports).

([GitHub contributors page for this release](https://github.com/2i2c-org/jupyterhub-usage-quotas/graphs/contributors?from=2026-04-13&to=2026-05-13&type=c))

@jnywong ([activity](https://github.com/search?q=repo%3A2i2c-org%2Fjupyterhub-usage-quotas+involves%3Ajnywong+updated%3A2026-04-13..2026-05-13&type=Issues)) | @sunu ([activity](https://github.com/search?q=repo%3A2i2c-org%2Fjupyterhub-usage-quotas+involves%3Asunu+updated%3A2026-04-13..2026-05-13&type=Issues))

## v0.1.0 2026-04-13

([full changelog](https://github.com/2i2c-org/jupyterhub-usage-quotas/compare/v0.0.3...a5cd1a4d37e5eaa054b6c9a3a61ce14dbcb30a48))

### Enhancements made

- feat: add failover logic [#31](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/31) ([@jnywong](https://github.com/jnywong))
- feat: custom 422 error page [#28](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/28) ([@jnywong](https://github.com/jnywong))
- Integrate usage quota viewer service [#27](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/27) ([@sunu](https://github.com/sunu), [@jnywong](https://github.com/jnywong))
- feat: calculate retry time when a user can relaunch their server after exceeding quota limit [#25](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/25) ([@jnywong](https://github.com/jnywong))

### Bugs fixed

- fix: link [#24](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/24) ([@jnywong](https://github.com/jnywong))
- fix: link [#23](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/23) ([@jnywong](https://github.com/jnywong))

### Documentation

- doc: add demo [#22](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/22) ([@jnywong](https://github.com/jnywong))
- docs: add explanation and basic tutorial on user group management [#21](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/21) ([@jnywong](https://github.com/jnywong))

### Contributors to this release

The following people contributed discussions, new ideas, code and documentation contributions, and review.
See [our definition of contributors](https://github-activity.readthedocs.io/en/latest/use/#how-does-this-tool-define-contributions-in-the-reports).

([GitHub contributors page for this release](https://github.com/2i2c-org/jupyterhub-usage-quotas/graphs/contributors?from=2026-03-13&to=2026-04-13&type=c))

@jnywong ([activity](https://github.com/search?q=repo%3A2i2c-org%2Fjupyterhub-usage-quotas+involves%3Ajnywong+updated%3A2026-03-13..2026-04-13&type=Issues)) | @sunu ([activity](https://github.com/search?q=repo%3A2i2c-org%2Fjupyterhub-usage-quotas+involves%3Asunu+updated%3A2026-03-13..2026-04-13&type=Issues))

## v0.0.3 2026-03-12

([full changelog](https://github.com/2i2c-org/jupyterhub-usage-quotas/compare/v0.0.2...2b471bb8c5cb2e46a2749ee9a84b6cea7ade3974))

### Enhancements made

- feat: test suite for policy resolver [#11](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/11) ([@jnywong](https://github.com/jnywong))
- feat: add grouping over all policy keys [#10](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/10) ([@jnywong](https://github.com/jnywong))
- feat: add policy resolver [#8](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/8) ([@jnywong](https://github.com/jnywong))
- feat: aggregate usage from prometheus [#14](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/14) ([@jnywong](https://github.com/jnywong))

### Bugs fixed

- refactor: move prometheus client [#15](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/15) ([@jnywong](https://github.com/jnywong))
- patch: pass api token to usage-quotas service [#12](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/12) ([@jnywong](https://github.com/jnywong))

### Maintenance and upkeep improvements

- refactor: use spawner object instead of hub api [#13](https://github.com/2i2c-org/jupyterhub-usage-quotas/pull/13) ([@jnywong](https://github.com/jnywong))

### Contributors to this release

The following people contributed discussions, new ideas, code and documentation contributions, and review.
See [our definition of contributors](https://github-activity.readthedocs.io/en/latest/use/#how-does-this-tool-define-contributions-in-the-reports).

([GitHub contributors page for this release](https://github.com/2i2c-org/jupyterhub-usage-quotas/graphs/contributors?from=2026-03-02&to=2026-03-12&type=c))

@jnywong ([activity](https://github.com/search?q=repo%3A2i2c-org%2Fjupyterhub-usage-quotas+involves%3Ajnywong+updated%3A2026-03-02..2026-03-12&type=Issues))

## v0.0.1 and v0.0.2 2026-03-02

- initialise project
