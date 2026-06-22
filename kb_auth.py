"""KB Securities BaaS authentication helpers.

This module replaces the legacy auth surface used by the copied
strategy builder.  It implements the KB BaaS token flows found in
``sample/1.BaaS 2.0 Dev Sample.postman_collection.json`` and keeps a small
compatibility layer for the rest of the application while market/order APIs are
migrated.
"""

from __future__ import annotations

import base64
import json
import os
from collections import namedtuple
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
import yaml
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad


CONFIG_ROOT = Path(os.path.expanduser("~")) / "KB" / "config"
CONFIG_FILE = CONFIG_ROOT / "kb_devlp.yaml"
TOKEN_FILE = CONFIG_ROOT / f"KB{datetime.today().strftime('%Y%m%d')}.yaml"
MODE_FILE = CONFIG_ROOT / "KB_MODE"

DEFAULT_BASE_URL = "https://dbaasapi.kbsec.com:32484"
DEFAULT_SCOPE = "public security"
PBKDF2_ITERATIONS = 1526

KBTREnv = namedtuple(
    "KBTREnv",
    [
        "client_id",
        "client_secret",
        "access_token",
        "refresh_token",
        "base_url",
        "mode",
        "scope",
        "account",
        "my_acct",
        "my_prod",
        "my_url",
        "my_token",
    ],
)

_TRENV = KBTREnv("", "", "", "", DEFAULT_BASE_URL, "vps", DEFAULT_SCOPE, "", "", "01", DEFAULT_BASE_URL, "")
_cfg: dict[str, Any] = {}
_is_paper = True


def _ensure_config_root() -> None:
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)


def _default_config() -> dict[str, Any]:
    return {
        "dev": {
            "base_url": DEFAULT_BASE_URL,
            "client_id": "",
            "client_secret": "",
            "scope": DEFAULT_SCOPE,
            "account": "",
            "product_code": "01",
            "ci_no": "",
            "ci_secret": "",
            "user_info": "",
            "user_info_plain": "",
        },
        "prod": {
            "base_url": DEFAULT_BASE_URL,
            "client_id": "",
            "client_secret": "",
            "scope": DEFAULT_SCOPE,
            "account": "",
            "product_code": "01",
            "ci_no": "",
            "ci_secret": "",
            "user_info": "",
            "user_info_plain": "",
        },
        "device": {
            "udId": "UDID",
            "subChannel": "subChannel",
            "deviceModel": "Android",
            "deviceOs": "Android",
            "carrier": "KT",
            "connectionType": "..",
            "appName": "..",
            "appVersion": "..",
            "scrNo": "0000",
        },
    }


