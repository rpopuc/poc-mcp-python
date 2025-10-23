from __future__ import annotations
from ..utils import coerce_args, pytype, debug, info

import os
import re
import json
import inspect
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP
from ..settings import settings
from ..utils import coerce_args, pytype
from ..http_client import http_call, infer_mime

mcp: FastMCP = settings.mcp
_PLACEHOLDER_RE = re.compile(r"{(\w+)}")

def _placeholders_in_uri(uri: str) -> list[str]:
    return _PLACEHOLDER_RE.findall(uri or "")

def _register_http_resource(defn: dict):
    uri = defn["uri"]
    description = defn.get("description")
    http_cfg = defn["http"]
    arg_spec: Dict[str, str] = defn.get("args") or {}

    mime = defn.get("mime_type") or infer_mime(http_cfg)
    placeholders = _placeholders_in_uri(uri)

    def _make_handler(param_names: list[str]):
        def _handler(**kwargs):
            args = coerce_args(arg_spec, kwargs) if arg_spec else kwargs
            ctx = {**os.environ, **{k: str(v) for k, v in args.items()}}
            mode, payload = http_call(http_cfg, ctx)
            if mode == "json":
                return json.dumps(payload, ensure_ascii=False)
            elif mode == "text":
                return payload
            else:
                return payload  # bytes

        params = [
            inspect.Parameter(n, kind=inspect.Parameter.KEYWORD_ONLY,
                              annotation=pytype(arg_spec.get(n, "str")))
            for n in param_names
        ]
        _handler.__signature__ = inspect.Signature(parameters=params)

        ann: Dict[str, Any] = {n: pytype(arg_spec.get(n, "str")) for n in param_names}
        ann["return"] = Any
        _handler.__annotations__ = ann

        return _handler

    handler = _make_handler(placeholders)
    debug(f"  Resource: {description}")
    mcp.resource(uri, description=description, mime_type=mime)(handler)

def load_resources_from_file(path: str):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list):
        raise ValueError("resources.json deve ser uma lista de objetos")
    for it in items:
        debug(f"Carregando resources de {path}")
        if "uri" in it and "http" in it:
            _register_http_resource(it)
