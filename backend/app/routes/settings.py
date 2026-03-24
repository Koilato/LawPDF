"""Thin settings route wrapper for frontend persistence."""

from __future__ import annotations

from typing import Any

from independent_case_pipeline.backend.app.config import get_default_frontend_settings, save_runtime_settings


# Handle settings.
def handle_settings() -> dict[str, object]:
    return get_default_frontend_settings()


# Save settings.
def handle_save_settings(request: Any) -> dict[str, object]:
    payload = dict(request or {})
    return save_runtime_settings(payload)
