"""
AIService — multi-provider AI interface with automatic fallback chain.

Provider priority (first available key/server wins):
  1. Anthropic Claude Fable 5  — best quality, needs ANTHROPIC_API_KEY
  2. Google Gemini 2.0 Flash   — free tier, needs GEMINI_API_KEY from aistudio.google.com
  3. Ollama (qwen2.5:7b)       — local & free, needs: ollama pull qwen2.5:7b
  4. OpenAI gpt-4o-mini        — needs OPENAI_API_KEY (already in .env)

Fable 5 specifics:
  - Thinking always on — budget_tokens is rejected with 400. Use output_config.effort.
  - Temperature omitted — not accepted when thinking is active.
  - stop_reason="refusal" → server-side fallback to Opus 4.8 rescues transparently.
  - All calls stream via .stream()/.get_final_message() to avoid timeout on long reasoning.

Non-Anthropic providers use the OpenAI-compatible API surface (tools/function calling).
complete_with_thinking() degrades gracefully on Gemini/Ollama (returns answer, thinking=None).
"""
from __future__ import annotations

import json
import time
import random
from typing import Any

from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("services.ai")

_RETRYABLE = (429, 529)

_FABLE_MODELS = frozenset({"claude-fable-5", "claude-mythos-5", "claude-mythos-preview"})
_FALLBACK_BETA = "server-side-fallback-2026-06-01"
_FALLBACK_MODEL = "claude-opus-4-8"


def _is_fable(model: str) -> bool:
    return model in _FABLE_MODELS


