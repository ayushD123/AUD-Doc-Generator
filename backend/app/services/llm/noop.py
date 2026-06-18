from app.core.config import Settings, get_settings
from app.services.llm.base import LLMService, validate_prompt_length


class NoOpLLMService(LLMService):
    provider_name = "none"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> str:
        validate_prompt_length(
            prompt=prompt,
            system_prompt=system_prompt,
            max_input_chars=self.settings.OCI_GENAI_MAX_INPUT_CHARS,
        )
        return "LLM provider is disabled."

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema_name: str | None = None,
    ) -> dict:
        validate_prompt_length(
            prompt=prompt,
            system_prompt=system_prompt,
            max_input_chars=self.settings.OCI_GENAI_MAX_INPUT_CHARS,
        )
        return {
            "provider": self.provider_name,
            "status": "disabled",
        }
