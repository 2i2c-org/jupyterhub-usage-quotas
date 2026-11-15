# Helm chart

(helm-chart-reference)=

The `jupyterhub-usage-quotas` Helm chart installs the usage viewer service next
to a Zero to JupyterHub deployment. See [Install the usage viewer
chart](../howto/quickstart.md#install-the-usage-viewer-chart).

The contents of this file were generated from the chart's `values.schema.yaml`
and `values.yaml` files using the helper script
`scripts/update_configuration_reference.py`.

## `enabled`

- Type: boolean

Configuration flag for charts that depend on this chart, to toggle the
installation of this chart.

## `nameOverride`

- Type: string | null

See the z2jh documentation for
[`fullnameOverride`](https://z2jh.jupyter.org/en/stable/resources/reference.html#fullnameoverride).

## `fullnameOverride`

- Type: string | null

Adjusts the names of the chart resources. If `""` (the default), the
resources are named after the component, e.g. `usage-viewer`. If `null`,
the names start with the release name. Do not change this value after
the first installation.

See the z2jh documentation for
[`fullnameOverride`](https://z2jh.jupyter.org/en/stable/resources/reference.html#fullnameoverride).

## `global`

- Type: object

## `config`

- Type: object

Configuration for the service traitlets. It is stored in a Secret, so it
can contain credentials such as `prometheus_auth`.

```yaml
config:
  UsageViewer:
    public_hub_url: https://hub.example.org/
    prometheus_url: http://prometheus-server.support.svc.cluster.local
    enable_compute: true
```

### `config.UsageViewer`

- Type: object

See the [UsageViewer reference](https://jupyterhub-usage-quotas.readthedocs.io/en/latest/reference/usageviewer/).

The chart also reads these options:

- `public_hub_url` (required): the public URL of JupyterHub, e.g.
  `https://hub.example.org/`.
- `service_name`: the key under the z2jh `hub.services` config. The
  default is `usage-quota`.
- `hub_api_token`: if set, the chart does not read the token from
  `hubApiToken.existingSecret`.

## `hubApiToken`

- Type: object

The API token that the service uses for Hub API requests, if
`config.UsageViewer.hub_api_token` is not set.

### `hubApiToken.existingSecret`

- Type: object

A Secret that contains the token. By default, this is the token
that z2jh makes for the `hub.services.<service_name>` entry. The
Secret must be in the same namespace as this chart.

#### `hubApiToken.existingSecret.name`

- Type: string
- Default: `"hub"`

#### `hubApiToken.existingSecret.key`

- Type: string

If empty, the key is `hub.services.<service_name>.apiToken`.

## `sessionSecretKey`

- Type: string

The key that signs the session cookies. If empty, a random key is
generated on install and kept on upgrade.

## `replicas`

- Type: integer
- Default: `1`

## `image`

- Type: object

### `image.repository`

- Type: string
- Default: `"ghcr.io/2i2c-org/jupyterhub-usage-quotas"`

### `image.tag`

- Type: string
- Default: `"set-by-chartpress"`

### `image.pullPolicy`

- Type: `null` | `""` | `"IfNotPresent"` | `"Always"` | `"Never"`

### `image.pullSecrets`

- Type: array

## `extraEnv`

- Type: array

More environment variables for the container, in the Kubernetes
`EnvVar` format. The values are rendered with `tpl`.

## `extraVolumes`

- Type: array

## `extraVolumeMounts`

- Type: array

## `resources`

- Type: object

## `securityContext`

- Type: object

- Default:

  ```yaml
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
  readOnlyRootFilesystem: true
  runAsGroup: 65534
  runAsNonRoot: true
  runAsUser: 65534
  ```

## `podSecurityContext`

- Type: object

## `podAnnotations`

- Type: object

## `nodeSelector`

- Type: object

## `affinity`

- Type: object

## `tolerations`

- Type: array

## `serviceAccount`

- Type: object

### `serviceAccount.create`

- Type: boolean
- Default: `true`

### `serviceAccount.name`

- Type: string

### `serviceAccount.annotations`

- Type: object

## `service`

- Type: object

### `service.type`

- Type: string
- Default: `"ClusterIP"`

### `service.port`

- Type: integer
- Default: `9000`

### `service.annotations`

- Type: object

## `networkPolicy`

- Type: object

### `networkPolicy.enabled`

- Type: boolean
- Default: `true`

### `networkPolicy.ingress`

- Type: array

More ingress rules, in the Kubernetes `NetworkPolicyIngressRule`
format.
