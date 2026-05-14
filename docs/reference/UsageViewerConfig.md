# UsageViewerConfig

(config-usage-viewer)=

```
UsageViewerConfig(UsageConfig) options
--------------------------------------
--UsageViewerConfig.config_file=<Unicode>
    Path to the config file to load. If not set, no config file is loaded.
    Default: ''
--UsageViewerConfig.dev_mode=<Bool>
    Enable development mode with mock data.
    When True, the service returns mock storage usage data instead of querying
    Prometheus. This is useful for local development without a real Prometheus
    instance.
    Mock data is only used when ALL three conditions are met: - dev_mode is
    True, AND - prometheus_url is the default (http://127.0.0.1:9090), AND -
    hub_namespace is empty
    If either prometheus_url or hub_namespace is configured, the service will
    query Prometheus even when dev_mode is True.
    Default: False (production mode - always query Prometheus)
    Default: False
--UsageViewerConfig.enable_component=<key-1>=<value-1>...
    Enable home storage and/or compute components on the usage quotas dashboard
    Default: {'home_storage': False, 'compute': False}
--UsageViewerConfig.escape_username_scheme=<key-1>=<value-1>...
    Kubespawner slug scheme for naming directories and pod names with escaped usernames. E.g
        - modern safe slugs for k8s pods and legacy slug for directory names (default): {"directory": "legacy", pod": "safe", max_length: 48},
    Default: {}
--UsageViewerConfig.hub_namespace=<Unicode>
    Kubernetes namespace of the JupyterHub deployment, used to filter Prometheus
    usage metrics in multi-tenant environments. Leave empty for single-tenant or
    development. Can be set via JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE
    environment variable.
    Default: ''
--UsageViewerConfig.log_datefmt=<Unicode>
    The date format used by logging formatters for %(asctime)s
    Default: '%Y-%m-%d %H:%M:%S'
--UsageViewerConfig.log_format=<Unicode>
    The Logging format template
    Default: '[%(name)s]%(highlevel)s %(message)s'
--UsageViewerConfig.log_level=<Enum>
    Set the log level by value or name.
    Choices: any of [0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL']
    Default: 30
--UsageViewerConfig.logging_config=<key-1>=<value-1>...
    Configure additional log handlers.
    The default stderr logs handler is configured by the log_level, log_datefmt
    and log_format settings.
    This configuration can be used to configure additional handlers (e.g. to
    output the log to a file) or for finer control over the default handlers.
    If provided this should be a logging configuration dictionary, for more
    information see:
    https://docs.python.org/3/library/logging.config.html#logging-config-
    dictschema
    This dictionary is merged with the base logging configuration which defines
    the following:
    * A logging formatter intended for interactive use called
      ``console``.
    * A logging handler that writes to stderr called
      ``console`` which uses the formatter ``console``.
    * A logger with the name of this application set to ``DEBUG``
      level.
    This example adds a new handler that writes to a file:
    .. code-block:: python
       c.Application.logging_config = {
           "handlers": {
               "file": {
                   "class": "logging.FileHandler",
                   "level": "DEBUG",
                   "filename": "<path/to/file>",
               }
           },
           "loggers": {
               "<application-name>": {
                   "level": "DEBUG",
                   # NOTE: if you don't list the default "console"
                   # handler here then it will be disabled
                   "handlers": ["console", "file"],
               },
           },
       }
    Default: {}
--UsageViewerConfig.prometheus_auth=<key-1>=<value-1>...
    Username and password credentials for authenticating with Prometheus.
    Can be set via JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME and
    JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD environment variables.
    For example:
        c.UsageConfig.prometheus_auth = {
            "username": "username",
            "password": "password",
        }
    Default: {}
--UsageViewerConfig.prometheus_url=<Unicode>
    The url of the Prometheus server, usually of the form 'http://<k8s-service-
    name>.<k8s-namespace>.svc.cluster.local' in a Kubernetes cluster. Defaults
    to 'http://127.0.0.1:9090' for local development.
    Default: 'http://127.0.0.1:9090'
--UsageViewerConfig.prometheus_usage_quota_metrics=<key-1>=<value-1>...
    Prometheus metrics for querying storage and/or compute usage and quotas.
    Defaults to:
    c.UsageViewerConfig.prometheus_usage_quota_metrics = {
        "home_storage": {
            "usage": "dirsize_total_size_bytes",
            "quota": "dirsize_hard_limit_bytes"
        },
        "compute": {
            "usage": "jupyterhub_memory_usage_gibibyte_hours",
            "quota": "jupyterhub_memory_limit_gibibyte_hours"
        }
    }
    Default: {'home_storage': {'usage': 'dirsize_total_size_bytes', 'quota...
--UsageViewerConfig.public_hub_url=<Unicode>
    Public URL of the JupyterHub instance. Required. Automatically set by
    JupyterHub via JUPYTERHUB_PUBLIC_HUB_URL environment variable.
    Default: ''
--UsageViewerConfig.service_host=<Unicode>
    Host to bind the usage viewer service to
    Default: '0.0.0.0'
--UsageViewerConfig.service_port=<Int>
    Port to bind the usage viewer service to
    Default: 9000
--UsageViewerConfig.service_prefix=<Unicode>
    URL prefix for the service. Automatically set by JupyterHub when running as
    a managed service. Defaults to /services/usage-quota.
    Default: ''
--UsageViewerConfig.session_secret_key=<Unicode>
    Secret key for session cookie encryption. Required for secure sessions. Set
    via config or JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY environment
    variable.
    Default: ''
--UsageViewerConfig.show_config=<Bool>
    Instead of starting the Application, dump configuration to stdout
    Default: False
--UsageViewerConfig.show_config_json=<Bool>
    Instead of starting the Application, dump configuration to stdout (as JSON)
    Default: False
```
