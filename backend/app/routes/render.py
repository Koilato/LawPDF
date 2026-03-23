"""Thin render route wrapper for future frontend integration."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from independent_case_pipeline.backend.app.services.render_service import render_word_from_replace_map


def handle_render(request: Any) -> dict[str, Any]:
    payload = asdict(request) if is_dataclass(request) else dict(request)
    return render_word_from_replace_map(**payload)
