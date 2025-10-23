from __future__ import annotations

from mcp_http_hub.settings import settings
from mcp_http_hub.loaders.tools_loader import load_tools_from_file
from mcp_http_hub.loaders.resources_loader import load_resources_from_file
from mcp_http_hub.loaders.prompts_loader import load_prompts_from_file

def main():
    # Carregadores registram tudo no objeto FastMCP global dos loaders
    load_tools_from_file(settings.TOOLS_FILE)
    load_resources_from_file(settings.RESOURCES_FILE)
    load_prompts_from_file(settings.PROMPTS_FILE)

    # Sobe servidor
    settings.mcp.run(transport="streamable-http")

if __name__ == "__main__":
    main()
