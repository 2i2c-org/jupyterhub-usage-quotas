# Helper script to generate the configuration reference pages in docs/reference:
#
# - UsageQuotaManager.md and UsageViewer.md, from the traitlets configuration
# - helm-chart.md, from the Helm chart's values.schema.yaml (descriptions and
#   types) and values.yaml (defaults)
#
# The docs build runs this script, so the generated pages are not committed.
# It needs the jupyterhub-usage-quotas package and PyYAML, e.g. the `docs`
# hatch environment:
#
#   hatch run docs:build

import json
from pathlib import Path

import yaml
from traitlets.config import Application

from jupyterhub_usage_quotas.manager import UsageQuotaManager
from jupyterhub_usage_quotas.services.usage_viewer.app import UsageViewer

REPO = Path(__file__).parents[2]
REFERENCE = REPO / "docs" / "reference"
CHART = REPO / "helm" / "jupyterhub-usage-quotas"


# Traitlets configuration
# -----------------------------------------------------------------------------


# UsageQuotaManager is a traitlets.config.LoggingConfigurable. Wrap in Application class to take advantage of generate_config_file()
class UsageQuotaConfigApp(Application):
    classes = [UsageQuotaManager]


file_config_map = {
    "UsageQuotaManager": UsageQuotaConfigApp,
    "UsageViewer": UsageViewer,
}


def update_traitlets_reference():
    for item in file_config_map:
        with open(REFERENCE / f"{item}.md", "w") as f:
            instance = file_config_map[item]()
            # Remove trailing whitespace, as the pre-commit hooks do
            content = "".join(
                line.rstrip() + "\n"
                for line in instance.generate_config_file().splitlines()
            )
            label = item.lower().replace("config", "-config")
            lines = [
                f"# {item}\n",
                "\n",
                f"({label})=\n",
                "\n",
                "```\n",
                content,
                "```\n",
            ]
            f.writelines(lines)


# Helm chart values
# -----------------------------------------------------------------------------

HELM_CHART_HEADER = """\
# Helm chart

(helm-chart-reference)=

The `jupyterhub-usage-quotas` Helm chart installs the usage viewer service next
to a Zero to JupyterHub deployment. See [Install the usage viewer
chart](../howto/quickstart.md#install-the-usage-viewer-chart).

The contents of this file were generated from the chart's `values.schema.yaml`
and `values.yaml` files using the helper script
`scripts/update_configuration_reference.py`.
"""


def get_default(values, path):
    """Return the default value at path in values.yaml, or None if not set."""
    for key in path:
        if not isinstance(values, dict) or key not in values:
            return None
        values = values[key]
    return values


def format_type(schema):
    if "enum" in schema:
        return " | ".join(f"`{json.dumps(v)}`" for v in schema["enum"])
    types = schema.get("type", "")
    if isinstance(types, list):
        return " | ".join(types)
    return types


def render_chart_value(schema, values, path, level):
    lines = [f"{'#' * level} `{'.'.join(path)}`", ""]
    lines.append(f"- Type: {format_type(schema)}")
    default = get_default(values, path)
    is_parent = "properties" in schema
    if not is_parent and default not in (None, "", [], {}):
        if isinstance(default, (dict, list)):
            default_yaml = yaml.safe_dump(default, default_flow_style=False).strip()
            # A list item with a code block makes the list loose, so mdformat
            # puts a blank line between the items.
            lines += ["", "- Default:", "", "  ```yaml"]
            lines += [f"  {line}" for line in default_yaml.splitlines()]
            lines += ["  ```"]
        else:
            lines.append(f"- Default: `{json.dumps(default)}`")
    lines.append("")
    if "description" in schema:
        lines += [schema["description"].strip(), ""]
    for child, child_schema in schema.get("properties", {}).items():
        lines += render_chart_value(
            child_schema, values, [*path, child], min(level + 1, 6)
        )
    return lines


def update_helm_chart_reference():
    schema = yaml.safe_load((CHART / "values.schema.yaml").read_text())
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    lines = [HELM_CHART_HEADER]
    for name, prop in schema["properties"].items():
        lines += render_chart_value(prop, values, [name], 2)
    (REFERENCE / "helm-chart.md").write_text("\n".join(lines).rstrip() + "\n")


if __name__ == "__main__":
    update_traitlets_reference()
    update_helm_chart_reference()
