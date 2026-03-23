"""Local HTTP API that exposes settings, extraction, rendering, and file download endpoints."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from independent_case_pipeline.backend.app.config import (
    DEFAULT_CASES_ROOT,
    DEFAULT_TARGET_KEYWORD,
    DEFAULT_REPLACE_MAP_CONFIG,
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    DEFAULT_UPLOADS_ROOT,
    STORAGE_ROOT,
    get_default_frontend_settings,
)
from independent_case_pipeline.backend.app.routes.extract import handle_extract
from independent_case_pipeline.backend.app.routes.render import handle_render
from independent_case_pipeline.backend.app.routes.settings import handle_settings
from independent_case_pipeline.backend.app.services.extract_service import copy_input_file, prepare_case_dirs, write_json
from independent_case_pipeline.backend.app.services.render_service import build_word_job_dict, sanitize_output_stem, write_word_job
from independent_case_pipeline.backend.app.services.replace_map_service import build_replace_map_from_config, write_replace_map

# Frontend development server allowed to call this local backend.
ALLOWED_ORIGIN = 'http://127.0.0.1:5173'

# Field names expected from the frontend request body when files are sent as base64 JSON blobs.
ENTERPRISE_REPORT_FIELD = 'enterpriseReportPdf'
LAWYER_LETTER_FIELD = 'lawyerLetterPdf'
TEMPLATE_FIELD = 'templateFile'


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get('Content-Length') or '0')
    raw = handler.rfile.read(content_length) if content_length > 0 else b'{}'
    if not raw:
        return {}
    return json.loads(raw.decode('utf-8'))


def _send_json(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    handler.send_response(status)
    _send_cors_headers(handler)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)



def _send_file(handler: BaseHTTPRequestHandler, file_path: Path) -> None:
    content = file_path.read_bytes()
    mime_type = mimetypes.guess_type(file_path.name)[0] or 'application/octet-stream'
    handler.send_response(HTTPStatus.OK)
    _send_cors_headers(handler)
    handler.send_header('Content-Type', mime_type)
    handler.send_header('Content-Length', str(len(content)))
    handler.send_header('Content-Disposition', f"attachment; filename*=UTF-8''{quote(file_path.name)}")
    handler.end_headers()
    handler.wfile.write(content)



def _send_cors_headers(handler: BaseHTTPRequestHandler) -> None:
    origin = handler.headers.get('Origin') or ALLOWED_ORIGIN
    handler.send_header('Access-Control-Allow-Origin', origin)
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type')



def _error_response(handler: BaseHTTPRequestHandler, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
    _send_json(handler, {'status': 'error', 'message': message}, status=status)



def _sanitize_case_name(raw_name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', '_', raw_name).strip().strip('.')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned or f'case_{time.strftime("%Y%m%d_%H%M%S")}'



def _guess_case_name(payload: dict[str, Any]) -> str:
    explicit = str(payload.get('case_name') or '').strip()
    if explicit:
        return _sanitize_case_name(explicit)

    files = payload.get('files') or {}
    for key in (LAWYER_LETTER_FIELD, ENTERPRISE_REPORT_FIELD, TEMPLATE_FIELD):
        upload = files.get(key) or {}
        name = str(upload.get('name') or '').strip()
        if name:
            return _sanitize_case_name(Path(name).stem)

    return _sanitize_case_name(f'case_{time.strftime("%Y%m%d_%H%M%S")}')



def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path



def _write_upload(upload: dict[str, Any], target_dir: Path) -> Path:
    file_name = str(upload.get('name') or '').strip()
    content_base64 = upload.get('contentBase64') or upload.get('content_base64') or ''
    if not file_name or not content_base64:
        raise ValueError('Uploaded file payload must include name and contentBase64')

    safe_file_name = re.sub(r'[<>:"/\\|?*]+', '_', Path(file_name).name).strip() or 'uploaded_file'
    output_path = _ensure_dir(target_dir) / safe_file_name
    output_path.write_bytes(base64.b64decode(content_base64))
    return output_path



def _read_replace_map_config_text(payload: dict[str, Any]) -> str:
    text = payload.get('replace_map_config_text')
    if isinstance(text, str) and text.strip():
        return text
    return DEFAULT_REPLACE_MAP_CONFIG.read_text(encoding='utf-8-sig')



def _relative_storage_path(path: Path) -> str:
    return str(path.resolve())



def _storage_download_url(path: Path) -> str:
    return f'/api/files?path={quote(_relative_storage_path(path))}'



def _is_within_storage(path: Path) -> bool:
    try:
        path.resolve().relative_to(STORAGE_ROOT.resolve())
        return True
    except ValueError:
        return False



def _copy_template_into_case(template_path: Path, input_dir: Path) -> Path:
    destination = input_dir / template_path.name
    if template_path.resolve() == destination.resolve():
        return destination
    return copy_input_file(template_path, input_dir)


def _read_case_defandent(case_dir: Path) -> dict[str, Any]:
    data_path = case_dir / 'data' / 'Defandent.json'
    if not data_path.is_file():
        return {}
    try:
        return json.loads(data_path.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}


def _first_non_empty(values: list[str]) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def _resolve_output_name(case_dir: Path, replace_map: dict[str, Any], template_path: Path) -> str:
    defandent = _read_case_defandent(case_dir)
    company_name = ''
    try:
        company_name = str(defandent['企业名称'][0]['value']).strip()
    except Exception:
        company_name = ''

    fallback_name = _first_non_empty([
        company_name,
        str(replace_map.get('[--需要替换的被告--]') or ''),
        str(replace_map.get('[--需要替换的被告2--]') or ''),
        template_path.stem,
    ])
    return sanitize_output_stem(fallback_name, template_path.stem)



def _handle_settings_request() -> dict[str, Any]:
    return {
        'status': 'ok',
        'settings': handle_settings(),
        'replace_map_config_text': DEFAULT_REPLACE_MAP_CONFIG.read_text(encoding='utf-8-sig'),
    }



def _handle_extract_request(payload: dict[str, Any]) -> dict[str, Any]:
    files = payload.get('files') or {}
    if ENTERPRISE_REPORT_FIELD not in files or LAWYER_LETTER_FIELD not in files:
        raise ValueError('缺少企业报告或律师函 PDF 文件')

    case_name = _guess_case_name(payload)
    upload_dir = _ensure_dir(DEFAULT_UPLOADS_ROOT / case_name / f'upload_{int(time.time() * 1000)}')

    enterprise_pdf_path = _write_upload(dict(files[ENTERPRISE_REPORT_FIELD]), upload_dir)
    lawyer_pdf_path = _write_upload(dict(files[LAWYER_LETTER_FIELD]), upload_dir)

    settings = payload.get('settings') or {}
    extract_result = handle_extract({
        'case_name': case_name,
        'lawyer_letter_pdf': str(lawyer_pdf_path),
        'enterprise_report_pdf': str(enterprise_pdf_path),
        'cases_root': str(DEFAULT_CASES_ROOT),
        'trim_last_page_for_lawyer_letter': bool(settings.get('trimLastPageForLawyerLetter', settings.get('trim_last_page_for_lawyer_letter', True))),
        'write_intermediate_jsons': bool(settings.get('writeIntermediateJsons', settings.get('write_intermediate_jsons', False))),
        'debug': bool(settings.get('debug', False)),
        'api_url': settings.get('apiUrl') or settings.get('api_url'),
        'api_key': settings.get('apiKey') or settings.get('api_key'),
        'model': settings.get('model'),
        'target_keyword': settings.get('targetKeyword') or settings.get('target_keyword') or DEFAULT_TARGET_KEYWORD,
    })

    replace_map_config_text = _read_replace_map_config_text(payload)
    replace_map_config = json.loads(replace_map_config_text)
    replace_map = build_replace_map_from_config(
        defandent=extract_result['Defandent'],
        demand_letter=extract_result['DemandLetter'],
        logical=extract_result['logical'],
        config=replace_map_config,
    )

    replace_dir = Path(extract_result['paths']['replace_dir'])
    replace_map_path = write_replace_map(replace_dir / 'replace_map.json', replace_map)
    config_path = write_json(replace_dir / 'replace_map_config.runtime.json', replace_map_config)

    template_case_path = None
    template_upload = files.get(TEMPLATE_FIELD)
    if isinstance(template_upload, dict) and template_upload.get('name'):
        uploaded_template_path = _write_upload(dict(template_upload), upload_dir)
        template_case_path = _copy_template_into_case(uploaded_template_path, Path(extract_result['paths']['input_dir']))

    return {
        'status': 'ok',
        'case_name': case_name,
        'case_dir': extract_result['case_dir'],
        'paths': {
            **extract_result['paths'],
            'replace_map_json': str(replace_map_path),
            'replace_map_config_runtime': str(config_path),
            'template_file': str(template_case_path) if template_case_path else None,
        },
        'markdowns': extract_result['markdowns'],
        'Defandent': extract_result['Defandent'],
        'DemandLetter': extract_result['DemandLetter'],
        'logical': extract_result['logical'],
        'replace_map_config_text': replace_map_config_text,
        'replace_map': replace_map,
    }



def _handle_render_request(payload: dict[str, Any]) -> dict[str, Any]:
    raw_case_name = str(payload.get('case_name') or '').strip()
    if not raw_case_name:
        raise ValueError('缺少 case_name')
    case_name = _sanitize_case_name(raw_case_name)

    replace_map = payload.get('replace_map') or {}
    if not isinstance(replace_map, dict) or not replace_map:
        raise ValueError('缺少 replace_map 或 replace_map 为空')

    dirs = prepare_case_dirs(case_name, DEFAULT_CASES_ROOT)
    settings = payload.get('settings') or {}

    template_path_value = payload.get('template_file_path')
    template_path = Path(template_path_value).expanduser().resolve() if template_path_value else None

    template_upload = payload.get('template_file')
    if isinstance(template_upload, dict) and template_upload.get('name'):
        upload_dir = _ensure_dir(DEFAULT_UPLOADS_ROOT / case_name / f'render_{int(time.time() * 1000)}')
        uploaded_template_path = _write_upload(template_upload, upload_dir)
        template_path = _copy_template_into_case(uploaded_template_path, dirs['input_dir'])

    if template_path is None:
        candidates = sorted(dirs['input_dir'].glob('*.doc')) + sorted(dirs['input_dir'].glob('*.docx'))
        if not candidates:
            raise ValueError('缺少 Word 模板，请先在抽取阶段上传模板或在渲染阶段重新提供模板')
        template_path = candidates[0]

    template_in_case = _copy_template_into_case(template_path, dirs['input_dir'])
    output_name = _resolve_output_name(dirs['case_dir'], replace_map, template_in_case)

    replace_map_path = write_replace_map(dirs['replace_dir'] / 'replace_map.json', replace_map)
    word_job_dict = build_word_job_dict(
        replace_map=replace_map,
        input_files=[str(template_in_case)],
        output_dir=str(dirs['word_output_dir']),
        input_base_dir=str(dirs['input_dir']),
        output_name=output_name,
        image_align=settings.get('imageAlign') or settings.get('image_align'),
        image_width_cm=settings.get('imageWidthCm', settings.get('image_width_cm')),
        image_height_cm=settings.get('imageHeightCm', settings.get('image_height_cm')),
    )
    word_job_path = write_word_job(dirs['replace_dir'] / 'word_job.json', word_job_dict)

    render_result = handle_render({
        'replace_map': replace_map,
        'input_files': [str(template_in_case)],
        'output_dir': str(dirs['word_output_dir']),
        'input_base_dir': str(dirs['input_dir']),
        'output_name': output_name,
        'image_align': settings.get('imageAlign') or settings.get('image_align'),
        'image_width_cm': settings.get('imageWidthCm', settings.get('image_width_cm')),
        'image_height_cm': settings.get('imageHeightCm', settings.get('image_height_cm')),
    })

    output_docx = dirs['word_output_dir'] / f'{output_name}.docx'
    manifest = {
        'status': 'ok',
        'case_name': case_name,
        'replace_map_json': str(replace_map_path),
        'word_job_json': str(word_job_path),
        'output_docx': str(output_docx),
        'download_url': _storage_download_url(output_docx),
        'processed': render_result['processed'],
        'finished_at': time.time(),
    }
    manifest_path = write_json(dirs['case_dir'] / 'render_manifest.json', manifest)
    manifest['manifest_path'] = str(manifest_path)
    return manifest



class CasePipelineRequestHandler(BaseHTTPRequestHandler):
    """Serve the local frontend with JSON APIs for extraction, rendering, and file download."""

    server_version = 'CasePipelineHTTP/1.0'

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        _send_cors_headers(self)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == '/api/health':
            _send_json(self, {'status': 'ok'})
            return
        if parsed.path == '/api/settings':
            _send_json(self, _handle_settings_request())
            return
        if parsed.path == '/api/files':
            query = parse_qs(parsed.query)
            path_value = query.get('path', [''])[0]
            if not path_value:
                _error_response(self, '缺少文件路径参数')
                return
            file_path = Path(path_value).expanduser().resolve()
            if not file_path.is_file() or not _is_within_storage(file_path):
                _error_response(self, '文件不存在或不允许访问', status=HTTPStatus.NOT_FOUND)
                return
            _send_file(self, file_path)
            return
        _error_response(self, f'未知 GET 路径: {parsed.path}', status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = _read_json_body(self)
            if parsed.path == '/api/extract':
                _send_json(self, _handle_extract_request(payload))
                return
            if parsed.path == '/api/render':
                _send_json(self, _handle_render_request(payload))
                return
            _error_response(self, f'未知 POST 路径: {parsed.path}', status=HTTPStatus.NOT_FOUND)
        except FileNotFoundError as exc:
            _error_response(self, str(exc), status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            _error_response(self, str(exc), status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive API boundary
            _error_response(self, f'{type(exc).__name__}: {exc}', status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        message = format % args
        sys.stdout.write(f'[backend] {self.address_string()} {message}\n')



def serve(host: str = DEFAULT_SERVER_HOST, port: int = DEFAULT_SERVER_PORT) -> None:
    _ensure_dir(DEFAULT_UPLOADS_ROOT)
    _ensure_dir(DEFAULT_CASES_ROOT)
    server = ThreadingHTTPServer((host, port), CasePipelineRequestHandler)
    print(f'Case pipeline backend listening on http://{host}:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping backend server...')
    finally:
        server.server_close()



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the local backend HTTP API for the case pipeline frontend.')
    parser.add_argument('--host', default=DEFAULT_SERVER_HOST, help='Host address for the local backend server.')
    parser.add_argument('--port', type=int, default=DEFAULT_SERVER_PORT, help='Port for the local backend server.')
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    serve(host=args.host, port=args.port)
    return 0


__all__ = [
    'CasePipelineRequestHandler',
    'DEFAULT_SERVER_HOST',
    'DEFAULT_SERVER_PORT',
    'get_default_frontend_settings',
    'handle_extract',
    'handle_render',
    'handle_settings',
    'main',
    'serve',
]


if __name__ == '__main__':
    raise SystemExit(main())





