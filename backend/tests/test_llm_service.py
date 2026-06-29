from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.services.llm import LLMError, LLMInputTooLongError, LLMInvalidJSONError
from app.services.llm.json_utils import parse_json_response, strip_markdown_json_fence
from app.services.llm.noop import NoOpLLMService
from app.services.llm.oci_genai_classic import (
    MAX_COMPLETION_TOKENS_FIELD,
    MAX_TOKENS_FIELD,
    OCIGenAIClassicLLMService,
)
from app.services.llm.oci_responses import OCIResponsesLLMService


class FakeTransientError(RuntimeError):
    def __init__(self, message: str = "Service request limit is exceeded") -> None:
        super().__init__(message)
        self.status = 429
        self.code = "429"


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


def test_parse_json_response_extracts_object_from_surrounding_text() -> None:
    assert parse_json_response('Here is the JSON:\n{"status":"ok"}\nDone.') == {
        "status": "ok"
    }


def test_parse_json_response_extracts_fenced_object_with_trailing_text() -> None:
    value = '```json\n{"message":"brace } inside string","status":"ok"}\n```\nDone.'

    assert parse_json_response(value) == {
        "message": "brace } inside string",
        "status": "ok",
    }


def test_parse_json_response_accepts_opening_fence_without_closing_fence() -> None:
    value = '```json\n{"section_id":"section-003","draft_text":"Table of Contents"}'

    assert parse_json_response(value) == {
        "section_id": "section-003",
        "draft_text": "Table of Contents",
    }


def test_parse_json_response_repairs_literal_newlines_inside_strings() -> None:
    value = (
        '```json\n'
        '{\n'
        '  "section_id": "section-007-process-list",\n'
        '  "draft_text": "Defined orchestration processes:\n'
        'CustomDOO_DOO_OrderFulfillmentGenericProcess_NoRSV"\n'
        '}\n'
        '```'
    )

    assert parse_json_response(value) == {
        "section_id": "section-007-process-list",
        "draft_text": (
            "Defined orchestration processes:\n"
            "CustomDOO_DOO_OrderFulfillmentGenericProcess_NoRSV"
        ),
    }


def test_parse_json_response_skips_bad_object_before_valid_object() -> None:
    value = 'Example: {"status": ok}\nActual:\n{"status":"ok"}'

    assert parse_json_response(value) == {"status": "ok"}


def test_parse_json_response_prefers_complete_object_over_small_example() -> None:
    value = (
        'Example shape: {"template_source":"default_scm_template"}\n'
        'Actual response:\n'
        '{"document_strategy":{"template_source":"default_scm_template"},'
        '"sections":[{"title":"Order Capture"}]}'
    )

    assert parse_json_response(value) == {
        "document_strategy": {"template_source": "default_scm_template"},
        "sections": [{"title": "Order Capture"}],
    }


def test_parse_json_response_repairs_truncated_object_end() -> None:
    value = (
        '{"document_strategy":{"template_source":"default_scm_template"},'
        '"sections":[{"title":"Order Capture"}'
    )

    assert parse_json_response(value) == {
        "document_strategy": {"template_source": "default_scm_template"},
        "sections": [{"title": "Order Capture"}],
    }


def test_parse_json_response_repairs_truncated_array_after_comma() -> None:
    value = '{"sections":[{"title":"Order Capture"},'

    assert parse_json_response(value) == {
        "sections": [{"title": "Order Capture"}],
    }


def test_parse_json_response_removes_trailing_commas() -> None:
    value = '{"sections":[{"title":"Order Capture",},],}'

    assert parse_json_response(value) == {
        "sections": [{"title": "Order Capture"}],
    }


def test_parse_json_response_accepts_single_object_array() -> None:
    assert parse_json_response('[{"status":"ok"}]') == {"status": "ok"}


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


def test_oci_classic_uses_max_tokens_for_llama4_model_ids() -> None:
    service = OCIGenAIClassicLLMService(
        settings=Settings(
            OCI_GENAI_MODEL_ID="meta.llama-4-maverick-17b-128e-instruct-fp8",
            OCI_GENAI_MAX_OUTPUT_TOKENS=1234,
            _env_file=None,
        ),
        client=object(),
    )
    request = SimpleNamespace()

    service._set_output_token_limit(
        chat_request=request,
        token_limit=service.settings.OCI_GENAI_MAX_OUTPUT_TOKENS,
        output_token_limit_field=service._output_token_limit_field,
    )

    assert service._output_token_limit_field == MAX_TOKENS_FIELD
    assert request.max_tokens == 1234
    assert not hasattr(request, "max_completion_tokens")


