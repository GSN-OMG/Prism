import { Router } from 'express';
import type { Pool } from 'pg';
import { createTwoFilesPatch } from 'diff';
import { z } from 'zod';
import {
  getCaseById,
  getRolePrompt,
  listCaseEvents,
  listCasesWithLatestRun,
  listCourtRuns,
  listPromptUpdates,
  type PromptUpdateRow,
} from '../db/queries.js';
import { escapeHtml, formatDate, pageLayout, renderJson } from '../ui/html.js';

const UuidSchema = z.string().uuid();

const EventFiltersSchema = z.object({
  actor_type: z.string().min(1).optional(),
  actor_id: z.string().min(1).optional(),
  role: z.string().min(1).optional(),
  event_type: z.string().min(1).optional(),
  stage: z.string().min(1).optional(),
});

function firstString(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
  return undefined;
}

function extractProposedPrompt(proposal: unknown): string | null {
  if (typeof proposal === 'string') return proposal;
  if (!proposal || typeof proposal !== 'object') return null;
  const obj = proposal as Record<string, unknown>;
  for (const key of ['prompt', 'full_prompt', 'fullPrompt']) {
    const value = obj[key];
    if (typeof value === 'string') return value;
  }
  return null;
}

function stageFromMeta(meta: unknown): string | null {
  if (!meta || typeof meta !== 'object') return null;
  const v = (meta as Record<string, unknown>).stage;
  if (typeof v !== 'string' || v.length === 0) return null;
  return v;
}

function eventKind(eventType: string): string {
  const t = eventType.toLowerCase();
  if (t === 'error' || t.endsWith('.error') || t.includes('error')) return 'error';
  if (t === 'model_call') return 'model_call';
  if (t === 'model_result') return 'model_result';
  if (t === 'tool_call') return 'tool_call';
  if (t === 'tool_result') return 'tool_result';
  if (t === 'artifact') return 'artifact';
  if (t.startsWith('github.')) return 'github';
  return 'event';
}

function eventIcon(opts: { actorType: string; stage: string | null; eventType: string }): string {
  if (opts.stage === 'judge') return 'J';
  if (opts.stage === 'prosecutor') return 'P';
  if (opts.stage === 'defense') return 'D';
  if (opts.stage === 'jury') return 'Y';

  const kind = eventKind(opts.eventType);
  if (kind === 'error') return 'ERR';
  if (kind === 'model_call') return 'CALL';
  if (kind === 'model_result') return 'AI';
  if (kind === 'tool_call') return 'TL';
  if (kind === 'tool_result') return 'TL';
  if (kind === 'artifact') return 'AR';

  if (opts.actorType === 'human') return 'H';
  if (opts.actorType === 'ai') return 'AI';
  if (opts.actorType === 'tool') return 'TL';
  return 'SYS';
}

function renderPromptUpdateItem(
  promptUpdate: PromptUpdateRow,
  opts: {
    basePrompt: string | null;
    proposedPrompt: string | null;
    diffText: string | null;
    redirectUrl: string;
  },
): string {
  const summaryParts = [
    `${promptUpdate.role}`,
    promptUpdate.from_version ? `(from v${promptUpdate.from_version})` : '',
    `• ${promptUpdate.status}`,
    promptUpdate.created_at ? `• ${formatDate(promptUpdate.created_at)}` : '',
  ].filter(Boolean);

  return `
  <details class="card">
    <summary class="card__summary">
      <span>${escapeHtml(summaryParts.join(' '))}</span>
    </summary>
    <div class="card__body">
      ${promptUpdate.reason ? `<div class="muted">Reason</div><div class="pre">${escapeHtml(promptUpdate.reason)}</div>` : ''}
      <div class="muted">Proposal (json)</div>
      ${renderJson(promptUpdate.proposal)}

      ${
        opts.diffText
          ? `<div class="muted">Diff</div><pre class="pre pre-diff">${escapeHtml(opts.diffText)}</pre>`
          : ''
      }

      ${
        opts.basePrompt
          ? `<details><summary>Base prompt</summary><pre class="pre">${escapeHtml(opts.basePrompt)}</pre></details>`
          : ''
      }
      ${
        opts.proposedPrompt
          ? `<details><summary>Proposed prompt</summary><pre class="pre">${escapeHtml(opts.proposedPrompt)}</pre></details>`
          : ''
      }

      <form method="post" action="/prompt-updates/${escapeHtml(promptUpdate.id)}/review" class="review-form">
        <input type="hidden" name="redirect_url" value="${escapeHtml(opts.redirectUrl)}" />
        <label class="label">
          <span class="label__title">Reviewer</span>
          <input class="input" type="text" name="reviewer" placeholder="(optional)" />
        </label>
        <label class="label">
          <span class="label__title">Comment</span>
          <textarea class="textarea" name="comment" rows="3" placeholder="(optional)"></textarea>
        </label>
        <div class="row">
          <button class="button button--primary" type="submit" name="action" value="approve">Approve</button>
          <button class="button button--danger" type="submit" name="action" value="reject">Reject</button>
        </div>
      </form>
    </div>
  </details>
  `;
}

