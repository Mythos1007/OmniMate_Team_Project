import re


def render_tts_template(template: str, context: dict[str, str]) -> str:
    """Replace placeholders like {name} using the provided context."""
    safe_template = str(template or "").strip()
    if not safe_template:
        return ""

    normalized_context = {str(k): str(v) for k, v in (context or {}).items()}

    def _replace(match: re.Match) -> str:
        key = match.group(1).strip()
        return normalized_context.get(key, match.group(0))

    return re.sub(r"\{([^{}]+)\}", _replace, safe_template)