def test_oci_classic_retries_with_max_tokens_when_model_rejects_max_completion_tokens() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.chat_details: list[SimpleNamespace] = []

        def chat(self, chat_detail: SimpleNamespace) -> SimpleNamespace:
            self.chat_details.append(chat_detail)
            if chat_detail.output_token_limit_field == MAX_COMPLETION_TOKENS_FIELD:
                raise RuntimeError(
                    "Invalid 'maxCompletionTokens': Unsupported parameter: "
                    "'maxCompletionTokens' is not supported with this model. "
                    "Use 'maxTokens' instead."
                )

            return SimpleNamespace(
                data=SimpleNamespace(
                    chat_response=SimpleNamespace(output_text='{"status":"ok"}')
                )
            )

    client = FakeClient()
    service = OCIGenAIClassicLLMService(
        settings=Settings(
            OCI_GENAI_MODEL_ID="ocid1.generativeaimodel.oc1..opaque",
            OCI_GENAI_MAX_INPUT_CHARS=1000,
            _env_file=None,
        ),
        client=client,
    )
    service._build_chat_detail = lambda **kwargs: SimpleNamespace(**kwargs)  # type: ignore[method-assign]

    assert service.generate_text("hello") == '{"status":"ok"}'
    assert [
        detail.output_token_limit_field for detail in client.chat_details
    ] == [
        MAX_COMPLETION_TOKENS_FIELD,
        MAX_TOKENS_FIELD,
    ]
    assert service._output_token_limit_field == MAX_TOKENS_FIELD


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


def test_oci_classic_retries_transient_429_with_backoff() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.chat_details: list[SimpleNamespace] = []

        def chat(self, chat_detail: SimpleNamespace) -> SimpleNamespace:
            self.chat_details.append(chat_detail)
            if len(self.chat_details) < 3:
                raise FakeTransientError()

            return SimpleNamespace(
                data=SimpleNamespace(
                    chat_response=SimpleNamespace(output_text='{"status":"ok"}')
                )
            )

    client = FakeClient()
    service = OCIGenAIClassicLLMService(
        settings=Settings(
            OCI_GENAI_MAX_INPUT_CHARS=1000,
            OCI_GENAI_RETRY_MAX_ATTEMPTS=3,
            OCI_GENAI_RETRY_BASE_SECONDS=0.5,
            OCI_GENAI_RETRY_MAX_SECONDS=2,
            _env_file=None,
        ),
        client=client,
    )
    sleeps: list[float] = []
    service._sleep = sleeps.append
    service._build_chat_detail = lambda **kwargs: SimpleNamespace(**kwargs)  # type: ignore[method-assign]

    assert service.generate_text("hello") == '{"status":"ok"}'
    assert len(client.chat_details) == 3
    assert sleeps == [0.5, 1.0]


def test_oci_responses_retries_transient_429_with_backoff() -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.payloads: list[dict] = []

        def create(self, **payload) -> dict:
            self.payloads.append(payload)
            if len(self.payloads) == 1:
                raise FakeTransientError()

            return {"output_text": '{"status":"ok"}'}

    class FakeClient:
        def __init__(self) -> None:
            self.responses = FakeResponses()

    client = FakeClient()
    service = OCIResponsesLLMService(
        settings=Settings(
            OCI_GENAI_REGION="us-chicago-1",
            OCI_GENAI_MODEL_ID="gemini-flash-2.5",
            OCI_GENAI_MAX_INPUT_CHARS=1000,
            OCI_GENAI_RETRY_MAX_ATTEMPTS=2,
            OCI_GENAI_RETRY_BASE_SECONDS=0.25,
            OCI_GENAI_RETRY_MAX_SECONDS=1,
            _env_file=None,
        ),
        client=client,
    )
    sleeps: list[float] = []
    service._sleep = sleeps.append

    assert service.generate_text("hello") == '{"status":"ok"}'
    assert len(client.responses.payloads) == 2
    assert sleeps == [0.25]


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