function renderApprovedPromptUpdateItem(
  promptUpdate: PromptUpdateRow,
  opts: {
    basePrompt: string | null;
    proposedPrompt: string | null;
    diffText: string | null;
    redirectUrl: string;
  },
): string {
  const summaryParts = [
    `${promptUpdate.role}`,
    promptUpdate.from_version ? `(from v${promptUpdate.from_version})` : '',
    `• ${promptUpdate.status}`,
    promptUpdate.created_at ? `• ${formatDate(promptUpdate.created_at)}` : '',
  ].filter(Boolean);

  return `
  <details class="card">
    <summary class="card__summary">
      <span>${escapeHtml(summaryParts.join(' '))}</span>
    </summary>
    <div class="card__body">
      ${promptUpdate.reason ? `<div class="muted">Reason</div><div class="pre">${escapeHtml(promptUpdate.reason)}</div>` : ''}
      <div class="muted">Proposal (json)</div>
      ${renderJson(promptUpdate.proposal)}

      ${
        opts.diffText
          ? `<div class="muted">Diff</div><pre class="pre pre-diff">${escapeHtml(opts.diffText)}</pre>`
          : ''
      }

      ${
        opts.basePrompt
          ? `<details><summary>Base prompt</summary><pre class="pre">${escapeHtml(opts.basePrompt)}</pre></details>`
          : ''
      }
      ${
        opts.proposedPrompt
          ? `<details><summary>Proposed prompt</summary><pre class="pre">${escapeHtml(opts.proposedPrompt)}</pre></details>`
          : ''
      }

      <form method="post" action="/prompt-updates/${escapeHtml(promptUpdate.id)}/apply" class="review-form">
        <input type="hidden" name="redirect_url" value="${escapeHtml(opts.redirectUrl)}" />
        <div class="row">
          <button class="button button--primary" type="submit">Apply</button>
        </div>
      </form>
    </div>
  </details>
  `;
}

function renderCaseListPage(items: Awaited<ReturnType<typeof listCasesWithLatestRun>>): string {
  const rows = items
    .map((c) => {
      const latest = c.latest_court_run;
      return `<tr>
        <td><a href="/gui/cases/${escapeHtml(c.id)}" class="mono">${escapeHtml(c.id)}</a></td>
        <td>${escapeHtml(formatDate(c.created_at))}</td>
        <td>${escapeHtml(c.summary ?? '')}</td>
        <td>${latest ? escapeHtml(latest.status) : '<span class="muted">(none)</span>'}</td>
      </tr>`;
    })
    .join('');

  return pageLayout({
    title: 'Prism • Cases',
    body: `
      <div class="header">
        <h1>Cases</h1>
        <div class="muted">GUI (review + timeline) • redacted-only</div>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>Case ID</th>
            <th>Created</th>
            <th>Summary</th>
            <th>Latest run</th>
          </tr>
        </thead>
        <tbody>
          ${rows || `<tr><td colspan="4" class="muted">No cases</td></tr>`}
        </tbody>
      </table>
      <div class="muted">
        API: <a href="/cases">GET /cases</a>
      </div>
    `,
  });
}

