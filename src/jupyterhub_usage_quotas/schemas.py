"""JSON schema for usage quotas config."""

import copy
import typing

Schema = typing.Dict[str, typing.Any]

# JSON schema for the scope backup policy for usage quotas
policy_schema_backup: Schema = {
    "type": "object",
    "properties": {
        "resource": {"enum": ["memory", "cpu"]},
        "limit": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "unit": {"enum": ["GiB-hours", "CPU-hours"]},
            },
        },
        "window": {"type": "number"},
    },
    "required": ["resource", "limit", "window"],
    "additionalProperties": False,
}

# Policy schema: Add scope to usage quota policy
policy_schema = copy.deepcopy(policy_schema_backup)
policy_schema["properties"].update(
    {
        "scope": {
            "type": "object",
            "properties": {"group": {"type": "array", "items": {"type": "string"}}},
            "additionalProperties": False,
        }
    }
)
policy_schema["required"].append("scope")

# Prometheus Usage Quota Metrics schema
prometheus_usage_quota_metrics_schema: Schema = {
    "type": "object",
    "properties": {
        "home_storage": {
            "type": "object",
            "properties": {
                "usage": {"type": "string"},
                "quota": {"type": "string"},
            },
            "required": ["usage", "quota"],
            "additionalProperties": False,
        },
        "compute": {
            "type": "object",
            "properties": {
                "usage": {"type": "string"},
                "quota": {"type": "string"},
            },
            "required": ["usage", "quota"],
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}
