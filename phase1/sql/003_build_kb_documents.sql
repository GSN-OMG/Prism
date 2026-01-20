WITH item_docs AS (
  SELECT
    md5(repo_full_name || '|' || type || '|' || number::text || '|title_body') AS kb_id,
    repo_full_name,
    type AS item_type,
    number AS item_number,
    'title_body' AS section,
    url AS source_ref,
    closed_at,
    (
      CASE WHEN type = 'pr' THEN 'PR' ELSE 'Issue' END
      || ' #' || number::text
      || E'\nTitle: ' || title
      || CASE WHEN body_excerpt <> '' THEN E'\n\nBody: ' || body_excerpt ELSE '' END
      || CASE WHEN labels_json <> '[]'::jsonb THEN E'\n\nLabels: ' || (SELECT string_agg(x, ', ') FROM jsonb_array_elements_text(labels_json) AS x) ELSE '' END
    ) AS text,
    jsonb_build_object(
      'url', url,
      'labels', labels_json,
      'author_login', author_login,
      'author_association', author_association,
      'milestone_title', milestone_title,
      'is_merged', is_merged,
      'merged_at', merged_at,
      'merged_by', merged_by
    ) AS metadata
  FROM repo_work_item
  WHERE closed_at IS NOT NULL
),
maintainer_comments AS (
  SELECT
    md5(c.repo_full_name || '|' || c.type || '|' || c.number::text || '|comment|' || c.comment_id) AS kb_id,
    c.repo_full_name,
    c.type AS item_type,
    c.number AS item_number,
    'comment' AS section,
    c.url AS source_ref,
    wi.closed_at,
    (
      'Comment by ' || c.author_login
      || CASE WHEN c.author_association <> '' THEN ' (' || c.author_association || ')' ELSE '' END
      || E'\n' || c.body_excerpt
    ) AS text,
    jsonb_build_object(
      'comment_id', c.comment_id,
      'comment_url', c.url,
      'author_login', c.author_login,
      'author_association', c.author_association,
      'work_item_url', wi.url,
      'work_item_title', wi.title
    ) AS metadata
  FROM repo_comment c
  JOIN repo_work_item wi
    ON wi.repo_full_name = c.repo_full_name
   AND wi.type = c.type
   AND wi.number = c.number
  WHERE wi.closed_at IS NOT NULL
    AND c.author_association IN ('MEMBER', 'OWNER', 'COLLABORATOR')
    AND c.body_excerpt <> ''
),
review_docs AS (
  SELECT
    md5(r.repo_full_name || '|pr|' || r.pr_number::text || '|review|' || r.review_id) AS kb_id,
    r.repo_full_name,
    'pr' AS item_type,
    r.pr_number AS item_number,
    'review' AS section,
    r.reference AS source_ref,
    wi.closed_at,
    (
      'Review by ' || r.author_login
      || CASE WHEN r.review_state <> '' THEN ' [' || r.review_state || ']' ELSE '' END
      || CASE WHEN r.body_excerpt <> '' THEN E'\n' || r.body_excerpt ELSE '' END
    ) AS text,
    jsonb_build_object(
      'review_id', r.review_id,
      'review_state', r.review_state,
      'author_login', r.author_login,
      'work_item_url', wi.url,
      'work_item_title', wi.title
    ) AS metadata
  FROM repo_pr_review r
  JOIN repo_work_item wi
    ON wi.repo_full_name = r.repo_full_name
   AND wi.type = 'pr'
   AND wi.number = r.pr_number
  WHERE wi.closed_at IS NOT NULL
),
all_docs AS (
  SELECT * FROM item_docs
  UNION ALL
  SELECT * FROM maintainer_comments
  UNION ALL
  SELECT * FROM review_docs
)
INSERT INTO kb_document(kb_id, repo_full_name, item_type, item_number, section, source_ref, closed_at, text, metadata, source_hash)
SELECT
  kb_id,
  repo_full_name,
  item_type,
  item_number,
  section,
  source_ref,
  closed_at,
  text,
  metadata,
  md5(coalesce(text, '') || '|' || coalesce(metadata::text, '')) AS source_hash
FROM all_docs
ON CONFLICT (kb_id) DO UPDATE SET
  repo_full_name = EXCLUDED.repo_full_name,
  item_type = EXCLUDED.item_type,
  item_number = EXCLUDED.item_number,
  section = EXCLUDED.section,
  source_ref = EXCLUDED.source_ref,
  closed_at = EXCLUDED.closed_at,
  text = EXCLUDED.text,
  metadata = EXCLUDED.metadata,
  source_hash = EXCLUDED.source_hash;
