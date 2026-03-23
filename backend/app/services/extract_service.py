"""Prepare uploaded files, run OCR, and extract Defandent, DemandLetter, and logical JSON."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

from independent_case_pipeline.backend.app.config import (
    DEFAULT_API_KEY,
    DEFAULT_API_MODEL,
    DEFAULT_API_URL,
    DEFAULT_CASES_ROOT,
    DEFAULT_LOGICAL_RULES_CONFIG,
    DEFAULT_TARGET_KEYWORD,
)
from independent_case_pipeline.backend.tools.build_logical_json import build_logical
from independent_case_pipeline.backend.tools.extract_enterprise_report import extract_enterprise_report
from independent_case_pipeline.backend.tools.extract_lawyer_letter_infringement import build_output as build_lawyer_letter_output
from independent_case_pipeline.backend.tools.pdf_to_markdown import build_docling_converter, convert_with_docling, disable_hf_symlinks, ensure_non_empty


def prepare_case_dirs(case_name: str, cases_root: str | Path = DEFAULT_CASES_ROOT) -> dict[str, Path]:
    case_dir = Path(cases_root).expanduser().resolve() / case_name
    dirs = {
        'case_dir': case_dir,
        'input_dir': case_dir / 'input_files',
        'working_dir': case_dir / 'working_files',
        'ocr_dir': case_dir / 'ocr_md',
        'data_dir': case_dir / 'data',
        'replace_dir': case_dir / 'replace',
        'word_output_dir': case_dir / 'word_output',
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def copy_input_file(src: str | Path, dst_dir: str | Path) -> Path:
    src_path = Path(src).expanduser().resolve()
    dst_dir_path = Path(dst_dir).expanduser().resolve()
    dst_dir_path.mkdir(parents=True, exist_ok=True)
    dst = dst_dir_path / src_path.name
    shutil.copy2(src_path, dst)
    return dst


def trim_pdf_last_page(src: str | Path, dst: str | Path) -> Path:
    src_path = Path(src).expanduser().resolve()
    dst_path = Path(dst).expanduser().resolve()
    reader = PdfReader(str(src_path))
    if len(reader.pages) <= 1:
        raise ValueError(f'PDF page count is too small to trim the last page: {src_path}')
    writer = PdfWriter()
    for page in reader.pages[:-1]:
        writer.add_page(page)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with dst_path.open('wb') as fp:
        writer.write(fp)
    return dst_path


def ocr_pdf_to_markdown(converter: Any, pdf_path: Path, output_path: Path) -> Path:
    markdown = convert_with_docling(converter, pdf_path)
    markdown = ensure_non_empty(markdown, pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding='utf-8')
    return output_path


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def run_with_retry(func, attempts: int = 3, delay_seconds: int = 20):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            message = str(exc)
            should_retry = '503' in message or 'MODEL_CAPACITY_EXHAUSTED' in message or 'No capacity available' in message
            if attempt >= attempts or not should_retry:
                raise
            time.sleep(delay_seconds)
    raise last_error


def extract_case_data(*, case_name: str, lawyer_letter_pdf: str | Path, enterprise_report_pdf: str | Path, cases_root: str | Path = DEFAULT_CASES_ROOT, trim_last_page_for_lawyer_letter: bool = True, write_intermediate_jsons: bool = False, debug: bool = False, api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY, model: str = DEFAULT_API_MODEL, target_keyword: str = DEFAULT_TARGET_KEYWORD, logical_rules_config: str | Path = DEFAULT_LOGICAL_RULES_CONFIG) -> dict[str, Any]:
    dirs = prepare_case_dirs(case_name, cases_root)
    copied_lawyer_pdf = copy_input_file(lawyer_letter_pdf, dirs['input_dir'])
    copied_enterprise_pdf = copy_input_file(enterprise_report_pdf, dirs['input_dir'])
    if trim_last_page_for_lawyer_letter:
        working_lawyer_pdf = trim_pdf_last_page(copied_lawyer_pdf, dirs['working_dir'] / f'{copied_lawyer_pdf.stem}-trimmed.pdf')
    else:
        working_lawyer_pdf = copy_input_file(copied_lawyer_pdf, dirs['working_dir'])
    working_enterprise_pdf = copy_input_file(copied_enterprise_pdf, dirs['working_dir'])

    disable_hf_symlinks()
    converter = build_docling_converter()
    defandent_md_path = ocr_pdf_to_markdown(converter, working_enterprise_pdf, dirs['ocr_dir'] / f'{copied_enterprise_pdf.stem}.md')
    demand_letter_md_path = ocr_pdf_to_markdown(converter, working_lawyer_pdf, dirs['ocr_dir'] / f'{copied_lawyer_pdf.stem}.md')

    defandent_markdown = defandent_md_path.read_text(encoding='utf-8')
    demand_letter_markdown = demand_letter_md_path.read_text(encoding='utf-8')
    defandent = extract_enterprise_report(markdown=defandent_markdown, source_name=defandent_md_path.name)
    demand_letter = run_with_retry(lambda: build_lawyer_letter_output(input_path=demand_letter_md_path, api_url=api_url, api_key=api_key, model=model, include_debug=debug))
    logical = build_logical(
        defandent=defandent,
        demand_letter=demand_letter,
        config_path=Path(logical_rules_config).expanduser().resolve(),
        target_keyword=target_keyword,
    )

    defandent_json_path = None
    demand_letter_json_path = None
    logical_json_path = None
    if write_intermediate_jsons:
        defandent_json_path = write_json(dirs['data_dir'] / 'Defandent.json', defandent)
        demand_letter_json_path = write_json(dirs['data_dir'] / 'DemandLetter.json', demand_letter)
        logical_json_path = write_json(dirs['data_dir'] / 'logical.json', logical)

    return {
        'case_name': case_name,
        'case_dir': str(dirs['case_dir']),
        'paths': {
            'input_dir': str(dirs['input_dir']),
            'working_dir': str(dirs['working_dir']),
            'ocr_dir': str(dirs['ocr_dir']),
            'data_dir': str(dirs['data_dir']),
            'replace_dir': str(dirs['replace_dir']),
            'word_output_dir': str(dirs['word_output_dir']),
            'enterprise_report_pdf': str(copied_enterprise_pdf),
            'lawyer_letter_pdf': str(copied_lawyer_pdf),
            'working_enterprise_report_pdf': str(working_enterprise_pdf),
            'working_lawyer_letter_pdf': str(working_lawyer_pdf),
            'enterprise_report_md': str(defandent_md_path),
            'lawyer_letter_md': str(demand_letter_md_path),
            'Defandent_json': str(defandent_json_path) if defandent_json_path else None,
            'DemandLetter_json': str(demand_letter_json_path) if demand_letter_json_path else None,
            'logical_json': str(logical_json_path) if logical_json_path else None,
        },
        'markdowns': {
            'enterprise_report': defandent_markdown,
            'lawyer_letter': demand_letter_markdown,
        },
        'Defandent': defandent,
        'DemandLetter': demand_letter,
        'logical': logical,
    }

