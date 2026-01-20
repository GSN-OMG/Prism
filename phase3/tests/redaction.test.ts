import { describe, expect, it } from 'vitest';
import path from 'node:path';

import { assertNoSensitiveData, UnredactedDataError } from '../src/redaction/guard.js';
import { loadRedactionPolicy } from '../src/redaction/policy.js';
import { redactJson, redactText } from '../src/redaction/redact.js';

const policyPath = path.resolve(process.cwd(), 'redaction-policy.default.json');
const policy = loadRedactionPolicy(policyPath);

describe('redaction (TS)', () => {
  it('redacts OpenAI key-like tokens (partial)', () => {
    const token = 'sk-proj-1234567890abcdefghijklmnopqrstuv';
    const out = redactText(`key=${token}`, { policy });
    expect(out).toContain('***REDACTED:secret***');
    expect(out).not.toContain(token);
  });

  it('redacts bearer tokens case-insensitively', () => {
    const out = redactText('bearer abcdefghijklmnop', { policy });
    expect(out).toBe('***REDACTED:secret***');
  });

  it('redacts nested JSON objects', () => {
    const payload = {
      meta: { authorization: 'Bearer abcdef' },
      events: [{ content: 'email me at user@example.com' }],
    };
    const out = redactJson(payload, { policy }) as any;
    expect(out.meta.authorization).toBe('***REDACTED:secret***');
    expect(out.events[0].content).toContain('***REDACTED:pii***');
  });

  it('guard reports the rule and json path', () => {
    const payload = { msg: 'token=ghp_1234567890abcdefghijklmnopqrstuvwxYZ12' };
    try {
      assertNoSensitiveData(payload, { policy });
      throw new Error('expected UnredactedDataError');
    } catch (err) {
      expect(err).toBeInstanceOf(UnredactedDataError);
      const e = err as UnredactedDataError;
      expect(e.ruleName).toBe('github_token_like');
      expect(e.jsonPath).toBe('$.msg');
    }
  });
});
