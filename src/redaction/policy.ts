import fs from 'node:fs';
import path from 'node:path';

export type RedactionAction = 'mask' | 'partial' | 'hash' | 'drop';

export type RedactionRule = {
  name: string;
  category: string;
  action: RedactionAction;
  pattern: string;
  replacement?: string | null;
  enabled?: boolean;
  notes?: string | null;
};

export type RedactionPolicy = {
  version: string;
  description?: string | null;
  rules: RedactionRule[];
};

export type CompiledRedactionRule = {
  name: string;
  category: string;
  action: RedactionAction;
  regex: RegExp;
  testRegex: RegExp;
  replacement?: string | null;
  enabled: boolean;
};

export type CompiledRedactionPolicy = {
  version: string;
  description?: string | null;
  rules: CompiledRedactionRule[];
};

function resolvePolicyPath(rawPath: string): string {
  if (path.isAbsolute(rawPath)) return rawPath;
  return path.resolve(process.cwd(), rawPath);
}

export function defaultRedactionPolicyPath(): string {
  const raw = process.env.REDACTION_POLICY_PATH ?? 'phase3/redaction-policy.default.json';
  return resolvePolicyPath(raw);
}

function compileRegex(pattern: string): { replace: RegExp; test: RegExp } {
  let source = pattern;
  let flags = '';

  if (source.startsWith('(?i)')) {
    source = source.slice(4);
    flags += 'i';
  }

  const replace = new RegExp(source, `${flags}g`);
  const test = new RegExp(source, flags);
  return { replace, test };
}

export function loadRedactionPolicy(
  policyPath: string = defaultRedactionPolicyPath(),
): CompiledRedactionPolicy {
  const raw = JSON.parse(fs.readFileSync(policyPath, 'utf8')) as unknown;

  if (!raw || typeof raw !== 'object') {
    throw new Error('Redaction policy must be a JSON object');
  }

  const version = (raw as any).version;
  const rules = (raw as any).rules;
  const description = (raw as any).description;

  if (typeof version !== 'string' || version.length === 0) {
    throw new Error("Redaction policy missing required field: 'version'");
  }
  if (!Array.isArray(rules) || rules.length === 0) {
    throw new Error("Redaction policy missing required field: non-empty 'rules' array");
  }

  const compiledRules: CompiledRedactionRule[] = [];
  for (const rule of rules) {
    if (!rule || typeof rule !== 'object') {
      throw new Error('Redaction rule must be an object');
    }
    const name = (rule as any).name;
    const category = (rule as any).category;
    const action = (rule as any).action;
    const pattern = (rule as any).pattern;
    const replacement = (rule as any).replacement ?? null;
    const enabled = (rule as any).enabled ?? true;

    if (typeof name !== 'string' || name.length === 0) {
      throw new Error('Redaction rule requires non-empty string name');
    }
    if (typeof category !== 'string' || category.length === 0) {
      throw new Error(`Redaction rule ${name} requires non-empty string category`);
    }
    if (action !== 'mask' && action !== 'partial' && action !== 'hash' && action !== 'drop') {
      throw new Error(`Redaction rule ${name} has invalid action: ${String(action)}`);
    }
    if (typeof pattern !== 'string' || pattern.length === 0) {
      throw new Error(`Redaction rule ${name} requires non-empty string pattern`);
    }
    if (typeof enabled !== 'boolean') {
      throw new Error(`Redaction rule ${name} enabled must be boolean`);
    }

    const { replace, test } = compileRegex(pattern);
    compiledRules.push({
      name,
      category,
      action,
      regex: replace,
      testRegex: test,
      replacement,
      enabled,
    });
  }

  return {
    version,
    description: typeof description === 'string' ? description : null,
    rules: compiledRules,
  };
}

let cachedPolicy: CompiledRedactionPolicy | null = null;
let cachedPath: string | null = null;

export function getRedactionPolicy(): CompiledRedactionPolicy {
  const policyPath = defaultRedactionPolicyPath();
  if (cachedPolicy && cachedPath === policyPath) return cachedPolicy;
  cachedPath = policyPath;
  cachedPolicy = loadRedactionPolicy(policyPath);
  return cachedPolicy;
}
