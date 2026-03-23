"""Thin settings route wrapper for future frontend integration."""

from __future__ import annotations

from independent_case_pipeline.backend.app.config import get_default_frontend_settings


def handle_settings() -> dict[str, object]:
    return get_default_frontend_settings()
