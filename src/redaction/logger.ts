import util from 'node:util';
import { redactText } from './redact.js';

export function formatErrorForLog(err: unknown): string {
  if (err instanceof Error) {
    const stack = err.stack ? String(err.stack) : '';
    const message = err.message ? String(err.message) : '';
    const raw = stack.length > 0 ? stack : `${err.name}: ${message}`;
    return redactText(raw);
  }

  if (typeof err === 'string') {
    return redactText(err);
  }

  return redactText(util.inspect(err, { depth: 4, maxArrayLength: 50, breakLength: 120 }));
}