class AIService:
    def __init__(self):
        self._anthropic = None
        self._openai_client = None
        self._gemini_client = None
        self._ollama_client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system: str | None = None,
        cache_system: bool | None = None,
    ) -> str | None:
        """Send a prompt and return text. Tries providers in priority order."""
        _model = model or settings.ai_primary_model
        _max_tokens = max_tokens or settings.ai_max_tokens
        _temp = temperature if temperature is not None else settings.ai_temperature
        _cache = cache_system if cache_system is not None else settings.ai_cache_system_prompt

        for provider in self._provider_order():
            try:
                if provider == "anthropic":
                    return self._anthropic_complete(prompt, _model, _max_tokens, _temp, system, _cache)
                elif provider == "gemini":
                    return self._compat_complete(prompt, settings.gemini_model, _max_tokens, _temp, system, self._get_gemini())
                elif provider == "ollama":
                    return self._compat_complete(prompt, settings.ollama_model, _max_tokens, _temp, system, self._get_ollama())
                elif provider == "openai":
                    return self._compat_complete(prompt, "gpt-4o-mini", _max_tokens, _temp, system, self._get_openai())
            except Exception as exc:
                logger.warning(f"[{provider}] complete failed: {exc} — trying next")

        logger.error("All AI providers failed")
        return None

    def complete_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model: str | None = None,
        system: str | None = None,
        cache_system: bool | None = None,
    ) -> dict | None:
        """Return a structured dict matching the JSON schema. Tries all providers."""
        _model = model or settings.ai_primary_model
        _cache = cache_system if cache_system is not None else settings.ai_cache_system_prompt

        for provider in self._provider_order():
            try:
                if provider == "anthropic":
                    return self._anthropic_structured(prompt, schema, _model, system, _cache)
                elif provider == "gemini":
                    return self._compat_structured(prompt, schema, settings.gemini_model, system, self._get_gemini())
                elif provider == "ollama":
                    return self._compat_structured(prompt, schema, settings.ollama_model, system, self._get_ollama())
                elif provider == "openai":
                    return self._compat_structured(prompt, schema, "gpt-4o-mini", system, self._get_openai())
            except Exception as exc:
                logger.warning(f"[{provider}] structured failed: {exc} — trying next")

        logger.error("All AI providers failed for structured completion")
        return None

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        model: str | None = None,
        system: str | None = None,
    ) -> dict | None:
        """Alias for complete_structured — preferred name in agents."""
        return self.complete_structured(prompt, schema, model=model, system=system)

    def complete_with_thinking(
        self,
        prompt: str,
        thinking_budget: int | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
    ) -> tuple[str | None, str | None]:
        """
        Deep reasoning call. Returns (answer_text, thinking_text).

        Fable 5: thinking always on, depth = output_config.effort (AI_EFFORT_LEVEL).
        Opus 4.8: thinking: {type: "adaptive"} — no budget_tokens.
        Gemini / Ollama / OpenAI: falls back to plain complete, thinking=None.
        """
        if not settings.ai_extended_thinking:
            result = self.complete(prompt, model=model, max_tokens=max_tokens, system=system)
            return result, None

        _model = model or settings.ai_primary_model
        _max_tokens = max_tokens or settings.ai_max_tokens

        if self._has_anthropic():
            try:
                return self._anthropic_thinking(prompt, _model, _max_tokens, thinking_budget, system)
            except Exception as exc:
                logger.warning(f"[anthropic/thinking] failed: {exc} — falling back to plain complete")

        result = self.complete(prompt, model=model, max_tokens=max_tokens, system=system)
        return result, None

    def embed(self, text: str) -> list[float] | None:
        """Generate text embeddings. Tries Gemini (free) → OpenAI (paid) → None."""
        # Gemini free-tier embeddings first (768-dim, text-embedding-004, no cost)
        if self._has_gemini():
            try:
                response = self._get_gemini().embeddings.create(
                    model="text-embedding-004",
                    input=text[:8000],
                )
                return response.data[0].embedding
            except Exception as exc:
                logger.warning(f"[gemini/embed] failed: {exc} — trying OpenAI")

        # OpenAI fallback (1536-dim, paid)
        if self._has_openai():
            try:
                response = self._get_openai().embeddings.create(
                    model="text-embedding-3-small",
                    input=text[:8000],
                )
                return response.data[0].embedding
            except Exception as exc:
                logger.warning(f"[openai/embed] failed: {exc}")

        logger.error("All embedding providers failed")
        return None

    # ------------------------------------------------------------------
    # Anthropic implementation
    # ------------------------------------------------------------------

    def _anthropic_complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        system: str | None,
        cache_system: bool,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = self._maybe_cached_system(system, cache_system)
        if _is_fable(model):
            kwargs["betas"] = [_FALLBACK_BETA]
            kwargs["fallbacks"] = [{"model": _FALLBACK_MODEL}]
        else:
            kwargs["temperature"] = temperature

        message = self._stream_complete(**kwargs)
        if message.stop_reason == "refusal":
            logger.warning(f"[{model}] Refusal — returning empty string")
            return ""
        return message.content[0].text if message.content else ""

    def _anthropic_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model: str,
        system: str | None,
        cache_system: bool,
    ) -> dict | None:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "tools": [{
                "name": "structured_output",
                "description": "Return structured data matching the schema",
                "input_schema": schema,
            }],
            "tool_choice": {"type": "tool", "name": "structured_output"},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = self._maybe_cached_system(system, cache_system)
        if _is_fable(model):
            kwargs["betas"] = [_FALLBACK_BETA]
            kwargs["fallbacks"] = [{"model": _FALLBACK_MODEL}]

        message = self._stream_complete(**kwargs)
        if message.stop_reason == "refusal":
            logger.warning(f"[{model}] Refusal on structured request")
            return None
        for block in message.content:
            if block.type == "tool_use" and block.name == "structured_output":
                return block.input
        return None

    def _anthropic_thinking(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        thinking_budget: int | None,
        system: str | None,
    ) -> tuple[str | None, str | None]:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        if _is_fable(model):
            kwargs["output_config"] = {"effort": settings.ai_effort_level}
            kwargs["betas"] = [_FALLBACK_BETA]
            kwargs["fallbacks"] = [{"model": _FALLBACK_MODEL}]
        else:
            _budget = thinking_budget or settings.ai_thinking_budget
            kwargs["max_tokens"] = max(_budget + 2048, max_tokens)
            kwargs["thinking"] = {"type": "adaptive"}

        message = self._stream_complete(**kwargs)
        if message.stop_reason == "refusal":
            logger.warning(f"[{model}] Refusal on thinking request")
            return None, None

        answer: str | None = None
        thinking: str | None = None
        for block in message.content:
            if block.type == "thinking":
                thinking = getattr(block, "thinking", None) or getattr(block, "summary", None)
            elif block.type == "text":
                answer = block.text
        return answer, thinking

    # ------------------------------------------------------------------
    # OpenAI-compatible implementation (Gemini, Ollama, OpenAI)
    # ------------------------------------------------------------------

    def _compat_complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        system: str | None,
        client: Any,
    ) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def _compat_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model: str,
        system: str | None,
        client: Any,
    ) -> dict | None:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        tools = [{
            "type": "function",
            "function": {
                "name": "structured_output",
                "description": "Return structured data matching the schema",
                "parameters": schema,
            },
        }]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=4096,
        )
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            return json.loads(tool_calls[0].function.arguments)
        content = (response.choices[0].message.content or "").strip()
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                import re as _re
                match = _re.search(r'\{[^{}]*\}', content, _re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass
        return None

    # ------------------------------------------------------------------
    # Provider routing
    # ------------------------------------------------------------------

    def _provider_order(self) -> list[str]:
        """
        Return providers to try in priority order.
        Free providers (Gemini, Ollama) preferred over paid (Anthropic, OpenAI).
        """
        order: list[str] = []
        if self._has_gemini():
            order.append("gemini")
        order.append("ollama")   # always include — fails fast (ConnectionRefused) if not running
        if self._has_anthropic():
            order.append("anthropic")
        if self._has_openai():
            order.append("openai")
        return order

    def _has_anthropic(self) -> bool:
        k = settings.anthropic_api_key
        return bool(k) and "sk-ant-..." not in k and k != ""

    def _has_gemini(self) -> bool:
        k = settings.gemini_api_key
        return bool(k) and k != ""

    def _has_openai(self) -> bool:
        k = settings.openai_api_key
        return bool(k) and "sk-..." not in k and k != ""

    # ------------------------------------------------------------------
    # Client factories
    # ------------------------------------------------------------------

    def _stream_complete(self, **kwargs) -> Any:
        client = self._get_anthropic()
        def _call():
            with client.messages.stream(**kwargs) as stream:
                return stream.get_final_message()
        return self._retry(_call)

    def _maybe_cached_system(self, system: str, cache: bool) -> Any:
        if not cache:
            return system
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def _retry(self, fn, max_attempts: int = 3, base_delay: float = 1.0):
        for attempt in range(max_attempts):
            try:
                return fn()
            except Exception as exc:
                status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
                is_retryable = status in _RETRYABLE or "rate" in str(exc).lower()
                if is_retryable and attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(f"Retryable error ({exc}), retry {attempt + 1} in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                raise

    def _get_anthropic(self):
        if self._anthropic is None:
            import anthropic
            self._anthropic = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._anthropic

    def _get_gemini(self):
        if self._gemini_client is None:
            import openai
            self._gemini_client = openai.OpenAI(
                api_key=settings.gemini_api_key,
                base_url=settings.gemini_base_url,
            )
        return self._gemini_client

    def _get_ollama(self):
        if self._ollama_client is None:
            import openai
            self._ollama_client = openai.OpenAI(
                api_key="ollama",
                base_url=settings.ollama_base_url,
            )
        return self._ollama_client

    def _get_openai(self):
        if self._openai_client is None:
            import openai
            self._openai_client = openai.OpenAI(api_key=settings.openai_api_key)
        return self._openai_client