def create_config_template(path: Path = CONFIG_FILE) -> None:
    """Create a KB config template if it does not already exist."""
    _ensure_config_root()
    if not path.exists():
        path.write_text(
            yaml.safe_dump(_default_config(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


def load_config() -> dict[str, Any]:
    """Load KB config from env vars plus ``~/KB/config/kb_devlp.yaml``."""
    create_config_template()
    try:
        file_cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        file_cfg = {}

    cfg = _default_config()
    for section, values in file_cfg.items():
        if isinstance(values, dict) and isinstance(cfg.get(section), dict):
            cfg[section].update(values)
        else:
            cfg[section] = values

    # Environment variables are useful for containers and quick local testing.
    for mode, prefix in (("dev", "KB_DEV"), ("prod", "KB_PROD")):
        cfg[mode]["base_url"] = os.getenv(f"{prefix}_BASE_URL", cfg[mode]["base_url"])
        cfg[mode]["client_id"] = os.getenv(f"{prefix}_CLIENT_ID", cfg[mode]["client_id"])
        cfg[mode]["client_secret"] = os.getenv(
            f"{prefix}_CLIENT_SECRET", cfg[mode]["client_secret"]
        )
        cfg[mode]["account"] = os.getenv(f"{prefix}_ACCOUNT", cfg[mode]["account"])
        cfg[mode]["product_code"] = os.getenv(
            f"{prefix}_PRODUCT_CODE", cfg[mode].get("product_code", "01")
        )
        cfg[mode]["ci_no"] = os.getenv(f"{prefix}_CI_NO", cfg[mode]["ci_no"])
        cfg[mode]["ci_secret"] = os.getenv(f"{prefix}_CI_SECRET", cfg[mode]["ci_secret"])
        cfg[mode]["user_info"] = os.getenv(f"{prefix}_USER_INFO", cfg[mode]["user_info"])
        cfg[mode]["user_info_plain"] = os.getenv(
            f"{prefix}_USER_INFO_PLAIN", cfg[mode].get("user_info_plain", "")
        )

    cfg["device"]["udId"] = os.getenv("KB_UD_ID", cfg["device"]["udId"])
    cfg["device"]["subChannel"] = os.getenv("KB_SUB_CHANNEL", cfg["device"]["subChannel"])
    cfg["device"]["appName"] = os.getenv("KB_APP_NAME", cfg["device"]["appName"])
    cfg["device"]["appVersion"] = os.getenv("KB_APP_VERSION", cfg["device"]["appVersion"])

    global _cfg
    _cfg = cfg
    return cfg


def _normalize_mode(mode: str) -> str:
    # Keep the existing UI modes for now: vps means dev/paper, prod means prod.
    if mode in ("vps", "dev", "paper", "demo"):
        return "dev"
    if mode in ("prod", "real"):
        return "prod"
    raise ValueError("mode must be one of vps/dev or prod/real")


def _ui_mode(mode: str) -> str:
    return "prod" if _normalize_mode(mode) == "prod" else "vps"


def _device_header(cfg: dict[str, Any], *, hs_key: str | None = None) -> dict[str, str]:
    header = dict(cfg.get("device", {}))
    if hs_key is not None:
        header["hsKey"] = hs_key
    return header


def _post(path: str, payload: dict[str, Any], base_url: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload, ensure_ascii=False),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _extract_body(response_json: dict[str, Any]) -> dict[str, Any]:
    data_body = response_json.get("dataBody")
    if isinstance(data_body, dict):
        return data_body
    return response_json


def derive_user_info_key(ci_no: str, secret: str) -> tuple[bytes, bytes]:
    """Derive KB sample AES key/IV from CI number and secret.

    Java sample:
    - key = PBKDF2(ciNo, secret, 1526, 16)
    - iv = PBKDF2(secret, ciNo, 1526, 16)
    - AES/CBC/PKCS5Padding, Base64 output
    """
    key = PBKDF2(ci_no, secret.encode("utf-8"), dkLen=16, count=PBKDF2_ITERATIONS)
    iv = PBKDF2(secret, ci_no.encode("utf-8"), dkLen=16, count=PBKDF2_ITERATIONS)
    return key, iv


def encrypt_user_info(user_info: str, ci_no: str, secret: str) -> str:
    key, iv = derive_user_info_key(ci_no, secret)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(user_info.encode("utf-8"), AES.block_size))
    return base64.b64encode(encrypted).decode("ascii")


def resolve_user_info(mode_cfg: dict[str, Any], user_info_plain: str | None = None) -> str:
    """Return encrypted KB userInfo for ``baas_auth_issue``.

    ``user_info`` in the config is treated as an already encrypted Base64 value
    matching the Postman sample.  Use ``user_info_plain`` only when you want this
    module to derive the PBKDF2 key/IV and encrypt the value for you.
    """
    plain = user_info_plain or mode_cfg.get("user_info_plain", "")
    if plain:
        ci_no = mode_cfg.get("ci_no", "")
        ci_secret = mode_cfg.get("ci_secret", "")
        if not ci_no or not ci_secret:
            raise ValueError("ci_no and ci_secret are required to encrypt user_info_plain")
        return encrypt_user_info(plain, ci_no, ci_secret)
    return mode_cfg.get("user_info", "")


def save_token(
    access_token: str,
    refresh_token: str = "",
    expires_in: int | str | None = None,
    mode: str = "vps",
) -> None:
    _ensure_config_root()
    expires = datetime.now() + timedelta(seconds=int(expires_in or 3600))
    TOKEN_FILE.write_text(
        yaml.safe_dump(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires.isoformat(),
                "mode": _ui_mode(mode),
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def read_token() -> str | None:
    token_data = read_token_data()
    return token_data.get("access_token") if token_data else None


def read_token_data() -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(TOKEN_FILE.read_text(encoding="utf-8")) or {}
        expires_at = datetime.fromisoformat(data.get("expires_at", "1970-01-01T00:00:00"))
        if expires_at <= datetime.now():
            return None
        return data
    except Exception:
        return None


def clear_token() -> None:
    try:
        TOKEN_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def save_mode(mode: str) -> None:
    _ensure_config_root()
    MODE_FILE.write_text(_ui_mode(mode), encoding="utf-8")


def read_mode() -> str:
    try:
        mode = MODE_FILE.read_text(encoding="utf-8").strip()
        return mode if mode in ("vps", "prod") else "vps"
    except OSError:
        return "vps"


def delete_mode() -> None:
    try:
        MODE_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def auth(svr: str = "vps", grant_type: str = "client_credentials", **kwargs) -> str:
    """Authenticate with KB BaaS and initialize the runtime environment."""
    cfg = load_config()
    normalized = _normalize_mode(svr)
    ui_mode = _ui_mode(normalized)
    mode_cfg = cfg[normalized]

    client_id = mode_cfg.get("client_id", "")
    client_secret = mode_cfg.get("client_secret", "")
    base_url = mode_cfg.get("base_url", DEFAULT_BASE_URL)
    scope = mode_cfg.get("scope", DEFAULT_SCOPE)

    if not client_id or not client_secret:
        raise ValueError(
            f"KB {normalized} client_id/client_secret is missing. "
            f"Edit {CONFIG_FILE} or set KB_DEV_CLIENT_ID/KB_DEV_CLIENT_SECRET."
        )

    saved = read_token_data()
    if saved and saved.get("mode") == ui_mode:
        access_token = saved["access_token"]
        refresh_token = saved.get("refresh_token", "")
    else:
        if grant_type != "client_credentials":
            raise ValueError("Only client_credentials login is supported by this UI flow")
        token_body = issue_client_credentials_token(normalized)
        access_token = token_body.get("access_token") or token_body.get("accessToken") or ""
        refresh_token = token_body.get("refresh_token") or token_body.get("refreshToken") or ""
        expires_in = token_body.get("expires_in") or token_body.get("expiresIn") or 3600
        if not access_token:
            raise ValueError(f"KB token response did not contain access_token: {token_body}")
        save_token(access_token, refresh_token, expires_in, ui_mode)

    global _TRENV, _is_paper
    _is_paper = ui_mode == "vps"
    _TRENV = KBTREnv(
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token,
        refresh_token=refresh_token,
        base_url=base_url,
        mode=ui_mode,
        scope=scope,
        account=mode_cfg.get("account", ""),
        my_acct=mode_cfg.get("account", ""),
        my_prod=mode_cfg.get("product_code", "01"),
        my_url=base_url,
        my_token=access_token,
    )
    save_mode(ui_mode)
    return access_token


def issue_client_credentials_token(mode: str = "dev") -> dict[str, Any]:
    cfg = load_config()
    normalized = _normalize_mode(mode)
    mode_cfg = cfg[normalized]
    payload = {
        "dataHeader": _device_header(cfg),
        "dataBody": {
            "clientId": mode_cfg.get("client_id", ""),
            "clientSecret": mode_cfg.get("client_secret", ""),
            "grantType": "client_credentials",
            "scope": mode_cfg.get("scope", DEFAULT_SCOPE),
        },
    }
    return _extract_body(_post("/baas/v2/baas_token_issue", payload, mode_cfg["base_url"]))


def refresh_token(mode: str | None = None) -> dict[str, Any]:
    cfg = load_config()
    token_data = read_token_data() or {}
    ui_mode = mode or token_data.get("mode") or read_mode()
    normalized = _normalize_mode(ui_mode)
    mode_cfg = cfg[normalized]
    refresh = token_data.get("refresh_token") or _TRENV.refresh_token
    if not refresh:
        raise ValueError("No refresh token is available")
    payload = {
        "dataHeader": _device_header(cfg),
        "dataBody": {
            "refreshToken": refresh,
            "clientId": mode_cfg.get("client_id", ""),
            "clientSecret": mode_cfg.get("client_secret", ""),
            "grantType": "refresh_token",
            "scope": mode_cfg.get("scope", DEFAULT_SCOPE),
        },
    }
    body = _extract_body(_post("/baas/v2/baas_token_issue", payload, mode_cfg["base_url"]))
    access = body.get("access_token") or body.get("accessToken")
    new_refresh = body.get("refresh_token") or body.get("refreshToken") or refresh
    expires = body.get("expires_in") or body.get("expiresIn") or 3600
    if access:
        save_token(access, new_refresh, expires, ui_mode)
        auth(ui_mode)
    return body


def issue_authorization_code(mode: str = "dev", user_info_plain: str | None = None) -> dict[str, Any]:
    cfg = load_config()
    normalized = _normalize_mode(mode)
    mode_cfg = cfg[normalized]
    ci_no = mode_cfg.get("ci_no", "")
    encrypted = resolve_user_info(mode_cfg, user_info_plain)
    payload = {
        "dataHeader": _device_header(cfg, hs_key="body"),
        "dataBody": {
            "clientId": mode_cfg.get("client_id", ""),
            "ciNo": ci_no,
            "userInfo": encrypted,
            "infoType": "1",
        },
    }
    return _extract_body(_post("/baas/v2/baas_auth_issue", payload, mode_cfg["base_url"]))


def revoke_token(token: str | None = None, mode: str | None = None) -> dict[str, Any]:
    cfg = load_config()
    ui_mode = mode or _TRENV.mode or read_mode()
    normalized = _normalize_mode(ui_mode)
    mode_cfg = cfg[normalized]
    target_token = token or _TRENV.access_token or read_token()
    if not target_token:
        clear_token()
        return {"status": "no_token"}
    payload = {
        "dataHeader": _device_header(cfg),
        "dataBody": {
            "token": target_token,
            "clientId": mode_cfg.get("client_id", ""),
            "clientSecret": mode_cfg.get("client_secret", ""),
        },
    }
    body = _extract_body(_post("/baas/v2/baas_token_revoke", payload, mode_cfg["base_url"]))
    clear_token()
    return body


def getTREnv():
    return _TRENV


def isPaperTrading() -> bool:
    return _is_paper


def changeTREnv(token_key=None, svr: str = "vps", product: str | None = None):
    auth(svr=svr)


def _url_fetch(*args, **kwargs):
    raise NotImplementedError(
        "KB market/order API transport is not implemented yet. "
        "Authentication has been migrated; migrate data_fetcher/order_executor next."
    )


# Load config lazily but create a template early so users can discover the file.
try:
    load_config()
except Exception:
    _cfg = _default_config()
