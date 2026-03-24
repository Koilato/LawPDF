"""Build logical.json from Defandent and DemandLetter using keyword-based rules."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from independent_case_pipeline.backend.app.config import DEFAULT_LOGICAL_RULES_CONFIG, DEFAULT_TARGET_KEYWORD

ExtractedSources = dict[str, dict[str, Any]]
RuntimeParams = dict[str, str]


# Read JSON.
def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


# Read rules config.
def read_rules_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


# Resolve path.
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


# Stringify.
def _stringify(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return str(value)


# Resolve source value.
def _resolve_source_value(source_name: str, path_parts: list[Any], sources: ExtractedSources, default: str = '') -> str:
    source = sources.get(source_name)
    if source is None:
        return default
    try:
        value = _resolve_path(source, path_parts)
    except KeyError:
        return default
    return _stringify(value)


# Render template.
def _render_template(template: str, values: dict[str, str]) -> str:
    # Replace var.
    def replace_var(match: re.Match[str]) -> str:
        return values.get(match.group(1), '')
    # Match variable names inside {{ ... }} without relying on locale-sensitive character ranges.
    return re.sub(r'\{\{\s*([^{}\s]+)\s*\}\}', replace_var, template)


# Resolve value rule.
def _resolve_value_rule(rule: dict[str, Any], sources: ExtractedSources, params: RuntimeParams) -> str:
    mode = str(rule.get('mode') or 'literal').strip().lower()
    default = _stringify(rule.get('default', ''))
    if mode == 'path':
        return _resolve_source_value(str(rule.get('source') or '').strip(), list(rule.get('path') or []), sources, default=default)
    if mode == 'param':
        name = str(rule.get('name') or rule.get('param') or '').strip()
        return _stringify(params.get(name, default))
    if mode == 'template':
        values = {str(k): _resolve_value_rule(dict(v), sources, params) for k, v in (rule.get('vars') or {}).items()}
        rendered = _render_template(_stringify(rule.get('template', '')), values)
        return rendered or default
    return _stringify(rule.get('value', default))


# Evaluate condition.
def _evaluate_condition(condition: dict[str, Any], sources: ExtractedSources, params: RuntimeParams) -> bool:
    condition_type = str(condition.get('type') or 'contains').strip().lower()
    actual_value = _resolve_source_value(str(condition.get('source') or '').strip(), list(condition.get('path') or []), sources, default='')
    if condition_type == 'exists':
        return bool(actual_value)
    expected = _stringify(condition.get('value', ''))
    param_name = str(condition.get('value_from_param') or '').strip()
    if param_name:
        expected = _stringify(params.get(param_name, expected))
    if condition_type == 'equals':
        return actual_value == expected
    return expected in actual_value


# Build logical from config.
def build_logical_from_config(*, defandent: dict[str, Any], demand_letter: dict[str, Any], config: dict[str, Any], target_keyword: str = DEFAULT_TARGET_KEYWORD) -> dict[str, list[dict[str, str]]]:
    sources: ExtractedSources = {'Defandent': defandent, 'DemandLetter': demand_letter}
    params: RuntimeParams = {'target_keyword': target_keyword}
    conditions = {str(name): _evaluate_condition(dict(rule), sources, params) for name, rule in (config.get('conditions') or {}).items()}

    logical: dict[str, list[dict[str, str]]] = {}
    for field_name, output_rule in (config.get('outputs') or {}).items():
        when = str(output_rule.get('when') or '').strip()
        branch = 'true' if conditions.get(when, False) else 'false'
        selected_rule = output_rule.get(branch) or {'mode': 'literal', 'value': ''}
        value = _resolve_value_rule(dict(selected_rule), sources, params)
        logical[str(field_name)] = [{'value': value, 'source': 'logical'}]
    return logical


# Build logical.
def build_logical(*, defandent: dict[str, Any], demand_letter: dict[str, Any], config_path: Path | None = DEFAULT_LOGICAL_RULES_CONFIG, target_keyword: str = DEFAULT_TARGET_KEYWORD) -> dict[str, list[dict[str, str]]]:
    resolved_config_path = Path(config_path or DEFAULT_LOGICAL_RULES_CONFIG).expanduser().resolve()
    return build_logical_from_config(defandent=defandent, demand_letter=demand_letter, config=read_rules_config(resolved_config_path), target_keyword=target_keyword)


# Write JSON.
def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


# Parse args.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build logical.json from Defandent.json, DemandLetter.json, and logical rules.')
    parser.add_argument('--defandent-json', required=True)
    parser.add_argument('--demand-letter-json', required=True)
    parser.add_argument('--config', default=str(DEFAULT_LOGICAL_RULES_CONFIG))
    parser.add_argument('--target-keyword', default=DEFAULT_TARGET_KEYWORD)
    parser.add_argument('--output', required=True)
    return parser.parse_args()


# Main.
def main() -> int:
    args = parse_args()
    defandent_json_path = Path(args.defandent_json).expanduser().resolve()
    demand_letter_json_path = Path(args.demand_letter_json).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    for path, label in ((defandent_json_path, 'defandent_json'), (demand_letter_json_path, 'demand_letter_json'), (config_path, 'config')):
        if not path.is_file():
            print(f'MISSING {label}: {path}', file=sys.stderr)
            return 1
    logical = build_logical(
        defandent=read_json(defandent_json_path),
        demand_letter=read_json(demand_letter_json_path),
        config_path=config_path,
        target_keyword=args.target_keyword,
    )
    write_json(output_path, logical)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print(json.dumps(logical, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

