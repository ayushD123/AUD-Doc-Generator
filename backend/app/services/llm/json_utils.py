import json

from app.services.llm.base import LLMInvalidJSONError


def strip_markdown_json_fence(value: str) -> str:
    stripped = value.strip()

    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()

    if len(lines) < 2:
        return stripped

    opening = lines[0].strip().lower()
    closing = lines[-1].strip()

    if opening in {"```", "```json", "```javascript", "```js"} and closing == "```":
        return "\n".join(lines[1:-1]).strip()

    return stripped


def parse_json_response(value: str) -> dict:
    stripped = strip_markdown_json_fence(value)

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise LLMInvalidJSONError("LLM response was not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise LLMInvalidJSONError("LLM response JSON must be an object.")

    return parsed
