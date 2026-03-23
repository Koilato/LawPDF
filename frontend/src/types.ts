export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];
export interface JsonObject {
  [key: string]: JsonValue;
}

export interface AppSettings {
  apiUrl: string;
  apiKey: string;
  model: string;
  targetKeyword: string;
  trimLastPageForLawyerLetter: boolean;
  writeIntermediateJsons: boolean;
  debug: boolean;
  imageAlign: 'left' | 'center' | 'right';
  imageWidthCm?: number;
  imageHeightCm?: number;
}

export interface ReplaceMapConfigPathRule {
  mode: 'path';
  source: 'Defandent' | 'DemandLetter' | 'logical';
  path: Array<string | number>;
  default?: string;
  required?: boolean;
  editable?: boolean;
  description?: string;
}

export interface ReplaceMapConfigLiteralRule {
  mode: 'literal';
  value: string;
  default?: string;
  required?: boolean;
  editable?: boolean;
  description?: string;
}

export interface ReplaceMapConfigTemplateRule {
  mode: 'template';
  template: string;
  vars: Record<string, ReplaceMapConfigRule>;
  default?: string;
  required?: boolean;
  editable?: boolean;
  description?: string;
}

export type ReplaceMapConfigRule =
  | ReplaceMapConfigPathRule
  | ReplaceMapConfigLiteralRule
  | ReplaceMapConfigTemplateRule;

export interface ReplaceMapConfig {
  schema_version: string;
  name: string;
  description?: string;
  on_missing?: 'empty' | 'error';
  mappings: Record<string, ReplaceMapConfigRule>;
}

export interface UploadSelection {
  enterpriseReportPdf?: File | null;
  lawyerLetterPdf?: File | null;
  templateFile?: File | null;
}

export interface LogItem {
  id: string;
  time: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

export interface OutputSummary {
  caseName?: string;
  docxPath?: string;
  replaceMapPath?: string;
  manifestPath?: string;
  downloadUrl?: string;
  status: 'idle' | 'ready' | 'success' | 'error';
}

export interface BackendSettingsResponse {
  status: 'ok' | 'error';
  settings: {
    trim_last_page_for_lawyer_letter: boolean;
    write_intermediate_jsons: boolean;
    debug: boolean;
    image_align: 'left' | 'center' | 'right';
    image_width_cm?: number | null;
    image_height_cm?: number | null;
    api_url: string;
    api_key: string;
    model: string;
    target_keyword: string;
    replace_map_config: string;
    cases_root: string;
    api_base_url: string;
  };
  replace_map_config_text: string;
}

export interface ExtractResponse {
  status: 'ok' | 'error';
  case_name: string;
  case_dir: string;
  paths: Record<string, string | null>;
  markdowns: {
    enterprise_report: string;
    lawyer_letter: string;
  };
  Defandent: JsonObject;
  DemandLetter: JsonObject;
  logical: JsonObject;
  replace_map_config_text: string;
  replace_map: Record<string, string>;
  message?: string;
}

export interface RenderResponse {
  status: 'ok' | 'error';
  case_name?: string;
  output_docx?: string;
  replace_map_json?: string;
  word_job_json?: string;
  manifest_path?: string;
  download_url?: string;
  processed?: number;
  message?: string;
}

