from __future__ import annotations

import json
import sys
import datetime
import os

from typing import Any, Dict

_TYPEMAP = {"int": int, "float": float, "bool": bool, "str": str}

def pytype(tname: str):
    return _TYPEMAP.get(str(tname).lower(), str)

def safe_format(template: str, mapping: dict) -> str:
    class _D(dict):
        def __missing__(self, k):  # mantém {chave} desconhecida
            return "{%s}" % k
    return template.format_map(_D(mapping))

def resolve_template_obj(obj: Any, ctx: dict) -> Any:
    if isinstance(obj, str):
        return safe_format(obj, ctx)
    if isinstance(obj, list):
        return [resolve_template_obj(x, ctx) for x in obj]
    if isinstance(obj, dict):
        return {k: resolve_template_obj(v, ctx) for k, v in obj.items()}
    return obj

def coerce_args(spec: Dict[str, str], args: Dict[str, Any] | None) -> Dict[str, Any]:
    args = args or {}
    if not spec:
        return args
    out: Dict[str, Any] = {}
    for k, t in spec.items():
        if k not in args or args[k] is None:
            raise ValueError(f"Argumento obrigatório ausente: {k}")
        v = args[k]
        ty = pytype(t)
        if ty is bool and not isinstance(v, bool):
            v = str(v).lower() in ("1","true","t","yes","y","sim","s")
        else:
            v = ty(v)
        out[k] = v
    for k, v in args.items():
        if k not in out:
            out[k] = v
    return out

def extract_filter(data, flt: dict | None, args: dict) -> Any:
    if not flt:
        return data
    seq = data if isinstance(data, list) else []
    wc = (flt.get("where_contains") or {})
    # args já deve vir mesclado com env na chamada
    wc_resolved = {k: safe_format(v, args) for k, v in wc.items()}
    def keep(item):
        for field, needle in wc_resolved.items():
            val = str(item.get(field, "")) if isinstance(item, dict) else ""
            if needle and needle.lower() not in val.lower():
                return False
        return True
    return [x for x in seq if keep(x)]

# ==================================================
# Logger estilo uvicorn (ex.: "INFO:     Started server process [43]")
# ==================================================

# permite ajustar via .env -> LOG_LEVEL=info
LOG_LEVEL = os.getenv("LOG_LEVEL", "debug").upper()
LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
CURRENT_LEVEL = LEVEL_ORDER.get(LOG_LEVEL, 20)

COLORS = {
    "DEBUG": "\033[94m",   # azul
    "INFO": "\033[38;5;2m",    # verde
    "WARNING": "\033[93m", # amarelo
    "ERROR": "\033[91m",   # vermelho
}
RESET = "\033[0m"

def _emit(level: str, msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color = COLORS.get(level, "")
    sys.stdout.write(f"{color}{level}:{RESET}    {msg}\n")
    sys.stdout.flush()

def log(level: str, msg: str):
    level = level.upper()
    if LEVEL_ORDER.get(level, 0) >= CURRENT_LEVEL:
        _emit(level, msg)

def debug(msg: str): log("DEBUG", msg)
def info(msg: str):  log("INFO", msg)
def warn(msg: str):  log("WARNING", msg)
def error(msg: str): log("ERROR", msg)
