from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.services.llm import LLMError, LLMInputTooLongError, LLMInvalidJSONError
from app.services.llm.json_utils import parse_json_response, strip_markdown_json_fence
from app.services.llm.noop import NoOpLLMService
from app.services.llm.oci_genai_classic import OCIGenAIClassicLLMService


def test_noop_generate_text_returns_disabled_message() -> None:
    service = NoOpLLMService(settings=Settings(_env_file=None))

    assert service.generate_text("hello") == "LLM provider is disabled."


def test_noop_generate_json_returns_disabled_payload() -> None:
    service = NoOpLLMService(settings=Settings(_env_file=None))

    assert service.generate_json("hello") == {
        "provider": "none",
        "status": "disabled",
    }


def test_json_fence_stripping() -> None:
    assert strip_markdown_json_fence('```json\n{"status":"ok"}\n```') == (
        '{"status":"ok"}'
    )
    assert parse_json_response('```json\n{"status":"ok"}\n```') == {
        "status": "ok"
    }


def test_invalid_json_raises_clean_error() -> None:
    with pytest.raises(LLMInvalidJSONError, match="not valid JSON"):
        parse_json_response("status: ok")


def test_non_object_json_raises_clean_error() -> None:
    with pytest.raises(LLMInvalidJSONError, match="must be an object"):
        parse_json_response('["status", "ok"]')


def test_prompt_length_safeguard() -> None:
    service = NoOpLLMService(
        settings=Settings(OCI_GENAI_MAX_INPUT_CHARS=4, _env_file=None)
    )

    with pytest.raises(LLMInputTooLongError, match="too large"):
        service.generate_text("hello")


def test_oci_classic_extracts_text_from_generic_choice_object() -> None:
    service = OCIGenAIClassicLLMService(
        settings=Settings(_env_file=None),
        client=object(),
    )
    response = SimpleNamespace(
        data=SimpleNamespace(
            chat_response=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=[SimpleNamespace(text='{"status":"ok"}')]
                        )
                    )
                ]
            )
        )
    )

    assert service._extract_chat_text(response) == '{"status":"ok"}'


def test_oci_classic_extracts_text_from_dict_response_shape() -> None:
    service = OCIGenAIClassicLLMService(
        settings=Settings(_env_file=None),
        client=object(),
    )
    response = SimpleNamespace(
        data={
            "chat_response": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {
                                    "type": "TEXT",
                                    "text": '{"status":"ok"}',
                                }
                            ]
                        }
                    }
                ]
            }
        }
    )

    assert service._extract_chat_text(response) == '{"status":"ok"}'


def test_oci_classic_extracts_direct_output_text() -> None:
    service = OCIGenAIClassicLLMService(
        settings=Settings(_env_file=None),
        client=object(),
    )
    response = SimpleNamespace(
        data=SimpleNamespace(
            chat_response=SimpleNamespace(output_text='{"status":"ok"}')
        )
    )

    assert service._extract_chat_text(response) == '{"status":"ok"}'


def test_oci_classic_retries_with_default_temperature_when_model_rejects_custom_value() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.chat_details: list[SimpleNamespace] = []

        def chat(self, chat_detail: SimpleNamespace) -> SimpleNamespace:
            self.chat_details.append(chat_detail)
            if len(self.chat_details) == 1:
                raise RuntimeError(
                    "Unsupported value: 'temperature' does not support 0.1 "
                    "with this model. Only the default (1) value is supported."
                )

            return SimpleNamespace(
                data=SimpleNamespace(
                    chat_response=SimpleNamespace(output_text='{"status":"ok"}')
                )
            )

    client = FakeClient()
    service = OCIGenAIClassicLLMService(
        settings=Settings(
            OCI_GENAI_TEMPERATURE=0.1,
            OCI_GENAI_MAX_INPUT_CHARS=1000,
            _env_file=None,
        ),
        client=client,
    )

    def build_fake_chat_detail(**kwargs) -> SimpleNamespace:
        temperature = (
            service.settings.OCI_GENAI_TEMPERATURE
            if kwargs["temperature"] is None
            else kwargs["temperature"]
        )
        return SimpleNamespace(temperature=temperature)

    service._build_chat_detail = build_fake_chat_detail  # type: ignore[method-assign]

    assert service.generate_text("hello") == '{"status":"ok"}'
    assert [detail.temperature for detail in client.chat_details] == [0.1, 1]


def test_oci_classic_reports_output_token_limit_when_finish_reason_is_length() -> None:
    service = OCIGenAIClassicLLMService(
        settings=Settings(_env_file=None),
        client=object(),
    )
    response = SimpleNamespace(
        data=SimpleNamespace(
            chat_response=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="length",
                        message=SimpleNamespace(content=[]),
                    )
                ]
            )
        )
    )

    with pytest.raises(LLMError, match="max output token limit"):
        service._extract_chat_text(response)
