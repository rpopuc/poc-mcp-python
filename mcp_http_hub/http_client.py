from __future__ import annotations

import os
import json
import time
import httpx
from typing import Any, Tuple, Dict, Optional

from .settings import settings
from .utils import safe_format, resolve_template_obj, extract_filter, info, debug, warn

# =========================
# Suporte a arquivos
# =========================
def _read_file_safely(path: str, max_mb: float) -> bytes:
    max_bytes = int(max_mb * 1024 * 1024)
    with open(path, "rb") as f:
        data = f.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"Arquivo '{path}' excede o limite de {max_mb} MB")
    return data

# =========================
# Auth helpers
# =========================
_OAUTH_CACHE: dict[str, dict] = {}
# cache key -> {"token": "...", "exp": epoch_seconds}

def _merge_no_overwrite(dst: Dict[str, str], src: Dict[str, str], overwrite: bool = False):
    """Mescla src em dst, sem sobrescrever chaves existentes a menos que overwrite=True."""
    for k, v in src.items():
        if overwrite or k not in dst:
            dst[k] = v

def _resolve_auth_headers_and_query(auth_cfg: Optional[dict], ctx: dict) -> tuple[dict, dict, Optional[dict]]:
    """
    Retorna (headers_add, query_add, oauth_meta)
    oauth_meta retorna dict com info de retry para oauth2 (ex.: {'type':'oauth2_client_credentials','cache_key':...})
    """
    if not auth_cfg:
        return {}, {}, None

    typ = (auth_cfg.get("type") or "").lower()
    overwrite = bool(auth_cfg.get("overwrite", False))

    # util: pegar valor de env (ou ctx) com fallback
    def val_of(*keys, default=None):
        for k in keys:
            if k in auth_cfg:
                return safe_format(str(auth_cfg[k]), ctx)
            envk = f"{k}_env"
            if envk in auth_cfg:
                v = os.getenv(auth_cfg[envk])
                if v is not None:
                    return v
        return default

    headers_add: Dict[str, str] = {}
    query_add: Dict[str, str] = {}
    oauth_meta: Optional[dict] = None

    if typ == "bearer":
        token = val_of("token", default=None)
        if token is None:
            # permite obter de {TOKEN} vindo do ctx/env via template
            token = val_of("token_template", default=None)
        if token is None:
            token = val_of("token_env", default=None)
        if not token:
            raise ValueError("auth.type=bearer requer 'token' (ou token_env/token_template)")
        prefix = auth_cfg.get("prefix") or "Bearer "
        _merge_no_overwrite(headers_add, {"Authorization": f"{prefix}{token}"}, overwrite)

    elif typ == "api_key":
        where = (auth_cfg.get("in") or "header").lower()  # header|query
        name = auth_cfg.get("name")
        if not name:
            raise ValueError("auth.type=api_key requer 'name'")
        value = val_of("value", default=None)
        if value is None:
            value = val_of("value_template", default=None)
        if value is None:
            value = val_of("value_env", default=None)
        if value is None:
            raise ValueError("auth.type=api_key requer 'value' (ou value_env/value_template)")
        if where == "query":
            _merge_no_overwrite(query_add, {name: value}, overwrite)
        else:
            prefix = auth_cfg.get("prefix") or ""  # ex.: "Token "
            _merge_no_overwrite(headers_add, {name: f"{prefix}{value}"} if prefix else {name: value}, overwrite)

    elif typ == "basic":
        user = val_of("username", default=None)
        if user is None:
            user = val_of("username_template", default=None)
        if user is None:
            user = val_of("username_env", default=None)
        pwd = val_of("password", default=None)
        if pwd is None:
            pwd = val_of("password_template", default=None)
        if pwd is None:
            pwd = val_of("password_env", default=None)
        if user is None or pwd is None:
            raise ValueError("auth.type=basic requer username e password (ou *_env/_template)")
        # httpx tem suporte nativo via auth=(user, pwd); devolvemos meta para chamada usar.
        return headers_add, query_add, {"type": "basic", "username": user, "password": pwd}

    elif typ == "oauth2_client_credentials":
        token_url = val_of("token_url", default=None)
        client_id = val_of("client_id", default=None)
        client_secret = val_of("client_secret", default=None)
        scope = val_of("scope", default=None)
        audience = val_of("audience", default=None)
        extra = auth_cfg.get("extra") or {}  # dict de params adicionais

        if not token_url or not client_id or not client_secret:
            raise ValueError("auth.type=oauth2_client_credentials requer token_url, client_id e client_secret")

        cache_key = json.dumps({"u": token_url, "id": client_id, "sc": scope, "au": audience}, sort_keys=True)
        now = int(time.time())
        tok = _OAUTH_CACHE.get(cache_key)
        if not tok or now >= tok.get("exp", 0):
            # obter novo token
            data = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
            if scope:
                data["scope"] = scope
            if audience:
                data["audience"] = audience
            # merge extra (stringify via template)
            for k, v in (extra or {}).items():
                data[k] = safe_format(str(v), ctx)

            verify_flag = settings.HTTP_VERIFY_SSL
            timeout = float(auth_cfg.get("timeout", settings.HTTP_TIMEOUT))
            headers_token = {"Content-Type": "application/x-www-form-urlencoded"}
            with httpx.Client(timeout=timeout, verify=verify_flag) as c:
                resp = c.post(token_url, data=data, headers=headers_token)
                resp.raise_for_status()
                j = resp.json()
            access = j.get("access_token")
            if not access:
                raise RuntimeError("Falha ao obter access_token em oauth2 client credentials")
            expires_in = int(j.get("expires_in", 3600))
            _OAUTH_CACHE[cache_key] = {"token": access, "exp": now + max(expires_in - 30, 30)}  # margem de 30s
            debug("oauth2: token obtido e cacheado")
            tok = _OAUTH_CACHE[cache_key]

        _merge_no_overwrite(headers_add, {"Authorization": f"Bearer {tok['token']}"}, overwrite)
        oauth_meta = {"type": "oauth2_client_credentials", "cache_key": cache_key}

    else:
        raise ValueError(f"auth.type desconhecido: {typ}")

    return headers_add, query_add, oauth_meta

