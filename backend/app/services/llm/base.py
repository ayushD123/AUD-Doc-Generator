from abc import ABC, abstractmethod
from typing import Any


class LLMError(RuntimeError):
    """Base error for controlled LLM service failures."""


class LLMConfigurationError(LLMError):
    """Raised when the selected LLM provider is missing required settings."""


class LLMInputTooLongError(LLMError):
    """Raised when a prompt exceeds the configured input safeguard."""


class LLMInvalidJSONError(LLMError):
    """Raised when an LLM response cannot be parsed as strict JSON."""


DEFAULT_PROMPT_OVERHEAD_CHARS = 4000


class LLMService(ABC):
    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema_name: str | None = None,
    ) -> dict:
        raise NotImplementedError


def get_prompt_body_budget(
    max_input_chars: int,
    overhead_chars: int = DEFAULT_PROMPT_OVERHEAD_CHARS,
) -> int:
    """Return a safe budget for user prompt text before provider wrappers."""
    return max(1000, max_input_chars - overhead_chars)


def validate_prompt_length(
    *,
    prompt: str,
    system_prompt: str | None,
    max_input_chars: int,
) -> None:
    total_chars = len(prompt) + len(system_prompt or "")

    if total_chars > max_input_chars:
        raise LLMInputTooLongError(
            "LLM input is too large for the configured safeguard "
            f"({total_chars} chars > {max_input_chars} chars). "
            "Increase OCI_GENAI_MAX_INPUT_CHARS or reduce prompt evidence."
        )


def get_error_status_code(error: Exception) -> int | None:
    for attr_name in ("status", "status_code"):
        value = getattr(error, attr_name, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)

    response = getattr(error, "response", None)
    if response is not None:
        for attr_name in ("status", "status_code"):
            value = getattr(response, attr_name, None)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)

    return None


def get_error_code(error: Exception) -> str:
    code = getattr(error, "code", "")
    return str(code or "").strip().lower()


def is_retryable_llm_error(error: Exception) -> bool:
    status_code = get_error_status_code(error)
    if status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
        return True

    code = get_error_code(error)
    if code in {"429", "rate_limit_exceeded", "too_many_requests", "throttled"}:
        return True

    message = str(error).lower()
    retryable_fragments = (
        "request limit is exceeded",
        "rate limit",
        "too many requests",
        "throttled",
        "temporarily unavailable",
        "service unavailable",
        "timeout",
        "timed out",
    )
    return any(fragment in message for fragment in retryable_fragments)


def retry_delay_seconds(
    *,
    attempt_index: int,
    base_seconds: float,
    max_seconds: float,
) -> float:
    safe_base = max(float(base_seconds), 0.0)
    safe_max = max(float(max_seconds), 0.0)
    if safe_base <= 0 or safe_max <= 0:
        return 0.0

    return min(safe_base * (2 ** max(attempt_index, 0)), safe_max)


def positive_attempt_count(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 1

    return max(parsed, 1)
