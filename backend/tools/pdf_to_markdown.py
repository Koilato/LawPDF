"""Convert PDF files to Markdown with Docling OCR."""

from __future__ import annotations

import argparse
import os
import time
import traceback
from pathlib import Path

import huggingface_hub.file_download as hf_file_download
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


# Disable HF symlinks.
def disable_hf_symlinks() -> None:
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    hf_file_download.are_symlinks_supported = lambda cache_dir=None: False


# Build docling converter.
def build_docling_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.accelerator_options.device = "cpu"

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


# Convert with docling.
def convert_with_docling(converter: DocumentConverter, pdf_path: Path) -> str:
    result = converter.convert(str(pdf_path))
    return result.document.export_to_markdown()


# Failure markdown.
def failure_markdown(pdf_path: Path, exc: Exception) -> str:
    return "\n".join(
        [
            "# Conversion Failed: docling",
            "",
            f"- source: `{pdf_path}`",
            f"- error: `{type(exc).__name__}`",
            "",
            "```text",
            "".join(traceback.format_exception(exc)).rstrip(),
            "```",
            "",
        ]
    )


# Ensure non empty.
def ensure_non_empty(markdown: str, pdf_path: Path) -> str:
    if markdown.strip():
        return markdown

    return "\n".join(
        [
            "# Empty Output: docling",
            "",
            f"- source: `{pdf_path}`",
            "- note: Docling returned an empty Markdown string.",
            "",
        ]
    )


# Write output.
def write_output(output_path: Path, content: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


# Main.
def main() -> int:
    parser = argparse.ArgumentParser(description="Convert PDFs to Markdown with docling.")
    parser.add_argument("pdfs", nargs="+", help="One or more PDF files to process.")
    parser.add_argument(
        "--output-dir",
        default="pdfocr_outputs",
        help="Directory where Markdown files will be written.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    pdf_paths = [Path(pdf).expanduser().resolve() for pdf in args.pdfs]

    missing = [str(pdf) for pdf in pdf_paths if not pdf.exists()]
    if missing:
        for item in missing:
            print(f"MISSING {item}")
        return 1

    disable_hf_symlinks()
    docling_converter = build_docling_converter()

    for pdf_path in pdf_paths:
        output_path = output_dir / f"{pdf_path.stem}.md"
        started_at = time.perf_counter()

        try:
            markdown = convert_with_docling(docling_converter, pdf_path)
            markdown = ensure_non_empty(markdown, pdf_path)
            write_output(output_path, markdown)
            elapsed = time.perf_counter() - started_at
            print(f"OK docling {pdf_path.name} -> {output_path} ({elapsed:.2f}s)")
        except Exception as exc:
            failure_text = failure_markdown(pdf_path, exc)
            write_output(output_path, failure_text)
            elapsed = time.perf_counter() - started_at
            print(f"FAIL docling {pdf_path.name} -> {output_path} ({elapsed:.2f}s)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
