"""Compatibility wrapper for the refactored PDF-to-Markdown tool."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from independent_case_pipeline.backend.tools.pdf_to_markdown import *  # noqa: F401,F403
from independent_case_pipeline.backend.tools.pdf_to_markdown import main


if __name__ == '__main__':
    raise SystemExit(main())
