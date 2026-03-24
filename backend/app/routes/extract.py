"""Thin extract route wrapper for future frontend integration."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from independent_case_pipeline.backend.app.services.extract_service import extract_case_data


# Handle extract.
def handle_extract(request: Any) -> dict[str, Any]:
    payload = asdict(request) if is_dataclass(request) else dict(request)
    return extract_case_data(**payload)
