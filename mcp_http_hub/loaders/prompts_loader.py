from __future__ import annotations
from ..utils import coerce_args, pytype, debug, info

import os
import json
import inspect
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from ..settings import settings
from ..utils import coerce_args, pytype, safe_format
from ..http_client import http_call

mcp: FastMCP = settings.mcp

def _register_static_prompt(name: str, description: Optional[str], template: str):
    debug(f"  Static prompt: {name} - {description}")
    @mcp.prompt(name=name, description=description)
    def _p() -> str:
        return template
    return _p

def _register_param_prompt(name: str, description: Optional[str], template: str, param_keys: list[str]):
    debug(f"  Param prompt: {name} - {description}")
    @mcp.prompt(name=name, description=description)
    def _p(args: dict[str, str]) -> str:
        args = args or {}
        try:
            return template.format(**args)
        except KeyError as e:
            missing = str(e).strip("'")
            return f"[prompt:{name}] argumento obrigatório ausente: {missing}"
    return _p

def _register_http_prompt(defn: dict):
    name = defn["name"]
    description = defn.get("description")

    debug(f"  HTTP prompt: {name} - {description}")

    http_cfg = defn["http"]
    arg_spec: Dict[str, str] = defn.get("args") or {}
    render = defn.get("render") or {}
    template = render.get("template") or "{text}"

    def _p(**arguments) -> str:
        args = coerce_args(arg_spec, arguments)
        ctx = {**os.environ, **{k: str(v) for k, v in args.items()}}
        rmode, payload = http_call(http_cfg, ctx)

        if rmode == "json":
            titles = []
            if isinstance(payload, list):
                titles = [str(x.get("title", "")) for x in payload if isinstance(x, dict)]
            ctx2 = {**ctx, "titles": ", ".join([t for t in titles if t]),
                    "json": json.dumps(payload, ensure_ascii=False)}
            return safe_format(template, ctx2)
        elif rmode == "text":
            return safe_format(template, {**ctx, "text": str(payload)})
        else:
            return safe_format(template, {**ctx, "text": "<binary>"})

    params = [
        inspect.Parameter(n, kind=inspect.Parameter.KEYWORD_ONLY,
                          annotation=pytype(arg_spec.get(n, "str")))
        for n in arg_spec.keys()
    ]
    _p.__signature__ = inspect.Signature(parameters=params)
    ann: Dict[str, Any] = {n: pytype(arg_spec.get(n, "str")) for n in arg_spec.keys()}
    ann["return"] = str
    _p.__annotations__ = ann

    mcp.prompt(name=name, description=description)(_p)

def load_prompts_from_file(path: str):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list):
        raise ValueError("prompts.json deve ser uma lista de objetos")

    debug(f"Carregando prompts de {path}")

    for it in items:
        name = it.get("name")
        if not name:
            continue
        if "http" in it:
            _register_http_prompt(it)
        else:
            template = it.get("content") or it.get("text")
            description = it.get("description")
            params = it.get("params") or []
            if not template:
                continue
            if params:
                _register_param_prompt(name, description, template, params)
            else:
                _register_static_prompt(name, description, template)
