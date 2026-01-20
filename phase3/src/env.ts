import dotenv from 'dotenv';
import { z } from 'zod';

dotenv.config();

const EnvSchema = z.object({
  PORT: z.coerce.number().int().positive().default(3000),
  DATABASE_URL: z.string().min(1).optional(),
  SEED_DEMO_DATA: z.string().optional(),
  REDACTION_POLICY_PATH: z.string().min(1).default('redaction-policy.default.json'),
  OPENAI_API_KEY: z.string().min(1).optional(),
  GITHUB_TOKEN: z.string().min(1).optional(),
});

const parsed = EnvSchema.parse(process.env);

export const env = {
  port: parsed.PORT,
  databaseUrl: parsed.DATABASE_URL,
  seedDemoData: parsed.SEED_DEMO_DATA === '1' || parsed.SEED_DEMO_DATA === 'true',
  redactionPolicyPath: parsed.REDACTION_POLICY_PATH,
  openaiApiKey: parsed.OPENAI_API_KEY,
  githubToken: parsed.GITHUB_TOKEN,
};
