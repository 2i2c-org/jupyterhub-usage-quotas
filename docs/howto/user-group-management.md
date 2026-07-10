# User Group Management

Quota policies can be scoped to user groups and *individually* applied to members on a per-hub basis. Therefore a key aspect of reliably enforcing the usage quota system is maintaining good user group management.

## Authentication and Authorization

Users and groups are managed by the [authenticator](https://jupyterhub.readthedocs.io/en/stable/tutorial/getting-started/authenticators-users-basics.html) enabled for your JupyterHub. [OAuthenticator](https://oauthenticator.readthedocs.io/en/latest/index.html) is a plugin for using common OAuth providers with JupyterHub[^1] and included specialized classes for using popular external identity providers, such as GitHub, Google, etc., as well as a general `GenericOAuthenticator` class that can support any general identity provider.

Depending on the authenticator used, the identity provider may or may not be a concept of group membership to be passed onto JupyterHub's state. We cover the key settings required for any authenticator for managing user accounts to support quotas policies for JupyterHub groups.

### Authenticator

The [base authenticator](https://jupyterhub.readthedocs.io/en/stable/reference/authenticators.html#how-the-base-authenticator-works) used by JupyterHub should have the following settings configured to support user group management:

```python
c.Authenticator.manage_groups = True
c.Authenticator.enable_auth_state = True
```

Further settings are required depending on the specific OAuthenticator used.

#### GenericOAuthenticator

The `GenericOAuthenticator` is a general purpose class that can support any identity provider. See [Generic OAuthenticator setups for various identity providers — OAuthenticator](https://oauthenticator.readthedocs.io/en/latest/tutorials/provider-specific-setup/providers/generic.html) for general guidance on configuration.

Ensure that groups are populated with an appropriate key from the `auth_state`, e.g. for OpenID Connect (OIDC) using `scope` as the JupyterHub group names.

```python
c.GenericOAuthenticator.scope = ["openid", "offline_access", "cpu-1", "cpu-2", "cpu-3", "group-1", "group-2"]
c.GenericOAuthenticator.auth_state_groups_key = scope
```

## Refreshing Authentication State

In the case where a user's group membership has changed, then the user may need to log out and log back into the JupyterHub to refresh their `auth_state`. See [Refreshing user authentication — OAuthenticator](https://oauthenticator.readthedocs.io/en/latest/how-to/refresh.html#refreshing-user-authentication) for more details.

[^1]: See [JupyterHub and OAuth — JupyterHub documentation](https://jupyterhub.readthedocs.io/en/stable/explanation/oauth.html#) for how OAuth flows work in JupyterHub.
