from __future__ import annotations
from ..utils import coerce_args, pytype, debug, info

import os
import json
import inspect
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP
from ..settings import settings
from ..utils import coerce_args, pytype
from ..http_client import http_call

# Reutilizamos o mesmo FastMCP para todo o servidor
mcp: FastMCP = settings.mcp

def _register_http_tool(defn: dict):
    name = defn["name"]
    description = defn.get("description") or f"HTTP tool {name}"
    http_cfg = defn["http"]
    arg_spec: Dict[str, str] = defn.get("args") or {}

    def _impl(**arguments):
        args = coerce_args(arg_spec, arguments)
        ctx = {**os.environ, **{k: str(v) for k, v in args.items()}}
        _, payload = http_call(http_cfg, ctx)
        return payload

    params = [
        inspect.Parameter(pname, kind=inspect.Parameter.KEYWORD_ONLY, annotation=pytype(typ))
        for pname, typ in arg_spec.items()
    ]
    _impl.__signature__ = inspect.Signature(parameters=params)

    debug(f"  Tool carregada: {name} - {description}")

    mcp.tool(name=name, description=description)(_impl)

def load_tools_from_file(path: str):
    if not os.path.exists(path):
        raise ValueError("tools.json: arquivo não encontrado")

    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)

    if not isinstance(items, list):
        raise ValueError("tools.json deve ser uma lista de objetos")

    debug(f"Carregando tools de {path}")

    for it in items:
        if "name" in it and "http" in it:
            _register_http_tool(it)
