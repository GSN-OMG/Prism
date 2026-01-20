import crypto from 'node:crypto';
import type { CompiledRedactionPolicy, CompiledRedactionRule } from './policy.js';
import { getRedactionPolicy } from './policy.js';

const DEFAULT_KEEP_START = 4;
const DEFAULT_KEEP_END = 4;

function placeholder(rule: CompiledRedactionRule): string {
  return rule.replacement ?? `***REDACTED:${rule.category}***`;
}

function hashPlaceholder(rule: CompiledRedactionRule, token: string): string {
  const digest = crypto.createHash('sha256').update(token, 'utf8').digest('hex').slice(0, 12);
  return rule.replacement ?? `***REDACTED:${rule.category}:HASH:${digest}***`;
}

export function redactText(
  text: string,
  opts: { policy?: CompiledRedactionPolicy; keepStart?: number; keepEnd?: number } = {},
): string {
  const policy = opts.policy ?? getRedactionPolicy();
  const keepStart = opts.keepStart ?? DEFAULT_KEEP_START;
  const keepEnd = opts.keepEnd ?? DEFAULT_KEEP_END;

  let out = text;
  for (const rule of policy.rules) {
    if (!rule.enabled) continue;

    if (rule.action === 'mask' || rule.action === 'drop') {
      out = out.replace(rule.regex, placeholder(rule));
      continue;
    }

    if (rule.action === 'partial') {
      const middle = placeholder(rule);
      out = out.replace(rule.regex, (match) => {
        if (match.length <= keepStart + keepEnd) return middle;
        return match.slice(0, keepStart) + middle + match.slice(-keepEnd);
      });
      continue;
    }

    if (rule.action === 'hash') {
      out = out.replace(rule.regex, (match) => hashPlaceholder(rule, match));
      continue;
    }

    // Exhaustive check
    const _never: never = rule.action;
    throw new Error(`Unhandled redaction action: ${_never}`);
  }

  return out;
}

export function redactJson(
  value: unknown,
  opts: { policy?: CompiledRedactionPolicy; keepStart?: number; keepEnd?: number } = {},
): unknown {
  if (typeof value === 'string') return redactText(value, opts);
  if (Array.isArray(value)) return value.map((item) => redactJson(item, opts));
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      out[key] = redactJson(child, opts);
    }
    return out;
  }
  return value;
}
