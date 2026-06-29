"""Runtime settings for the KB OpenAPI B2B test backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Mapping


RuntimeMode = Literal["development", "production"]

DEFAULT_DEV_ALLOWED_HOST_SUFFIXES = (
    "kbsec.com",
    "localhost",
    "127.0.0.1",
)
DEFAULT_PROD_ALLOWED_HOST_SUFFIXES = ("kbsec.com",)

DEFAULT_DEVELOPMENT_ENVIRONMENT = {
    "KB_B2B_BASE_URL": "https://dbaasapi.kbsec.com:32484",
}
DEFAULT_PRODUCTION_ENVIRONMENT = {
    "KB_B2B_BASE_URL": "https://baasapi.kbsec.com:32484",
}


def _clean(value: str | None) -> str:
    return (value or "").strip().strip("\"'")


def _split_csv(value: str | None) -> tuple[str, ...]:
    return tuple(item for item in (_clean(part) for part in (value or "").split(",")) if item)


def _truthy(value: str | None) -> bool:
    return _clean(value).lower() in {"1", "true", "yes", "y", "on"}


def _first_env(*keys: str, default: str) -> str:
    for key in keys:
        value = _clean(os.getenv(key))
        if value:
            return value
    return default


def normalize_runtime_mode(value: str | None) -> RuntimeMode:
    normalized = _clean(value).lower()
    if normalized in {"prod", "production", "real", "live", "operate", "operation"}:
        return "production"
    return "development"


@dataclass(frozen=True)
class OpenApiEnvironmentSettings:
    kb_b2b_base_url: str

    def as_public_dict(self) -> dict[str, str]:
        return {
            "kbB2bBaseUrl": self.kb_b2b_base_url,
        }


@dataclass(frozen=True)
class RuntimeSettings:
    mode: RuntimeMode
    host: str
    port: int
    cors_origins: tuple[str, ...]
    allowed_host_suffixes: tuple[str, ...]
    allow_http_targets: bool
    expose_local_defaults: bool
    docs_enabled: bool
    environments: Mapping[RuntimeMode, OpenApiEnvironmentSettings]

    @property
    def is_development(self) -> bool:
        return self.mode == "development"

    @property
    def kb_config_mode(self) -> Literal["dev", "prod"]:
        return "prod" if self.mode == "production" else "dev"

    @property
    def active_environment(self) -> OpenApiEnvironmentSettings:
        return self.environments[self.mode]


def _environment_settings(mode: RuntimeMode) -> OpenApiEnvironmentSettings:
    if mode == "production":
        prefixes = ("AIS_OPENAPI_PRODUCTION", "AIS_OPENAPI_PROD")
        defaults = DEFAULT_PRODUCTION_ENVIRONMENT
    else:
        prefixes = ("AIS_OPENAPI_DEVELOPMENT", "AIS_OPENAPI_DEV")
        defaults = DEFAULT_DEVELOPMENT_ENVIRONMENT

    return OpenApiEnvironmentSettings(
        kb_b2b_base_url=_first_env(
            *(f"{prefix}_KB_B2B_BASE_URL" for prefix in prefixes),
            default=defaults["KB_B2B_BASE_URL"],
        ),
    )


@lru_cache(maxsize=1)
def get_runtime_settings() -> RuntimeSettings:
    mode = normalize_runtime_mode(
        os.getenv("AIS_OPENAPI_MODE")
        or os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("NODE_ENV")
    )

    port = int(_clean(os.getenv("AIS_OPENAPI_BACKEND_PORT")) or "8020")
    cors_origins = _split_csv(os.getenv("AIS_OPENAPI_CORS_ORIGINS"))
    allowed_host_suffixes = _split_csv(os.getenv("AIS_OPENAPI_ALLOWED_HOST_SUFFIXES"))

    if not cors_origins and mode == "development":
        cors_origins = ("*",)
    if not allowed_host_suffixes:
        allowed_host_suffixes = (
            DEFAULT_DEV_ALLOWED_HOST_SUFFIXES
            if mode == "development"
            else DEFAULT_PROD_ALLOWED_HOST_SUFFIXES
        )

    environments: Mapping[RuntimeMode, OpenApiEnvironmentSettings] = {
        "development": _environment_settings("development"),
        "production": _environment_settings("production"),
    }

    expose_local_defaults = mode == "development" or _truthy(os.getenv("AIS_OPENAPI_EXPOSE_LOCAL_DEFAULTS"))

    return RuntimeSettings(
        mode=mode,
        host=_clean(os.getenv("AIS_OPENAPI_BACKEND_HOST")) or "0.0.0.0",
        port=port,
        cors_origins=cors_origins,
        allowed_host_suffixes=allowed_host_suffixes,
        allow_http_targets=mode == "development" or _truthy(os.getenv("AIS_OPENAPI_ALLOW_HTTP_TARGETS")),
        expose_local_defaults=expose_local_defaults,
        docs_enabled=mode == "development" or _truthy(os.getenv("AIS_OPENAPI_ENABLE_DOCS")),
        environments=environments,
    )
