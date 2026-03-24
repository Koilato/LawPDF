"""Standalone enterprise-report standardizer based on fixed field mappings."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


STANDARD_FIELDS = [
    "统一社会信用代码",
    "名称",
    "经营者",
    "注册日期",
    "核准日期",
    "类型",
    "组成形式",
    "登记机关",
    "登记状态",
    "经营场所",
    "经营范围",
    "经营日期自",
    "经营日期至",
]

DEFAULT_FIELD_MAPPING: dict[str, list[str]] = {
    "统一社会信用代码": ["统一社会信用代码"],
    "名称": ["名称", "企业名称"],
    "经营者": ["经营者", "投资人", "法定代表人", "负责人"],
    "注册日期": ["注册日期", "成立日期"],
    "核准日期": ["核准日期"],
    "类型": ["类型"],
    "组成形式": ["组成形式"],
    "登记机关": ["登记机关"],
    "登记状态": ["登记状态"],
    "经营场所": ["经营场所", "住所"],
    "经营范围": ["经营范围"],
    "经营日期自": ["经营日期自", "营业期限自"],
    "经营日期至": ["经营日期至", "营业期限至"],
}

DATE_FIELDS = {"注册日期", "核准日期", "经营日期自", "经营日期至"}
RAW_DATE_FIELDS = {
    "成立日期",
    "注册日期",
    "核准日期",
    "经营日期自",
    "经营日期至",
    "营业期限自",
    "营业期限至",
}


def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


# Clean line.
def clean_line(line: str) -> str:
    text = line.strip()
    text = text.replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[，。:；：、“”‘’（）《》])", "", text)
    text = re.sub(r"(?<=[，。；：、“”‘’（）《》])\s+(?=[\u4e00-\u9fff])", "", text)
    return text


# Useful lines.
def useful_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = clean_line(raw_line)
        if not line or line == "<!-- image -->":
            continue
        lines.append(line)
    return lines


# Normalize cn date.
def normalize_cn_date(value: str | None) -> str:
    if not value:
        return ""

    text = clean_line(value)
    patterns = [
        r"(\d{4})年\s*0?(\d{1,2})月\s*0?(\d{1,2})日",
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
        r"(\d{4})\.(\d{1,2})\.(\d{1,2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{year}年{int(month)}月{int(day)}日"

    return text


# Extract k:v json from markdown lines.
def extract_kv_pairs(lines: list[str]) -> dict[str, str | list[str]]:
    result: dict[str, str | list[str]] = {}

    def add_kv(key: str, value: str) -> None:
        key = key.rstrip("：:").strip()
        value = value.strip()

        if not key or not value:
            return

        if key in result:
            existing = result[key]
            if isinstance(existing, list):
                if value not in existing:
                    existing.append(value)
            else:
                if value != existing:
                    result[key] = [existing, value]
        else:
            result[key] = value

    def is_key_line(text: str) -> bool:
        text = text.strip()
        if not text or text.startswith("##"):
            return False

        if "：" not in text and ":" not in text:
            return False

        parts = re.split(r"[：:]", text, maxsplit=1)
        if len(parts) != 2:
            return False

        key = parts[0].strip()
        if not key:
            return False

        if not re.search(r"[\u4e00-\u9fff]", key):
            return False

        return True

    def split_key_value(text: str) -> tuple[str, str]:
        parts = re.split(r"[：:]", text, maxsplit=1)
        key = parts[0].strip()
        value = parts[1].strip()
        return key, value

    def find_next_value(start_index: int) -> str | None:
        for i in range(start_index + 1, len(lines)):
            candidate = lines[i].strip()

            if not candidate:
                continue

            if candidate.startswith("##"):
                continue

            if is_key_line(candidate):
                return None

            return candidate

        return None

    for index, line in enumerate(lines):
        text = line.strip()
        if not is_key_line(text):
            continue

        key, value = split_key_value(text)

        if value:
            add_kv(key, value)
            continue

        next_value = find_next_value(index)
        if next_value is not None:
            add_kv(key, next_value)

    return result


def normalize_raw_kv(raw_kv: dict[str, Any]) -> dict[str, str | list[str]]:
    normalized: dict[str, str | list[str]] = {}
    for raw_key, raw_value in raw_kv.items():
        key = clean_line(str(raw_key)).rstrip("：:").strip()
        if not key:
            continue

        if isinstance(raw_value, list):
            values: list[str] = []
            for item in raw_value:
                text = clean_line(str(item)).strip()
                if key in RAW_DATE_FIELDS or key.endswith("日期"):
                    text = normalize_cn_date(text)
                if text and text not in values:
                    values.append(text)
            if values:
                normalized[key] = values if len(values) > 1 else values[0]
            continue

        text = clean_line(str(raw_value)).strip()
        if key in RAW_DATE_FIELDS or key.endswith("日期"):
            text = normalize_cn_date(text)
        if text:
            normalized[key] = text

    return normalized


def read_field_mapping(path: Path | None) -> dict[str, list[str]]:
    if path is None:
        return dict(DEFAULT_FIELD_MAPPING)

    mapping = read_json(path)
    result: dict[str, list[str]] = {}
    for standard_field, raw_keys in mapping.items():
        keys = [clean_line(str(item)).strip() for item in raw_keys if clean_line(str(item)).strip()]
        result[clean_line(str(standard_field)).strip()] = keys
    return result


def _first_non_empty_value(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            text = clean_line(str(item)).strip()
            if text:
                return text
        return ""
    return clean_line(str(value)).strip() if value is not None else ""


# Standardize raw_kv with a fixed mapping table.
def map_raw_kv_to_standard_fields(
    raw_kv: dict[str, Any],
    field_mapping: dict[str, list[str]],
) -> dict[str, str]:
    standardized = {field: "" for field in STANDARD_FIELDS}

    for standard_field in STANDARD_FIELDS:
        for candidate_key in field_mapping.get(standard_field, []):
            if candidate_key not in raw_kv:
                continue

            value = _first_non_empty_value(raw_kv[candidate_key])
            if not value:
                continue

            if standard_field in DATE_FIELDS:
                value = normalize_cn_date(value)

            standardized[standard_field] = value
            break

    return standardized


def standardize_enterprise_markdown(markdown: str, field_mapping: dict[str, list[str]]) -> tuple[dict[str, str | list[str]], dict[str, str]]:
    lines = useful_lines(markdown)
    raw_kv = normalize_raw_kv(extract_kv_pairs(lines))
    standardized_fields = map_raw_kv_to_standard_fields(raw_kv, field_mapping)
    return raw_kv, standardized_fields


def standardize_enterprise_raw_kv(raw_kv: dict[str, Any], field_mapping: dict[str, list[str]]) -> tuple[dict[str, str | list[str]], dict[str, str]]:
    normalized_raw_kv = normalize_raw_kv(raw_kv)
    standardized_fields = map_raw_kv_to_standard_fields(normalized_raw_kv, field_mapping)
    return normalized_raw_kv, standardized_fields


# Legacy LLM-based implementation kept for reference and intentionally disabled.
# It is not used by the current script.
'''
DEFAULT_API_URL = os.environ.get("LLM_API_URL", "http://104.168.109.197:8317/v1/chat/completions")
DEFAULT_API_KEY = os.environ.get("LLM_API_KEY", "sk-001")
DEFAULT_API_MODEL = os.environ.get("LLM_MODEL", "gpt-5.1")

SYSTEM_PROMPT = """你是企业信用信息公示报告字段标准化助手。
输入中的 raw_kv 已经由程序清洗完成，你不要重新做 OCR 抽取，只需要把 raw_kv 映射为固定模板字段。
...省略旧版 LLM prompt...
"""

def strip_code_fences(text: str) -> str:
    ...

def extract_json_text(text: str) -> str:
    ...

def parse_json_response(text: str) -> Any:
    ...

def chat_completion(api_url: str, api_key: str, model: str, messages: list[dict[str, str]], temperature: float = 0.0, timeout: int = 120) -> str:
    ...

def build_user_prompt(source_name: str, raw_kv: dict[str, str | list[str]]) -> str:
    ...

def standardize_raw_kv_with_llm(raw_kv: dict[str, str | list[str]], source_name: str, api_url: str, api_key: str, model: str) -> dict[str, str]:
    ...
'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standardize enterprise-report data with a fixed field mapping table.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--input", help="Path to the enterprise-report markdown file.")
    source_group.add_argument("--raw-kv-json", help="Path to an already extracted raw_kv JSON file.")
    parser.add_argument("--mapping", help="Optional path to the field mapping JSON file.")
    parser.add_argument("--output", help="Optional path to write JSON. Prints to stdout if omitted.")
    parser.add_argument("--debug", action="store_true", help="Include raw_kv and field_mapping in the output JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mapping_path = Path(args.mapping).expanduser().resolve() if args.mapping else None
    field_mapping = read_field_mapping(mapping_path)

    if args.input:
        input_path = Path(args.input).expanduser().resolve()
        if not input_path.is_file():
            print(f"MISSING {input_path}", file=sys.stderr)
            return 1
        raw_kv, standardized_fields = standardize_enterprise_markdown(read_markdown(input_path), field_mapping)
    else:
        raw_kv_path = Path(args.raw_kv_json).expanduser().resolve()
        if not raw_kv_path.is_file():
            print(f"MISSING {raw_kv_path}", file=sys.stderr)
            return 1
        raw_kv, standardized_fields = standardize_enterprise_raw_kv(read_json(raw_kv_path), field_mapping)

    result: dict[str, Any] | dict[str, str]
    if args.debug:
        result = {
            "raw_kv": raw_kv,
            "field_mapping": field_mapping,
            "standardized_fields": standardized_fields,
        }
    else:
        result = standardized_fields

    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        sys.stdout.write(output_text)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
