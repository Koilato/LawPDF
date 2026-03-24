"""Extract structured enterprise-report fields from OCR Markdown."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


JsonField = list[dict[str, str]]

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
    "注册资本",
    "联系电话",
    "报告生成时间",
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
    "注册资本": ["注册资本"],
    "联系电话": ["联系电话", "联络电话", "联系电话号码"],
    "报告生成时间": ["报告生成时间"],
}

DATE_FIELDS = {"注册日期", "核准日期", "经营日期自", "经营日期至", "报告生成时间"}
RAW_DATE_FIELDS = {
    "成立日期",
    "注册日期",
    "核准日期",
    "经营日期自",
    "经营日期至",
    "营业期限自",
    "营业期限至",
    "报告生成时间",
}


# Read markdown.
def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# Clean line.
def clean_line(line: str) -> str:
    text = line.strip()
    text = text.replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[，。:；：、“”‘’（）《》])", "", text)
    text = re.sub(r"(?<=[，。；：、“”‘’（）《》])\s+(?=[\u4e00-\u9fff])", "", text)
    return text


# Clean line + useful lines.
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


# Extract k:v pairs.
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
        return parts[0].strip(), parts[1].strip()

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


def _normalize_value_by_key(key: str, value: str) -> str:
    cleaned = clean_line(value).strip()
    if key in RAW_DATE_FIELDS or key.endswith("日期"):
        return normalize_cn_date(cleaned)
    return cleaned


# Normalize raw kv.
def normalize_raw_kv(raw_kv: dict[str, Any]) -> dict[str, str | list[str]]:
    normalized: dict[str, str | list[str]] = {}
    for raw_key, raw_value in raw_kv.items():
        key = clean_line(str(raw_key)).rstrip("：:").strip()
        if not key:
            continue

        if isinstance(raw_value, list):
            values: list[str] = []
            for item in raw_value:
                text = _normalize_value_by_key(key, str(item))
                if text and text not in values:
                    values.append(text)
            if values:
                normalized[key] = values if len(values) > 1 else values[0]
            continue

        text = _normalize_value_by_key(key, str(raw_value))
        if text:
            normalized[key] = text

    return normalized


def _first_non_empty_value(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            text = clean_line(str(item)).strip()
            if text:
                return text
        return ""
    return clean_line(str(value)).strip() if value is not None else ""


# Standardize raw_kv with fixed mapping table.
def map_raw_kv_to_standard_fields(raw_kv: dict[str, Any], field_mapping: dict[str, list[str]]) -> dict[str, str]:
    standardized = {field: "" for field in field_mapping.keys()}

    for standard_field, candidate_keys in field_mapping.items():
        for candidate_key in candidate_keys:
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


# Convert standardized fields into project JSON field structure.
def build_output(standardized_fields: dict[str, str], source_name: str) -> dict[str, JsonField]:
    result: dict[str, JsonField] = {field: [] for field in STANDARD_FIELDS}
    for field in STANDARD_FIELDS:
        value = standardized_fields.get(field, "")
        if not value:
            continue
        result[field] = [{"value": value, "source": source_name}]
    return result


# Extract enterprise report.
def extract_enterprise_report(markdown: str, source_name: str) -> dict[str, JsonField]:
    lines = useful_lines(markdown)
    raw_kv = normalize_raw_kv(extract_kv_pairs(lines))
    standardized_fields = map_raw_kv_to_standard_fields(raw_kv, DEFAULT_FIELD_MAPPING)
    return build_output(standardized_fields, source_name)


# Parse args.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract enterprise report fields from markdown.")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the enterprise report markdown file.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write JSON. Prints to stdout if omitted.",
    )
    return parser.parse_args()


# Main.
def main() -> int:
    args = parse_args()
    report_path = Path(args.input).expanduser().resolve()

    if not report_path.is_file():
        print(f"MISSING {report_path}", file=sys.stderr)
        return 1

    result = extract_enterprise_report(
        markdown=read_markdown(report_path),
        source_name=report_path.name,
    )

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    output_text = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
    else:
        sys.stdout.write(output_text)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
