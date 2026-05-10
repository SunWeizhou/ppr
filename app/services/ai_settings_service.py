"""AI settings helpers for safe local provider configuration."""

from __future__ import annotations

import os
from typing import Mapping


SUPPORTED_PROVIDERS = {"none", "deepseek"}
KEEP_SENTINEL = "__keep__"
ENV_SENTINEL = "__env_var__"


def normalize_provider(value: str | None) -> str:
    provider = str(value or "none").strip().lower()
    if provider in ("", "disabled"):
        return "none"
    if provider in ("openai", "openai_compat", "openai-compatible"):
        raise ValueError("OpenAI-compatible provider is not implemented yet")
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    return provider


def mask_api_key(key: str) -> str:
    key = str(key or "").strip()
    if not key:
        return ""
    if len(key) <= 6:
        return key[:2] + "****" if len(key) > 2 else "****"
    return key[:3] + "..." + key[-4:]


def resolve_ai_env(environ: Mapping[str, str] | None = None) -> dict:
    if environ is None:
        environ = os.environ
    for name in ("STATDESK_AI_API_KEY", "DEEPSEEK_API_KEY"):
        value = str(environ.get(name, "") or "").strip()
        if value:
            return {
                "has_key": True,
                "source": "env",
                "env_var": name,
                "api_key": value,
            }
    return {"has_key": False, "source": "none", "env_var": "", "api_key": ""}


def build_ai_settings_context(ai_config: dict, environ: Mapping[str, str] | None = None) -> dict:
    env = resolve_ai_env(environ)
    provider = normalize_provider(ai_config.get("provider", "none"))
    stored_key = str(ai_config.get("api_key", "") or "")
    effective_has_key = env["has_key"] or bool(stored_key)
    effective_enabled = provider != "none" and effective_has_key
    return {
        "provider": provider,
        "base_url": ai_config.get("base_url") or "https://api.deepseek.com",
        "model": ai_config.get("model") or "deepseek-chat",
        "enabled": bool(ai_config.get("enabled")) and provider != "none",
        "effective_enabled": effective_enabled,
        "has_key": effective_has_key,
        "key_source": "none" if provider == "none" else (env["source"] if env["has_key"] else ("stored" if stored_key else "none")),
        "env_var": env["env_var"],
        "api_key": "" if env["has_key"] else mask_api_key(stored_key),
        "api_key_mask": bool(stored_key) and not env["has_key"],
        "using_env_var": env["has_key"] and provider != "none",
    }


def apply_ai_settings_payload(config_manager, data: dict) -> dict:
    provider = normalize_provider(data.get("provider", config_manager._ai.provider))
    raw_key = str(data.get("api_key", "") or "").strip()

    if provider == "none":
        config_manager._ai.provider = "none"
        config_manager._ai.api_key = ""
        config_manager._ai.enabled = False
    else:
        config_manager._ai.provider = provider
        if raw_key in (KEEP_SENTINEL, ENV_SENTINEL):
            pass
        elif raw_key:
            config_manager._ai.api_key = raw_key
            config_manager._ai.enabled = True
        else:
            config_manager._ai.api_key = ""
            config_manager._ai.enabled = False

    config_manager._ai.base_url = (
        str(data.get("base_url", config_manager._ai.base_url) or "").strip()
        or "https://api.deepseek.com"
    )
    config_manager._ai.model = (
        str(data.get("model", config_manager._ai.model) or "").strip()
        or "deepseek-chat"
    )
    config_manager.save()
    return build_ai_settings_context(config_manager.get_ai_config())


def resolve_test_api_key(data: dict, current_ai_config: dict, environ: Mapping[str, str] | None = None) -> str:
    raw_key = str(data.get("api_key", "") or "").strip()
    if raw_key == ENV_SENTINEL:
        return resolve_ai_env(environ)["api_key"]
    if raw_key == KEEP_SENTINEL:
        return str(current_ai_config.get("api_key", "") or "")
    return raw_key
