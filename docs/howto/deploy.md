# Deployment guide

## Deployment

### Single-cluster setups

See the [Admins](#admins) section in the [Getting Started](./quickstart.md) page for a quick-start guide to deploying `jupyterhub-usage-quotas` in a [Zero to JupyterHub](https://z2jh.jupyter.org/en/stable/) context for a single cluster.

### Multi-cluster setups

In the case where you are managing multiple Kubernetes clusters, we recommend the following strategy for programmatically setting configuration for the `jupyterhub-usage-quotas` system.

```{tip} Example
For an example of rolling out the usage quota system for a multi-cluster setup, see https://github.com/2i2c-org/infrastructure/pull/8897.
```

#### Jsonnet for common configuration

For required but repetitive configuration, e.g.

```{code} yaml
---
filename: values.yaml
---
hub:
  config:
    UsageQuotaManager:
      hub_namespace: <hub_name>
```

you can generate common config and inject external variables with [Jsonnet](https://jsonnet.org/). The above config becomes

```{code} javascript
---
filename: values.jsonnet
---
local hub_name = std.extVar('VARS_HUB_NAME');
local jupyterhubUsageQuotasHubConfig = {
  config: {
    UsageQuotaManager: {
      hub_namespace: '%s' % hub_name,
    },
  },
};

emitConfig(
  {
    hub: jupyterhubUsageQuotasHubConfig,
  }
)
```

You can programmatically render the jsonnet as yaml with `jsonnet --ext-str VARS_HUB_NAME=<hub_name>` and then pass the output into the `helm upgrade --values` flag.

#### Kubernetes configuration maps

Normally, we can configure application settings with Helm chart values, e.g.

```{code} yaml
---
filename: values.yaml
---
hub:
  config:
    UsageViewer:
      enable_compute: true
```

However, the `UsageViewer` is a [hub-managed service](https://jupyterhub.readthedocs.io/en/stable/reference/services.html#hub-managed-services) that is a child process of the hub process. For a single-cluster setup we can pass configuration to the `UsageViewer` service at runtime via a k8s-mounted configuration file. For a multi-cluster setup, we can instead dynamically populate the contents of the configuration file rather than hard-coding the file contents for each cluster.

With a [k8s ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) and helper template partials, we can pass `UsageViewer` config defined in a `values.yaml` file into a configuration file `jupyterhub_usage_quotas_config.py` mounted to the path `/usr/local/etc/jupyterhub/jupyterhub_config.d/jupyterhub_usage_quotas_config.py`.

```{code} yaml
---
filename: templates/configmap-usage-quotas.yaml
---
kind: ConfigMap
apiVersion: v1
metadata:
  name: usage-quotas-config
  labels:
    app: jupyterhub
data:
  jupyterhub_usage_quotas_config.py: |
    {{- range $name, $value := .Values.jupyterhub.hub.config.UsageViewer }}
    {{- if ne $value nil }}
    c.UsageViewer.{{ $name }} = {{ include "python.literal" $value }}
    {{- end }}
    {{- end }}
```

```{code} javascript
---
filename: templates/_helpers.tpl
---
# Helper template partials

# Converts helm values to python literals
{{- define "python.literal" -}}
{{- if kindIs "bool" . -}}
{{ ternary "True" "False" . }}
{{- else if kindIs "string" . -}}
{{ printf "%q" . }}
{{- else -}}
{{ . }}
{{- end -}}
{{- end -}}
```

```{code} yaml
---
filename: values.yaml
---
hub:
  extraVolumeMounts:
    - mountPath: /usr/local/etc/jupyterhub/jupyterhub_config.d/jupyterhub_usage_quotas_config.py
      name: usage-quotas
      subPath: jupyterhub_usage_quotas_config.py
```

```{warning}
Defining `jupyterhub_usage_quotas_config.py` with both `extraFiles` and `extraVolumeMounts` will lead to a conflict. Move all required config from `extraFiles` into a ConfigMap and use only `extraVolumeMounts` instead.
```

#### Secrets management

The `jupyterhub-usage-quotas` application relies on Prometheus for both quota enforcement at server-launch-time and the usage quota dashboard at service run-tume. In a multi-cluster setup, the secrets for Prometheus authorisation may need to be passed between multiple k8s namespaces.

We can mirror secrets between k8s namespaces with a reflector using [emberstack](https://github.com/emberstack/kubernetes-reflector) and pass them to the application with environment variables using `extraEnv`.

```{code} yaml
---
filename: support/Chart.yaml
---
apiVersion: v2
name: support
version: "0.1.0"
description: Cluster wide support dependencies for all hubs
dependencies:
  - name: reflector
    version: "10.0.61"
    repository: oci://ghcr.io/emberstack/helm-charts
```

```{code} yaml
---
filename: templates/mirrored-prometheus-creds.yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: prometheus-auth
  annotations:
    reflector.v1.k8s.emberstack.com/reflects: "support/prometheus-auth"
```

```{code} yaml
---
filename: templates/prometheus-auth/secret.yaml
---
{{- if .Values.prometheusAuthSecret.enabled -}}
apiVersion: v1
kind: Secret
metadata:
  name: prometheus-auth
  annotations:
   reflector.v1.k8s.emberstack.com/reflection-allowed: "true"
type: Opaque
stringData:
  username: {{ .Values.prometheusAuthSecret.username }}
  password: {{ .Values.prometheusAuthSecret.password }}
{{- end }}
```

```{code} yaml
---
filename: enc-support.secret.values.yaml
---
prometheusAuthSecret:
  username: <encrypted-username>
  password: <encrypted-password>
```

```{code} yaml
---
filename: values.yaml
---
hub:
  extraEnv:
    JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME:
      valueFrom:
        secretKeyRef:
          name: prometheus-auth
          key: username
          optional: false
    JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD:
      valueFrom:
        secretKeyRef:
          name: prometheus-auth
          key: password
          optional: false
    # We can also pass the metrics exporter token with an env var
    JUPYTERHUB_USAGE_QUOTAS_METRICS_TOKEN:
      valueFrom:
        secretKeyRef:
          name: hub
          key: hub.services.metrics-exporter.apiToken
          optional: false
```

```{tip}
Remember to encrypt secrets with a tool such as [sops](https://github.com/getsops/sops).
```

## Monitoring and Alerting

The [Usage Quota Dashboard](./usage-quota-dashboard.md) makes use of Prometheus metrics exported by the usage quota system. You can use the same metrics to configure your own monitoring and alerting systems to detect events such as:

- Cumulative compute usage

  ```sql
  # PromQL
  max(jupyterhub_memory_usage_gibibyte_hours{namespace=~"$hub"}) by (namespace, username, policy_group, window)
  ```

- Number of fail opens

  ```sql
  # PromQL
  sum by (namespace) (changes(jupyterhub_usage_quotas_fail_open_total[30m]))
  ```

- Denied server launches over the last 30 minutes

  ```sql
  # PromQL
  changes((max by (namespace) (jupyterhub_request_duration_seconds_count{code="422",handler="jupyterhub.handlers.pages.SpawnPendingHandler"} or 0 * jupyterhub_request_duration_seconds_count))[30m:1m])
  ```

### Grafana dashboards

In the `dashboards/` folder of this repository, there is a jsonnet file that defines a basic Grafana dashboard for the usage quotas system for you to use. See the `README.md` file in the same folder for how to deploy.

See [Grafana Dashboard](./grafana-dashboard.md) for an overview of the Grafana Dashboard layout.

## Tips

- The `jupyterhub-usage-quotas` library is installed within the hub image, so make sure that you give enough memory and compute [requests and limits](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) for the kubernetes pod to work
  - You may have to fine-tune this over time, since the memory used by the usage quota system scales weakly with the number of hub users
