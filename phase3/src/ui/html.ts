export function escapeHtml(unsafe: string): string {
  return unsafe
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

export function pageLayout(opts: { title: string; body: string }): string {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(opts.title)}</title>
    <link rel="stylesheet" href="/assets/styles.css" />
  </head>
  <body>
    <div class="container">
      ${opts.body}
    </div>
  </body>
</html>`;
}

export function renderJson(value: unknown): string {
  return `<pre class="pre">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
}

export function formatDate(value: Date | string | null | undefined): string {
  if (!value) return '';
  if (value instanceof Date) return value.toISOString();
  return String(value);
}
