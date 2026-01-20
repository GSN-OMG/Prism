import type { CompiledRedactionPolicy, CompiledRedactionRule } from './policy.js';
import { getRedactionPolicy } from './policy.js';

export class UnredactedDataError extends Error {
  readonly ruleName: string;
  readonly jsonPath: string;

  constructor(opts: { ruleName: string; jsonPath: string }) {
    super(`Unredacted data detected (rule=${opts.ruleName}, path=${opts.jsonPath}).`);
    this.name = 'UnredactedDataError';
    this.ruleName = opts.ruleName;
    this.jsonPath = opts.jsonPath;
  }
}

function* iterStrings(value: unknown, path: string): Generator<{ path: string; text: string }> {
  if (value === null || value === undefined) return;

  if (typeof value === 'string') {
    yield { path, text: value };
    return;
  }

  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) {
      yield* iterStrings(value[i], `${path}[${i}]`);
    }
    return;
  }

  if (typeof value === 'object') {
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      yield* iterStrings(child, `${path}.${key}`);
    }
  }
}

function matches(rule: CompiledRedactionRule, text: string): boolean {
  // `testRegex` is non-global, so it's safe to call multiple times.
  return rule.testRegex.test(text);
}

export function assertNoSensitiveData(
  value: unknown,
  opts: { policy?: CompiledRedactionPolicy } = {},
): void {
  const policy = opts.policy ?? getRedactionPolicy();
  for (const { path, text } of iterStrings(value, '$')) {
    for (const rule of policy.rules) {
      if (!rule.enabled) continue;
      if (matches(rule, text)) {
        throw new UnredactedDataError({ ruleName: rule.name, jsonPath: path });
      }
    }
  }
}
