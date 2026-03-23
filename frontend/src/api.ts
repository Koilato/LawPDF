import type { AppSettings, BackendSettingsResponse, ExtractResponse, RenderResponse, UploadSelection } from './types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

interface UploadPayload {
  name: string;
  contentBase64: string;
}

interface ExtractRequestPayload {
  case_name?: string;
  files: Partial<Record<'enterpriseReportPdf' | 'lawyerLetterPdf' | 'templateFile', UploadPayload>>;
  settings: Partial<AppSettings>;
  replace_map_config_text?: string;
}

interface RenderRequestPayload {
  case_name: string;
  template_file_path?: string;
  template_file?: UploadPayload;
  replace_map: Record<string, string>;
  settings: Partial<AppSettings>;
}

function normalizeSettings(payload: BackendSettingsResponse['settings']): AppSettings {
  return {
    apiUrl: payload.api_url,
    apiKey: payload.api_key,
    model: payload.model,
    targetKeyword: payload.target_keyword ?? '光明',
    trimLastPageForLawyerLetter: payload.trim_last_page_for_lawyer_letter,
    writeIntermediateJsons: payload.write_intermediate_jsons,
    debug: payload.debug,
    imageAlign: payload.image_align,
    imageWidthCm: payload.image_width_cm ?? undefined,
    imageHeightCm: payload.image_height_cm ?? undefined,
  };
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const data = (await response.json()) as T & { message?: string; status?: string };
  if (!response.ok || (typeof data === 'object' && data !== null && 'status' in data && data.status === 'error')) {
    const message = typeof data === 'object' && data !== null && 'message' in data ? data.message : `HTTP ${response.status}`;
    throw new Error(message || `HTTP ${response.status}`);
  }
  return data;
}

async function fileToBase64(file: File): Promise<string> {
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : '';
      const [, base64 = ''] = result.split(',', 2);
      resolve(base64);
    };
    reader.onerror = () => reject(reader.error ?? new Error(`无法读取文件：${file.name}`));
    reader.readAsDataURL(file);
  });
}

async function serializeFile(file: File): Promise<UploadPayload> {
  return {
    name: file.name,
    contentBase64: await fileToBase64(file),
  };
}

export async function fetchBackendSettings(): Promise<{
  settings: AppSettings;
  replaceMapConfigText: string;
  apiBaseUrl: string;
}> {
  const response = await fetch(`${API_BASE_URL}/api/settings`);
  const data = await parseJsonResponse<BackendSettingsResponse>(response);
  return {
    settings: normalizeSettings(data.settings),
    replaceMapConfigText: data.replace_map_config_text,
    apiBaseUrl: data.settings.api_base_url,
  };
}

export async function extractCaseData(options: {
  files: UploadSelection;
  settings: AppSettings;
  replaceMapConfigText: string;
  caseName?: string;
}): Promise<ExtractResponse> {
  const { files, settings, replaceMapConfigText, caseName } = options;
  if (!files.enterpriseReportPdf || !files.lawyerLetterPdf) {
    throw new Error('请先选择企业报告 PDF 和律师函 PDF');
  }

  const payload: ExtractRequestPayload = {
    case_name: caseName,
    files: {
      enterpriseReportPdf: await serializeFile(files.enterpriseReportPdf),
      lawyerLetterPdf: await serializeFile(files.lawyerLetterPdf),
    },
    settings,
    replace_map_config_text: replaceMapConfigText,
  };

  if (files.templateFile) {
    payload.files.templateFile = await serializeFile(files.templateFile);
  }

  const response = await fetch(`${API_BASE_URL}/api/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return await parseJsonResponse<ExtractResponse>(response);
}

export async function renderWordDocument(options: {
  caseName: string;
  replaceMap: Record<string, string>;
  settings: AppSettings;
  templateFilePath?: string;
  templateFile?: File | null;
}): Promise<RenderResponse> {
  const payload: RenderRequestPayload = {
    case_name: options.caseName,
    template_file_path: options.templateFilePath,
    replace_map: options.replaceMap,
    settings: options.settings,
  };

  if (options.templateFile) {
    payload.template_file = await serializeFile(options.templateFile);
  }

  const response = await fetch(`${API_BASE_URL}/api/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return await parseJsonResponse<RenderResponse>(response);
}

export { API_BASE_URL };
