# UsageViewer

(usageviewer-config)=

```
# Configuration file for jupyterhub-usage-viewer.

c = get_config()  #noqa

#------------------------------------------------------------------------------
# Application(SingletonConfigurable) configuration
#------------------------------------------------------------------------------
## This is an application.

## The date format used by logging formatters for %(asctime)s
#  Default: '%Y-%m-%d %H:%M:%S'
# c.Application.log_datefmt = '%Y-%m-%d %H:%M:%S'

## The Logging format template
#  Default: '[%(name)s]%(highlevel)s %(message)s'
# c.Application.log_format = '[%(name)s]%(highlevel)s %(message)s'

## Set the log level by value or name.
#  Choices: any of [0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL']
#  Default: 30
# c.Application.log_level = 30

## Configure additional log handlers.
#
#  The default stderr logs handler is configured by the log_level, log_datefmt
#  and log_format settings.
#
#  This configuration can be used to configure additional handlers (e.g. to
#  output the log to a file) or for finer control over the default handlers.
#
#  If provided this should be a logging configuration dictionary, for more
#  information see:
#  https://docs.python.org/3/library/logging.config.html#logging-config-
#  dictschema
#
#  This dictionary is merged with the base logging configuration which defines
#  the following:
#
#  * A logging formatter intended for interactive use called
#    ``console``.
#  * A logging handler that writes to stderr called
#    ``console`` which uses the formatter ``console``.
#  * A logger with the name of this application set to ``DEBUG``
#    level.
#
#  This example adds a new handler that writes to a file:
#
#  .. code-block:: python
#
#     c.Application.logging_config = {
#         "handlers": {
#             "file": {
#                 "class": "logging.FileHandler",
#                 "level": "DEBUG",
#                 "filename": "<path/to/file>",
#             }
#         },
#         "loggers": {
#             "<application-name>": {
#                 "level": "DEBUG",
#                 # NOTE: if you don't list the default "console"
#                 # handler here then it will be disabled
#                 "handlers": ["console", "file"],
#             },
#         },
#     }
#  Default: {}
# c.Application.logging_config = {}

## Instead of starting the Application, dump configuration to stdout
#  Default: False
# c.Application.show_config = False

## Instead of starting the Application, dump configuration to stdout (as JSON)
#  Default: False
# c.Application.show_config_json = False

#------------------------------------------------------------------------------
# UsageViewer(Application) configuration
#------------------------------------------------------------------------------
## Application for running the usage quota viewer service.

## List of config files to load. If not set, then no config file is loaded.
#  Default: []
# c.UsageViewer.config_files = []

## Enable development mode with mock data.
#
#  When True, the service returns mock storage usage data instead of querying
#  Prometheus. This is useful for local development without a real Prometheus
#  instance.
#
#  Mock data is only used when ALL three conditions are met: - dev_mode is True,
#  AND - prometheus_url is the default (http://127.0.0.1:9090), AND -
#  hub_namespace is empty
#
#  If either prometheus_url or hub_namespace is configured, the service will
#  query Prometheus even when dev_mode is True.
#
#  Default: False (production mode - always query Prometheus)
#  Default: False
# c.UsageViewer.dev_mode = False

## Enable compute component on the usage quotas dashboard
#  Default: True
# c.UsageViewer.enable_compute = True

## Enable home storage component on the usage quotas dashboard
#  Default: True
# c.UsageViewer.enable_home_storage = True

## Kubespawner slug scheme for naming directories and pod names with escaped usernames. E.g
#      - modern safe slugs for k8s pods and legacy slug for directory names (default): {"directory": "legacy", pod": "safe", max_length: 48},
#  Default: {}
# c.UsageViewer.escape_username_scheme = {}

## HTML content shown in the footer of the usage dashboard page. Set to empty
#  string to hide the footer.
#  Default: 'Contact your JupyterHub Admin if you need additional quota.'
# c.UsageViewer.footer_note = 'Contact your JupyterHub Admin if you need additional quota.'

## Kubernetes namespace of the JupyterHub deployment, used to filter Prometheus
#  usage metrics in multi-tenant environments. Leave empty for single-tenant or
#  development. Can be set via JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE environment
#  variable.
#  Default: ''
# c.UsageViewer.hub_namespace = ''

## List of additional paths to search for JupyterHub templates, in order of
#  preference. The default JupyterHub templates path is always appended so custom
#  paths take precedence while falling back to JupyterHub's default templates.
#  Default: []
# c.UsageViewer.hub_template_paths = []

## JupyterHub URL, e.g. http://localhost:8000 for local development.
#  Default: ''
# c.UsageViewer.hub_url = ''

## The date format used by logging formatters for %(asctime)s
#  See also: Application.log_datefmt
# c.UsageViewer.log_datefmt = '%Y-%m-%d %H:%M:%S'

## The Logging format template
#  See also: Application.log_format
# c.UsageViewer.log_format = '[%(name)s]%(highlevel)s %(message)s'

## Set the log level by value or name.
#  See also: Application.log_level
# c.UsageViewer.log_level = 30

##
#  See also: Application.logging_config
# c.UsageViewer.logging_config = {}

## Username and password credentials for authenticating with Prometheus.
#  Can be set via JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME and
#  JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD environment variables.
#  For example:
#      c.UsageConfig.prometheus_auth = {
#          "username": "username",
#          "password": "password",
#      }
#  Default: {}
# c.UsageViewer.prometheus_auth = {}

## The url of the Prometheus server, usually of the form 'http://<k8s-service-
#  name>.<k8s-namespace>.svc.cluster.local' in a Kubernetes cluster. Defaults to
#  'http://127.0.0.1:9090' for local development.
#  Default: 'http://127.0.0.1:9090'
# c.UsageViewer.prometheus_url = 'http://127.0.0.1:9090'

## Prometheus metrics for querying storage and/or compute usage and quotas.
#  Defaults to:
#
#  c.UsageViewerConfig.prometheus_usage_quota_metrics = {
#      "home_storage": {
#          "usage": "dirsize_total_size_bytes",
#          "quota": "dirsize_hard_limit_bytes"
#      },
#      "compute": {
#          "usage": "jupyterhub_memory_usage_gibibyte_hours",
#          "quota": "jupyterhub_memory_limit_gibibyte_hours"
#      }
#  }
#  Default: {'home_storage': {'usage': 'dirsize_total_size_bytes', 'quota': 'dirsize_hard_limit_bytes'}, 'compute': {'usage': 'jupyterhub_memory_usage_gibibyte_hours', 'quota': 'jupyterhub_memory_limit_gibibyte_hours'}}
# c.UsageViewer.prometheus_usage_quota_metrics = {'home_storage': {'usage': 'dirsize_total_size_bytes', 'quota': 'dirsize_hard_limit_bytes'}, 'compute': {'usage': 'jupyterhub_memory_usage_gibibyte_hours', 'quota': 'jupyterhub_memory_limit_gibibyte_hours'}}

## Public URL of the JupyterHub instance. Required. Automatically set by
#  JupyterHub via JUPYTERHUB_PUBLIC_HUB_URL environment variable.
#  Default: ''
# c.UsageViewer.public_hub_url = ''

## Host to bind the usage viewer service to
#  Default: '0.0.0.0'
# c.UsageViewer.service_host = '0.0.0.0'

## Port to bind the usage viewer service to
#  Default: 9000
# c.UsageViewer.service_port = 9000

## URL prefix for the service. Automatically set by JupyterHub when running as a
#  managed service. Defaults to /services/usage-quota.
#  Default: ''
# c.UsageViewer.service_prefix = ''

## Secret key for session cookie encryption. Required for secure sessions. Set
#  via config or JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY environment variable.
#  Default: ''
# c.UsageViewer.session_secret_key = ''

## Instead of starting the Application, dump configuration to stdout
#  See also: Application.show_config
# c.UsageViewer.show_config = False

## Instead of starting the Application, dump configuration to stdout (as JSON)
#  See also: Application.show_config_json
# c.UsageViewer.show_config_json = False
```
