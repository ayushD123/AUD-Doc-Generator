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


class OCIResponsesLLMService(LLMService):
    provider_name = "oci_responses"

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or self.build_client()
        self._sleep = sleep

    def build_client(self) -> Any:
        self._require_setting("OCI_GENAI_REGION", self.settings.OCI_GENAI_REGION)
        self._require_setting("OCI_GENAI_MODEL_ID", self.settings.OCI_GENAI_MODEL_ID)

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMConfigurationError(
                "OpenAI Python SDK is required when LLM_PROVIDER=oci_responses."
            ) from exc

        return OpenAI(
            api_key=self.settings.OCI_GENAI_API_KEY or "oci",
            base_url=self.base_url,
            timeout=self.settings.OCI_GENAI_TIMEOUT_SECONDS,
        )

    @property
    def base_url(self) -> str:
        region = self.settings.OCI_GENAI_REGION
        return f"https://inference.generativeai.{region}.oci.oraclecloud.com/openai/v1"

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
        self._require_setting("OCI_GENAI_MODEL_ID", self.settings.OCI_GENAI_MODEL_ID)

        response = self._create_response_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return self._extract_output_text(response)

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

    def _create_response_with_retry(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
    ) -> Any:
        attempts = positive_attempt_count(self.settings.OCI_GENAI_RETRY_MAX_ATTEMPTS)

        for attempt_index in range(attempts):
            try:
                return self.client.responses.create(
                    **self._build_response_payload(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                    )
                )
            except Exception as error:
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

        raise LLMError("OCI Responses API retry loop ended unexpectedly.")

    def _build_response_payload(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
    ) -> dict[str, Any]:
        input_payload: str | list[dict[str, str]]

        if system_prompt:
            input_payload = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
        else:
            input_payload = prompt

        payload: dict[str, Any] = {
            "model": self.settings.OCI_GENAI_MODEL_ID,
            "input": input_payload,
            "temperature": (
                self.settings.OCI_GENAI_TEMPERATURE
                if temperature is None
                else temperature
            ),
            "max_output_tokens": self.settings.OCI_GENAI_MAX_OUTPUT_TOKENS,
        }

        if self.settings.OCI_GENAI_PROJECT_OCID:
            payload["extra_body"] = {
                "project_id": self.settings.OCI_GENAI_PROJECT_OCID,
            }

        return payload

    def _extract_output_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)

        if isinstance(output_text, str) and output_text.strip():
            return output_text

        if isinstance(response, dict):
            dict_output_text = response.get("output_text")

            if isinstance(dict_output_text, str) and dict_output_text.strip():
                return dict_output_text

        output = getattr(response, "output", None)
        if output is None and isinstance(response, dict):
            output = response.get("output")

        text_parts: list[str] = []

        for item in output or []:
            content = getattr(item, "content", None)
            if content is None and isinstance(item, dict):
                content = item.get("content")

            for content_item in content or []:
                text = getattr(content_item, "text", None)
                if text is None and isinstance(content_item, dict):
                    text = content_item.get("text")

                if isinstance(text, str):
                    text_parts.append(text)

        text = "\n".join(part for part in text_parts if part.strip()).strip()

        if not text:
            raise LLMError("OCI Responses API returned no output text.")

        return text

    @staticmethod
    def _require_setting(setting_name: str, value: str | None) -> None:
        if not value:
            raise LLMConfigurationError(
                f"{setting_name} is required when LLM_PROVIDER=oci_responses."
            )