def _invalidate_oauth_cache(meta: Optional[dict]):
    if meta and meta.get("type") == "oauth2_client_credentials":
        ck = meta.get("cache_key")
        if ck and ck in _OAUTH_CACHE:
            _OAUTH_CACHE.pop(ck, None)
            warn("oauth2: invalidando token cache após 401")

# =========================
# HTTP principal
# =========================
def http_call(http_cfg: dict, ctx: dict) -> Tuple[str, Any]:
    """
    method/url/query/headers/body/form/multipart/timeout/response/filter/auth
    Retorna: ("json"|"text"|"bytes", payload)
    """
    method = (http_cfg.get("method") or "GET").upper()
    url_tmpl = http_cfg["url"]
    response_mode = (http_cfg.get("response") or "json").lower()
    query_tmpl = http_cfg.get("query") or {}
    headers_tmpl = http_cfg.get("headers") or {}
    body_tmpl = http_cfg.get("body")
    form_tmpl = http_cfg.get("form")
    multipart_tmpl = http_cfg.get("multipart")
    timeout = float(http_cfg.get("timeout", settings.HTTP_TIMEOUT))
    flt = http_cfg.get("filter")
    auth_cfg = http_cfg.get("auth")  # <---- NOVO

    url = safe_format(url_tmpl, ctx)
    qparams = {k: safe_format(str(v), ctx) for k, v in query_tmpl.items()}
    headers = {k: safe_format(str(v), ctx) for k, v in headers_tmpl.items()}

    # -------- autenticação
    add_h, add_q, oauth_meta = _resolve_auth_headers_and_query(auth_cfg, {**os.environ, **ctx})
    # mescla sem sobrescrever (a menos que overwrite=true dentro do auth_cfg)
    _merge_no_overwrite(headers, add_h, overwrite=bool(auth_cfg and auth_cfg.get("overwrite")))
    _merge_no_overwrite(qparams, add_q, overwrite=bool(auth_cfg and auth_cfg.get("overwrite")))

    json_body = None
    data_body = None
    files_body = None
    basic_auth = None  # httpx basic auth tuple

    # se basic foi solicitado, setar auth tuple
    if oauth_meta and oauth_meta.get("type") == "basic":
        basic_auth = (oauth_meta["username"], oauth_meta["password"])

    # prioridade: multipart > form > body
    if multipart_tmpl is not None:
        resolved = resolve_template_obj(multipart_tmpl, ctx)
        data_body = {}
        files_list = []
        default_per_file_mb = 10.0
        max_multipart_mb = settings.MAX_MULTIPART_MB
        total_bytes = 0
        for field, value in (resolved or {}).items():
            if isinstance(value, dict) and "file" in value:
                fpath = value.get("file")
                if not fpath or not os.path.exists(fpath):
                    raise ValueError(f"Caminho inválido para campo '{field}': {fpath!r}")
                per_file_mb = float(value.get("max_mb", default_per_file_mb))
                content = _read_file_safely(fpath, per_file_mb)
                total_bytes += len(content)
                if total_bytes > int(max_multipart_mb * 1024 * 1024):
                    raise ValueError(f"Soma dos arquivos excede {max_multipart_mb} MB")
                filename = value.get("filename") or os.path.basename(fpath)
                ctype = value.get("content_type")
                files_list.append((field, (filename, content, ctype)))
            else:
                data_body[field] = "" if value is None else str(value)
        files_body = files_list
        headers.pop("Content-Type", None)

    elif form_tmpl is not None:
        resolved = resolve_template_obj(form_tmpl, ctx)
        if not isinstance(resolved, dict):
            raise ValueError("http.form deve ser um objeto (dict)")
        data_body = {k: "" if v is None else str(v) for k, v in resolved.items()}
        headers.pop("Content-Type", None)

    elif body_tmpl is not None:
        if isinstance(body_tmpl, dict):
            json_body = resolve_template_obj(body_tmpl, ctx)
            headers.setdefault("Content-Type", "application/json")
        else:
            data_body = safe_format(str(body_tmpl), ctx)

    verify_flag = settings.HTTP_VERIFY_SSL

    def _do_request():
        with httpx.Client(timeout=timeout, verify=verify_flag) as client:
            return client.request(
                method,
                url,
                params=qparams,
                headers=headers,
                json=json_body,
                data=data_body,
                files=files_body,
                auth=basic_auth,
            )

    # 1ª tentativa
    resp = _do_request()
    # se deu 401 e usamos oauth2, tenta renovar e repetir uma vez
    if resp.status_code == 401 and auth_cfg and (auth_cfg.get("type") == "oauth2_client_credentials"):
        _invalidate_oauth_cache(oauth_meta)
        add_h2, add_q2, _ = _resolve_auth_headers_and_query(auth_cfg, {**os.environ, **ctx})
        _merge_no_overwrite(headers, add_h2, overwrite=True)  # agora força atualizar Authorization
        _merge_no_overwrite(qparams, add_q2, overwrite=True)
        resp = _do_request()

    resp.raise_for_status()

    if response_mode == "text":
        return ("text", resp.text)
    elif response_mode == "bytes":
        return ("bytes", resp.content)
    else:
        data = resp.json()
        data = extract_filter(data, flt, ctx)
        return ("json", data)

def infer_mime(http_cfg: Dict[str, Any]) -> str:
    resp_mode = (http_cfg.get("response") or "json").lower()
    if resp_mode == "bytes":
        return "application/octet-stream"
    if resp_mode == "text":
        return "text/plain"
    return "application/json"
