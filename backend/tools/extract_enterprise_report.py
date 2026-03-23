"""Extract structured enterprise-report fields from OCR Markdown."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


JsonField = list[dict[str, str]]


def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def clean_line(line: str) -> str:
    text = line.strip()
    text = text.replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[，。；：、“”‘’（）《》])", "", text)
    text = re.sub(r"(?<=[，。；：、“”‘’（）《》])\s+(?=[\u4e00-\u9fff])", "", text)
    return text


def useful_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = clean_line(raw_line)
        if not line or line == "<!-- image -->":
            continue
        lines.append(line)
    return lines


def label_candidates(label: str) -> list[str]:
    normalized = label.rstrip("：:")
    return [label, f"{normalized}：", f"{normalized}:"]


def extract_labeled_value(lines: list[str], label: str) -> str | None:
    candidates = label_candidates(label)

    for index, line in enumerate(lines):
        for candidate in candidates:
            if line == candidate:
                for next_index in range(index + 1, len(lines)):
                    value = lines[next_index].strip()
                    if value:
                        return value

            if line.startswith(candidate):
                tail = line[len(candidate) :].strip()
                if tail:
                    return tail

                for next_index in range(index + 1, len(lines)):
                    value = lines[next_index].strip()
                    if value:
                        return value

    return None


def extract_first_value(lines: list[str], labels: list[str]) -> str | None:
    for label in labels:
        value = extract_labeled_value(lines, label)
        if value:
            return value
    return None


def normalize_cn_date(value: str | None) -> str | None:
    if not value:
        return None

    text = clean_line(value)
    match = re.search(r"(\d{4})年0?(\d{1,2})月0?(\d{1,2})日", text)
    if match:
        year, month, day = match.groups()
        return f"{year}年{int(month)}月{int(day)}日"

    match = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{year}年{int(month)}月{int(day)}日"

    return clean_line(value)


def to_entries(value: str | None, source_name: str) -> JsonField:
    if value is None:
        return []

    normalized = clean_line(value)
    if not normalized:
        return []

    return [{"value": normalized, "source": source_name}]


def extract_enterprise_report(markdown: str, source_name: str) -> dict[str, JsonField]:
    lines = useful_lines(markdown)

    company_name = extract_first_value(lines, ["企业名称", "名称"])
    credit_code = extract_first_value(lines, ["统一社会信用代码"])
    company_type = extract_first_value(lines, ["类型"])

    # 个体工商户/个人独资等企业报告里常见的是“负责人”“投资人”或“经营者”，
    # 这里统一归一化输出到“法定代表人”，避免后续 replace_map 再分支处理。
    legal_representative = extract_first_value(
        lines,
        ["法定代表人", "负责人", "投资人", "经营者"],
    )

    registered_capital = extract_first_value(lines, ["注册资本"])
    established_date = extract_first_value(lines, ["成立日期", "注册日期"])
    business_term_from = extract_first_value(lines, ["营业期限自"])
    business_term_to = extract_first_value(lines, ["营业期限至"])
    registration_authority = extract_first_value(lines, ["登记机关"])
    approval_date = extract_first_value(lines, ["核准日期"])
    registration_status = extract_first_value(lines, ["登记状态"])
    address = extract_first_value(lines, ["住所", "经营场所"])
    business_scope = extract_first_value(lines, ["经营范围"])
    report_generated_at = extract_first_value(lines, ["报告生成时间"])

    return {
        "企业名称": to_entries(company_name, source_name),
        "统一社会信用代码": to_entries(credit_code, source_name),
        "类型": to_entries(company_type, source_name),
        "法定代表人": to_entries(legal_representative, source_name),
        "注册资本": to_entries(registered_capital, source_name),
        "成立日期": to_entries(normalize_cn_date(established_date), source_name),
        "营业期限自": to_entries(normalize_cn_date(business_term_from), source_name),
        "营业期限至": to_entries(normalize_cn_date(business_term_to), source_name),
        "登记机关": to_entries(registration_authority, source_name),
        "核准日期": to_entries(normalize_cn_date(approval_date), source_name),
        "登记状态": to_entries(registration_status, source_name),
        "住所": to_entries(address, source_name),
        "送达地址": to_entries(address, source_name),
        "经营范围": to_entries(business_scope, source_name),
        "报告生成时间": to_entries(report_generated_at, source_name),
    }


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
