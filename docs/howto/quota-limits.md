# Applying quota policies for your hub

One of the first things a hub admin will want to think about when using the usage quotas system is:

- what resource can I constrain with quota limits?
- when/over what period do the quota limits apply?
- who can I apply quota limits to?
- how can I choose sensible values for quota limits?

This how-to provides some opinionated guidance on how to answer the above questions.

## What?

We recommend applying compute quotas to either memory-hour or cpu-hour {term}`requests`. If you are conscious of cloud usage costs, then enforcing quota limits on:

- memory-hours (base unit: {term}`byte-hour`) is more appropriate for interactive computing (bursty workloads)
- {term}`CPU-hour`s is more appropriate for high-performance computing (predictable workloads).

## When?

You can apply quota limits over a rolling window. There is no hard reset event. With a rolling window, quota expires continuously over time if a user is over their limit. This expiry is proportional to the historical usage at the beginning of the rolling window. See [Retry time](/explanation/technical.md#retry-time) for more details on quota expiry and retry times.

## Who?

You can either specify:

1. A blanket quota policy applied to all users on the hub
1. A quota policy applied individually to each member of a JupyterHub group, with a fallback for members who are not a part of any group.

## How?

If you know that you would like to enforce quotas for a specific event, then you can devise a quota limit depending on the compute resource you would like your participants to use and the duration of the event.

```{tip} Example
> "During my event, which last for 5 days, I want my participants who are members of group A to use 8 GiB RAM servers each day.”

This means you could choose to enforce:

- an 8 GiB $\times$ 24 hours $\times$ 1 day = 192 GiB-hour limit over a 1 day rolling window
- an 8 GiB $\times$ 24 hours $\times$ 5 days = 960 GiB-hour limit over a 5 day rolling window

to each participant who is a member of JupyterHub group A.
```

For more general usage, a first order approach to choosing sensible limits is to analyze historical usage of your current users over a certain time period and use that to set a quota limit. You can usually find this from your Prometheus/Grafana instance by running the following example PromQL:

```sql
sum(
  sum_over_time(
    kube_pod_container_resource_requests{
      resource="memory",
      namespace="prod",
      pod=~"jupyter.*",
      }[30d]
    )
  ) * 60 / 60^2 / 1024^3
```

where

- `resource="memory"` or `"cpu"` is the compute resource of interest
- `namespace="prod"` is the k8s namespace your hub is deployed
- `pod=~"jupyter.*"` filters for all user pods
- `[30d]` is the time window of interest
- `* 60` is to convert from samples to seconds using the default Prometheus scrape interval
- `/ 60^2` converts from seconds to hours
- `/ 1024^3` converts from bytes to GiB.

If you need to break this down by JupyterHub group[^1], then you can try the PromQL

```sql
sum(
  kube_pod_container_resource_requests{resource="memory", pod=~"jupyter-.*", namespace=~"prod"}
  * on (namespace, pod) group_left(annotation_hub_jupyter_org_username, usergroup)
  group(
      kube_pod_annotations{namespace=~"prod", annotation_hub_jupyter_org_username=~".*", pod=~"jupyter-.*"}
  ) by (pod, namespace, annotation_hub_jupyter_org_username)
  * on (namespace, annotation_hub_jupyter_org_username) group_left(usergroup)
  group(
  label_replace(jupyterhub_user_group_info{namespace=~"prod", username=~".*", usergroup=~".*"},
      "annotation_hub_jupyter_org_username", "$1", "username", "(.+)")
  ) by (annotation_hub_jupyter_org_username, usergroup, namespace)
) by (usergroup, namespace)
```

````{note}
If you have users assigned to multiple groups, then the above query will return an error: `found duplicate series for the match group...`. This is because PromQL cannot double-count usage to multiple groups (perform a many-to-many match). In this case, you will need use another tool to manually match the user names from the first PromQL query with the group names from the output of

```sql
group(jupyterhub_user_group_info) by (namespace, username, username_escaped, usergroup)
```
````

## Further reading

See [Policy configuration](policy-configuration) for more information on how compute quota policies are configured.

[^1]: Assuming that [jupyterhub-groups-exporter](https://github.com/2i2c-org/jupyterhub-groups-exporter) is deployed in the hub's k8s namespace.
