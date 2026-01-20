import { Router } from 'express';
import { z } from 'zod';
import type { Pool } from 'pg';
import {
  getCaseById,
  listCaseEvents,
  listCasesWithLatestRun,
  listCourtRuns,
  listPromptUpdates,
  applyPromptUpdate,
  reviewPromptUpdate,
} from '../db/queries.js';
import { UnredactedDataError } from '../redaction/index.js';

function asyncHandler(fn: (req: any, res: any, next: any) => Promise<void>) {
  return (req: any, res: any, next: any) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}

const UuidSchema = z.string().uuid();

const EventFiltersSchema = z.object({
  actor_type: z.string().min(1).optional(),
  actor_id: z.string().min(1).optional(),
  role: z.string().min(1).optional(),
  event_type: z.string().min(1).optional(),
  stage: z.string().min(1).optional(),
});

const PromptUpdatesQuerySchema = z.object({
  case_id: z.string().uuid().optional(),
  status: z.string().min(1).optional(),
});

const ReviewBodySchema = z.object({
  action: z.enum(['approve', 'reject']),
  comment: z.string().optional(),
  reviewer: z.string().optional(),
  redirect_url: z.string().optional(),
});

const ApplyBodySchema = z.object({
  redirect_url: z.string().optional(),
});

export function createApiRouter(opts: { pool: Pool }): Router {
  const router = Router();

  router.get(
    '/cases',
    asyncHandler(async (_req, res) => {
      const cases = await listCasesWithLatestRun(opts.pool);
      res.json(cases);
    }),
  );

  router.get(
    '/cases/:id',
    asyncHandler(async (req, res) => {
      const caseId = UuidSchema.parse(req.params.id);
      const caseRow = await getCaseById(opts.pool, caseId);
      if (!caseRow) return res.status(404).json({ error: 'case_not_found' });
      res.json(caseRow);
    }),
  );

  router.get(
    '/cases/:id/events',
    asyncHandler(async (req, res) => {
      const caseId = UuidSchema.parse(req.params.id);
      const filters = EventFiltersSchema.parse(req.query);
      const events = await listCaseEvents(opts.pool, caseId, filters);
      res.json(events);
    }),
  );

  router.get(
    '/cases/:id/court-runs',
    asyncHandler(async (req, res) => {
      const caseId = UuidSchema.parse(req.params.id);
      const runs = await listCourtRuns(opts.pool, caseId);
      res.json(runs);
    }),
  );

  router.get(
    '/prompt-updates',
    asyncHandler(async (req, res) => {
      const query = PromptUpdatesQuerySchema.parse(req.query);
      const updates = await listPromptUpdates(opts.pool, {
        caseId: query.case_id,
        status: query.status,
      });
      res.json(updates);
    }),
  );

  router.post(
    '/prompt-updates/:id/review',
    asyncHandler(async (req, res) => {
      const promptUpdateId = UuidSchema.parse(req.params.id);
      const parsed = ReviewBodySchema.parse({
        action: req.body.action,
        comment: req.body.comment,
        reviewer: req.body.reviewer ?? req.body.approved_by,
        redirect_url: req.body.redirect_url,
      });

      try {
        const updated = await reviewPromptUpdate(opts.pool, promptUpdateId, parsed.action, {
          comment: parsed.comment,
          approvedBy: parsed.reviewer,
        });

        if (parsed.redirect_url) {
          return res.redirect(303, parsed.redirect_url);
        }
        res.json(updated);
      } catch (err: any) {
        if (err instanceof UnredactedDataError) {
          return res
            .status(400)
            .json({ error: 'sensitive_data_detected', path: err.jsonPath, rule: err.ruleName });
        }
        if (err instanceof Error && err.message === 'NOT_FOUND') {
          return res.status(404).json({ error: 'prompt_update_not_found' });
        }
        if (err instanceof Error && err.message === 'INVALID_STATUS') {
          return res.status(409).json({ error: 'prompt_update_not_proposed' });
        }
        throw err;
      }
    }),
  );

  router.post(
    '/prompt-updates/:id/apply',
    asyncHandler(async (req, res) => {
      const promptUpdateId = UuidSchema.parse(req.params.id);
      const parsed = ApplyBodySchema.parse({
        redirect_url: req.body.redirect_url,
      });

      try {
        const result = await applyPromptUpdate(opts.pool, promptUpdateId);
        if (parsed.redirect_url) {
          return res.redirect(303, parsed.redirect_url);
        }
        res.json(result);
      } catch (err: any) {
        if (err instanceof UnredactedDataError) {
          return res
            .status(400)
            .json({ error: 'sensitive_data_detected', path: err.jsonPath, rule: err.ruleName });
        }
        if (err instanceof Error && err.message === 'NOT_FOUND') {
          return res.status(404).json({ error: 'prompt_update_not_found' });
        }
        if (err instanceof Error && err.message === 'INVALID_STATUS') {
          return res.status(409).json({ error: 'prompt_update_not_approved' });
        }
        if (err instanceof Error && err.message === 'FROM_VERSION_MISMATCH') {
          return res.status(409).json({ error: 'prompt_update_from_version_mismatch' });
        }
        if (err instanceof Error && err.message === 'INVALID_PROPOSAL') {
          return res.status(400).json({ error: 'prompt_update_invalid_proposal' });
        }
        throw err;
      }
    }),
  );

  return router;
}
