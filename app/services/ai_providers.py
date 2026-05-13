"""AI analysis providers.

Providers are optional and must never require real API keys in tests. The
DeepSeek provider uses an injectable HTTP function so unit tests can validate
payloads without network access.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


ANALYSIS_FIELDS = (
    "one_sentence_summary",
    "problem",
    "method",
    "contribution",
    "limitations",
    "why_it_matters",
    "recommended_reading_level",
)

READING_LEVELS = {"ignore", "inbox"}

SYSTEM_PROMPT = (
    "You are a research paper triage assistant. Analyze the paper for a machine "
    "learning / statistics researcher. Return strict JSON only. Do not include markdown."
)


class ProviderError(RuntimeError):
    pass


def fallback_analysis(*, reading_level: str = "inbox") -> dict:
    return {
        "one_sentence_summary": "",
        "problem": "",
        "method": "",
        "contribution": "",
        "limitations": "",
        "why_it_matters": "",
        "recommended_reading_level": reading_level,
    }


def normalize_reading_level(value) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "save": "inbox",
        "saved": "inbox",
        "skim": "inbox",
        "deep_read": "inbox",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in READING_LEVELS else "inbox"


def normalize_analysis_result(result: dict | None) -> dict:
    normalized = fallback_analysis()
    if isinstance(result, dict):
        for key in ANALYSIS_FIELDS:
            if result.get(key):
                normalized[key] = str(result[key])
    normalized["recommended_reading_level"] = normalize_reading_level(
        normalized.get("recommended_reading_level")
    )
    return normalized


class NoProvider:
    model_name = "none"

    def analyze(self, paper, user_profile=None, recommendation_context=None):
        return fallback_analysis()

    def chat(self, messages, *, page_context=None):
        raise ProviderError("No AI provider configured")


class FakeProvider:
    model_name = "fake-test-provider"

    def analyze(self, paper, user_profile=None, recommendation_context=None):
        title = paper.get("title") or "Untitled paper"
        abstract = paper.get("abstract") or paper.get("summary") or ""
        return {
            "one_sentence_summary": f"Fake analysis for {title}.",
            "problem": "Identifies the research problem from the paper metadata.",
            "method": "Summarizes the method using deterministic test-only logic.",
            "contribution": "Provides a stable generated analysis for local tests.",
            "limitations": "This fake provider does not inspect full paper text.",
            "why_it_matters": abstract[:160] or "It may matter based on the recommendation context.",
            "recommended_reading_level": "skim",
        }

    def chat(self, messages, *, page_context=None):
        last = ""
        for item in reversed(messages or []):
            if item.get("role") == "user":
                last = item.get("content", "")
                break
        return f"Fake chat reply for: {last}"


class _BaseProvider:
    """Shared implementation for OpenAI-compatible providers.

    Provider-specific strings (error messages, provider name) are
    configured in subclasses via ``_provider_name`` and ``_model``.
    """

    model_name = "generic-openai-compatible"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout: int = 60,
        post_json=None,
    ):
        if not api_key:
            raise ValueError(f"{self._provider_name} API key is required")
        self.api_key = api_key
        self.base_url = str(base_url or "https://api.deepseek.com").rstrip("/")
        self.model = model or "deepseek-chat"
        self.model_name = self.model
        self.timeout = timeout
        self._post_json = post_json or self._default_post_json

    def analyze(self, paper, user_profile=None, recommendation_context=None):
        payload = self._build_payload(
            paper,
            user_profile=user_profile,
            recommendation_context=recommendation_context,
            include_response_format=True,
        )
        try:
            response = self._request(payload)
        except ProviderError as exc:
            if not self._looks_like_response_format_error(exc):
                raise
            fallback_payload = self._build_payload(
                paper,
                user_profile=user_profile,
                recommendation_context=recommendation_context,
                include_response_format=False,
            )
            response = self._request(fallback_payload)
        content = self._extract_message_content(response)
        return normalize_analysis_result(self._parse_json_content(content))

    def chat(self, messages, *, page_context=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
        }
        response = self._request(payload)
        return self._extract_message_content(response).strip()

    def _build_payload(
        self,
        paper,
        *,
        user_profile=None,
        recommendation_context=None,
        include_response_format: bool = True,
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": self._build_user_prompt(
                        paper,
                        user_profile=user_profile,
                        recommendation_context=recommendation_context,
                    ),
                },
            ],
            "temperature": 0.2,
        }
        if include_response_format:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _build_user_prompt(self, paper, *, user_profile=None, recommendation_context=None) -> str:
        return "\n".join(
            [
                "Title:",
                str(paper.get("title", "")),
                "",
                "Authors:",
                str(paper.get("authors", "")),
                "",
                "Abstract:",
                str(paper.get("abstract") or paper.get("summary") or ""),
                "",
                "User research profile:",
                json.dumps(user_profile or {}, ensure_ascii=False, sort_keys=True),
                "",
                "Recommendation context:",
                json.dumps(recommendation_context or {}, ensure_ascii=False, sort_keys=True),
                "",
                "Return JSON with keys: one_sentence_summary, problem, method, "
                "contribution, limitations, why_it_matters, recommended_reading_level. "
                "recommended_reading_level must be one of ignore, inbox.",
            ]
        )

    def _request(self, payload: dict) -> dict:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            return self._post_json(url, payload, headers=headers, timeout=self.timeout)
        except Exception as exc:
            raise ProviderError(self._redact(f"{self._provider_name} request failed: {exc}")) from exc

    @classmethod
    def _default_post_json(cls, url, payload, *, headers, timeout):
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 — user-configured HTTPS endpoint
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"HTTP {exc.code}: {body}") from exc
        except json.JSONDecodeError as exc:
            raise ProviderError(f"{cls._provider_name} returned non-JSON HTTP response") from exc

    def _redact(self, message: str) -> str:
        return str(message).replace(self.api_key, "[redacted]")

    @staticmethod
    def _looks_like_response_format_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return "response_format" in text or "json_object" in text

    @classmethod
    def _extract_message_content(cls, response: dict) -> str:
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{cls._provider_name} response did not include message content") from exc

    @classmethod
    def _parse_json_content(cls, content: str) -> dict:
        text = str(content or "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError as exc:
                    raise ProviderError(f"{cls._provider_name} returned malformed analysis JSON") from exc
            raise ProviderError(f"{cls._provider_name} returned malformed analysis JSON") from None


class OpenAICompatibleProvider(_BaseProvider):
    _provider_name = "OpenAI-compatible"
    model_name = "openai-compatible"


class DeepSeekProvider(_BaseProvider):
    _provider_name = "DeepSeek"
    model_name = "deepseek-chat"


def build_ai_provider_from_env():
    # 1) Check environment variables first. OPENAI_COMPATIBLE_API_KEY is the
    # provider-neutral name; older DeepSeek-compatible names remain supported.
    openai_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
    if openai_key:
        return OpenAICompatibleProvider(
            api_key=openai_key,
            base_url=os.getenv("OPENAI_COMPATIBLE_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("OPENAI_COMPATIBLE_MODEL") or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        )
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("STATDESK_AI_API_KEY")
    if api_key:
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        )

    # 2) Fall back to user_profile.json via config_manager
    try:
        from config_manager import get_config

        ai_config = get_config().get_ai_config()
        if ai_config.get("enabled") and ai_config.get("api_key"):
            provider_name = ai_config.get("provider", "none")
            if provider_name in ("openai_compatible", "deepseek"):
                return OpenAICompatibleProvider(
                    api_key=ai_config["api_key"],
                    base_url=ai_config.get("base_url", "https://api.deepseek.com"),
                    model=ai_config.get("model", "deepseek-chat"),
                )
    except Exception:
        import logging
        logging.getLogger(__name__).debug(
            "Could not load AI config from user_profile.json", exc_info=True
        )

    return NoProvider()
