"""Compatibility wrapper for the refactored extract-only case pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from independent_case_pipeline.backend.app.config import (
    DEFAULT_API_KEY,
    DEFAULT_API_MODEL,
    DEFAULT_API_URL,
    DEFAULT_CASES_ROOT,
)
from independent_case_pipeline.backend.app.services.extract_service import extract_case_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the extract-only OCR pipeline for one case.')
    parser.add_argument('--case-name', required=True, help='Case folder name under the output root.')
    parser.add_argument('--lawyer-letter-pdf', required=True, help='Path to the lawyer-letter PDF.')
    parser.add_argument('--enterprise-report-pdf', required=True, help='Path to the enterprise-report PDF.')
    parser.add_argument('--cases-root', default=str(DEFAULT_CASES_ROOT), help='Root directory for case outputs.')
    parser.add_argument('--api-url', default=DEFAULT_API_URL, help='OpenAI-compatible chat completions URL.')
    parser.add_argument('--api-key', default=DEFAULT_API_KEY, help='API key for the LLM endpoint.')
    parser.add_argument('--model', default=DEFAULT_API_MODEL, help='Model name.')
    parser.add_argument('--debug', action='store_true', help='Include LLM request/response details in the lawyer-letter JSON.')
    parser.add_argument('--write-intermediate-jsons', action='store_true', help='Write Defandent.json and DemandLetter.json to disk.')
    parser.add_argument('--no-trim-last-page-for-lawyer-letter', action='store_false', dest='trim_last_page_for_lawyer_letter', help='Keep the lawyer-letter PDF unchanged before OCR.')
    parser.set_defaults(trim_last_page_for_lawyer_letter=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = extract_case_data(
        case_name=args.case_name,
        lawyer_letter_pdf=args.lawyer_letter_pdf,
        enterprise_report_pdf=args.enterprise_report_pdf,
        cases_root=args.cases_root,
        trim_last_page_for_lawyer_letter=args.trim_last_page_for_lawyer_letter,
        write_intermediate_jsons=args.write_intermediate_jsons,
        debug=args.debug,
        api_url=args.api_url,
        api_key=args.api_key,
        model=args.model,
    )

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

