"""Build replace_map dictionaries from extracted JSON and JSON config rules."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from independent_case_pipeline.backend.app.config import DEFAULT_REPLACE_MAP_CONFIG

ExtractedSources = dict[str, dict[str, Any]]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def read_replace_map_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def normalize_replace_map(raw_map: dict[Any, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in raw_map.items():
        if value is None:
            normalized[str(key)] = ''
        elif isinstance(value, str):
            normalized[str(key)] = value
        else:
            normalized[str(key)] = str(value)
    return normalized


def _resolve_path(data: Any, path_parts: list[Any]) -> Any:
    current = data
    for part in path_parts:
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                raise KeyError(part)
            current = current[part]
            continue
        if isinstance(current, list) and isinstance(part, str) and part.isdigit():
            index = int(part)
            if index >= len(current):
                raise KeyError(part)
            current = current[index]
            continue
        if not isinstance(current, dict) or part not in current:
            raise KeyError(part)
        current = current[part]
    return current


def _stringify(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return str(value)


def _resolve_source_value(source_name: str, path_parts: list[Any], sources: ExtractedSources, default: str = '') -> str:
    source = sources.get(source_name)
    if source is None:
        return default
    try:
        value = _resolve_path(source, path_parts)
    except KeyError:
        return default
    return _stringify(value)


def _render_template(template: str, values: dict[str, str]) -> str:
    def replace_var(match: re.Match[str]) -> str:
        return values.get(match.group(1), '')
    return re.sub(r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}', replace_var, template)


def _build_mapping_value(mapping: dict[str, Any], sources: ExtractedSources, on_missing: str = 'empty') -> str:
    mode = str(mapping.get('mode') or 'path').strip().lower()
    default = _stringify(mapping.get('default', ''))
    if mode == 'path':
        source_name = str(mapping.get('source') or '').strip()
        path_parts = list(mapping.get('path') or [])
        value = _resolve_source_value(source_name, path_parts, sources, default=default)
        if not value and on_missing == 'error' and mapping.get('required'):
            raise KeyError(f'Missing required value for source={source_name} path={path_parts}')
        return value or default
    if mode == 'literal':
        return _stringify(mapping.get('value', default))
    if mode == 'template':
        template = _stringify(mapping.get('template', ''))
        vars_config = mapping.get('vars') or {}
        values = {str(var_name): _build_mapping_value(dict(var_config), sources, on_missing='empty') for var_name, var_config in vars_config.items()}
        rendered = _render_template(template, values)
        return rendered or default
    raise ValueError(f'Unsupported mapping mode: {mode}')


def build_replace_map_from_config(*, defandent: dict[str, Any], demand_letter: dict[str, Any], config: dict[str, Any], logical: dict[str, Any] | None = None, overrides: dict[str, Any] | None = None) -> dict[str, str]:
    sources: ExtractedSources = {
        'Defandent': defandent,
        'DemandLetter': demand_letter,
        'logical': logical or {},
    }
    on_missing = str(config.get('on_missing') or 'empty').strip().lower()
    mappings = config.get('mappings') or {}
    replace_map: dict[str, str] = {}
    for keyword, mapping in mappings.items():
        replace_map[str(keyword)] = _build_mapping_value(dict(mapping), sources, on_missing=on_missing)
    for keyword, value in (overrides or {}).items():
        replace_map[str(keyword)] = _stringify(value)
    return normalize_replace_map(replace_map)


def build_replace_map(*, defandent: dict[str, Any], demand_letter: dict[str, Any], logical: dict[str, Any] | None = None, config_path: Path | None = DEFAULT_REPLACE_MAP_CONFIG, overrides: dict[str, Any] | None = None, rules_path: Path | None = None) -> dict[str, str]:
    resolved_config_path = rules_path or config_path or DEFAULT_REPLACE_MAP_CONFIG
    return build_replace_map_from_config(defandent=defandent, demand_letter=demand_letter, logical=logical, config=read_replace_map_config(Path(resolved_config_path)), overrides=overrides)


def write_replace_map(path: Path, replace_map: dict[str, str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(replace_map, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build replace_map.json from Defandent.json, DemandLetter.json, logical.json, and replace_map_config.json.')
    parser.add_argument('--defandent-json', required=True)
    parser.add_argument('--demand-letter-json', required=True)
    parser.add_argument('--logical-json')
    parser.add_argument('--config', default=str(DEFAULT_REPLACE_MAP_CONFIG))
    parser.add_argument('--output', required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    defandent_json_path = Path(args.defandent_json).expanduser().resolve()
    demand_letter_json_path = Path(args.demand_letter_json).expanduser().resolve()
    logical_json_path = Path(args.logical_json).expanduser().resolve() if args.logical_json else None
    config_path = Path(args.config).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    for path, label in ((defandent_json_path, 'defandent_json'), (demand_letter_json_path, 'demand_letter_json'), (config_path, 'config')):
        if not path.is_file():
            print(f'MISSING {label}: {path}', file=sys.stderr)
            return 1
    if logical_json_path and not logical_json_path.is_file():
        print(f'MISSING logical_json: {logical_json_path}', file=sys.stderr)
        return 1
    replace_map = build_replace_map(
        defandent=read_json(defandent_json_path),
        demand_letter=read_json(demand_letter_json_path),
        logical=read_json(logical_json_path) if logical_json_path else None,
        config_path=config_path,
    )
    write_replace_map(output_path, replace_map)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print(json.dumps(replace_map, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

