"""Export local Codex Desktop threads to Markdown files."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

THREAD_ID_PATTERN = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
DEFAULT_CODEX_HOME = Path.home() / ".codex"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "exports" / "codex_threads"


@dataclass(slots=True)
class ThreadRecord:
    id: str
    title: str
    rollout_path: Path
    created_at: int | None = None
    updated_at: int | None = None
    source: str | None = None
    cwd: str | None = None
    git_branch: str | None = None
    git_origin_url: str | None = None
    archived: bool = False


@dataclass(slots=True)
class RenderEntry:
    source: str
    kind: str
    label: str
    text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Codex Desktop threads from ~/.codex into Markdown files."
    )
    parser.add_argument(
        "--codex-home",
        default=str(DEFAULT_CODEX_HOME),
        help="Codex home directory. Defaults to ~/.codex",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory that will receive the Markdown export.",
    )
    parser.add_argument(
        "--thread-id",
        action="append",
        dest="thread_ids",
        help="Only export the given thread ID. Can be repeated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Only export the newest N matching threads.",
    )
    parser.add_argument(
        "--include-tools",
        action="store_true",
        help="Include tool calls and tool outputs inline in each Markdown file.",
    )
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Include base and developer instructions from the session metadata.",
    )
    return parser.parse_args()


def connect_sqlite(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.is_file():
        return None
    return sqlite3.connect(str(db_path))


def load_thread_index(index_path: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not index_path.is_file():
        return index
    with index_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            thread_id = payload.get("id")
            if isinstance(thread_id, str) and thread_id:
                index[thread_id] = payload
    return index


def find_session_files(sessions_root: Path) -> dict[str, Path]:
    sessions: dict[str, Path] = {}
    if not sessions_root.is_dir():
        return sessions
    for session_path in sessions_root.rglob("*.jsonl"):
        match = THREAD_ID_PATTERN.search(session_path.stem)
        if match:
            sessions[match.group(1)] = session_path
    return sessions


def sanitize_title(value: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub("_", value).strip()
    if not cleaned:
        return "untitled"
    return cleaned[:120].rstrip(" .")


def load_threads(codex_home: Path) -> list[ThreadRecord]:
    session_index = load_thread_index(codex_home / "session_index.jsonl")
    session_files = find_session_files(codex_home / "sessions")
    records: dict[str, ThreadRecord] = {}

    db_path = codex_home / "state_5.sqlite"
    conn = connect_sqlite(db_path)
    if conn is not None:
        conn.row_factory = sqlite3.Row
        try:
            query = """
                SELECT
                    id,
                    title,
                    rollout_path,
                    created_at,
                    updated_at,
                    source,
                    cwd,
                    git_branch,
                    git_origin_url,
                    archived
                FROM threads
                ORDER BY updated_at DESC, created_at DESC
            """
            for row in conn.execute(query):
                thread_id = row["id"]
                rollout_path = Path(row["rollout_path"])
                if thread_id in session_files and not rollout_path.is_file():
                    rollout_path = session_files[thread_id]
                records[thread_id] = ThreadRecord(
                    id=thread_id,
                    title=row["title"] or session_index.get(thread_id, {}).get("thread_name") or thread_id,
                    rollout_path=rollout_path,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    source=row["source"],
                    cwd=row["cwd"],
                    git_branch=row["git_branch"],
                    git_origin_url=row["git_origin_url"],
                    archived=bool(row["archived"]),
                )
        finally:
            conn.close()

    for thread_id, session_path in session_files.items():
        if thread_id in records:
            continue
        indexed = session_index.get(thread_id, {})
        records[thread_id] = ThreadRecord(
            id=thread_id,
            title=indexed.get("thread_name") or thread_id,
            rollout_path=session_path,
        )

    return sorted(
        records.values(),
        key=lambda item: ((item.updated_at or 0), (item.created_at or 0), item.id),
        reverse=True,
    )


def format_timestamp(value: int | None) -> str:
    if not value:
        return "unknown"
    timestamp = datetime.fromtimestamp(value, tz=timezone.utc).astimezone()
    return timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")


def format_json_block(raw_text: str) -> str:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text.strip()
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def extract_message_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""

    fragments: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            fragments.append(text.strip())
            continue

        block_type = str(block.get("type") or "").lower()
        if "image" in block_type:
            image_value = block.get("image_url") or block.get("file_path") or "attachment"
            fragments.append(f"[Image attachment: {image_value}]")
            continue

        if block_type:
            fragments.append(f"[Unsupported content block: {block_type}]")

    return "\n\n".join(fragment for fragment in fragments if fragment).strip()


def append_fenced_block(lines: list[str], language: str, text: str) -> None:
    lines.append(f"```{language}".rstrip())
    lines.append(text.rstrip())
    lines.append("```")


def render_system_sections(lines: list[str], session_meta: dict[str, Any]) -> None:
    base_instructions = session_meta.get("base_instructions") or {}
    base_text = base_instructions.get("text")
    developer_text = session_meta.get("developer_instructions")
    dynamic_tools = session_meta.get("dynamic_tools") or []

    if base_text:
        lines.extend(["", "## Base Instructions", ""])
        append_fenced_block(lines, "text", str(base_text))

    if developer_text:
        lines.extend(["", "## Developer Instructions", ""])
        append_fenced_block(lines, "text", str(developer_text))

    if dynamic_tools:
        tool_names = [
            str(tool.get("name"))
            for tool in dynamic_tools
            if isinstance(tool, dict) and tool.get("name")
        ]
        if tool_names:
            lines.extend(["", "## Dynamic Tools", ""])
            for tool_name in tool_names:
                lines.append(f"- `{tool_name}`")


def build_visible_entry(payload: dict[str, Any]) -> RenderEntry | None:
    payload_type = payload.get("type")
    if payload_type == "user_message":
        text = str(payload.get("message") or "").strip()
        attachments: list[str] = []
        for image in payload.get("images") or []:
            if image:
                attachments.append(f"[Image URL: {image}]")
        for image in payload.get("local_images") or []:
            if image:
                attachments.append(f"[Local image: {image}]")
        if attachments:
            attachment_text = "\n".join(attachments)
            text = f"{text}\n\n{attachment_text}" if text else attachment_text
        if not text:
            return None
        return RenderEntry(source="event_msg", kind="message", label="User", text=text)

    if payload_type == "agent_message":
        text = str(payload.get("message") or "").strip()
        if not text:
            return None
        phase = payload.get("phase")
        label = "Assistant"
        if phase:
            label = f"Assistant ({phase})"
        return RenderEntry(source="event_msg", kind="message", label=label, text=text)

    return None


def build_response_entry(payload: dict[str, Any], include_tools: bool) -> RenderEntry | None:
    item_type = payload.get("type")
    if item_type == "message":
        role = payload.get("role")
        if role not in {"user", "assistant"}:
            return None
        text = extract_message_text(payload.get("content"))
        if not text:
            return None
        phase = payload.get("phase")
        label = role.title()
        if role == "assistant" and phase:
            label = f"Assistant ({phase})"
        return RenderEntry(source="response_item", kind="message", label=label, text=text)

    if item_type == "function_call" and include_tools:
        name = payload.get("name", "unknown")
        text = format_json_block(str(payload.get("arguments") or ""))
        return RenderEntry(source="response_item", kind="tool_call", label=f"Tool Call: `{name}`", text=text)

    if item_type == "function_call_output" and include_tools:
        call_id = payload.get("call_id", "unknown")
        text = str(payload.get("output") or "").strip()
        return RenderEntry(source="response_item", kind="tool_output", label=f"Tool Output: `{call_id}`", text=text)

    return None


def render_entries(lines: list[str], entries: list[RenderEntry]) -> None:
    lines.extend(["", "## Conversation"])
    for entry in entries:
        lines.extend(["", f"### {entry.label}", ""])
        if entry.kind == "message":
            lines.append(entry.text)
            continue
        language = "json" if entry.kind == "tool_call" else "text"
        append_fenced_block(lines, language, entry.text)


def render_thread_markdown(
    record: ThreadRecord,
    include_tools: bool,
    include_system: bool,
) -> str:
    lines = [f"# {record.title}", ""]
    lines.extend(
        [
            "## Metadata",
            "",
            f"- Thread ID: `{record.id}`",
            f"- Created: {format_timestamp(record.created_at)}",
            f"- Updated: {format_timestamp(record.updated_at)}",
            f"- Source: `{record.source or 'unknown'}`",
            f"- Archived: `{'yes' if record.archived else 'no'}`",
            f"- Working Directory: `{record.cwd or 'unknown'}`",
            f"- Rollout Path: `{record.rollout_path}`",
        ]
    )
    if record.git_branch:
        lines.append(f"- Git Branch: `{record.git_branch}`")
    if record.git_origin_url:
        lines.append(f"- Git Origin: `{record.git_origin_url}`")

    session_meta_payload: dict[str, Any] = {}
    entries: list[RenderEntry] = []
    saw_visible_events = False

    if not record.rollout_path.is_file():
        lines.extend(["", "## Warning", "", "Session file was not found on disk."])
        return "\n".join(lines).rstrip() + "\n"

    with record.rollout_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")
            payload = event.get("payload")

            if event_type == "session_meta" and isinstance(payload, dict):
                session_meta_payload = payload
                continue

            if event_type == "event_msg" and isinstance(payload, dict):
                visible_entry = build_visible_entry(payload)
                if visible_entry is not None:
                    saw_visible_events = True
                    entries.append(visible_entry)
                continue

            if event_type == "response_item" and isinstance(payload, dict):
                response_entry = build_response_entry(payload, include_tools=include_tools)
                if response_entry is not None:
                    entries.append(response_entry)

    if saw_visible_events:
        entries = [
            entry
            for entry in entries
            if not (entry.source == "response_item" and entry.kind == "message")
        ]

    if include_system and session_meta_payload:
        render_system_sections(lines, session_meta_payload)

    if entries:
        render_entries(lines, entries)
    else:
        lines.extend(["", "## Conversation", "", "No user-visible conversation content was found in this session file."])

    return "\n".join(lines).rstrip() + "\n"


def write_index(
    output_dir: Path,
    exported_threads: Iterable[ThreadRecord],
    include_tools: bool,
    include_system: bool,
) -> None:
    threads = list(exported_threads)
    lines = [
        "# Codex Thread Export",
        "",
        f"- Generated: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- Threads: {len(threads)}",
        f"- Include Tools: `{'yes' if include_tools else 'no'}`",
        f"- Include System Instructions: `{'yes' if include_system else 'no'}`",
        "",
        "## Files",
        "",
    ]
    for record in threads:
        file_name = f"{record.id}.md"
        lines.append(
            f"- [{sanitize_title(record.title)}]({file_name}) | `{record.id}` | {format_timestamp(record.updated_at)}"
        )

    (output_dir / "index.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    thread_filter = set(args.thread_ids or [])

    threads = load_threads(codex_home)
    if thread_filter:
        threads = [thread for thread in threads if thread.id in thread_filter]
    if args.limit is not None:
        threads = threads[: args.limit]

    if not threads:
        print("No matching threads were found.", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    exported: list[ThreadRecord] = []
    for record in threads:
        rendered = render_thread_markdown(
            record=record,
            include_tools=args.include_tools,
            include_system=args.include_system,
        )
        target_path = output_dir / f"{record.id}.md"
        target_path.write_text(rendered, encoding="utf-8")
        exported.append(record)

    write_index(
        output_dir=output_dir,
        exported_threads=exported,
        include_tools=args.include_tools,
        include_system=args.include_system,
    )

    print(f"Exported {len(exported)} thread(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

