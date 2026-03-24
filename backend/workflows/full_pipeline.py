"""Run the end-to-end workflow from PDFs to extracted JSON and rendered Word output."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from independent_case_pipeline.backend.app.config import (
    DEFAULT_API_KEY,
    DEFAULT_API_MODEL,
    DEFAULT_API_URL,
    DEFAULT_CASES_ROOT,
    DEFAULT_DEBUG,
    DEFAULT_DERIVED_FIELD_RULES,
    DEFAULT_IMAGE_ALIGN,
    DEFAULT_IMAGE_HEIGHT_CM,
    DEFAULT_IMAGE_WIDTH_CM,
    DEFAULT_LOGICAL_RULES_CONFIG,
    DEFAULT_REPLACE_MAP_CONFIG,
    DEFAULT_TARGET_KEYWORD,
    DEFAULT_TRIM_LAST_PAGE_FOR_LAWYER_LETTER,
    DEFAULT_WRITE_INTERMEDIATE_JSONS,
)
from independent_case_pipeline.backend.app.services.extract_service import copy_input_file, extract_case_data, write_json
from independent_case_pipeline.backend.app.services.render_service import build_word_job_dict, render_word_from_replace_map, sanitize_output_stem, write_word_job
from independent_case_pipeline.backend.app.services.replace_map_service import build_replace_map, write_replace_map


# Parse args.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Full pipeline: PDFs -> Defandent/DemandLetter/logical -> replace_map -> rendered Word.')
    parser.add_argument('--case-name', required=True)
    parser.add_argument('--lawyer-letter-pdf', required=True)
    parser.add_argument('--enterprise-report-pdf', required=True)
    parser.add_argument('--template', required=True)
    parser.add_argument('--cases-root', default=str(DEFAULT_CASES_ROOT))
    parser.add_argument('--replace-map-config', default=str(DEFAULT_REPLACE_MAP_CONFIG))
    parser.add_argument('--logical-rules-config', default=str(DEFAULT_LOGICAL_RULES_CONFIG))
    parser.add_argument('--derived-rules-config', default=str(DEFAULT_DERIVED_FIELD_RULES), help=argparse.SUPPRESS)
    parser.add_argument('--rules', dest='replace_map_config', help=argparse.SUPPRESS)
    parser.add_argument('--api-url', default=DEFAULT_API_URL)
    parser.add_argument('--api-key', default=DEFAULT_API_KEY)
    parser.add_argument('--model', default=DEFAULT_API_MODEL)
    parser.add_argument('--target-keyword', default=DEFAULT_TARGET_KEYWORD)
    parser.add_argument('--trim-last-page-for-lawyer-letter', action='store_true', default=DEFAULT_TRIM_LAST_PAGE_FOR_LAWYER_LETTER)
    parser.add_argument('--no-trim-last-page-for-lawyer-letter', action='store_false', dest='trim_last_page_for_lawyer_letter')
    parser.add_argument('--debug', action='store_true', default=DEFAULT_DEBUG)
    parser.add_argument('--write-intermediate-jsons', action='store_true', default=DEFAULT_WRITE_INTERMEDIATE_JSONS)
    parser.add_argument('--image-align', default=DEFAULT_IMAGE_ALIGN)
    parser.add_argument('--image-width-cm', type=float, default=DEFAULT_IMAGE_WIDTH_CM)
    parser.add_argument('--image-height-cm', type=float, default=DEFAULT_IMAGE_HEIGHT_CM)
    return parser.parse_args()


# Run full pipeline.
def run_full_pipeline(*, case_name: str, lawyer_letter_pdf: str | Path, enterprise_report_pdf: str | Path, template: str | Path, cases_root: str | Path = DEFAULT_CASES_ROOT, replace_map_config: str | Path = DEFAULT_REPLACE_MAP_CONFIG, logical_rules_config: str | Path = DEFAULT_LOGICAL_RULES_CONFIG, rules: str | Path | None = None, trim_last_page_for_lawyer_letter: bool = DEFAULT_TRIM_LAST_PAGE_FOR_LAWYER_LETTER, write_intermediate_jsons: bool = DEFAULT_WRITE_INTERMEDIATE_JSONS, debug: bool = DEFAULT_DEBUG, api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY, model: str = DEFAULT_API_MODEL, target_keyword: str = DEFAULT_TARGET_KEYWORD, image_align: str | None = DEFAULT_IMAGE_ALIGN, image_width_cm: float | None = DEFAULT_IMAGE_WIDTH_CM, image_height_cm: float | None = DEFAULT_IMAGE_HEIGHT_CM, replace_map_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    started_at = time.time()
    template_path = Path(template).expanduser().resolve()
    replace_map_config_path = Path((rules or replace_map_config)).expanduser().resolve()
    logical_rules_config_path = Path(logical_rules_config).expanduser().resolve()

    for path, label in (
        (Path(lawyer_letter_pdf).expanduser().resolve(), 'lawyer_letter_pdf'),
        (Path(enterprise_report_pdf).expanduser().resolve(), 'enterprise_report_pdf'),
        (template_path, 'template'),
        (replace_map_config_path, 'replace_map_config'),
        (logical_rules_config_path, 'logical_rules_config'),
    ):
        if not path.is_file():
            raise FileNotFoundError(f'MISSING {label}: {path}')

    extract_result = extract_case_data(
        case_name=case_name,
        lawyer_letter_pdf=lawyer_letter_pdf,
        enterprise_report_pdf=enterprise_report_pdf,
        cases_root=cases_root,
        trim_last_page_for_lawyer_letter=trim_last_page_for_lawyer_letter,
        write_intermediate_jsons=write_intermediate_jsons,
        debug=debug,
        api_url=api_url,
        api_key=api_key,
        model=model,
        target_keyword=target_keyword,
        logical_rules_config=logical_rules_config_path,
    )

    case_dir = Path(extract_result['case_dir'])
    input_dir = Path(extract_result['paths']['input_dir'])
    replace_dir = Path(extract_result['paths']['replace_dir'])
    word_output_dir = Path(extract_result['paths']['word_output_dir'])

    copied_template = copy_input_file(template_path, input_dir)
    output_name = sanitize_output_stem(
        str((extract_result['Defandent'].get('名称') or [{}])[0].get('value') or ''),
        copied_template.stem,
    )

    replace_map = build_replace_map(
        defandent=extract_result['Defandent'],
        demand_letter=extract_result['DemandLetter'],
        logical=extract_result['logical'],
        config_path=replace_map_config_path,
        overrides=replace_map_overrides,
    )
    replace_map_path = write_replace_map(replace_dir / 'replace_map.json', replace_map)

    word_job = build_word_job_dict(
        replace_map=replace_map,
        input_files=[str(copied_template)],
        output_dir=str(word_output_dir),
        input_base_dir=str(input_dir),
        output_name=output_name,
        image_align=image_align,
        image_width_cm=image_width_cm,
        image_height_cm=image_height_cm,
    )
    word_job_path = write_word_job(replace_dir / 'word_job.json', word_job)

    render_result = render_word_from_replace_map(
        replace_map=replace_map,
        input_files=[str(copied_template)],
        output_dir=str(word_output_dir),
        input_base_dir=str(input_dir),
        output_name=output_name,
        image_align=image_align,
        image_width_cm=image_width_cm,
        image_height_cm=image_height_cm,
    )
    output_docx_path = word_output_dir / f'{output_name}.docx'

    manifest = {
        'status': 'ok',
        'processed_word_files': render_result['processed'],
        'case_name': case_name,
        'target_keyword': target_keyword,
        'trim_last_page_for_lawyer_letter': trim_last_page_for_lawyer_letter,
        'write_intermediate_jsons': write_intermediate_jsons,
        'Defandent_json': extract_result['paths']['Defandent_json'],
        'DemandLetter_json': extract_result['paths']['DemandLetter_json'],
        'logical_json': extract_result['paths']['logical_json'],
        'replace_map_config': str(replace_map_config_path),
        'logical_rules_config': str(logical_rules_config_path),
        'replace_map_json': str(replace_map_path),
        'word_job_json': str(word_job_path),
        'output_docx': str(output_docx_path),
        'template': str(template_path),
        'started_at': started_at,
        'finished_at': time.time(),
    }
    manifest_path = write_json(case_dir / 'FullPipeline_manifest.json', manifest)
    manifest['manifest'] = str(manifest_path)
    write_json(case_dir / 'FullPipeline_manifest.json', manifest)
    return manifest


# Main.
def main() -> int:
    args = parse_args()
    try:
        manifest = run_full_pipeline(
            case_name=args.case_name,
            lawyer_letter_pdf=args.lawyer_letter_pdf,
            enterprise_report_pdf=args.enterprise_report_pdf,
            template=args.template,
            cases_root=args.cases_root,
            replace_map_config=args.replace_map_config,
            logical_rules_config=getattr(args, 'logical_rules_config', args.derived_rules_config),
            trim_last_page_for_lawyer_letter=args.trim_last_page_for_lawyer_letter,
            write_intermediate_jsons=args.write_intermediate_jsons,
            debug=args.debug,
            api_url=args.api_url,
            api_key=args.api_key,
            model=args.model,
            target_keyword=args.target_keyword,
            image_align=args.image_align,
            image_width_cm=args.image_width_cm,
            image_height_cm=args.image_height_cm,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


