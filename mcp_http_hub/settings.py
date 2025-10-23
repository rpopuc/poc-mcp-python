from __future__ import annotations

import os
from dataclasses import dataclass, field
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

def _as_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1","true","t","yes","y")

def _as_int(v: str | None, default: int) -> int:
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default

def _as_float(v: str | None, default: float) -> float:
    try:
        return float(v) if v is not None else default
    except ValueError:
        return default

load_dotenv(dotenv_path=os.getenv("DOTENV_PATH", ".env"))

@dataclass(frozen=True)
class Settings:
    PORT: int = _as_int(os.getenv("PORT"), 8030)
    HOST: str = os.getenv("HOST", "0.0.0.0")
    SERVER_NAME: str = os.getenv("SERVER_NAME", "MCP-HTTP-Hub")

    TOOLS_FILE: str = os.getenv("TOOLS_FILE", "config/tools.json")
    PROMPTS_FILE: str = os.getenv("PROMPTS_FILE", "config/prompts.json")
    RESOURCES_FILE: str = os.getenv("RESOURCES_FILE", "config/resources.json")

    HTTP_TIMEOUT: float = _as_float(os.getenv("HTTP_TIMEOUT"), 15.0)
    HTTP_VERIFY_SSL: bool = _as_bool(os.getenv("HTTP_VERIFY_SSL"), False)
    MAX_MULTIPART_MB: float = _as_float(os.getenv("MAX_MULTIPART_MB"), 25.0)

    # instância única do FastMCP (preenchida no __post_init__)
    mcp: FastMCP = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "mcp", FastMCP(self.SERVER_NAME, host=self.HOST, port=self.PORT))

settings = Settings()