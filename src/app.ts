import express from 'express';
import type { Pool } from 'pg';
import { createApiRouter } from './routes/api.js';
import { createGuiRouter } from './routes/gui.js';
import { formatErrorForLog } from './redaction/index.js';
import { pageLayout } from './ui/html.js';

export function createApp(opts: { pool: Pool }): express.Express {
  const app = express();

  app.disable('x-powered-by');

  app.use(express.json({ limit: '1mb' }));
  app.use(express.urlencoded({ extended: true }));

  app.use('/assets', express.static('public'));

  app.get('/', (_req, res) => res.redirect('/gui'));

  app.use(createApiRouter({ pool: opts.pool }));
  app.use('/gui', createGuiRouter({ pool: opts.pool }));

  app.use(
    (err: unknown, req: express.Request, res: express.Response, _next: express.NextFunction) => {
      console.error(formatErrorForLog(err));
      if (req.accepts('html')) {
        res
          .status(500)
          .type('html')
          .send(
            pageLayout({
              title: 'Internal error',
              body: `<h1>Internal error</h1><div class="muted">Check server logs for details.</div>`,
            }),
          );
        return;
      }
      res.status(500).json({ error: 'internal_error' });
    },
  );

  return app;
}