export function createGuiRouter(opts: { pool: Pool }): Router {
  const router = Router();

  router.get('/', async (_req, res, next) => {
    try {
      const cases = await listCasesWithLatestRun(opts.pool);
      res.type('html').send(renderCaseListPage(cases));
    } catch (err) {
      next(err);
    }
  });

  router.get('/cases/:id', async (req, res, next) => {
    try {
      const caseId = UuidSchema.parse(req.params.id);
      const filters = EventFiltersSchema.parse({
        actor_type: firstString(req.query.actor_type),
        actor_id: firstString(req.query.actor_id),
        role: firstString(req.query.role),
        event_type: firstString(req.query.event_type),
        stage: firstString(req.query.stage),
      });

      const caseRow = await getCaseById(opts.pool, caseId);
      if (!caseRow) {
        res
          .status(404)
          .type('html')
          .send(
            pageLayout({
              title: 'Case not found',
              body: `<a href="/gui">← Back</a><h1>Case not found</h1>`,
            }),
          );
        return;
      }

      const queryParams = new URLSearchParams();
      for (const [k, v] of Object.entries(filters)) {
        if (!v) continue;
        queryParams.set(k, v);
      }
      const queryString = queryParams.toString();
      const redirectUrl = `/gui/cases/${caseId}${queryString ? `?${queryString}` : ''}`;

      const [events, runs, promptUpdates] = await Promise.all([
        listCaseEvents(opts.pool, caseId, filters),
        listCourtRuns(opts.pool, caseId),
        listPromptUpdates(opts.pool, { caseId, status: 'proposed' }),
      ]);
      const approvedPromptUpdates = await listPromptUpdates(opts.pool, {
        caseId,
        status: 'approved',
      });

      const timelineHtml = events
        .map((ev, idx) => {
          const stage = stageFromMeta(ev.meta);
          const icon = eventIcon({ actorType: ev.actor_type, stage, eventType: ev.event_type });
          const kind = eventKind(ev.event_type);
          const parts = [
            ev.ts ? formatDate(ev.ts) : '',
            ev.seq ? `seq=${escapeHtml(String(ev.seq))}` : '',
            `#${ev.id}`,
            ev.event_type,
            ev.actor_type,
            ev.actor_id ? `(${ev.actor_id})` : '',
            ev.role ? `[${ev.role}]` : '',
          ].filter(Boolean);
          const dataAttrs = [
            `data-kind="${escapeHtml(kind)}"`,
            `data-actor-type="${escapeHtml(ev.actor_type)}"`,
            `data-event-type="${escapeHtml(ev.event_type)}"`,
            stage ? `data-stage="${escapeHtml(stage)}"` : '',
            `style="--i:${idx}"`,
          ]
            .filter(Boolean)
            .join(' ');

          return `<details class="card event" ${dataAttrs}>
            <summary class="card__summary" data-icon="${escapeHtml(icon)}">
              <span class="mono">${escapeHtml(parts.join(' '))}</span>
            </summary>
            <div class="card__body">
              <div class="muted">Content</div>
              <pre class="pre">${escapeHtml(ev.content)}</pre>
              ${
                typeof ev.usage !== 'undefined' && ev.usage !== null
                  ? `<div class="muted">Usage</div>${renderJson(ev.usage)}`
                  : ''
              }
              <div class="muted">Meta</div>
              ${renderJson(ev.meta)}
            </div>
          </details>`;
        })
        .join('');

      const runsHtml = runs
        .map((run) => {
          const artifactsObj =
            run.artifacts && typeof run.artifacts === 'object' ? (run.artifacts as any) : null;
          const topLevel = artifactsObj ?? {};
          const containers = [
            topLevel,
            topLevel.agents,
            topLevel.outputs,
            topLevel.results,
            topLevel.artifacts,
          ].filter(Boolean);
          const findKey = (key: string) => {
            for (const c of containers) {
              if (!c || typeof c !== 'object') continue;
              for (const [k, v] of Object.entries(c)) {
                if (k.toLowerCase() === key) return v;
              }
            }
            return undefined;
          };
          const roleOutputs = ['prosecutor', 'defense', 'jury', 'judge']
            .map((role) => {
              const out = findKey(role);
              if (typeof out === 'undefined') return '';
              return `<div class="muted">${escapeHtml(role.toUpperCase())}</div>${renderJson(out)}`;
            })
            .filter(Boolean)
            .join('');

          const summaryParts = [
            `#${run.id}`,
            run.status,
            run.model ? `• ${run.model}` : '',
            run.started_at ? `• ${formatDate(run.started_at)}` : '',
          ].filter(Boolean);

          return `<details class="card">
            <summary class="card__summary">
              <span class="mono">${escapeHtml(summaryParts.join(' '))}</span>
            </summary>
            <div class="card__body">
              ${roleOutputs ? `<div class="muted">Role outputs</div>${roleOutputs}` : ''}
              <div class="muted">Artifacts (json)</div>
              ${renderJson(run.artifacts)}
            </div>
          </details>`;
        })
        .join('');

      const promptUpdatesHtml = await Promise.all(
        promptUpdates.map(async (update) => {
          const proposedPrompt = extractProposedPrompt(update.proposal);
          const basePrompt =
            update.from_version && proposedPrompt
              ? await getRolePrompt(opts.pool, update.role, update.from_version)
              : null;
          const diffText =
            basePrompt?.prompt && proposedPrompt
              ? createTwoFilesPatch('base', 'proposed', basePrompt.prompt, proposedPrompt, '', '')
              : null;
          return renderPromptUpdateItem(update, {
            basePrompt: basePrompt?.prompt ?? null,
            proposedPrompt,
            diffText,
            redirectUrl,
          });
        }),
      );

      const approvedPromptUpdatesHtml = await Promise.all(
        approvedPromptUpdates.map(async (update) => {
          const proposedPrompt = extractProposedPrompt(update.proposal);
          const basePrompt =
            update.from_version && proposedPrompt
              ? await getRolePrompt(opts.pool, update.role, update.from_version)
              : null;
          const diffText =
            basePrompt?.prompt && proposedPrompt
              ? createTwoFilesPatch('base', 'proposed', basePrompt.prompt, proposedPrompt, '', '')
              : null;
          return renderApprovedPromptUpdateItem(update, {
            basePrompt: basePrompt?.prompt ?? null,
            proposedPrompt,
            diffText,
            redirectUrl,
          });
        }),
      );

      res.type('html').send(
        pageLayout({
          title: `Prism • Case ${caseId}`,
          body: `
            <a href="/gui">← Back</a>
            <h1>Case</h1>
            <div class="muted mono">${escapeHtml(caseId)}</div>

            <details class="card" open>
              <summary class="card__summary">Case data</summary>
              <div class="card__body">${renderJson(caseRow)}</div>
            </details>

            <h2>Timeline</h2>
            <div class="timeline-toolbar" data-timeline-toolbar>
              <div class="timeline-toolbar__left">
                <div class="hud">
                  <div class="hud__item"><span class="muted">Events</span> <span class="mono">${events.length}</span></div>
                  <div class="hud__item"><span class="muted">Proposed</span> <span class="mono">${promptUpdates.length}</span></div>
                  <div class="hud__item"><span class="muted">Approved</span> <span class="mono">${approvedPromptUpdates.length}</span></div>
                </div>
              </div>
              <div class="timeline-toolbar__right">
                <button class="button button--primary" type="button" data-timeline-play>Play</button>
                <button class="button" type="button" data-timeline-pause disabled>Pause</button>
                <label class="label label--inline">
                  <span class="label__title">Speed</span>
                  <input class="range" type="range" min="0.5" max="3" step="0.5" value="1" data-timeline-speed />
                </label>
                <div class="timeline-progress" aria-label="Replay progress">
                  <div class="timeline-progress__bar" data-timeline-progress></div>
                </div>
              </div>
            </div>
            <form method="get" class="filters">
              <div class="row">
                <label class="label"><span class="label__title">actor_type</span><input class="input" name="actor_type" value="${escapeHtml(filters.actor_type ?? '')}" /></label>
                <label class="label"><span class="label__title">actor_id</span><input class="input" name="actor_id" value="${escapeHtml(filters.actor_id ?? '')}" /></label>
                <label class="label"><span class="label__title">role</span><input class="input" name="role" value="${escapeHtml(filters.role ?? '')}" /></label>
              </div>
              <div class="row">
                <label class="label"><span class="label__title">event_type</span><input class="input" name="event_type" value="${escapeHtml(filters.event_type ?? '')}" /></label>
                <label class="label"><span class="label__title">stage</span><input class="input" name="stage" value="${escapeHtml(filters.stage ?? '')}" /></label>
              </div>
              <div class="row">
                <button class="button button--primary" type="submit">Apply filters</button>
                <a class="button" href="/gui/cases/${escapeHtml(caseId)}">Reset</a>
                <a class="button" href="/cases/${escapeHtml(caseId)}/events?${escapeHtml(queryString)}">API</a>
              </div>
            </form>
            <div class="timeline" data-timeline>
              ${timelineHtml || `<div class="muted">No events</div>`}
            </div>

            <h2>Court runs</h2>
            ${runsHtml || `<div class="muted">No runs</div>`}

            <h2>Judge prompt update review (proposed)</h2>
            ${promptUpdatesHtml.join('') || `<div class="muted">No proposed prompt updates</div>`}

            <h2>Prompt updates ready to apply (approved)</h2>
            ${approvedPromptUpdatesHtml.join('') || `<div class="muted">No approved prompt updates</div>`}
          `,
        }),
      );
    } catch (err) {
      next(err);
    }
  });

  return router;
}
