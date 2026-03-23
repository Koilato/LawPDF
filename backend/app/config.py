"""Central defaults for frontend-overridable backend settings."""

from __future__ import annotations

from pathlib import Path

from independent_case_pipeline.backend.tools.extract_lawyer_letter_infringement import (
    DEFAULT_API_KEY as TOOL_DEFAULT_API_KEY,
    DEFAULT_API_MODEL as TOOL_DEFAULT_API_MODEL,
    DEFAULT_API_URL as TOOL_DEFAULT_API_URL,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / 'backend'
STORAGE_ROOT = BACKEND_ROOT / 'storage'
DEFAULT_CASES_ROOT = STORAGE_ROOT / 'cases'
DEFAULT_UPLOADS_ROOT = STORAGE_ROOT / 'uploads'
DEFAULT_REPLACE_MAP_CONFIG = BACKEND_ROOT / 'configs' / 'replace_map_config.json'
DEFAULT_LOGICAL_RULES_CONFIG = BACKEND_ROOT / 'configs' / 'logical_rules.json'
DEFAULT_DERIVED_FIELD_RULES = DEFAULT_LOGICAL_RULES_CONFIG
DEFAULT_SERVER_HOST = '127.0.0.1'
DEFAULT_SERVER_PORT = 8000
DEFAULT_TRIM_LAST_PAGE_FOR_LAWYER_LETTER = True
DEFAULT_WRITE_INTERMEDIATE_JSONS = False
DEFAULT_DEBUG = False
DEFAULT_IMAGE_ALIGN = 'left'
DEFAULT_IMAGE_WIDTH_CM: float | None = None
DEFAULT_IMAGE_HEIGHT_CM: float | None = None
DEFAULT_API_URL = TOOL_DEFAULT_API_URL
DEFAULT_API_KEY = TOOL_DEFAULT_API_KEY
DEFAULT_API_MODEL = TOOL_DEFAULT_API_MODEL
DEFAULT_TARGET_KEYWORD = '光明'


def get_default_frontend_settings() -> dict[str, object]:
    return {
        'trim_last_page_for_lawyer_letter': DEFAULT_TRIM_LAST_PAGE_FOR_LAWYER_LETTER,
        'write_intermediate_jsons': DEFAULT_WRITE_INTERMEDIATE_JSONS,
        'debug': DEFAULT_DEBUG,
        'image_align': DEFAULT_IMAGE_ALIGN,
        'image_width_cm': DEFAULT_IMAGE_WIDTH_CM,
        'image_height_cm': DEFAULT_IMAGE_HEIGHT_CM,
        'api_url': DEFAULT_API_URL,
        'api_key': DEFAULT_API_KEY,
        'model': DEFAULT_API_MODEL,
        'target_keyword': DEFAULT_TARGET_KEYWORD,
        'replace_map_config': str(DEFAULT_REPLACE_MAP_CONFIG),
        'logical_rules_config': str(DEFAULT_LOGICAL_RULES_CONFIG),
        'derived_field_rules_config': str(DEFAULT_DERIVED_FIELD_RULES),
        'cases_root': str(DEFAULT_CASES_ROOT),
        'api_base_url': f'http://{DEFAULT_SERVER_HOST}:{DEFAULT_SERVER_PORT}',
    }
