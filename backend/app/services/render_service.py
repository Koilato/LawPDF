"""Render Word files from replace_map dictionaries."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from independent_case_pipeline.backend.tools.word_replace import ImageSettings, Job, Replacement, process_documents


# Sanitize output stem.
def sanitize_output_stem(raw_name: str, fallback: str) -> str:
    text = (raw_name or '').strip()
    if not text:
        text = fallback
    text = re.sub(r'[<>:"/\\|?*]+', '_', text).strip().strip('.')
    text = re.sub(r'\s+', ' ', text)
    return text or fallback


# Build word job dict.
def build_word_job_dict(
    *,
    replace_map: dict[str, str],
    input_files: list[str],
    output_dir: str,
    input_base_dir: str | None = None,
    output_name: str | None = None,
    image_align: str | None = None,
    image_width_cm: float | None = None,
    image_height_cm: float | None = None,
) -> dict[str, Any]:
    replacements = [
        {'keyword': keyword, 'text': text}
        for keyword, text in replace_map.items()
    ]
    job: dict[str, Any] = {
        'input_files': input_files,
        'output_dir': output_dir,
        'replacements': replacements,
    }
    if input_base_dir:
        job['input_base_dir'] = input_base_dir
    if output_name:
        job['output_name'] = output_name
    if image_align:
        job['image_align'] = image_align
    if image_width_cm is not None:
        job['image_width_cm'] = image_width_cm
    if image_height_cm is not None:
        job['image_height_cm'] = image_height_cm
    return job


# Build word job.
def build_word_job(
    *,
    replace_map: dict[str, str],
    input_files: list[str],
    output_dir: str,
    input_base_dir: str | None = None,
    output_name: str | None = None,
    image_align: str | None = None,
    image_width_cm: float | None = None,
    image_height_cm: float | None = None,
) -> Job:
    replacements = [Replacement(keyword=keyword, text=text) for keyword, text in replace_map.items()]
    image_settings = ImageSettings(width_cm=image_width_cm, height_cm=image_height_cm, align=image_align)
    return Job(
        input_files=input_files,
        output_dir=output_dir,
        input_base_dir=input_base_dir,
        output_name=output_name,
        replacements=replacements,
        image_settings=image_settings,
    )


# Write word job.
def write_word_job(path: Path, job_dict: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(job_dict, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


# Render word from replace map.
def render_word_from_replace_map(
    *,
    replace_map: dict[str, str],
    input_files: list[str],
    output_dir: str,
    input_base_dir: str | None = None,
    output_name: str | None = None,
    image_align: str | None = None,
    image_width_cm: float | None = None,
    image_height_cm: float | None = None,
) -> dict[str, Any]:
    job = build_word_job(
        replace_map=replace_map,
        input_files=input_files,
        output_dir=output_dir,
        input_base_dir=input_base_dir,
        output_name=output_name,
        image_align=image_align,
        image_width_cm=image_width_cm,
        image_height_cm=image_height_cm,
    )
    processed = process_documents(job)
    return {
        'status': 'ok',
        'processed': processed,
        'output_dir': output_dir,
        'input_files': input_files,
        'output_name': output_name,
    }
