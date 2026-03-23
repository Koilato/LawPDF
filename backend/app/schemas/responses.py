"""Simple response schemas for extraction and rendering workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ExtractResponse:
    payload: dict[str, Any]


@dataclass(slots=True)
class RenderResponse:
    payload: dict[str, Any]
