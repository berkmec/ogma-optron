"""Intent classifier helpers: JSON tolerance + enum normalization.

We don't call Qwen here — only exercise the pure helpers around it.
"""

from __future__ import annotations

from app.intent.classifier import _normalize, _parse
from app.schemas.intent import IntentKind


def test_normalize_accepts_canonical_values() -> None:
    assert _normalize("error_debug") is IntentKind.ERROR_DEBUG
    assert _normalize("repo_review") is IntentKind.REPO_REVIEW
    assert _normalize("ui_help") is IntentKind.UI_HELP


def test_normalize_handles_minor_variants() -> None:
    assert _normalize("Error-Debug") is IntentKind.ERROR_DEBUG
    assert _normalize(" UI help ") is IntentKind.UI_HELP


def test_normalize_falls_back_to_unknown() -> None:
    assert _normalize("") is IntentKind.UNKNOWN
    assert _normalize("totally-invented") is IntentKind.UNKNOWN


def test_parse_handles_bare_json() -> None:
    payload = '{"primary_intent": "error_debug", "confidence": 0.9}'
    parsed = _parse(payload)
    assert parsed["primary_intent"] == "error_debug"
    assert parsed["confidence"] == 0.9


def test_parse_handles_markdown_fenced_json() -> None:
    payload = '```json\n{"primary_intent": "ui_help", "confidence": 0.8}\n```'
    parsed = _parse(payload)
    assert parsed["primary_intent"] == "ui_help"


def test_parse_returns_unknown_on_garbage() -> None:
    parsed = _parse("definitely not json")
    assert parsed["primary_intent"] == "unknown"
    assert parsed["confidence"] == 0.0
    assert parsed.get("ambiguity")
