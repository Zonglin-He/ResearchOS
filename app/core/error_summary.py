from __future__ import annotations

import re


_TRUNCATION_MARKERS = (
    "<role_contract>",
    "<task_input>",
    '"input_payload"',
    '"resume_from_checkpoint"',
    '"shared_state"',
    "resume_from_checkpoint",
    "shared_state",
    "checkpoint_path",
    "workdir:",
    " user Follow the role contract",
)

_SESSION_PATTERNS = (
    re.compile(r"\bsession[_ ]id\s*:\s*\S+", flags=re.IGNORECASE),
    re.compile(r"\bapproval\s*:\s*\S+", flags=re.IGNORECASE),
    re.compile(r"\bsandbox\s*:\s*\S+", flags=re.IGNORECASE),
)


def summarize_error_detail(detail: str, *, max_length: int = 240) -> str:
    text = str(detail or "").replace("\r", "\n").strip()
    if not text:
        return "Provider invocation failed."

    for marker in _TRUNCATION_MARKERS:
        marker_index = text.find(marker)
        if marker_index > 0:
            text = text[:marker_index].strip()
            break

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = lines[0] if lines else text
    for pattern in _SESSION_PATTERNS:
        text = pattern.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" -:\t")

    if not text:
        return "Provider invocation failed."
    if len(text) <= max_length:
        return text

    shortened = text[: max_length - 1].rsplit(" ", 1)[0].strip()
    if not shortened:
        shortened = text[: max_length - 1].strip()
    return shortened + "…"
