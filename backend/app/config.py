"""Central defaults and runtime settings helpers for the local backend."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from independent_case_pipeline.backend.tools.extract_lawyer_letter_infringement import (
    DEFAULT_API_KEY as TOOL_DEFAULT_API_KEY,
    DEFAULT_API_MODEL as TOOL_DEFAULT_API_MODEL,
    DEFAULT_API_URL as TOOL_DEFAULT_API_URL,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / 'backend'
STORAGE_ROOT = BACKEND_ROOT / 'storage'
RUNTIME_ROOT = STORAGE_ROOT / 'runtime'
RUNTIME_SETTINGS_PATH = RUNTIME_ROOT / 'llm_settings.json'
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
DEFAULT_TARGET_KEYWORD = '鍏夋槑'


def get_builtin_settings() -> dict[str, object]:
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


def _normalize_runtime_settings(payload: dict[str, Any]) -> dict[str, object]:
    return {
        'trim_last_page_for_lawyer_letter': bool(
            payload.get('trim_last_page_for_lawyer_letter', DEFAULT_TRIM_LAST_PAGE_FOR_LAWYER_LETTER)
        ),
        'write_intermediate_jsons': bool(payload.get('write_intermediate_jsons', DEFAULT_WRITE_INTERMEDIATE_JSONS)),
        'debug': bool(payload.get('debug', DEFAULT_DEBUG)),
        'image_align': payload.get('image_align') or DEFAULT_IMAGE_ALIGN,
        'image_width_cm': payload.get('image_width_cm', DEFAULT_IMAGE_WIDTH_CM),
        'image_height_cm': payload.get('image_height_cm', DEFAULT_IMAGE_HEIGHT_CM),
        'api_url': str(payload.get('api_url') or DEFAULT_API_URL),
        'api_key': str(payload.get('api_key') or DEFAULT_API_KEY),
        'model': str(payload.get('model') or DEFAULT_API_MODEL),
        'target_keyword': str(payload.get('target_keyword') or DEFAULT_TARGET_KEYWORD),
        'replace_map_config': str(payload.get('replace_map_config') or DEFAULT_REPLACE_MAP_CONFIG),
        'logical_rules_config': str(payload.get('logical_rules_config') or DEFAULT_LOGICAL_RULES_CONFIG),
        'derived_field_rules_config': str(payload.get('derived_field_rules_config') or DEFAULT_DERIVED_FIELD_RULES),
        'cases_root': str(payload.get('cases_root') or DEFAULT_CASES_ROOT),
        'api_base_url': str(payload.get('api_base_url') or f'http://{DEFAULT_SERVER_HOST}:{DEFAULT_SERVER_PORT}'),
    }


def _read_runtime_settings_file() -> dict[str, Any]:
    if not RUNTIME_SETTINGS_PATH.is_file():
        return {}
    try:
        return json.loads(RUNTIME_SETTINGS_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _read_env_overrides() -> dict[str, Any]:
    env_map = {
        'api_url': 'CASE_PIPELINE_API_URL',
        'api_key': 'CASE_PIPELINE_API_KEY',
        'model': 'CASE_PIPELINE_MODEL',
        'target_keyword': 'CASE_PIPELINE_TARGET_KEYWORD',
    }
    overrides: dict[str, Any] = {}
    for key, env_name in env_map.items():
        value = os.getenv(env_name)
        if value:
            overrides[key] = value
    return overrides


def load_runtime_settings() -> dict[str, object]:
    settings = get_builtin_settings()
    settings.update(_read_runtime_settings_file())
    settings.update(_read_env_overrides())
    return _normalize_runtime_settings(settings)


def save_runtime_settings(payload: dict[str, Any]) -> dict[str, object]:
    current = load_runtime_settings()
    next_settings = _normalize_runtime_settings({**current, **payload})
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    RUNTIME_SETTINGS_PATH.write_text(json.dumps(next_settings, ensure_ascii=False, indent=2), encoding='utf-8')
    return next_settings


# Get default frontend settings.
def get_default_frontend_settings() -> dict[str, object]:
    return load_runtime_settings()
