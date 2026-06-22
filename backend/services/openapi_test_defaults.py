"""Local defaults for the KB OpenAPI B2B sample page."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import kb_auth
from backend.settings import RuntimeSettings, get_runtime_settings, normalize_runtime_mode


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError:
            return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _load_key_txt_defaults() -> dict[str, str]:
    raw = _read_text(_repo_root() / "key.txt")
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip().lower()] = value.strip()

    def first(*keys: str) -> str:
        for key in keys:
            value = values.get(key.lower())
            if value:
                return value
        return ""

    client_secret = first("clientSecret", "client_secret", "secretkey", "secret_key")
    ci_no = first("ciNo", "ci_no")
    raw_user_info = first("userInfo", "userIfno", "user_info")
    user_info = raw_user_info
    if raw_user_info and ci_no and client_secret:
        try:
            user_info = kb_auth.encrypt_user_info(raw_user_info, ci_no, client_secret)
        except Exception:
            user_info = raw_user_info

    return {
        "clientId": first("clientId", "client_id", "appkey", "app_key", "b2bClientId", "b2b_client_id"),
        "clientSecret": client_secret,
        "ciNo": ci_no,
        "userInfo": user_info,
    }


def _walk_postman_items(items: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("request"), dict):
            result.append(item)
            continue
        nested = item.get("item")
        if isinstance(nested, list):
            result.extend(_walk_postman_items(nested))
    return result


def _request_body(item: dict[str, Any]) -> dict[str, Any]:
    request = item.get("request")
    if not isinstance(request, dict):
        return {}
    body = request.get("body")
    if not isinstance(body, dict):
        return {}
    raw = body.get("raw")
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _request_raw_url(item: dict[str, Any]) -> str:
    request = item.get("request")
    if not isinstance(request, dict):
        return ""
    url = request.get("url")
    if isinstance(url, dict):
        raw = url.get("raw")
        return raw if isinstance(raw, str) else ""
    return url if isinstance(url, str) else ""


def _request_method(item: dict[str, Any]) -> str:
    request = item.get("request")
    if not isinstance(request, dict):
        return "POST"
    method = request.get("method")
    return method if isinstance(method, str) and method else "POST"


def _kb_b2b_base_url(settings: RuntimeSettings) -> str:
    return settings.active_environment.kb_b2b_base_url


def _request_draft(item: dict[str, Any], settings: RuntimeSettings) -> dict[str, Any]:
    raw_url = _request_raw_url(item)
    parsed = urlparse(raw_url)
    return {
        "method": _request_method(item),
        "baseUrl": f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else _kb_b2b_base_url(settings),
        "path": parsed.path or "",
        "body": _request_body(item),
    }


def _load_b2b_postman_defaults(settings: RuntimeSettings) -> dict[str, Any]:
    collection_path = (
        _repo_root().parent
        / "_dev_"
        / "KB_BaaS 2.0 Dev (B2B).postman_collection"
        / "1.BaaS 2.0 Dev Sample.postman_collection.json"
    )
    collection = _load_json(collection_path)
    items = _walk_postman_items(collection.get("item", []))
    requests: dict[str, Any] = {}

    for item in items:
        raw_url = _request_raw_url(item)
        body = _request_body(item)
        data_body = body.get("dataBody") if isinstance(body.get("dataBody"), dict) else {}
        grant_type = data_body.get("grantType") if isinstance(data_body, dict) else ""

        if "clause_agree_process" in raw_url and "clauseAgree" not in requests and grant_type != "client_credentials":
            requests["clauseAgree"] = _request_draft(item, settings)
        elif "email_agree_process" in raw_url and "emailAgree" not in requests:
            requests["emailAgree"] = _request_draft(item, settings)
        elif "baas_auth_issue" in raw_url and "authIssue" not in requests:
            requests["authIssue"] = _request_draft(item, settings)
        elif "baas_token_issue" in raw_url and "tokenIssue" not in requests and grant_type == "authorization_code":
            requests["tokenIssue"] = _request_draft(item, settings)

    return requests


def _load_b2b_config_defaults(settings: RuntimeSettings) -> dict[str, Any]:
    cfg = kb_auth.load_config()
    key_txt = _load_key_txt_defaults() if settings.expose_local_defaults else {}
    dev_cfg = cfg.get("dev", {}) if isinstance(cfg.get("dev"), dict) else {}
    prod_cfg = cfg.get("prod", {}) if isinstance(cfg.get("prod"), dict) else {}
    active_mode = settings.kb_config_mode
    mode_cfg = prod_cfg if active_mode == "prod" else dev_cfg
    try:
        user_info = kb_auth.resolve_user_info(mode_cfg)
    except ValueError:
        user_info = mode_cfg.get("user_info", "")

    secret_values = {
        "clientId": key_txt.get("clientId") or mode_cfg.get("client_id") or "",
        "clientSecret": key_txt.get("clientSecret") or mode_cfg.get("client_secret") or "",
        "account": mode_cfg.get("account") or "",
        "ciNo": key_txt.get("ciNo") or mode_cfg.get("ci_no") or "",
        "userInfo": key_txt.get("userInfo") or user_info,
    }
    if not settings.expose_local_defaults:
        secret_values = {key: "" for key in secret_values}

    return {
        "activeMode": active_mode,
        "runtimeMode": settings.mode,
        "baseUrl": mode_cfg.get("base_url") or _kb_b2b_base_url(settings),
        "clientId": secret_values["clientId"],
        "clientSecret": secret_values["clientSecret"],
        "scope": mode_cfg.get("scope") or kb_auth.DEFAULT_SCOPE,
        "account": secret_values["account"],
        "productCode": mode_cfg.get("product_code") or "01",
        "ciNo": secret_values["ciNo"],
        "userInfo": secret_values["userInfo"],
        "device": cfg.get("device", {}),
        "requests": _load_b2b_postman_defaults(settings) if settings.expose_local_defaults else {},
    }


def openapi_test_defaults(mode: str | None = None) -> dict[str, Any]:
    settings = get_runtime_settings()
    if mode:
        selected_mode = normalize_runtime_mode(mode)
        settings = replace(
            settings,
            mode=selected_mode,
            expose_local_defaults=settings.expose_local_defaults and selected_mode == "development",
        )

    return {
        "runtimeMode": settings.mode,
        "kb": {
            "b2b": _load_b2b_config_defaults(settings),
        },
    }
