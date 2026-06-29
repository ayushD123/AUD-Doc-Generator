from collections.abc import Iterable
from time import sleep
from typing import Any

from app.core.config import Settings, get_settings
from app.services.llm.base import (
    LLMConfigurationError,
    LLMError,
    LLMService,
    is_retryable_llm_error,
    positive_attempt_count,
    retry_delay_seconds,
    validate_prompt_length,
)
from app.services.llm.json_utils import parse_json_response
from app.services.llm.prompts import build_json_system_prompt

MAX_TOKENS_FIELD = "max_tokens"
MAX_COMPLETION_TOKENS_FIELD = "max_completion_tokens"


class OCIGenAIClassicLLMService(LLMService):
    provider_name = "oci_genai_classic"

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or self.build_client()
        self._sleep = sleep
        self._output_token_limit_field = self._initial_output_token_limit_field()

    def build_client(self) -> Any:
        self._require_setting("OCI_GENAI_REGION", self.settings.OCI_GENAI_REGION)
        self._require_setting("OCI_GENAI_MODEL_ID", self.settings.OCI_GENAI_MODEL_ID)
        self._require_setting(
            "OCI_GENAI_COMPARTMENT_OCID",
            self.settings.OCI_GENAI_COMPARTMENT_OCID,
        )

        try:
            import oci
        except ImportError as exc:
            raise LLMConfigurationError(
                "OCI Python SDK is required when LLM_PROVIDER=oci_genai_classic."
            ) from exc

        endpoint = (
            f"https://inference.generativeai.{self.settings.OCI_GENAI_REGION}."
            "oci.oraclecloud.com"
        )
        return oci.generative_ai_inference.GenerativeAiInferenceClient(
            config=self.build_oci_config(),
            service_endpoint=endpoint,
            retry_strategy=oci.retry.NoneRetryStrategy(),
            timeout=(10, self.settings.OCI_GENAI_TIMEOUT_SECONDS),
        )

    def build_oci_config(self) -> dict[str, Any]:
        try:
            import oci
        except ImportError as exc:
            raise LLMConfigurationError(
                "OCI Python SDK is required when LLM_PROVIDER=oci_genai_classic."
            ) from exc

        profile = self.settings.OCI_PROFILE or "DEFAULT"
        config_file = self.settings.OCI_CONFIG_FILE

        return (
            oci.config.from_file(file_location=config_file, profile_name=profile)
            if config_file
            else oci.config.from_file(profile_name=profile)
        )

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

        response = self._chat_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )

        return self._extract_chat_text(response)

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema_name: str | None = None,
    ) -> dict:
        json_system_prompt = build_json_system_prompt(
            system_prompt=system_prompt,
            schema_name=schema_name,
        )
        return parse_json_response(
            self.generate_text(prompt=prompt, system_prompt=json_system_prompt)
        )

    def _chat_with_retry(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
    ) -> Any:
        attempts = positive_attempt_count(self.settings.OCI_GENAI_RETRY_MAX_ATTEMPTS)
        effective_temperature = temperature
        attempt_index = 0
        token_limit_fields_tried: set[str] = set()

        while attempt_index < attempts:
            output_token_limit_field = self._output_token_limit_field
            token_limit_fields_tried.add(output_token_limit_field)
            chat_detail = self._build_chat_detail(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=effective_temperature,
                output_token_limit_field=output_token_limit_field,
            )
            try:
                return self.client.chat(chat_detail)
            except Exception as error:
                token_limit_fallback = self._token_limit_fallback_for_error(
                    error,
                    current_field=output_token_limit_field,
                )
                if (
                    token_limit_fallback
                    and token_limit_fallback not in token_limit_fields_tried
                ):
                    self._output_token_limit_field = token_limit_fallback
                    continue

                if (
                    self._is_unsupported_temperature_error(error)
                    and effective_temperature != 1
                ):
                    effective_temperature = 1
                    continue

                is_last_attempt = attempt_index >= attempts - 1
                if is_last_attempt or not is_retryable_llm_error(error):
                    raise

                self._sleep(
                    retry_delay_seconds(
                        attempt_index=attempt_index,
                        base_seconds=self.settings.OCI_GENAI_RETRY_BASE_SECONDS,
                        max_seconds=self.settings.OCI_GENAI_RETRY_MAX_SECONDS,
                    )
                )
                attempt_index += 1

        raise LLMError("OCI Generative AI classic API retry loop ended unexpectedly.")

    def _build_chat_detail(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        output_token_limit_field: str | None = None,
    ) -> Any:
        try:
            import oci
        except ImportError as exc:
            raise LLMConfigurationError(
                "OCI Python SDK is required when LLM_PROVIDER=oci_genai_classic."
            ) from exc

        models = oci.generative_ai_inference.models
        chat_detail = models.ChatDetails()
        chat_request = models.GenericChatRequest()
        chat_request.api_format = models.BaseChatRequest.API_FORMAT_GENERIC
        chat_request.messages = self._build_messages(models, prompt, system_prompt)
        self._set_output_token_limit(
            chat_request=chat_request,
            token_limit=self.settings.OCI_GENAI_MAX_OUTPUT_TOKENS,
            output_token_limit_field=(
                output_token_limit_field or self._output_token_limit_field
            ),
        )
        chat_request.temperature = (
            self.settings.OCI_GENAI_TEMPERATURE
            if temperature is None
            else temperature
        )
        if hasattr(chat_request, "verbosity"):
            chat_request.verbosity = "MEDIUM"

        chat_detail.serving_mode = models.OnDemandServingMode(
            model_id=self.settings.OCI_GENAI_MODEL_ID
        )
        chat_detail.chat_request = chat_request
        chat_detail.compartment_id = self.settings.OCI_GENAI_COMPARTMENT_OCID
        return chat_detail

    def _initial_output_token_limit_field(self) -> str:
        return self._output_token_limit_field_for_model(
            self.settings.OCI_GENAI_MODEL_ID
        )

    @staticmethod
    def _output_token_limit_field_for_model(model_id: str | None) -> str:
        normalized_model_id = (model_id or "").strip().lower()

        if "llama-4" in normalized_model_id or "llama4" in normalized_model_id:
            return MAX_TOKENS_FIELD

        return MAX_COMPLETION_TOKENS_FIELD

    @staticmethod
    def _set_output_token_limit(
        *,
        chat_request: Any,
        token_limit: int,
        output_token_limit_field: str,
    ) -> None:
        if output_token_limit_field == MAX_TOKENS_FIELD:
            chat_request.max_tokens = token_limit
            return

        chat_request.max_completion_tokens = token_limit

    @staticmethod
    def _token_limit_fallback_for_error(
        error: Exception,
        *,
        current_field: str,
    ) -> str | None:
        error_text = str(error).lower()

        if (
            current_field == MAX_COMPLETION_TOKENS_FIELD
            and "maxcompletiontokens" in error_text
            and "maxtokens" in error_text
            and "unsupported parameter" in error_text
        ):
            return MAX_TOKENS_FIELD

        if (
            current_field == MAX_TOKENS_FIELD
            and "maxtokens" in error_text
            and "maxcompletiontokens" in error_text
            and "unsupported parameter" in error_text
        ):
            return MAX_COMPLETION_TOKENS_FIELD

        return None

    @staticmethod
    def _build_messages(
        models: Any,
        prompt: str,
        system_prompt: str | None,
    ) -> list[Any]:
        messages: list[Any] = []

        if system_prompt:
            messages.append(
                OCIGenAIClassicLLMService._build_message(
                    models=models,
                    role="SYSTEM",
                    text=system_prompt,
                )
            )

        messages.append(
            OCIGenAIClassicLLMService._build_message(
                models=models,
                role="USER",
                text=prompt,
            )
        )
        return messages

    @staticmethod
    def _build_message(models: Any, role: str, text: str) -> Any:
        content = models.TextContent()
        content.text = text
        message = models.Message()
        message.role = role
        message.content = [content]
        return message

    def _extract_chat_text(self, response: Any) -> str:
        data = getattr(response, "data", None)
        chat_response = getattr(data, "chat_response", None)
        candidates = [
            chat_response,
            data,
            response,
        ]

        for candidate in candidates:
            for text in self._iter_text_candidates(candidate):
                if text.strip():
                    return text

        response_summary = self._summarize_response_for_error(response)
        if response_summary.get("finish_reason") == "length":
            raise LLMError(
                "OCI Generative AI classic API stopped because the response hit "
                "the configured max output token limit. Increase "
                "OCI_GENAI_MAX_OUTPUT_TOKENS or reduce the requested JSON output. "
                f"Response summary: {response_summary}"
            )

        raise LLMError(
            "OCI Generative AI classic API returned no output text. "
            f"Response summary: {response_summary}"
        )

    @classmethod
    def _iter_text_candidates(
        cls,
        value: Any,
        visited: set[int] | None = None,
    ) -> Iterable[str]:
        if value is None:
            return

        if isinstance(value, str):
            yield value
            return

        visited = visited or set()
        value_id = id(value)
        if value_id in visited:
            return

        visited.add(value_id)

        if isinstance(value, dict):
            for key in (
                "text",
                "output_text",
                "content",
                "message",
                "messages",
                "choices",
                "chat_response",
                "data",
            ):
                if key in value:
                    yield from cls._iter_text_candidates(value[key], visited)
            return

        if isinstance(value, list | tuple):
            for item in value:
                yield from cls._iter_text_candidates(item, visited)
            return

        for attr in (
            "text",
            "output_text",
            "content",
            "message",
            "messages",
            "choices",
            "chat_response",
            "data",
        ):
            if hasattr(value, attr):
                yield from cls._iter_text_candidates(getattr(value, attr), visited)

    @classmethod
    def _summarize_response_for_error(cls, response: Any) -> dict[str, Any]:
        data = cls._safe_get(response, "data")
        chat_response = cls._safe_get(data, "chat_response")
        choices = cls._safe_get(chat_response, "choices")
        first_choice = choices[0] if choices else None

        return {
            "response_type": type(response).__name__,
            "data_type": type(data).__name__ if data is not None else None,
            "chat_response_type": (
                type(chat_response).__name__ if chat_response is not None else None
            ),
            "choices_count": len(choices) if choices is not None else None,
            "finish_reason": cls._safe_get(first_choice, "finish_reason"),
            "finish_details": cls._safe_get(first_choice, "finish_details"),
        }

    @staticmethod
    def _safe_get(value: Any, key: str) -> Any:
        if value is None:
            return None

        if isinstance(value, dict):
            return value.get(key)

        return getattr(value, key, None)

    @staticmethod
    def _is_unsupported_temperature_error(error: Exception) -> bool:
        error_text = str(error).lower()
        return (
            "temperature" in error_text
            and "unsupported value" in error_text
            and "default" in error_text
        )

    @staticmethod
    def _require_setting(setting_name: str, value: str | None) -> None:
        if not value:
            raise LLMConfigurationError(
                f"{setting_name} is required when LLM_PROVIDER=oci_genai_classic."
            )
