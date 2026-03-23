"""Compatibility wrapper for building Word replacement job dictionaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from independent_case_pipeline.backend.app.services.render_service import build_word_job_dict, write_word_job
from independent_case_pipeline.backend.app.services.replace_map_service import read_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Convert replace_map.json to a word_replace job JSON.')
    parser.add_argument('--replace-map', required=True, help='Path to replace_map.json')
    parser.add_argument('--template', required=True, action='append', help='Template doc/docx file. Can be repeated.')
    parser.add_argument('--output-dir', required=True, help='Output directory for replaced documents')
    parser.add_argument('--job-output', required=True, help='Path to output word_job.json')
    parser.add_argument('--input-base-dir', help='Optional base dir for preserving relative paths')
    parser.add_argument('--image-align', help='Optional image alignment for inserted pictures')
    parser.add_argument('--image-width-cm', type=float, help='Optional default image width in centimeters')
    parser.add_argument('--image-height-cm', type=float, help='Optional default image height in centimeters')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    replace_map_path = Path(args.replace_map).expanduser().resolve()
    job_output_path = Path(args.job_output).expanduser().resolve()
    template_paths = [str(Path(item).expanduser().resolve()) for item in args.template]

    if not replace_map_path.is_file():
        print(f'MISSING replace_map: {replace_map_path}', file=sys.stderr)
        return 1
    for template in template_paths:
        if not Path(template).is_file():
            print(f'MISSING template: {template}', file=sys.stderr)
            return 1

    replace_map = read_json(replace_map_path)
    word_job = build_word_job_dict(
        replace_map=replace_map,
        input_files=template_paths,
        output_dir=str(Path(args.output_dir).expanduser().resolve()),
        input_base_dir=str(Path(args.input_base_dir).expanduser().resolve()) if args.input_base_dir else None,
        image_align=args.image_align,
        image_width_cm=args.image_width_cm,
        image_height_cm=args.image_height_cm,
    )
    write_word_job(job_output_path, word_job)

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print(json.dumps(word_job, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
