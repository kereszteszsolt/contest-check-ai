# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Backend-only provider settings. Loading configuration performs no network I/O."""

import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from pydantic import SecretStr

from contest_check.authoring_contracts import ModelCatalog, ModelChoice

OPENROUTER_URL = "https://openrouter.ai/api/v1"
ISSUES = {
    "invalid_limits": "AI generation limits are invalid. Ask the local operator to correct them.",
    "ollama_url": "Ollama models are disabled: configure a valid Ollama base URL.",
    "ollama_model": "An invalid Ollama model slot was hidden. Ask the local operator to check it.",
    "openrouter_url": "OpenRouter models are disabled: use https://openrouter.ai/api/v1.",
    "openrouter_key": "OpenRouter models are disabled: the backend API key is missing or invalid.",
    "openrouter_model": "An invalid OpenRouter model slot was hidden. Check backend configuration.",
}
ERRORS = {
    "unknown_model": (
        400,
        "Choose an available configured model; arbitrary model names are refused.",
    ),
    "call_budget": (429, "The generation provider-call budget is exhausted."),
    "timeout": (504, "The selected model did not respond within the configured time limit."),
    "rate_limit": (503, "The selected provider is rate-limiting requests. Try again later."),
    "credentials": (503, "The selected provider rejected its backend credentials."),
    "provider_error": (503, "The selected provider is unavailable or rejected the request."),
    "invalid_output": (502, "The model did not return a valid structured task draft."),
    "output_size": (502, "The model response exceeded the configured output size limit."),
    "transport_policy": (503, "A provider request violated the configured endpoint policy."),
}


class ProviderError(ValueError):
    def __init__(self, code: str):
        self.code = code
        self.status, self.message = ERRORS[code]
        super().__init__(self.message)


@dataclass(frozen=True, repr=False)
class ModelSettings:
    choices: tuple[ModelChoice, ...]
    issues: tuple[str, ...]
    ollama_url: str = field(repr=False)
    openrouter_key: SecretStr = field(repr=False)
    timeout_seconds: float = 60
    max_calls: int = 6
    max_output_tokens: int = 4096

    def catalog(self) -> ModelCatalog:
        return ModelCatalog(
            models=list(self.choices), issues=[ISSUES[code] for code in self.issues]
        )

    def resolve(self, slot: str) -> ModelChoice:
        for choice in self.choices:
            if choice.slot == slot:
                return choice
        raise ProviderError("unknown_model")


def valid_ollama_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and parsed.port != 0
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
            and not any(ord(char) <= 32 or ord(char) >= 127 for char in value)
            and "\\" not in value
        )
    except ValueError:
        return False


def load_model_settings(environment: Mapping[str, str] | None = None) -> ModelSettings:
    env = os.environ if environment is None else environment
    issues = []
    try:
        timeout = float(env.get("AI_REQUEST_TIMEOUT_SECONDS", "60"))
        calls = int(env.get("AI_MAX_CALLS_PER_GENERATION", "6"))
        tokens = int(env.get("AI_MAX_OUTPUT_TOKENS", "4096"))
        if not (math.isfinite(timeout) and 1 <= timeout <= 120 and 1 <= calls <= 6):
            raise ValueError
        if not 256 <= tokens <= 8192:
            raise ValueError
    except (ValueError, OverflowError):
        timeout, calls, tokens = 60, 6, 4096
        issues.append("invalid_limits")
    ollama_url = env.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    key = env.get("OPENROUTER_API_KEY", "").strip()
    choices = []
    for provider in ("ollama", "openrouter"):
        slots = [env.get(f"{provider.upper()}_MODEL_{n}", "").strip() for n in range(1, 4)]
        if not any(slots):
            continue
        if provider == "ollama" and not valid_ollama_url(ollama_url):
            issues.append("ollama_url")
            continue
        if provider == "openrouter":
            if env.get("OPENROUTER_BASE_URL", OPENROUTER_URL).strip().rstrip("/") != OPENROUTER_URL:
                issues.append("openrouter_url")
                continue
            if not key or len(key) > 512 or not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
                issues.append("openrouter_key")
                continue
        seen = set()
        for index, model in enumerate(slots, 1):
            if not model or model in seen:
                continue
            valid = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model)
            if provider == "openrouter":
                valid = valid and "/" in model and not model.startswith("openrouter/")
                valid = valid and not model.endswith(":online")
            else:
                valid = valid and not model.endswith(":cloud")
            if not valid:
                issues.append(f"{provider}_model")
                continue
            seen.add(model)
            choices.append(ModelChoice(slot=f"{provider}:{index}", provider=provider, model=model))
    return ModelSettings(
        choices=tuple(choices) if "invalid_limits" not in issues else (),
        issues=tuple(dict.fromkeys(issues)),
        ollama_url=ollama_url,
        openrouter_key=SecretStr(key),
        timeout_seconds=timeout,
        max_calls=calls,
        max_output_tokens=tokens,
    )
