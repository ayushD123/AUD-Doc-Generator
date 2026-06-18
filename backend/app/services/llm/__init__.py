from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.llm.base import (
    LLMConfigurationError,
    LLMError,
    LLMInputTooLongError,
    LLMInvalidJSONError,
    LLMService,
)
from app.services.llm.noop import NoOpLLMService
from app.services.llm.oci_genai_classic import OCIGenAIClassicLLMService
from app.services.llm.oci_responses import OCIResponsesLLMService


def build_llm_service(settings: Settings | None = None) -> LLMService:
    resolved_settings = settings or get_settings()
    provider = resolved_settings.LLM_PROVIDER.strip().lower()

    if provider == "none":
        return NoOpLLMService(settings=resolved_settings)

    if provider == "oci_responses":
        return OCIResponsesLLMService(settings=resolved_settings)

    if provider == "oci_genai_classic":
        return OCIGenAIClassicLLMService(settings=resolved_settings)

    raise LLMConfigurationError(
        "LLM_PROVIDER must be one of: none, oci_responses, oci_genai_classic."
    )


def get_llm_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMService:
    return build_llm_service(settings)


__all__ = [
    "LLMConfigurationError",
    "LLMError",
    "LLMInputTooLongError",
    "LLMInvalidJSONError",
    "LLMService",
    "NoOpLLMService",
    "OCIResponsesLLMService",
    "OCIGenAIClassicLLMService",
    "build_llm_service",
    "get_llm_service",
]
