from abc import ABC, abstractmethod


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
