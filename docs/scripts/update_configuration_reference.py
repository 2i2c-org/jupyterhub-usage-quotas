# Helper script to update configuration.md

# Make sure you are using the `hatch shell dev` environment when running this script

from jupyterhub_usage_quotas.config import (
    UsageConfig,
    UsageQuotaConfig,
    UsageViewerConfig,
)

file_config_map = {
    "UsageConfig": UsageConfig,
    "UsageQuotaConfig": UsageQuotaConfig,
    "UsageViewerConfig": UsageViewerConfig,
}

for item in file_config_map:
    with open(f"../reference/{item}.md", "w") as f:
        instance = file_config_map[item]()
        content = instance.generate_config_file()
        label = item.lower().replace("config", "-config")
        lines = [f"# {item}\n", "\n", f"({label})=\n", "\n", "```\n", content, "```\n"]
        f.writelines(lines)
