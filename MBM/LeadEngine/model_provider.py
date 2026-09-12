"""Shared model-provider abstraction (factory model-routing primitive).

One opt-in home for "which model runs this task" so new LeadEngine code stops
hard-coding providers per file. Rules:

- Routing is a PURE function of (task profile, configured providers).
  No network, no credentials, no inference inside ``route()``.
- Availability comes from environment presence only (``*_API_KEY`` set,
  ``OLLAMA_ENABLED=true``). Never probe the network to decide.
- Secrets stay in the environment. :meth:`ModelProvider.describe` reports
  booleans, never values.
- Unconfigured providers FAIL LOUDLY (:class:`ProviderNotConfigured`).
  Nothing fabricates model output; deterministic fallback is explicit.
- Model names are defaults overridable via env (``GEMINI_MODEL``,
  ``GROQ_MODEL``, ``NVIDIA_MODEL``, ``OLLAMA_MODEL``) — never hard-code
  a model into business logic; pass it through here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Mapping, Optional, Set


class Provider(str, Enum):
    DETERMINISTIC = "deterministic"  # no LLM: rules/templates, always available
    LOCAL_OLLAMA = "local_ollama"  # private, on-machine (Ollama)
    GEMINI = "gemini"  # Google AI Studio / Generative Language API
    GROQ = "groq"  # low-latency LPU inference
    NVIDIA = "nvidia"  # NVIDIA NIM / build.nvidia.com
    VERTEX_GEMMA = "vertex_gemma"  # Gemma on Vertex AI (ADC, dedicated endpoint optional)
    ANTHROPIC = "anthropic"  # Anthropic Claude
    QWEN = "qwen"  # Qwen models (usually via OpenAI compatible API or HuggingFace)
    MISTRAL = "mistral"  # Mistral AI models


# Vertex/Gemma target architecture (env-driven; see vertex_status()).
# No endpoint is provisioned by this module — it only resolves configuration
# and serves through an operator-provisioned endpoint when present.
VERTEX_DEFAULTS = {
    "location": "europe-west4",
    "model": "gemma-4-12b",  # override via GEMMA_MODEL when the fleet publishes the id
}


DEFAULT_MODELS: Dict[str, str] = {
    Provider.GEMINI.value: "gemini-2.0-flash",
    Provider.GROQ.value: "llama-3.3-70b-versatile",
    Provider.NVIDIA.value: "meta/llama-3.3-70b-instruct",
    Provider.LOCAL_OLLAMA.value: "qwen2.5-coder:7b",
    Provider.VERTEX_GEMMA.value: VERTEX_DEFAULTS["model"],
    Provider.ANTHROPIC.value: "claude-3-5-sonnet-latest",
    Provider.QWEN.value: "qwen-max",
    Provider.MISTRAL.value: "mistral-large-latest",
}

_ENV_MODEL_KEYS = {
    Provider.GEMINI.value: "GEMINI_MODEL",
    Provider.GROQ.value: "GROQ_MODEL",
    Provider.NVIDIA.value: "NVIDIA_MODEL",
    Provider.LOCAL_OLLAMA.value: "OLLAMA_MODEL",
    Provider.VERTEX_GEMMA.value: "GEMMA_MODEL",
    Provider.ANTHROPIC.value: "ANTHROPIC_MODEL",
    Provider.QWEN.value: "QWEN_MODEL",
    Provider.MISTRAL.value: "MISTRAL_MODEL",
}

_ENV_AVAILABILITY = {
    Provider.GEMINI.value: ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    Provider.GROQ.value: ("GROQ_API_KEY",),
    Provider.NVIDIA.value: ("NVIDIA_API_KEY",),
    Provider.ANTHROPIC.value: ("ANTHROPIC_API_KEY",),
    Provider.QWEN.value: ("QWEN_API_KEY", "DASHSCOPE_API_KEY"),
    Provider.MISTRAL.value: ("MISTRAL_API_KEY",),
}


def vertex_config(env: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Resolved Vertex/Gemma configuration (values stay in env; see vertex_status)."""
    env = env if env is not None else os.environ
    project = str(env.get("VERTEX_PROJECT") or env.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    location = str(env.get("VERTEX_LOCATION") or env.get("GOOGLE_CLOUD_LOCATION")
                   or VERTEX_DEFAULTS["location"]).strip()
    return {
        "project": project,
        "location": location or VERTEX_DEFAULTS["location"],
        "endpoint": str(env.get("VERTEX_ENDPOINT") or env.get("GOOGLE_CLOUD_ENDPOINT") or "").strip(),
        "model": model_name(Provider.VERTEX_GEMMA.value, env),
    }


def vertex_status(env: Optional[Mapping[str, str]] = None) -> Dict[str, object]:
    """Operator readiness probe. Env + import signals only — no network, no
    deployment, no credential values. Anything False is a deployment blocker."""
    env = env if env is not None else os.environ
    cfg = vertex_config(env)
    try:
        import importlib.util as _u
        sdk = bool(_u.find_spec("google.cloud.aiplatform"))
    except Exception:
        sdk = False
    adc = bool(str(env.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip())
    blockers = []
    if not cfg["project"]:
        blockers.append("VERTEX_PROJECT (or GOOGLE_CLOUD_PROJECT) not set")
    if not sdk:
        blockers.append("google-cloud-aiplatform SDK not installed")
    if not adc:
        blockers.append("no GOOGLE_APPLICATION_CREDENTIALS pointer (ambient ADC unverified)")
    return {
        "configured": not blockers,
        "project_set": bool(cfg["project"]),
        "location": cfg["location"],
        "model": cfg["model"],
        "dedicated_endpoint_set": bool(cfg["endpoint"]),
        "adc_file_var_set": adc,
        "sdk_importable": sdk,
        "blockers": blockers,
    }


@dataclass(frozen=True)
class TaskProfile:
    """What the task needs. Keep mechanical; reasoning lives in agents."""

    task_kind: str = "general"  # e.g. classification, drafting, reasoning, vision
    modality: str = "text"  # text | image | audio | video
    need_tools: bool = False
    need_structured: bool = False
    privacy_sensitive: bool = False  # PII / lead data that must not leave the machine
    context_heavy: bool = False  # large artifacts, long histories
    latency_sensitive: bool = False  # dialer-speed paths
    offline_ok: bool = False  # durable background work (WorkManager-style)


def configured_providers(env: Optional[Mapping[str, str]] = None) -> Set[str]:
    """Providers usable right now, from env presence alone (no I/O)."""
    env = env if env is not None else os.environ
    out = {Provider.DETERMINISTIC.value}
    for provider, keys in _ENV_AVAILABILITY.items():
        if any(str(env.get(k) or "").strip() for k in keys):
            out.add(provider)
    flag = str(env.get("OLLAMA_ENABLED", "")).strip().lower()
    if flag in ("1", "true", "yes", "on"):
        out.add(Provider.LOCAL_OLLAMA.value)
    if vertex_config(env)["project"]:
        out.add(Provider.VERTEX_GEMMA.value)
    return out


def model_name(provider: str, env: Optional[Mapping[str, str]] = None) -> str:
    """Effective model id for a provider (env override wins over default)."""
    env = env if env is not None else os.environ
    key = _ENV_MODEL_KEYS.get(provider, "")
    override = str(env.get(key, "") or "").strip() if key else ""
    return override or DEFAULT_MODELS.get(provider, provider)


def route(profile: TaskProfile, available: Optional[Set[str]] = None) -> str:
    """Pick the cheapest capable provider. Pure function — no I/O.

    Priority: privacy/offline -> capability (tools/modality) ->
    latency/cost -> strongest configured cloud -> deterministic.
    """
    available = set(available) if available is not None else configured_providers()
    if Provider.DETERMINISTIC.value not in available:
        available = set(available) | {Provider.DETERMINISTIC.value}

    # 1. Privacy / offline: data must not leave the machine.
    if profile.privacy_sensitive or profile.offline_ok:
        if Provider.LOCAL_OLLAMA.value in available:
            return Provider.LOCAL_OLLAMA.value
        return Provider.DETERMINISTIC.value

    cloud = [p for p in (Provider.VERTEX_GEMMA.value, Provider.GEMINI.value,
                          Provider.GROQ.value, Provider.NVIDIA.value)
             if p in available]

    # 2. Capability: tool calling / structured output / non-text modality.
    if profile.need_tools or profile.need_structured or profile.modality != "text":
        for preference in (Provider.VERTEX_GEMMA.value, Provider.GEMINI.value,
                           Provider.GROQ.value, Provider.NVIDIA.value):
            if preference in cloud:
                return preference
        if Provider.LOCAL_OLLAMA.value in available:
            return Provider.LOCAL_OLLAMA.value
        return Provider.DETERMINISTIC.value

    # 3. Latency / cost: fast small-path inference first.
    if profile.latency_sensitive or profile.task_kind in ("classification", "scoring", "triage"):
        if Provider.GROQ.value in cloud:
            return Provider.GROQ.value

    # 4. Strongest configured cloud. Dedicated Vertex capacity first when
    # provisioned (EU data-residency story), else Gemini, Groq, NVIDIA.
    for preference in (Provider.VERTEX_GEMMA.value, Provider.GEMINI.value,
                       Provider.GROQ.value, Provider.NVIDIA.value):
        if preference in cloud:
            return preference
    if Provider.LOCAL_OLLAMA.value in available:
        return Provider.LOCAL_OLLAMA.value
    return Provider.DETERMINISTIC.value


class ProviderNotConfigured(RuntimeError):
    """Raised instead of fabricating output when no provider can serve."""


@dataclass
class ModelProvider:
    """Env-driven facade. Lazy: third-party SDKs import only on real use."""

    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))

    def describe(self) -> Dict[str, object]:
        """UI/audit-safe snapshot. Booleans only — never secret values."""
        available = configured_providers(self.env)
        return {
            "available": sorted(available),
            "models": {p: model_name(p, self.env) for p in sorted(available)
                       if p != Provider.DETERMINISTIC.value},
            "credentials_present": {
                "gemini": any(self.env.get(k) for k in _ENV_AVAILABILITY[Provider.GEMINI.value]),
                "groq": bool(self.env.get("GROQ_API_KEY")),
                "nvidia": bool(self.env.get("NVIDIA_API_KEY")),
                "ollama": "local_ollama" in available,
            },
        }

    def complete(self, prompt: str, profile: Optional[TaskProfile] = None,
                 **kwargs: object) -> Dict[str, object]:
        """Route then serve against the real provider SDK (lazy import).

        Raises ProviderNotConfigured when nothing can serve — never fakes
        output. Network happens only here, never in route()/describe().
        """
        profile = profile or TaskProfile()
        chosen = route(profile, configured_providers(self.env))
        if chosen == Provider.DETERMINISTIC.value:
            raise ProviderNotConfigured(
                f"no model provider configured for this task (kind={profile.task_kind}, "
                f"modality={profile.modality}); set GEMINI_API_KEY / GROQ_API_KEY / "
                "NVIDIA_API_KEY or OLLAMA_ENABLED=true"
            )
        if chosen == Provider.GEMINI.value:
            return self._serve_gemini(prompt, **kwargs)
        if chosen == Provider.GROQ.value:
            return self._serve_groq(prompt, **kwargs)
        if chosen == Provider.VERTEX_GEMMA.value:
            return self._serve_vertex_gemma(prompt, **kwargs)
        if chosen == Provider.ANTHROPIC.value:
            return self._serve_anthropic(prompt, **kwargs)
        if chosen == Provider.MISTRAL.value:
            return self._serve_mistral(prompt, **kwargs)
        if chosen == Provider.QWEN.value:
            return self._serve_qwen(prompt, **kwargs)
        raise ProviderNotConfigured(
            f"provider '{chosen}' is configured but has no transport attached yet"
        )

    def _serve_gemini(self, prompt: str, **kwargs: object) -> Dict[str, object]:
        from google import genai  # lazy: only on real use

        key = str(self.env.get("GEMINI_API_KEY") or self.env.get("GOOGLE_API_KEY") or "")
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model_name(Provider.GEMINI.value, self.env), contents=prompt, **kwargs
        )
        return {"provider": Provider.GEMINI.value,
                "model": model_name(Provider.GEMINI.value, self.env),
                "text": getattr(response, "text", ""), "served": True}

    def _serve_groq(self, prompt: str, **kwargs: object) -> Dict[str, object]:
        from groq import Groq  # lazy: only on real use

        client = Groq(api_key=str(self.env.get("GROQ_API_KEY") or ""))
        completion = client.chat.completions.create(
            model=model_name(Provider.GROQ.value, self.env),
            messages=[{"role": "user", "content": prompt}], **kwargs
        )
        return {"provider": Provider.GROQ.value,
                "model": model_name(Provider.GROQ.value, self.env),
                "text": completion.choices[0].message.content, "served": True}

    def _serve_vertex_gemma(self, prompt: str, **kwargs: object) -> Dict[str, object]:
        """Serve via an operator-provisioned Vertex AI endpoint (ADC auth).

        Never provisions infrastructure. Requires VERTEX_PROJECT (+ ADC) and
        VERTEX_ENDPOINT; without them it raises ProviderNotConfigured with the
        exact blocker instead of failing obscurely at the SDK layer.
        """
        cfg = vertex_config(self.env)
        if not cfg["project"]:
            raise ProviderNotConfigured("VERTEX_PROJECT (or GOOGLE_CLOUD_PROJECT) not set")
        if not cfg["endpoint"]:
            raise ProviderNotConfigured(
                "VERTEX_ENDPOINT not provisioned: deploy the Gemma model to a Vertex "
                f"endpoint in {cfg['location']} first (no auto-provisioning by design)"
            )
        try:
            from google.cloud import aiplatform  # lazy: only on real use
        except Exception as exc:
            raise ProviderNotConfigured(
                "google-cloud-aiplatform SDK not installed"
            ) from exc
        aiplatform.init(project=cfg["project"], location=cfg["location"])
        endpoint = aiplatform.Endpoint(cfg["endpoint"])
        response = endpoint.predict(instances=[{"prompt": prompt}], **kwargs)
        predictions = list(getattr(response, "predictions", []) or [])
        text = ""
        if predictions:
            first = predictions[0]
            text = first if isinstance(first, str) else str(first)
        return {"provider": Provider.VERTEX_GEMMA.value, "model": cfg["model"],
                "endpoint": cfg["endpoint"], "text": text, "served": True}

    def _serve_anthropic(self, prompt: str, **kwargs: object) -> Dict[str, object]:
        try:
            import anthropic
        except Exception as exc:
            raise ProviderNotConfigured("anthropic SDK not installed") from exc

        client = anthropic.Anthropic(api_key=str(self.env.get("ANTHROPIC_API_KEY") or ""))
        response = client.messages.create(
            model=model_name(Provider.ANTHROPIC.value, self.env),
            max_tokens=kwargs.get("max_tokens", 1024),
            messages=[{"role": "user", "content": prompt}],
        )
        return {"provider": Provider.ANTHROPIC.value,
                "model": model_name(Provider.ANTHROPIC.value, self.env),
                "text": response.content[0].text, "served": True}

    def _serve_qwen(self, prompt: str, **kwargs: object) -> Dict[str, object]:
        # Utilizing OpenAI compatible SDK
        try:
            from openai import OpenAI
        except Exception as exc:
            raise ProviderNotConfigured("openai SDK not installed for Qwen fallback") from exc

        key = str(self.env.get("QWEN_API_KEY") or self.env.get("DASHSCOPE_API_KEY") or "")
        client = OpenAI(api_key=key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
        completion = client.chat.completions.create(
            model=model_name(Provider.QWEN.value, self.env),
            messages=[{"role": "user", "content": prompt}], **kwargs
        )
        return {"provider": Provider.QWEN.value,
                "model": model_name(Provider.QWEN.value, self.env),
                "text": completion.choices[0].message.content, "served": True}

    def _serve_mistral(self, prompt: str, **kwargs: object) -> Dict[str, object]:
        try:
            from mistralai import Mistral
        except Exception as exc:
            raise ProviderNotConfigured("mistralai SDK not installed") from exc

        client = Mistral(api_key=str(self.env.get("MISTRAL_API_KEY") or ""))
        response = client.chat.complete(
            model=model_name(Provider.MISTRAL.value, self.env),
            messages=[{"role": "user", "content": prompt}], **kwargs
        )
        return {"provider": Provider.MISTRAL.value,
                "model": model_name(Provider.MISTRAL.value, self.env),
                "text": response.choices[0].message.content, "served": True}
