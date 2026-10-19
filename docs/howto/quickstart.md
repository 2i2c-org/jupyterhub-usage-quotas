# Getting Started

## Who this guide is for

🧑‍💻 Are you a JupyterHub user who wants a quick tour of the usage quota system? See the quickstart guide for [Users](#users).

🔧 Are you a JupyterHub admin who wants to quickly understand how to deploy the usage quota system? See the quickstart guide for [Admins](#admins).

(users)=

## Users

### Background

Usage quotas are an effective safeguard against excessive resource consumption and spiralling costs, especially in a cloud computing environment. They can be applied to resources such as:

- {term}`home storage`
- {term}`compute`

### Usage Quota Dashboard

You can view any usage quotas applied to your account with the [Usage Quota Dashboard](./usage-quota-dashboard.md).

```{embed} #dashboard
```

### Home storage

```{embed} #home-storage-expire
```

### Compute

```{embed} #compute-expire
```

```{embed} #server-launch-deny
```

(admins)=

## Admins

### Prerequisites

This quickstart guide assumes that the reader is running a [Zero to JupyterHub](https://z2jh.jupyter.org/en/stable/) deployment with a [Prometheus](https://prometheus.io/) instance scraping metrics from[`kube-state-metrics`](https://kubernetes.io/docs/concepts/cluster-administration/kube-state-metrics/) and optionally [`jupyterhub-home-nfs`](https://github.com/2i2c-org/jupyterhub-home-nfs) for home storage quotas (see [Explanation - Overview](../explanation/overview.md)), and has some knowledge of

- [Kubernetes](https://kubernetes.io/)
- [Helm](https://helm.sh/)
- Building images

### Components

The `jupyterhub-usage-quotas` system has two components:

1. The *manager*. It enforces compute quotas when a user starts a server. It runs in the hub process, so we must install it in the hub image.
1. The *usage viewer* service. It shows the [usage quota dashboard](./usage-quota-dashboard.md) to users. It runs as an [external JupyterHub service](../explanation/service.md) in its own pod. We install it with the `jupyterhub-usage-quotas` Helm chart.

### Install the manager in the hub image

1. Create a custom hub image with [jupyterhub-usage-quotas](https://github.com/2i2c-org/jupyterhub-usage-quotas) installed. See [Services — Zero to JupyterHub with Kubernetes documentation](https://z2jh.jupyter.org/en/stable/administrator/services.html#example-service) for details on how to do this.

   - Make sure we list all of the dependencies we require for the hub image, e.g. in a `requirements.txt` file
   - See the example below

   ````{tip} Example
   ```{code} bash
   # requirements.txt

   jupyterhub-usage-quotas ~= 0.2.0
   other-hub-dependencies <= 1.0.0
   ```
   ```{code} dockerfile
   # Dockerfile

   FROM jupyterhub/k8s-hub:<tag>
   USER root
   COPY ./requirements.txt /tmp/
   RUN python3 -m pip install -r /tmp/requirements.txt
   USER ${NB_USER}
   ```
   ````

1. Build and push the custom hub image to a registry and make a note of the image tag.

### Configure z2jh

#### Authentication

Usage quota policies are applied to user groups, therefore this information needs to be available in a user's [`auth_state`](https://jupyterhub.readthedocs.io/en/stable/reference/authenticators.html#authentication-state). This minimal working example assumes a z2jh deployment that uses [OAuthenticator](https://oauthenticator.readthedocs.io/en/latest/) to handle authentication, specifically the [Generic OAuthenticator](https://oauthenticator.readthedocs.io/en/latest/tutorials/provider-specific-setup/providers/generic.html). Make sure that we set the appropriate configuration for our authenticator in addition to the minimal example below. See [User Group Management](./user-group-management.md) for more details.

#### Home Storage Quotas

If we are using home storage quotas, then make sure that we set the appropriate configuration for [jupyterhub-home-nfs](https://github.com/2i2c-org/jupyterhub-home-nfs) in addition to the minimal example below.

#### Set up the manager

Add this to `hub.extraConfig`. It sets up the manager, and adds the templates of the usage quota system to the hub templates.

```yaml
hub:
  extraConfig:
    01-setup-usage-quotas: |
      from jupyterhub_usage_quotas import setup_usage_quotas, get_template_path
      setup_usage_quotas(c)
      c.JupyterHub.template_paths.insert(0, get_template_path())
```

The manager needs these settings:

- `c.UsageQuotaManager.prometheus_url`: the URL of the Prometheus server that has the usage data
- `c.UsageQuotaManager.hub_namespace`: the Kubernetes namespace of the hub pod
- `c.UsageQuotaManager.metrics_exporter_token`: the API token of the `metrics-exporter` service. z2jh makes this token. The examples below give it to the hub in the `JUPYTERHUB_USAGE_QUOTAS_METRICS_TOKEN` environment variable.

#### Register the usage viewer service

Add the usage viewer to `hub.services`, and give the service and the users the necessary scopes with `hub.loadRoles`. z2jh makes the API token of the service, and the Helm chart reads it from the `hub` Secret.

```yaml
hub:
  services:
    usage-quota:
      url: http://usage-viewer:9000
      display: true
      oauth_no_confirm: true
  loadRoles:
    usage-quota-service:
      scopes:
        - read:users
        - list:services
        - read:services
      services:
        - usage-quota
    user:
      scopes:
        - self
        - access:services!service=usage-quota
```

```{note}
The `user` role replaces the default user role of JupyterHub. If our configuration already has a `user` role, add the `access:services!service=usage-quota` scope to it.
```

The service URL is `http://<service name>:<port>`. With the default chart values, the name is `usage-viewer` and the port is `9000`. After we install the chart, its notes show the correct URL.

#### Minimal z2jh example

```{code} yaml
---
label: minimal-z2jh-config
---
# config.yaml

hub:
  image:
    name: myregistry/my-custom-hub-image
    tag: <image-tag>
  config:
    JupyterHub:
      authenticator_class: generic-oauth
    GenericOAuthenticator:
      allowed_scopes:
        - group-0
      auth_state_groups_key: scope
      enable_auth_state: true
      manage_groups: true
      scope:
        - group-0
    UsageQuotaManager:
      prometheus_url: http://<prometheus-service-name>.<k8s-prometheus-namespace>.svc.cluster.local
      hub_namespace: <k8s-hub-namespace>
      scope_fallback_strategy:
        intersection: min
      policy:
        - resource: memory
          limit: '1000G'
          window: 7
          scope:
            group:
              - group-0
      failover_open: false
  extraConfig:
    01-setup-usage-quotas: |
      from jupyterhub_usage_quotas import setup_usage_quotas, get_template_path
      setup_usage_quotas(c)
      c.JupyterHub.template_paths.insert(0, get_template_path())
  extraEnv:
    JUPYTERHUB_USAGE_QUOTAS_METRICS_TOKEN:
      valueFrom:
        secretKeyRef:
          name: hub
          key: hub.services.metrics-exporter.apiToken
  services:
    usage-quota:
      url: http://usage-viewer:9000
      display: true
      oauth_no_confirm: true
    metrics-exporter:
      display: false
  loadRoles:
    usage-quota-service:
      scopes:
        - read:users
        - list:services
        - read:services
      services:
        - usage-quota
    user:
      scopes:
        - self
        - access:services!service=usage-quota
    metrics-exporter-service:
      scopes:
        - users
      services:
        - metrics-exporter
```

```{code} yaml
---
label: enc-minimal-z2jh-config
---
# enc-config.yaml
# Note: this contains secrets so make sure we encrypt this file if using a version control system

hub:
  config:
    UsageQuotaManager:
      prometheus_auth:
        username: <prometheus_username>
        password: <prometheus_password>
```

```{tip}
Make sure we encrypt any secrets files if using a version control system, using a tool such as [SOPS](https://getsops.io/).
```

### Install the usage viewer chart

Install the `jupyterhub-usage-quotas` Helm chart in the same Kubernetes namespace as z2jh. The chart reads the API token of the service from the `hub` Secret of z2jh.

```{code} yaml
---
label: minimal-usage-quotas-values
---
# usage-quotas-values.yaml

jupyterhub:
  # The public URL of our JupyterHub
  publicUrl: https://<public-hub-url>/

config:
  UsageViewer:
    prometheus_url: http://<prometheus-service-name>.<k8s-prometheus-namespace>.svc.cluster.local
```

```{code} yaml
---
label: enc-minimal-usage-quotas-values
---
# enc-usage-quotas-values.yaml
# Note: this contains secrets so make sure we encrypt this file if using a version control system

config:
  UsageViewer:
    prometheus_auth:
      username: <prometheus_username>
      password: <prometheus_password>
```

```bash
helm upgrade --install usage-quotas \
  oci://ghcr.io/2i2c-org/jupyterhub-usage-quotas/jupyterhub-usage-quotas \
  --version <chart-version> \
  --namespace <k8s-hub-namespace> \
  --values usage-quotas-values.yaml \
  --values enc-usage-quotas-values.yaml
```

The chart does these things:

- It sets the hub namespace of the usage viewer to the namespace of the release.
- It makes a session secret key, and keeps it when we upgrade the chart.
- It adds a NetworkPolicy that lets the z2jh proxy and hub pods access the service.

Install or upgrade z2jh with the configuration from the previous section. Then go to `https://<public-hub-url>/hub/home` and click **Services > usage-quota** in the navbar.

See [Configuration](../reference/configuration.md) for a full list of the `UsageQuotaManager` and `UsageViewer` options. We set the `UsageViewer` options in `config.UsageViewer` in the chart values. See [Helm chart](../reference/helm-chart.md) for all the chart values.

### Multi-cluster setups

If we operate multiple clusters and want to deploy `jupyterhub-usage-quotas`, we may want to programmatically pass config to each cluster. We recommend following the [Multi-cluster setups](./deploy.md#multi-cluster-setups) guide to take advantage of jsonnet and mirroring secrets across namespaces.
