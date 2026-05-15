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

You can view any usage quotas applied to your account with the [Usage Quota Dashboard](../tutorial/usage-quota-dashboard.md).

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

This quickstart guide assumes that the reader is running a [Zero to JupyterHub](https://z2jh.jupyter.org/en/stable/) deployment and has some knowledge of

- [Kubernetes](https://kubernetes.io/)
- [Helm](https://helm.sh/)
- Building images

### Installing JupyterHub with `jupyterhub-usage-quotas`

1. Create custom Hub image with [jupyterhub-usage-quotas](https://github.com/2i2c-org/jupyterhub-usage-quotas) installed. See [Services — Zero to JupyterHub with Kubernetes documentation](https://z2jh.jupyter.org/en/stable/administrator/services.html#example-service) for details on how to do this.

   - Make sure you list all of the dependencies you require for the Hub image, e.g. in a `requirements.txt` file
   - You can install the package with `jupyterhub-usage-quotas` or you can optionally install the package with `jupyterhub-usage-quotas[service]` to include the [Usage Quota Dashboard](../tutorial/usage-quota-dashboard.md)
   - See the example below

   ````{tip} Example
   ```{code} bash
   # requirements.txt

   jupyterhub-usage-quotas[service] ~= 0.1.0
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

1. Build and push your custom Hub image to a registry and make a note of the image tag.

### Minimal z2jh configuration example

#### Authentication

Usage quota policies are applied to user groups, therefore this information needs to be available in a user's [`auth_state`](https://jupyterhub.readthedocs.io/en/stable/reference/authenticators.html#authentication-state). This minimal working example assumes a z2jh deployment that uses [OAuthenticator](https://oauthenticator.readthedocs.io/en/latest/) to handle authentication, specifically the [Generic OAuthenticator](https://oauthenticator.readthedocs.io/en/latest/tutorials/provider-specific-setup/providers/generic.html). Make sure that you set the appropriate configuration for your authenticator in addition to the minimal example below. See [User Group Management](../tutorial/user-group-management.md) for more details.

#### Home Storage Quotas

If you are using home storage quotas, then make sure that you set the appropriate configuration for [jupyterhub-home-nfs](https://github.com/2i2c-org/jupyterhub-home-nfs) in addition to the minimal example below.

#### Common Configuration

The `jupyterhub-usage-quotas` library is composed of two main modules:

1. The *manager* that enforces compute quotas at server launch time
1. The *service* that runs the user-facing [usage quota dashboard](./usage-quota-dashboard.md).

Configuration common to both modules include:

- `c.UsageConfig.prometheus_url`: the server url of the Prometheus instance that is used as a source of truth for usage data
- `c.UsageConfig.hub_namespace`: the Kubernetes namespace where the Hub pod is running

You can mount this common configuration under [`extraFiles`](https://z2jh.jupyter.org/en/stable/resources/reference.html#hub-extrafiles) so that they can be referenced by both modules.

#### Secrets Management

The usage quota system relies on configuring sensitive secrets, such as session keys and credentials, including:

- `c.UsageConfig.prometheus_auth`: credentials for the Prometheus server
- `c.UsageViewer.secret_session_key`: maintain a secure session with the usage quotas dashboard without needing to log in again.

You can also mount this secret configuration under [`extraFiles`](https://z2jh.jupyter.org/en/stable/resources/reference.html#hub-extrafiles) so that they can be referenced by both modules.

```{tip}
Make sure you encrypt any secrets files if using a version control system, using a tool such as [SOPS](https://getsops.io/).
```

#### Minimal Example

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
      manage_groups: true
      enable_auth_state: true
      scope:
        - group-0
      auth_state_groups_key: scope
    UsageQuotaManager:
      scope_backup_strategy:
        intersection: min
      policy:
        - resource: memory
          limit:
            value: 1000
            unit: GiB-hours
          window: 7
          scope:
            group:
              - group-0
      failover_open: false
    extraConfig:
      00-usage-quota: |
        from jupyterhub_usage_quotas import setup_usage_quotas
        setup_usage_quotas(c)
    extraFiles:
      usage_quota_config:
        mountPath: /usr/local/etc/jupyterhub/jupyterhub_config.d/jupyterhub_usage_quota_config.py
        stringData: |
          c.UsageConfig.prometheus_url: "http://<prometheus-service-name>.<k8s-prometheus-namespace>.svc.cluster.local"
          c.UsageConfig.hub_namespace: "<k8s-hub-namespace>"
  services:
    usage-quota:
      url: http://hub:9000
      display: false
      oauth_no_confirm: true
      command:
        - python3
        - -m
        - jupyterhub_usage_quotas.services.usage_viewer
          - --config-files=/usr/local/etc/jupyterhub/jupyterhub_config.d/jupyterhub_usage_quota_config.py
          - --config-files=/usr/local/etc/jupyterhub/jupyterhub_config.d/jupyterhub_usage_quota_config_secret.py
  loadRoles:
    usage-quota-service:
      scopes:
        - read:users
      services:
        - usage-quota
      user:
        scopes:
          - self
          - access:services!service=usage-quota
  networkPolicy:
    ingress:
      - ports:
          - port: 9000
        from:
          # Allow traffic from the proxy api pod
          - podSelector:
              matchLabels:
                hub.jupyter.org/network-access-hub: "true"
          # Allow traffic from the hub pod itself for Jupyterhub's internal healthchecks for hub managed services.
          - podSelector:
              matchLabels:
                app.kubernetes.io/component: hub
                app.kubernetes.io/name: jupyterhub
      - ports:
        - port: 8081
        from:
        # Allow traffic from the hub pod itself for oauth calls from the usage-quota service to the hub api.
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: hub
              app.kubernetes.io/name: jupyterhub
  service:
    extraPorts:
      - port: 9000
        targetPort: 9000
        name: usage-quota
  # The proxy.chp.networkPolicy.egress configuration below is required for the usage-quota dashboard service to be accessible for users.
  proxy:
    chp:
      networkPolicy:
        egress:
          - to:
              - podSelector:
                  matchLabels:
                    app.kubernetes.io/name: jupyterhub
                    app.kubernetes.io/component: hub
            ports:
              - port: 9000
```

```{code} yaml
---
label: enc-minimal-z2jh-config
---
# enc-config.yaml
# Note: this contains secrets so make sure you encrypt this file if using a version control system

hub:
  extraFiles:
    usage_quota_config_secret:
      mountPath: /usr/local/etc/jupyterhub/jupyterhub_config.d/jupyterhub_usage_quota_config_secret.py
      stringData: |
        c.UsageConfig.prometheus_auth = {
          "username": "<prometheus_username>",
          "password": "<prometheus_password>",
        },
        c.UsageViewer.session_secret_key: "<use-a-secure-key-in-production>"
```

See [Configuration](../reference/configuration.md) for a full list of configuration options.
