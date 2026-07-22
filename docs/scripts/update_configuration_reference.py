# Helper script to update configuration.md

# Make sure you are using the `hatch shell dev` environment when running this script

from traitlets.config import Application

from jupyterhub_usage_quotas.manager import UsageQuotaManager
from jupyterhub_usage_quotas.services.usage_viewer.app import UsageViewer

# UsageQuotaManager is a traitlets.config.LoggingConfigurable. Wrap in Application class to take advantage of generate_config_file()


class UsageQuotaConfigApp(Application):
    classes = [UsageQuotaManager]


file_config_map = {
    "UsageQuotaManager": UsageQuotaConfigApp,
    "UsageViewer": UsageViewer,
}


for item in file_config_map:
    with open(f"../reference/{item}.md", "w") as f:
        instance = file_config_map[item]()
        content = instance.generate_config_file()
        label = item.lower().replace("config", "-config")
        lines = [f"# {item}\n", "\n", f"({label})=\n", "\n", "```\n", content, "```\n"]
        f.writelines(lines)
