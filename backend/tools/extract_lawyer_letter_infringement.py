"""Extract structured infringement facts from lawyer-letter markdown."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import openai
from openai import OpenAI


DEFAULT_API_URL = "http://104.168.109.197:8317/v1"
DEFAULT_API_KEY = "sk-001"
DEFAULT_API_MODEL = "gpt-5.1"
VALID_CATEGORIES = {"引言", "权利基础", "侵权事实", "法律评价", "整改要求", "结尾", "其他"}
FACT_SOURCE_CATEGORIES = {"侵权事实", "法律评价"}
VALID_FACT_JUDGMENTS = {"客观事实", "混合法律评价", "非客观事实"}


# Read markdown.
def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# Clean text.
def clean_text(text: str) -> str:
    value = text.strip().replace("&gt;", ">")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[，。；：、“”‘’（）《》])", "", value)
    value = re.sub(r"(?<=[，。；：、“”‘’（）《》])\s+(?=[\u4e00-\u9fff])", "", value)
    return value


def clean_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []

    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = clean_text(item)
        if normalized:
            cleaned.append(normalized)
    return cleaned


def finalize_sentence(text: str) -> str:
    value = clean_text(text)
    if not value:
        return ""
    value = re.sub(r"[；。]+$", "", value)
    return f"{value}。"


def join_sentences(values: list[str]) -> str:
    parts = [re.sub(r"[；。]+$", "", clean_text(value)) for value in values if clean_text(value)]
    if not parts:
        return ""
    if len(parts) == 1:
        return f"{parts[0]}。"
    return "；".join(parts) + "。"


def fallback_rewrite_value(source_text: str) -> str:
    value = clean_text(source_text)
    value = re.sub(r"^近日，据[^，。]+反馈，", "", value)
    value = value.replace("你方", "其")
    value = value.replace("贵方", "其")
    return finalize_sentence(value)


# Split paragraphs.
def split_paragraphs(markdown: str) -> list[dict[str, Any]]:
    paragraphs: list[dict[str, Any]] = []
    buffer: list[str] = []

    # Flush.
    def flush() -> None:
        if not buffer:
            return
        text = clean_text("".join(buffer))
        buffer.clear()
        if not text:
            return
        paragraphs.append(
            {
                "paragraph_id": len(paragraphs) + 1,
                "text": text,
            }
        )

    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if stripped == "<!-- image -->":
            continue
        if stripped.startswith("## "):
            flush()
            continue
        if not stripped:
            flush()
            continue
        buffer.append(clean_text(stripped))

    flush()
    return paragraphs


# Strip code fences.
def strip_code_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


# Extract JSON text.
def extract_json_text(text: str) -> str:
    stripped = strip_code_fences(text)
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped

    first_object = stripped.find("{")
    last_object = stripped.rfind("}")
    if first_object != -1 and last_object != -1 and last_object > first_object:
        return stripped[first_object:last_object + 1]

    first_array = stripped.find("[")
    last_array = stripped.rfind("]")
    if first_array != -1 and last_array != -1 and last_array > first_array:
        return stripped[first_array:last_array + 1]

    raise ValueError("模型返回中未找到 JSON。")


# Parse JSON response.
def parse_json_response(text: str) -> Any:
    return json.loads(extract_json_text(text))


# Build a Responses API payload from chat-style messages.
def build_responses_payload(messages: list[dict[str, str]]) -> tuple[str | None, str | list[dict[str, str]]]:
    instructions_parts: list[str] = []
    response_input: list[dict[str, str]] = []

    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        if role == "system":
            instructions_parts.append(content)
            continue

        normalized_role = role if role in {"user", "assistant", "developer"} else "user"
        response_input.append({"role": normalized_role, "content": content})

    if not response_input:
        raise ValueError("Responses API input is empty.")

    instructions = "\n\n".join(part.strip() for part in instructions_parts if part.strip()) or None
    if len(response_input) == 1 and response_input[0]["role"] == "user":
        return instructions, response_input[0]["content"]
    return instructions, response_input


# Extract text from a Responses API result.
def extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    response_dict = response.to_dict() if hasattr(response, "to_dict") else {}
    parts: list[str] = []
    for item in response_dict.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content_item in item.get("content") or []:
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") in {"output_text", "text"} and isinstance(content_item.get("text"), str):
                parts.append(content_item["text"])

    assistant_text = "".join(parts).strip()
    if assistant_text:
        return assistant_text

    raise RuntimeError("LLM response did not contain parseable text.")


# Responses API call.
def create_response_text(
    api_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    timeout: int = 120,
    debug_label: str | None = None,
    debug_store: list[dict[str, Any]] | None = None,
) -> str:
    instructions, response_input = build_responses_payload(messages)
    payload: dict[str, Any] = {
        "model": model,
        "input": response_input,
        "temperature": temperature,
    }
    if instructions:
        payload["instructions"] = instructions

    try:
        with OpenAI(base_url=api_url, api_key=api_key, timeout=float(timeout)) as client:
            response = client.responses.create(**payload)
    except openai.APIConnectionError as exc:
        raise RuntimeError(f"LLM connection error: {exc}") from exc
    except openai.APIStatusError as exc:
        response_body = ""
        try:
            if exc.response is not None:
                response_body = exc.response.text
        except Exception:
            response_body = ""
        request_id = getattr(exc, "request_id", None)
        detail = f"LLM status error {exc.status_code}"
        if request_id:
            detail += f" (request_id={request_id})"
        if response_body:
            detail += f": {response_body}"
        raise RuntimeError(detail) from exc
    except openai.APIError as exc:
        raise RuntimeError(f"LLM API error: {exc}") from exc

    parsed = response.to_dict() if hasattr(response, "to_dict") else {}
    assistant_text = extract_response_text(response)
    if debug_store is not None:
        debug_store.append(
            {
                "stage": debug_label or "create_response_text",
                "request": payload,
                "raw_response": parsed,
                "assistant_content": assistant_text,
                "request_id": getattr(response, "_request_id", None),
            }
        )

    return assistant_text


# Classify paragraphs.
def classify_paragraphs(
    paragraphs: list[dict[str, Any]],
    api_url: str,
    api_key: str,
    model: str,
    debug_store: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    system_prompt = (
        "你是法律文书段落分类助手。"
        "你的任务是对律师函段落进行单标签分类。"
        "标签只能是：引言、权利基础、侵权事实、法律评价、整改要求、结尾、其他。"
        "其中，侵权事实是指律师函中对相对方客观行为的事实陈述，包括但不限于实施了什么行为、针对什么对象、在何处或何渠道、使用了什么标识/作品/商品/技术、用于什么载体、何时实施等。"
        "如果一个段落同时包含客观行为事实和少量法律评价，但仍能清楚识别出具体行为事实，应优先归为侵权事实。"
        "只有当段落主要内容是权利归属、法律分析、涉嫌侵权或不正当竞争判断、停止侵权要求、赔偿要求时，才不要归为侵权事实。"
        "只返回 JSON，不要输出解释。"
    )

    user_prompt = json.dumps(
        {
            "task": "classify_paragraphs",
            "paragraphs": paragraphs,
            "output_schema": {
                "paragraphs": [{"paragraph_id": 1, "category": "侵权事实"}]
            },
        },
        ensure_ascii=False,
        indent=2,
    )

    content = create_response_text(
        api_url=api_url,
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        debug_label="classify_paragraphs",
        debug_store=debug_store,
    )
    parsed = parse_json_response(content)
    result_items = parsed.get("paragraphs") or []

    category_map: dict[int, str] = {}
    for item in result_items:
        paragraph_id = item.get("paragraph_id")
        category = item.get("category")
        if isinstance(paragraph_id, int) and isinstance(category, str) and category in VALID_CATEGORIES:
            category_map[paragraph_id] = category

    classified: list[dict[str, Any]] = []
    for paragraph in paragraphs:
        classified.append(
            {
                "paragraph_id": paragraph["paragraph_id"],
                "text": paragraph["text"],
                "category": category_map.get(paragraph["paragraph_id"], "其他"),
            }
        )
    return classified


# Extract structured fact judgments.
def extract_fact_judgments(
    candidate_paragraphs: list[dict[str, Any]],
    api_url: str,
    api_key: str,
    model: str,
    debug_store: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not candidate_paragraphs:
        return []

    system_prompt = (
        "你是法律事实结构化助手。"
        "你只可以基于输入的律师函段落，拆分出其中可用于后续侵权事实判断的客观事实项。"
        "这里的侵权事实是律师函提出的行为指控，不等于已经成立的法律侵权结论。"
        "要求："
        "1. 只能摘录或轻微整理原句，不得加入新事实；"
        "2. 一个段落可以拆成多条事实项；"
        "3. 请把客观事实与法律评价严格区分；如原段落夹带“涉嫌侵权”“构成不正当竞争”等结论词，应在判断中体现，但不要把这些结论词写进客观事实原文；"
        "4. 判断只能是：客观事实、混合法律评价、非客观事实；"
        "5. 事实类型可从：标识使用、名称/字号使用、商品销售、宣传推广、制造/提供服务、网络展示、著作权使用、专利/技术实施、其他 中选择最贴近的一项；"
        "6. 涉案对象填写原文中的标识、作品、商品、技术、企业名称或其他争议对象，没有则返回空数组；"
        "7. 场所/渠道/载体填写门店、网页、包装、招牌、订单、宣传物料等，没有则返回空数组；"
        "8. 时间没有就返回空字符串；"
        "9. 只返回 JSON。"
    )

    user_prompt = json.dumps(
        {
            "task": "extract_fact_judgments",
            "paragraphs": candidate_paragraphs,
            "output_schema": {
                "侵权事实判断": [
                    {
                        "fact_id": "3-1",
                        "paragraph_id": 3,
                        "判断": "客观事实",
                        "判断理由": "该片段描述了被函告方实施的具体行为、对象和载体，不包含独立法律结论。",
                        "事实类型": "标识使用",
                        "客观事实原文": "你方在门店招牌、包装袋等载体上使用了\"XX\"标识",
                        "行为主体": "你方",
                        "行为动作": "使用",
                        "行为对象": "\"XX\"标识",
                        "涉案对象": ["XX"],
                        "场所/渠道/载体": ["门店招牌", "包装袋"],
                        "时间": "",
                        "source_text": "原段落全文"
                    }
                ]
            },
        },
        ensure_ascii=False,
        indent=2,
    )

    content = create_response_text(
        api_url=api_url,
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        debug_label="extract_fact_judgments",
        debug_store=debug_store,
    )
    parsed = parse_json_response(content)
    result_items = parsed.get("侵权事实判断") or []

    source_map = {item["paragraph_id"]: item["text"] for item in candidate_paragraphs}
    sequence_map: dict[int, int] = {}
    extracted: list[dict[str, Any]] = []
    for item in result_items:
        paragraph_id = item.get("paragraph_id")
        if not isinstance(paragraph_id, int) or paragraph_id not in source_map:
            continue

        sequence_map[paragraph_id] = sequence_map.get(paragraph_id, 0) + 1
        fact_id = item.get("fact_id")
        if not isinstance(fact_id, str) or not fact_id.strip():
            fact_id = f"{paragraph_id}-{sequence_map[paragraph_id]}"

        objective_text = item.get("客观事实原文", "")
        normalized_objective_text = clean_text(objective_text) if isinstance(objective_text, str) else ""

        judgment = item.get("判断")
        if judgment not in VALID_FACT_JUDGMENTS:
            judgment = "客观事实" if normalized_objective_text else "非客观事实"

        source_text = item.get("source_text")
        extracted.append(
            {
                "fact_id": clean_text(fact_id),
                "paragraph_id": paragraph_id,
                "判断": judgment,
                "判断理由": clean_text(item.get("判断理由", "")) if isinstance(item.get("判断理由"), str) else "",
                "事实类型": clean_text(item.get("事实类型", "")) if isinstance(item.get("事实类型"), str) else "其他",
                "客观事实原文": normalized_objective_text,
                "行为主体": clean_text(item.get("行为主体", "")) if isinstance(item.get("行为主体"), str) else "",
                "行为动作": clean_text(item.get("行为动作", "")) if isinstance(item.get("行为动作"), str) else "",
                "行为对象": clean_text(item.get("行为对象", "")) if isinstance(item.get("行为对象"), str) else "",
                "涉案对象": clean_string_list(item.get("涉案对象")),
                "场所/渠道/载体": clean_string_list(item.get("场所/渠道/载体")),
                "时间": clean_text(item.get("时间", "")) if isinstance(item.get("时间"), str) else "",
                "source_text": clean_text(source_text) if isinstance(source_text, str) and source_text.strip() else source_map[paragraph_id],
            }
        )
    return extracted


# Rewrite infringement facts.
def rewrite_infringement_facts(
    fact_judgments: list[dict[str, Any]],
    source_name: str,
    api_url: str,
    api_key: str,
    model: str,
    debug_store: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    preferred_judgments = [
        item
        for item in fact_judgments
        if item.get("判断") == "客观事实" and item.get("客观事实原文")
    ]
    if not preferred_judgments:
        preferred_judgments = [
            item
            for item in fact_judgments
            if item.get("判断") == "混合法律评价" and item.get("客观事实原文")
        ]

    rewrite_inputs = []
    for item in preferred_judgments:
        objective_fact = item.get("客观事实原文") or ""
        rewrite_inputs.append(
            {
                "fact_id": item["fact_id"],
                "paragraph_id": item["paragraph_id"],
                "source_text": objective_fact,
            }
        )

    if not rewrite_inputs:
        return []

    system_prompt = (
        "你是法律文书事实归纳助手。"
        "你只可以基于输入的客观事实原文进行轻度改写。"
        "目标是生成适合起诉状“事实与理由”部分使用的中性客观表述。"
        "必须遵守以下规则："
        "1. 只能保留客观行为事实，不能加入法律评价、涉嫌、侵权、违法、不正当竞争等结论；"
        "2. 尽量使用第三人称表述，可将“你方”改为“其”；"
        "3. 不得擅自归一化、替换或删改争议对象名称；原文写什么就保留什么；"
        "4. 尽量保留行为、对象、场所或渠道、载体、时间等关键事实；"
        "5. 必须保留 fact_id、paragraph_id 和 source_text 原文。"
        "只返回 JSON，不要输出解释。"
    )

    user_prompt = json.dumps(
        {
            "task": "rewrite_infringement_facts",
            "facts": rewrite_inputs,
            "output_schema": {
                "侵权事实": [
                    {
                        "fact_id": "3-1",
                        "paragraph_id": 3,
                        "value": "其在门店招牌、包装袋等载体上使用了\"XX\"标识。",
                        "source_text": "你方在门店招牌、包装袋等载体上使用了\"XX\"标识"
                    }
                ]
            },
        },
        ensure_ascii=False,
        indent=2,
    )

    content = create_response_text(
        api_url=api_url,
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        debug_label="rewrite_infringement_facts",
        debug_store=debug_store,
    )
    parsed = parse_json_response(content)
    result_items = parsed.get("侵权事实") or []

    source_map = {item["fact_id"]: item for item in rewrite_inputs}
    rewritten: list[dict[str, Any]] = []
    seen_fact_ids: set[str] = set()
    for item in result_items:
        paragraph_id = item.get("paragraph_id")
        value = item.get("value")
        source_text = item.get("source_text")
        fact_id = item.get("fact_id")
        if not isinstance(paragraph_id, int) or not isinstance(value, str):
            continue
        if not isinstance(fact_id, str) or fact_id not in source_map:
            continue
        source_item = source_map[fact_id]
        seen_fact_ids.add(fact_id)
        rewritten.append(
            {
                "fact_id": clean_text(fact_id),
                "value": finalize_sentence(value),
                "source": source_name,
                "source_text": clean_text(source_text) if isinstance(source_text, str) and source_text.strip() else source_item["source_text"],
                "paragraph_id": paragraph_id,
            }
        )

    for item in rewrite_inputs:
        if item["fact_id"] in seen_fact_ids:
            continue
        rewritten.append(
            {
                "fact_id": item["fact_id"],
                "value": fallback_rewrite_value(item["source_text"]),
                "source": source_name,
                "source_text": item["source_text"],
                "paragraph_id": item["paragraph_id"],
            }
        )
    return rewritten


def build_fact_summary(rewritten_facts: list[dict[str, Any]], source_name: str) -> list[dict[str, Any]]:
    if not rewritten_facts:
        return []

    return [
        {
            "value": join_sentences([item["value"] for item in rewritten_facts]),
            "source": source_name,
            "source_text": join_sentences([item["source_text"] for item in rewritten_facts]),
            "paragraph_ids": sorted({item["paragraph_id"] for item in rewritten_facts}),
            "fact_ids": [item["fact_id"] for item in rewritten_facts],
        }
    ]


# Build output.
def build_output(
    input_path: Path,
    api_url: str,
    api_key: str,
    model: str,
    include_debug: bool = False,
) -> dict[str, Any]:
    markdown = read_markdown(input_path)
    paragraphs = split_paragraphs(markdown)
    debug_store: list[dict[str, Any]] | None = [] if include_debug else None
    classified = classify_paragraphs(paragraphs, api_url, api_key, model, debug_store)
    selected = [item for item in classified if item["category"] in FACT_SOURCE_CATEGORIES]
    fact_judgments = extract_fact_judgments(selected, api_url, api_key, model, debug_store)
    rewritten_details = rewrite_infringement_facts(fact_judgments, input_path.name, api_url, api_key, model, debug_store)
    rewritten_summary = build_fact_summary(rewritten_details, input_path.name)

    result = {
        "侵权事实": rewritten_summary,
        "侵权事实明细": rewritten_details,
        "中间结果": {
            "source": input_path.name,
            "paragraphs": classified,
            "selected_categories": sorted(FACT_SOURCE_CATEGORIES),
            "侵权事实判断": fact_judgments,
        },
    }
    if include_debug:
        result["中间结果"]["llm_debug"] = debug_store or []
    return result


# Parse args.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract structured infringement facts from lawyer-letter markdown.")
    parser.add_argument("--input", required=True, help="Path to the cleaned lawyer-letter markdown file.")
    parser.add_argument("--output", help="Optional path to write JSON. Prints to stdout if omitted.")
    parser.add_argument(
        "--api-url",
        "--base-url",
        dest="api_url",
        default=os.environ.get("LLM_BASE_URL") or os.environ.get("LLM_API_URL", DEFAULT_API_URL),
        help="OpenAI-compatible API base URL.",
    )
    parser.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", DEFAULT_API_KEY), help="API key for the LLM endpoint.")
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL", DEFAULT_API_MODEL), help="Model name.")
    parser.add_argument("--debug", action="store_true", help="Include request and raw response details in output JSON.")
    return parser.parse_args()


# Main.
def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()

    if not input_path.is_file():
        print(f"MISSING {input_path}", file=sys.stderr)
        return 1
    if not args.api_url:
        print("缺少 --api-url/--base-url 或环境变量 LLM_BASE_URL/LLM_API_URL", file=sys.stderr)
        return 1
    if not args.api_key:
        print("缺少 --api-key 或环境变量 LLM_API_KEY", file=sys.stderr)
        return 1
    if not args.model:
        print("缺少 --model 或环境变量 LLM_MODEL", file=sys.stderr)
        return 1

    result = build_output(
        input_path=input_path,
        api_url=args.api_url,
        api_key=args.api_key,
        model=args.model,
        include_debug=args.debug,
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
