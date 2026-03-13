# Limitations

No real time enforcement, quotas apply only at server launch time.

- Overages can occur and running server sessions will not be throttled
- I.e. a user can still launch a server when they are close to the limit and continue to consume resources over the limit once the server is running

Rolling window continually expires usage.

- Users might find it confusing that there is no hard reset event
- Some may try to game the system when approaching the quota limit by keeping the their last valid server session alive longer than needed

Compute usage is an approximation.

- There is a tradeoff between performance and time resolution of usage metrics
- I.e. More frequent metric collection gives better accuracy but longer to process for quota decision making

Prometheus as a single-source-of-truth for usage must be reliable.

- Quota decisions are based on historical metrics fetched from a time-series database that cannot be overridden or patched
- Prometheus and its dependencies are therefore on the critical path of a fail closed usage quota system

`jupyterhub-usage-quotas` cannot be used to configure home storage usage and quotas.

- This lives in `jupyterhub-home-nfs`, which might make it difficult for admins to track separate policies for different resources
- The JupyterHub service cross-references and displays usage and quota metrics from `jupyterhub-home-nfs` to end users
