JSON_ONLY_SYSTEM_PROMPT = (
    "Return JSON only. Do not wrap the response in markdown fences. "
    "Do not include prose before or after the JSON object."
)


def build_json_system_prompt(
    system_prompt: str | None = None,
    schema_name: str | None = None,
) -> str:
    parts: list[str] = []

    if system_prompt:
        parts.append(system_prompt.strip())

    if schema_name:
        parts.append(f"Use the requested JSON schema name: {schema_name}.")

    parts.append(JSON_ONLY_SYSTEM_PROMPT)
    return "\n\n".join(parts)
