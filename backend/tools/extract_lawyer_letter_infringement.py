"""Classify lawyer-letter paragraphs and rewrite infringement facts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_API_URL = "http://104.168.109.197:8317/v1/chat/completions"
DEFAULT_API_KEY = "sk-001"
DEFAULT_API_MODEL = "gpt-5.1"
VALID_CATEGORIES = {"引言", "权利基础", "侵权事实", "法律评价", "整改要求", "结尾", "其他"}


def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def clean_text(text: str) -> str:
    value = text.strip().replace("&gt;", ">")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[，。；：、“”‘’（）《》])", "", value)
    value = re.sub(r"(?<=[，。；：、“”‘’（）《》])\s+(?=[\u4e00-\u9fff])", "", value)
    return value


def split_paragraphs(markdown: str) -> list[dict[str, Any]]:
    paragraphs: list[dict[str, Any]] = []
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        text = clean_text("".join(buffer))
        buffer.clear()
        if not text:
            return
        paragraphs.append({
            "paragraph_id": len(paragraphs) + 1,
            "text": text,
        })

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


def strip_code_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


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


def parse_json_response(text: str) -> Any:
    return json.loads(extract_json_text(text))


def chat_completion(
    api_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    timeout: int = 120,
    debug_label: str | None = None,
    debug_store: list[dict[str, Any]] | None = None,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = request.Request(api_url, data=data, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTPError {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"LLM URL error: {exc}") from exc

    parsed = json.loads(body)
    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError("LLM 返回中缺少 choices。")

    message = choices[0].get("message") or {}
    content = message.get("content")

    if isinstance(content, str):
        assistant_text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        assistant_text = "".join(parts)
    else:
        raise RuntimeError("LLM 返回的 content 不是可解析文本。")

    if debug_store is not None:
        debug_store.append(
            {
                "stage": debug_label or "chat_completion",
                "request": payload,
                "raw_response": parsed,
                "assistant_content": assistant_text,
            }
        )

    return assistant_text


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
        "其中，侵权事实只包含对方客观实施了什么行为、在哪里实施、使用了什么标识、用于什么载体。"
        "商标权归属、法律评价、涉嫌侵权、不正当竞争判断、停止侵权要求、赔偿要求都不能归为侵权事实。"
        "只返回 JSON，不要输出解释。"
    )

    user_prompt = json.dumps(
        {
            "task": "classify_paragraphs",
            "paragraphs": paragraphs,
            "output_schema": {
                "paragraphs": [
                    {"paragraph_id": 1, "category": "侵权事实"}
                ]
            },
        },
        ensure_ascii=False,
        indent=2,
    )

    content = chat_completion(
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


def extract_fact_components(
    selected_paragraphs: list[dict[str, Any]],
    api_url: str,
    api_key: str,
    model: str,
    debug_store: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not selected_paragraphs:
        return []

    system_prompt = (
        "你是法律事实拆分助手。"
        "你只可以基于输入的侵权事实段落，拆分出其中的客观子事实。"
        "重点拆分两个槽位：商标使用事实原文、字号使用事实原文。"
        "要求："
        "1. 只能摘录或轻微整理原句，不得加入新事实；"
        "2. 商标使用事实原文只保留经营活动中使用标识的事实；"
        "3. 字号使用事实原文只保留企业名称/字号使用的事实；"
        "4. 如果某个槽位不存在，返回空字符串；"
        "5. 只返回 JSON。"
    )

    user_prompt = json.dumps(
        {
            "task": "extract_fact_components",
            "paragraphs": selected_paragraphs,
            "output_schema": {
                "侵权事实拆分": [
                    {
                        "paragraph_id": 3,
                        "商标使用事实原文": "你方在该店铺的门店招牌、店内装饰装潢、眼镜配镜订单等经营场所和经营活动上面，使用了\"老光明\"标识",
                        "字号使用事实原文": "你方企业名称中也含有\"老光明\"字号"
                    }
                ]
            }
        },
        ensure_ascii=False,
        indent=2,
    )

    content = chat_completion(
        api_url=api_url,
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        debug_label="extract_fact_components",
        debug_store=debug_store,
    )
    parsed = parse_json_response(content)
    result_items = parsed.get("侵权事实拆分") or []

    source_map = {item["paragraph_id"]: item["text"] for item in selected_paragraphs}
    extracted: list[dict[str, Any]] = []
    for item in result_items:
        paragraph_id = item.get("paragraph_id")
        if not isinstance(paragraph_id, int) or paragraph_id not in source_map:
            continue
        trademark_fact = item.get("商标使用事实原文", "")
        trade_name_fact = item.get("字号使用事实原文", "")
        extracted.append(
            {
                "paragraph_id": paragraph_id,
                "source_text": source_map[paragraph_id],
                "商标使用事实原文": clean_text(trademark_fact) if isinstance(trademark_fact, str) else "",
                "字号使用事实原文": clean_text(trade_name_fact) if isinstance(trade_name_fact, str) else "",
            }
        )
    return extracted


def rewrite_infringement_facts(
    fact_components: list[dict[str, Any]],
    source_name: str,
    api_url: str,
    api_key: str,
    model: str,
    debug_store: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rewrite_inputs = []
    for item in fact_components:
        trademark_fact = item.get("商标使用事实原文") or ""
        if trademark_fact:
            rewrite_inputs.append(
                {
                    "paragraph_id": item["paragraph_id"],
                    "source_text": trademark_fact,
                }
            )

    if not rewrite_inputs:
        return []

    system_prompt = (
        "你是法律文书事实改写助手。"
        "你只可以基于输入的商标使用事实原文进行轻度改写。"
        "目标是生成适合起诉状使用的客观事实表述。"
        "必须遵守以下规则："
        "1. 只能保留客观行为事实，不能加入法律评价、涉嫌、侵权、不正当竞争等结论；"
        "2. 用第三人称表述，可将你方改为其；"
        "3. 不要再加入企业字号使用事实；"
        "4. 当原文标识为老光明时，可归一表述为光明；"
        "5. 优先使用句式：其在经营眼镜店的A、B、C等上面，大量使用了“光明”作为商标标识。"
        "6. 必须保留 source_text 原文。"
        "只返回 JSON，不要输出解释。"
    )

    user_prompt = json.dumps(
        {
            "task": "rewrite_infringement_facts",
            "facts": rewrite_inputs,
            "output_schema": {
                "侵权事实": [
                    {
                        "paragraph_id": 3,
                        "value": "其在经营眼镜店的门店招牌、店内装饰装潢、眼镜配镜订单等上面，大量使用了“光明”作为商标标识。",
                        "source_text": "你方在该店铺的门店招牌、店内装饰装潢、眼镜配镜订单等经营场所和经营活动上面，使用了\"老光明\"标识"
                    }
                ]
            }
        },
        ensure_ascii=False,
        indent=2,
    )

    content = chat_completion(
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

    source_map = {item["paragraph_id"]: item["source_text"] for item in rewrite_inputs}
    rewritten: list[dict[str, Any]] = []
    for item in result_items:
        paragraph_id = item.get("paragraph_id")
        value = item.get("value")
        source_text = item.get("source_text")
        if not isinstance(paragraph_id, int) or not isinstance(value, str):
            continue
        if paragraph_id not in source_map:
            continue
        rewritten.append(
            {
                "value": clean_text(value),
                "source": source_name,
                "source_text": clean_text(source_text) if isinstance(source_text, str) else source_map[paragraph_id],
                "paragraph_id": paragraph_id,
            }
        )
    return rewritten


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
    selected = [item for item in classified if item["category"] == "侵权事实"]
    fact_components = extract_fact_components(selected, api_url, api_key, model, debug_store)
    rewritten = rewrite_infringement_facts(fact_components, input_path.name, api_url, api_key, model, debug_store)

    result = {
        "侵权事实": rewritten,
        "中间结果": {
            "source": input_path.name,
            "paragraphs": classified,
            "selected_categories": ["侵权事实"],
            "侵权事实拆分": fact_components,
        },
    }
    if include_debug:
        result["中间结果"]["llm_debug"] = debug_store or []
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify lawyer-letter paragraphs and rewrite infringement facts.")
    parser.add_argument("--input", required=True, help="Path to the cleaned lawyer-letter markdown file.")
    parser.add_argument("--output", help="Optional path to write JSON. Prints to stdout if omitted.")
    parser.add_argument("--api-url", default=os.environ.get("LLM_API_URL", DEFAULT_API_URL), help="OpenAI-compatible chat completions URL.")
    parser.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", DEFAULT_API_KEY), help="API key for the LLM endpoint.")
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL", DEFAULT_API_MODEL), help="Model name.")
    parser.add_argument("--debug", action="store_true", help="Include request and raw response details in output JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()

    if not input_path.is_file():
        print(f"MISSING {input_path}", file=sys.stderr)
        return 1
    if not args.api_url:
        print("缺少 --api-url 或环境变量 LLM_API_URL", file=sys.stderr)
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

