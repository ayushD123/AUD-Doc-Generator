import json

from app.services.llm.base import LLMInvalidJSONError

PREFERRED_JSON_OBJECT_KEYS = {
    "ai_enhanced_plan",
    "aud_generation_plan",
    "aud_plan",
    "aud_sections",
    "document_plan",
    "document_strategy",
    "document_sections",
    "draft_text",
    "enhanced_aud_plan",
    "enhanced_plan",
    "enhanced_sections",
    "open_points",
    "plan_sections",
    "section_id",
    "section_plan",
    "sections",
    "source_role",
    "source_summary",
    "summary",
}
INVALID_JSON_PREVIEW_CHARS = 500


def strip_markdown_json_fence(value: str) -> str:
    stripped = value.strip()

    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()

    if len(lines) < 2:
        return stripped

    opening = lines[0].strip().lower()
    closing = lines[-1].strip()

    if opening in {"```", "```json", "```javascript", "```js"}:
        body_lines = lines[1:-1] if closing == "```" else lines[1:]
        return "\n".join(body_lines).strip()

    return stripped


def iter_json_object_candidates(value: str) -> list[str]:
    candidates: list[str] = []

    for start_index, character in enumerate(value):
        if character != "{":
            continue

        depth = 0
        in_string = False
        escaped = False

        for index in range(start_index, len(value)):
            current = value[index]

            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue

            if current == '"':
                in_string = True
            elif current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(value[start_index : index + 1])
                    break

    return candidates


def remove_trailing_commas(value: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False

    for index, current in enumerate(value):
        if in_string:
            result.append(current)
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == '"':
                in_string = False
            continue

        if current == '"':
            in_string = True
            result.append(current)
            continue

        if current == ",":
            next_index = index + 1
            while next_index < len(value) and value[next_index].isspace():
                next_index += 1
            if next_index < len(value) and value[next_index] in {"]", "}"}:
                continue

        result.append(current)

    return "".join(result)


def escape_control_characters_in_strings(value: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False

    for current in value:
        if in_string:
            if escaped:
                result.append(current)
                escaped = False
            elif current == "\\":
                result.append(current)
                escaped = True
            elif current == '"':
                result.append(current)
                in_string = False
            elif current == "\n":
                result.append("\\n")
            elif current == "\r":
                result.append("\\r")
            elif current == "\t":
                result.append("\\t")
            elif ord(current) < 32:
                result.append(json.dumps(current)[1:-1])
            else:
                result.append(current)
            continue

        result.append(current)
        if current == '"':
            in_string = True

    return "".join(result)


def iter_json_cleanup_candidates(value: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        if candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

    add(value)
    add(remove_trailing_commas(value))

    for candidate in list(candidates):
        escaped = escape_control_characters_in_strings(candidate)
        add(escaped)
        add(remove_trailing_commas(escaped))

    return candidates


def load_json_with_cleanup(value: str) -> object:
    last_error: json.JSONDecodeError | None = None

    for candidate in iter_json_cleanup_candidates(value):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    return json.loads(value)


def build_invalid_json_error_message(value: str) -> str:
    preview = " ".join(value.strip().split())
    if len(preview) > INVALID_JSON_PREVIEW_CHARS:
        preview = f"{preview[:INVALID_JSON_PREVIEW_CHARS].rstrip()}..."

    if not preview:
        preview = "<empty response>"

    return f"LLM response was not valid JSON. Response preview: {preview}"


def iter_json_object_suffixes(value: str) -> list[str]:
    return [
        value[index:].strip()
        for index, character in enumerate(value)
        if character == "{"
    ]


def try_repair_truncated_json_object(value: str) -> dict | None:
    candidate = value.rstrip()

    while candidate.endswith("```"):
        candidate = candidate[: -len("```")].rstrip()

    stack: list[str] = []
    in_string = False
    escaped = False

    for current in candidate:
        if in_string:
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == '"':
                in_string = False
            continue

        if current == '"':
            in_string = True
        elif current == "{":
            stack.append("}")
        elif current == "[":
            stack.append("]")
        elif current in {"}", "]"}:
            if not stack or stack[-1] != current:
                return None
            stack.pop()

    if not stack and not in_string:
        return None

    repaired = candidate.rstrip()

    if in_string:
        repaired += '"'

    for closing_character in reversed(stack):
        repaired = repaired.rstrip()
        if repaired.endswith(","):
            repaired = repaired[:-1].rstrip()
        repaired += closing_character

    try:
        parsed = load_json_with_cleanup(repaired)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def select_best_json_object_candidate(candidates: list[tuple[str, dict]]) -> dict | None:
    if not candidates:
        return None

    def score(candidate: tuple[str, dict]) -> tuple[int, int, int]:
        raw_value, parsed = candidate
        keys = set(parsed.keys())
        return (
            len(keys & PREFERRED_JSON_OBJECT_KEYS),
            len(keys),
            len(raw_value),
        )

    return max(candidates, key=score)[1]


def parse_json_response(value: str) -> dict:
    stripped = strip_markdown_json_fence(value)

    try:
        parsed = load_json_with_cleanup(stripped)
    except json.JSONDecodeError as exc:
        parsed_candidates: list[tuple[str, dict]] = []
        for extracted in iter_json_object_candidates(stripped):
            try:
                extracted_payload = load_json_with_cleanup(extracted)
            except json.JSONDecodeError:
                continue

            if isinstance(extracted_payload, dict):
                parsed_candidates.append((extracted, extracted_payload))
            elif (
                isinstance(extracted_payload, list)
                and len(extracted_payload) == 1
                and isinstance(extracted_payload[0], dict)
            ):
                parsed_candidates.append((extracted, extracted_payload[0]))

        for suffix in iter_json_object_suffixes(stripped):
            repaired_payload = try_repair_truncated_json_object(suffix)
            if isinstance(repaired_payload, dict):
                parsed_candidates.append((suffix, repaired_payload))

        parsed = select_best_json_object_candidate(parsed_candidates)
        if parsed is None:
            raise LLMInvalidJSONError(build_invalid_json_error_message(stripped)) from exc
    else:
        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
            parsed = parsed[0]

    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        parsed = parsed[0]

    if not isinstance(parsed, dict):
        raise LLMInvalidJSONError("LLM response JSON must be an object.")

    return parsed
