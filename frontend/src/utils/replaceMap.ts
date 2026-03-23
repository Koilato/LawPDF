import type { ReplaceMapConfig, ReplaceMapConfigRule } from '../types';

function toText(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
}

function resolvePath(data: unknown, pathParts: Array<string | number>): unknown {
  let current: unknown = data;

  for (const part of pathParts) {
    if (typeof part === 'number') {
      if (!Array.isArray(current) || part >= current.length) {
        return undefined;
      }
      current = current[part];
      continue;
    }

    if (Array.isArray(current) && /^\d+$/.test(part)) {
      const index = Number(part);
      if (index >= current.length) {
        return undefined;
      }
      current = current[index];
      continue;
    }

    if (typeof current !== 'object' || current === null || !(part in current)) {
      return undefined;
    }

    current = (current as Record<string, unknown>)[part];
  }

  return current;
}

function renderTemplate(template: string, values: Record<string, string>): string {
  return template.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, key: string) => values[key] ?? '');
}

function resolveRuleValue(
  rule: ReplaceMapConfigRule,
  sources: Record<string, unknown>,
): string {
  if (rule.mode === 'path') {
    const source = sources[rule.source];
    const value = resolvePath(source, rule.path);
    return toText(value ?? rule.default ?? '');
  }

  if (rule.mode === 'literal') {
    return toText(rule.value ?? rule.default ?? '');
  }

  const values = Object.fromEntries(
    Object.entries(rule.vars).map(([key, childRule]) => [key, resolveRuleValue(childRule, sources)]),
  );
  const rendered = renderTemplate(rule.template, values);
  return rendered || toText(rule.default ?? '');
}

export function buildReplaceMap(
  config: ReplaceMapConfig,
  sources: {
    Defandent: unknown;
    DemandLetter: unknown;
    logical?: unknown;
  },
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(config.mappings).map(([keyword, rule]) => [keyword, resolveRuleValue(rule, sources)]),
  );
}

export function safeParseConfig(text: string): ReplaceMapConfig {
  return JSON.parse(text) as ReplaceMapConfig;
}

export function toPrettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

