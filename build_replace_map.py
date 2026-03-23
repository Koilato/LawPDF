"""Compatibility wrapper for JSON-config-driven replace_map building."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from independent_case_pipeline.backend.app.services.replace_map_service import (
    build_replace_map,
    build_replace_map_from_config,
    main,
    normalize_replace_map,
    read_json,
    read_replace_map_config,
    write_replace_map,
)

__all__ = [
    'build_replace_map',
    'build_replace_map_from_config',
    'normalize_replace_map',
    'read_json',
    'read_replace_map_config',
    'write_replace_map',
    'main',
]


if __name__ == '__main__':
    raise SystemExit(main())
