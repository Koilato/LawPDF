"""Simple request schemas for extraction and rendering workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ExtractRequest:
    case_name: str
    lawyer_letter_pdf: str | Path
    enterprise_report_pdf: str | Path
    trim_last_page_for_lawyer_letter: bool = True
    write_intermediate_jsons: bool = False
    debug: bool = False
    api_url: str | None = None
    api_key: str | None = None
    model: str | None = None


@dataclass(slots=True)
class RenderRequest:
    template_files: list[str | Path]
    output_dir: str | Path
    replace_map: dict[str, str]
    input_base_dir: str | Path | None = None
    image_align: str | None = None
    image_width_cm: float | None = None
    image_height_cm: float | None = None


@dataclass(slots=True)
class FullPipelineRequest:
    case_name: str
    lawyer_letter_pdf: str | Path
    enterprise_report_pdf: str | Path
    template: str | Path
    cases_root: str | Path
    replace_map_config: str | Path
    trim_last_page_for_lawyer_letter: bool = True
    write_intermediate_jsons: bool = False
    debug: bool = False
    api_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    image_align: str | None = None
    image_width_cm: float | None = None
    image_height_cm: float | None = None
    replace_map_overrides: dict[str, Any] | None = None
