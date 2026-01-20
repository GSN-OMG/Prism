# openai/openai-agents-python 최근 2주(ClosedAt 기준) PR/Issue 수집·정규화·KB/에이전트 산출물 기획서 (초안)

기준일: **2026-01-20 (UTC)**  
대상 기간(최근 2주): **2026-01-06T00:00:00Z ~ 2026-01-20T23:59:59Z** (ClosedAt 기준, inclusive)

> 목표: `is:pr state:closed` + `is:issue state:closed`의 **상세 내용과 메타데이터를 가능한 한 “완전 스냅샷”**으로 가져와서  
> 1) Raw(JSON) 보존, 2) RDB 정규화, 3) KB 인덱스/에이전트 프롬프트·카드, 4) 컨트리뷰터 통계 테이블을 생성한다.

---

## 0) 의사결정/가정

- **기간 필터는 `closedAt` 기준**으로만 한다.
  - PR은 “merged”도 “closed without merge”도 `closedAt`에 잡힌다.
  - “최근 업데이트(updatedAt)”가 아니라 **닫힌 시점** 기준이라, 기간 내에 닫히지 않은 오래된 PR/Issue는 제외된다.
- 시간대/경계 문제 방지:
  - API 쿼리에서는 `closed:YYYY-MM-DD..YYYY-MM-DD`처럼 **날짜 범위(inclusive)**를 쓰되,
  - 내부 저장(RDB)에서는 `closed_at`을 UTC 타임스탬프로 저장하고 최종 필터는 RDB에서 다시 한 번 한다.
- “모든 메타데이터”의 현실적 한계:
  - GitHub는 **삭제된 댓글/편집 히스토리 전체**를 완전 제공하지 않을 수 있다.
  - 따라서 **수집 시점 스냅샷(raw JSON)**을 원본으로 보존해 “그 시점의 완전성”을 담보한다.

---

## 1) 전체 파이프라인(ETL) 개요

1. **Discovery(대상 번호 수집)**: Search로 기간 내 닫힌 PR/Issue 후보 목록(번호+URL)을 확보
2. **Hydration(번호별 상세 풀스캔)**: 각 번호에 대해 GraphQL/REST로 댓글/리뷰/타임라인/파일/체크 등을 페이지네이션 끝까지 수집
3. **Raw 저장**: 모든 응답을 `raw_github_payloads`에 “요청 단위”로 저장(감사/재현 목적)
4. **정규화 저장**: users/items/comments/reviews/timeline/pr_files… 테이블로 upsert
5. **파생 데이터 생성**
   - `contributor_stats_daily`(기여자별 일 단위 지표)
   - KB chunk 생성(`kb_documents`)
6. **검증/리포트**: “Discovery 결과 수 vs 정규화 저장 수”, 페이지네이션 누락 여부, 에러율, 재시도 현황 출력

---

## 2) 수집 체크리스트 (필수/권장/선택)

> 체크리스트는 “**어떤 필드를 어떤 API로 수집하는가**”를 고정한다.  
> “선택”은 이후 단계에서 필요 시 확장.

### 2.1 공통: PR/Issue(Item) 기본

- [ ] 식별자: `repo(owner/name)`, `number`, `url`, `node_id`, `database_id(가능하면)`
- [ ] 상태/시각: `state`, `createdAt`, `updatedAt`, `closedAt`
- [ ] 본문: `title`, `body`, `bodyHTML(선택)`, `author`, `authorAssociation`
- [ ] 분류: `labels[]`, `milestone`, `projects(v2)`
- [ ] 담당: `assignees[]`
- [ ] 참여자: `participants[]` 또는 `comments/reviews` 기반 집계
- [ ] 연결: `linked issues/PRs`(cross-reference/closing references)
- [ ] 카운트: `comments.totalCount`, (PR의 경우 `reviews.totalCount`, `changedFiles/additions/deletions`)
- [ ] 리액션(선택): `reactions`(item 본문)

**권장 원천**
- Discovery: REST `search/issues` 또는 GraphQL `search` (둘 중 하나 고정)
- 상세: GraphQL `repository{ issueOrPullRequest(number) { … } }`

### 2.2 공통: 댓글(Comments)

- [ ] 댓글 메타: `comment_id(node/database)`, `item_number`, `author`, `authorAssociation`, `createdAt`, `updatedAt`, `url`
- [ ] 댓글 본문: `body`(필수), `bodyHTML(선택)`
- [ ] 리액션(선택): `reactionGroups` 또는 REST reactions

**권장 원천**
- GraphQL `comments(first:100, after:cursor)` 페이지네이션 끝까지

### 2.3 공통: 타임라인 이벤트(Timeline)

- [ ] 이벤트 공통: `event_type`, `createdAt`, `actor`, `subject(라벨/마일스톤/참조 등)`, `source url`
- [ ] 최소 이벤트 타입(권장):
  - `ClosedEvent`, `ReopenedEvent`
  - `LabeledEvent`, `UnlabeledEvent`
  - `AssignedEvent`, `UnassignedEvent`
  - `MilestonedEvent`, `DemilestonedEvent`
  - `RenamedTitleEvent`
  - `CrossReferencedEvent`(연결/참조 핵심)
  - `ReferencedEvent`(언급)
- [ ] 프로젝트/자동화(선택): `AddedToProjectEvent`, `MovedColumnsInProjectEvent`(레포 설정에 따라 다름)

**권장 원천**
- GraphQL `timelineItems(first:100, after:cursor, itemTypes:[...])`
- 보강(선택): REST issue timeline(엔드포인트 사용 가능 시)

### 2.4 PR 전용: 머지/브랜치/커밋

- [ ] `mergedAt`, `mergedBy`, `mergeCommit(sha/url)`
- [ ] `baseRefName`, `headRefName`, `headRepository`, `headRefOid`
- [ ] `isDraft`, `mergeable`, `rebaseable(가능하면)`

**권장 원천**
- GraphQL `PullRequest` 필드

### 2.5 PR 전용: 변경 파일/패치

- [ ] 파일 목록: `path`, `changeType`, `additions`, `deletions`
- [ ] 패치: `patch`(가능하면), 또는 PR diff/patch 원문 링크
- [ ] 변경 규모: `additions/deletions/changedFiles`

**권장 원천(혼합)**
- GraphQL: `files(first:100)` (경로/변경량/타입)
- REST: `GET /repos/{owner}/{repo}/pulls/{number}/files` (patch 포함 가능, 단 truncation 가능)
- REST(선택): `GET /repos/{owner}/{repo}/pulls/{number}` + `Accept: application/vnd.github.v3.diff` 또는 `application/vnd.github.v3.patch`

### 2.6 PR 전용: 리뷰/리뷰 코멘트/스레드

- [ ] 리뷰: `review_id`, `author`, `state(APPROVED/CHANGES_REQUESTED/COMMENTED)`, `body`, `submittedAt`
- [ ] 리뷰 코멘트: `path`, `position/line`, `body`, `createdAt`
- [ ] 스레드(선택): review threads 단위로 묶기(코멘트 흐름 보존)

**권장 원천**
- GraphQL: `reviews(first:100)` + 필요시 `comments(first:100)` (리뷰 코멘트는 별 connection)
- REST 보강(선택): `pulls/{number}/reviews`, `pulls/{number}/comments`

### 2.7 CI/체크/상태(선택)

- [ ] `statusCheckRollup` 또는 `checkRuns` 요약
- [ ] 실패/성공/스킵, 결론(conclusion), 실행 시각

**권장 원천**
- GraphQL `statusCheckRollup`(가능할 때)
- REST `check-runs`(필요 시)

---

## 3) 호출 설계서: GitHub API (ClosedAt 기준)

### 3.1 인증/헤더(공통)

- 인증: GitHub PAT 또는 GitHub App 토큰
- 공통 헤더(REST):
  - `Accept: application/vnd.github+json`
  - `X-GitHub-Api-Version: 2022-11-28`
- GraphQL: `POST https://api.github.com/graphql`
- 레이트리밋:
  - GraphQL은 cost 기반, REST는 요청 수 기반 → **요청 큐 + 백오프 + 재시도**(429/502/503) 필수

### 3.2 Discovery(대상 번호 수집) — ClosedAt 기준 쿼리

**권장(단순/안정): REST Search API로 번호 수집**

- PR:
  - 쿼리: `repo:openai/openai-agents-python is:pr state:closed closed:2026-01-06..2026-01-20`
  - 호출: `GET /search/issues?q={query}&per_page=100&page=N`
- Issue:
  - 쿼리: `repo:openai/openai-agents-python is:issue state:closed closed:2026-01-06..2026-01-20`
  - 호출: `GET /search/issues?q={query}&per_page=100&page=N`

**저장(Discovery 결과)**
- 최소 저장 필드: `number`, `url`, `title`, `closed_at`, `updated_at`
- 이후 상세 수집은 **number 기반**으로 수행

**주의**
- Search 결과는 “이슈/PR 통합” 리소스 형태로 나오므로, 상세는 별도 호출로 보강해야 한다.

### 3.3 Hydration(번호별 상세 풀스캔) — GraphQL 중심

#### 3.3.1 단일 번호의 Issue/PR 기본 엔트리

GraphQL(개념):
- `repository(owner:"openai", name:"openai-agents-python") { issueOrPullRequest(number:$n) { ... on Issue { ... } ... on PullRequest { ... } } }`

필수 포함:
- item 기본(2.1)
- comments connection(2.2) cursor로 끝까지
- timelineItems connection(2.3) cursor로 끝까지
- PR이면 reviews/files도 cursor로 끝까지

#### 3.3.2 페이지네이션 규칙(필수)

- 모든 connection에 대해:
  - `first: 100`(최대치) 사용
  - `pageInfo { hasNextPage endCursor }`로 반복
  - 반복마다 **raw payload 저장**
- 권장 수집 순서(1 item 기준):
  1) 기본 item + 1페이지 comments/reviews/files/timeline
  2) comments 다음 페이지들
  3) timeline 다음 페이지들
  4) reviews 다음 페이지들
  5) files 다음 페이지들 (GraphQL)
  6) REST 보강(files patch/diff 등)

#### 3.3.3 REST 보강 호출(권장)

- PR 파일(패치 확보):
  - `GET /repos/openai/openai-agents-python/pulls/{pull_number}/files?per_page=100&page=N`
  - 응답의 `patch`는 길이 제한으로 누락/절단될 수 있음 → 절단 여부를 raw에 기록하고, 필요 시 diff 엔드포인트로 보강
- PR diff/patch(선택):
  - `GET /repos/openai/openai-agents-python/pulls/{pull_number}`
  - `Accept: application/vnd.github.v3.diff` 또는 `application/vnd.github.v3.patch`
- (선택) Issue timeline(REST가 더 풍부한 경우):
  - `GET /repos/openai/openai-agents-python/issues/{issue_number}/timeline?per_page=100&page=N`

### 3.4 요청/재시도/중복 방지 설계

- idempotent upsert 원칙:
  - `items(repo_id, number)` unique
  - `comments(comment_node_id)` unique
  - `timeline_events(event_node_id or (item_id,event_type,created_at,actor))` unique(가능한 안정키로)
- 재시도 정책:
  - 429/secondary rate limit: `Retry-After` 존중 + 지수 백오프
  - 5xx: 지수 백오프(최대 N회) 후 실패 기록
- 중복 방지:
  - raw는 “요청 단위”로 중복 저장 가능(감사 목적)
  - normalized는 unique key로 upsert

### 3.5 GraphQL 쿼리 템플릿(초안)

> 원칙: **한 번에 너무 많은 connection을 같이 당기지 않는다.**  
> Core(단건) + 각 connection 별 “페이지 쿼리”로 나누면 rate limit/cost 관리와 재시도가 쉬워진다.

#### 3.5.1 Core(단건) — Issue/PR 공통 + PR 핵심 필드

```graphql
query GetIssueOrPRCore($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issueOrPullRequest(number: $number) {
      __typename
      ... on Issue {
        id
        databaseId
        number
        url
        title
        body
        state
        locked
        author { login id databaseId url avatarUrl __typename }
        authorAssociation
        createdAt
        updatedAt
        closedAt
        labels(first: 100) { nodes { name color description } }
        milestone { title description dueOn state number }
        assignees(first: 100) { nodes { login id databaseId url avatarUrl __typename } }
        comments { totalCount }
      }
      ... on PullRequest {
        id
        databaseId
        number
        url
        title
        body
        state
        isDraft
        locked
        author { login id databaseId url avatarUrl __typename }
        authorAssociation
        createdAt
        updatedAt
        closedAt
        mergedAt
        mergedBy { login id databaseId url avatarUrl __typename }
        mergeCommit { oid url }
        baseRefName
        headRefName
        headRefOid
        additions
        deletions
        changedFiles
        labels(first: 100) { nodes { name color description } }
        milestone { title description dueOn state number }
        assignees(first: 100) { nodes { login id databaseId url avatarUrl __typename } }
        comments { totalCount }
        reviews { totalCount }
        files { totalCount }
      }
    }
  }
}
```

#### 3.5.2 Comments 페이지 쿼리(공통)

```graphql
query GetItemCommentsPage($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    issueOrPullRequest(number: $number) {
      __typename
      ... on Issue {
        comments(first: 100, after: $after) {
          pageInfo { hasNextPage endCursor }
          nodes {
            id
            databaseId
            url
            body
            createdAt
            updatedAt
            author { login id databaseId url avatarUrl __typename }
            authorAssociation
          }
        }
      }
      ... on PullRequest {
        comments(first: 100, after: $after) {
          pageInfo { hasNextPage endCursor }
          nodes {
            id
            databaseId
            url
            body
            createdAt
            updatedAt
            author { login id databaseId url avatarUrl __typename }
            authorAssociation
          }
        }
      }
    }
  }
}
```

#### 3.5.3 Timeline 페이지 쿼리(공통)

> `itemTypes`는 레포에서 실제로 쓰는 이벤트를 보고 점진 확장. (초기엔 아래 “핵심 이벤트”부터)

```graphql
query GetItemTimelinePage($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    issueOrPullRequest(number: $number) {
      __typename
      ... on Issue {
        timelineItems(
          first: 100
          after: $after
          itemTypes: [
            CLOSED_EVENT, REOPENED_EVENT,
            LABELED_EVENT, UNLABELED_EVENT,
            ASSIGNED_EVENT, UNASSIGNED_EVENT,
            MILESTONED_EVENT, DEMILESTONED_EVENT,
            RENAMED_TITLE_EVENT,
            CROSS_REFERENCED_EVENT, REFERENCED_EVENT
          ]
        ) {
          pageInfo { hasNextPage endCursor }
          nodes {
            __typename
            ... on ClosedEvent { id createdAt actor { login id } }
            ... on ReopenedEvent { id createdAt actor { login id } }
            ... on LabeledEvent { id createdAt actor { login id } label { name color } }
            ... on UnlabeledEvent { id createdAt actor { login id } label { name color } }
            ... on AssignedEvent { id createdAt actor { login id } assignee { __typename ... on User { login id } } }
            ... on UnassignedEvent { id createdAt actor { login id } assignee { __typename ... on User { login id } } }
            ... on MilestonedEvent { id createdAt actor { login id } milestoneTitle }
            ... on DemilestonedEvent { id createdAt actor { login id } milestoneTitle }
            ... on RenamedTitleEvent { id createdAt actor { login id } previousTitle currentTitle }
            ... on CrossReferencedEvent {
              id createdAt actor { login id }
              source {
                __typename
                ... on Issue { number url title }
                ... on PullRequest { number url title }
              }
            }
            ... on ReferencedEvent {
              id createdAt actor { login id }
              commit { oid url }
              commitRepository { nameWithOwner }
            }
          }
        }
      }
      ... on PullRequest {
        timelineItems(
          first: 100
          after: $after
          itemTypes: [
            CLOSED_EVENT, REOPENED_EVENT,
            LABELED_EVENT, UNLABELED_EVENT,
            ASSIGNED_EVENT, UNASSIGNED_EVENT,
            MILESTONED_EVENT, DEMILESTONED_EVENT,
            RENAMED_TITLE_EVENT,
            CROSS_REFERENCED_EVENT, REFERENCED_EVENT
          ]
        ) {
          pageInfo { hasNextPage endCursor }
          nodes {
            __typename
            ... on ClosedEvent { id createdAt actor { login id } }
            ... on ReopenedEvent { id createdAt actor { login id } }
            ... on LabeledEvent { id createdAt actor { login id } label { name color } }
            ... on UnlabeledEvent { id createdAt actor { login id } label { name color } }
            ... on AssignedEvent { id createdAt actor { login id } assignee { __typename ... on User { login id } } }
            ... on UnassignedEvent { id createdAt actor { login id } assignee { __typename ... on User { login id } } }
            ... on MilestonedEvent { id createdAt actor { login id } milestoneTitle }
            ... on DemilestonedEvent { id createdAt actor { login id } milestoneTitle }
            ... on RenamedTitleEvent { id createdAt actor { login id } previousTitle currentTitle }
            ... on CrossReferencedEvent {
              id createdAt actor { login id }
              source {
                __typename
                ... on Issue { number url title }
                ... on PullRequest { number url title }
              }
            }
            ... on ReferencedEvent {
              id createdAt actor { login id }
              commit { oid url }
              commitRepository { nameWithOwner }
            }
          }
        }
      }
    }
  }
}
```

#### 3.5.4 PR Reviews 페이지 쿼리(PR 전용)

```graphql
query GetPRReviewsPage($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviews(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          databaseId
          author { login id databaseId url avatarUrl __typename }
          state
          body
          submittedAt
        }
      }
    }
  }
}
```

#### 3.5.5 PR Files 페이지 쿼리(PR 전용, “경로/변경량”)

```graphql
query GetPRFilesPage($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      files(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          path
          additions
          deletions
          changeType
        }
      }
    }
  }
}
```

### 3.6 REST 호출 목록(고정)

#### 3.6.1 Discovery(검색)

```http
GET /search/issues?q=repo:openai/openai-agents-python+is:pr+state:closed+closed:2026-01-06..2026-01-20&per_page=100&page=1
GET /search/issues?q=repo:openai/openai-agents-python+is:issue+state:closed+closed:2026-01-06..2026-01-20&per_page=100&page=1
```

#### 3.6.2 PR 파일(패치)

```http
GET /repos/openai/openai-agents-python/pulls/{pull_number}/files?per_page=100&page=1
```

#### 3.6.3 (선택) PR diff/patch 원문

```http
GET /repos/openai/openai-agents-python/pulls/{pull_number}
Accept: application/vnd.github.v3.diff

GET /repos/openai/openai-agents-python/pulls/{pull_number}
Accept: application/vnd.github.v3.patch
```

### 3.7 저장 매핑(요약)

- `GetIssueOrPRCore` → `items`, `labels/item_labels`, `milestones`, `item_assignees`, (PR이면) `pull_requests`
- `GetItemCommentsPage` → `comments` (+ `users` upsert)
- `GetItemTimelinePage` → `timeline_events` (+ `users` upsert)
- `GetPRReviewsPage` → `pr_reviews` (+ `users` upsert)
- `GetPRFilesPage` + `pulls/{n}/files` → `pr_files`
- 모든 API 응답 → `raw_github_payloads`

---

## 4) RDB 스키마(초안, PostgreSQL 기준)

> 목적: “필터/집계/리포트”는 정규화 테이블로 빠르게, “원문/이벤트 상세/확장필드”는 JSONB로 보존.

```sql
-- repos
create table if not exists repos (
  id bigserial primary key,
  owner text not null,
  name text not null,
  unique (owner, name)
);

-- users (GitHub Actor)
create table if not exists users (
  id bigserial primary key,
  node_id text unique,
  login text not null,
  type text,
  is_bot boolean,
  avatar_url text,
  html_url text,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);
create index if not exists idx_users_login on users(login);

-- items: Issue/PR 공통
create table if not exists items (
  id bigserial primary key,
  repo_id bigint not null references repos(id) on delete cascade,
  number int not null,
  type text not null check (type in ('issue','pr')),
  url text not null,
  node_id text,
  database_id bigint,
  title text not null,
  body text,
  state text not null,
  author_user_id bigint references users(id),
  author_association text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  closed_at timestamptz,
  locked boolean,
  raw_json jsonb,
  unique (repo_id, number)
);
create index if not exists idx_items_repo_type_closed on items(repo_id, type, closed_at);
create index if not exists idx_items_repo_updated on items(repo_id, updated_at);

-- labels + join
create table if not exists labels (
  id bigserial primary key,
  repo_id bigint not null references repos(id) on delete cascade,
  name text not null,
  color text,
  description text,
  unique (repo_id, name)
);

create table if not exists item_labels (
  item_id bigint not null references items(id) on delete cascade,
  label_id bigint not null references labels(id) on delete cascade,
  primary key (item_id, label_id)
);

-- milestones (간단 보관; 확장 필요 시 raw_json 추가)
create table if not exists milestones (
  id bigserial primary key,
  repo_id bigint not null references repos(id) on delete cascade,
  number int,
  title text not null,
  description text,
  due_on timestamptz,
  state text,
  unique (repo_id, title)
);

alter table items
  add column if not exists milestone_id bigint references milestones(id);

-- assignees join
create table if not exists item_assignees (
  item_id bigint not null references items(id) on delete cascade,
  user_id bigint not null references users(id) on delete cascade,
  primary key (item_id, user_id)
);

-- comments
create table if not exists comments (
  id bigserial primary key,
  item_id bigint not null references items(id) on delete cascade,
  node_id text unique,
  database_id bigint,
  url text,
  author_user_id bigint references users(id),
  author_association text,
  body text not null,
  created_at timestamptz not null,
  updated_at timestamptz,
  raw_json jsonb
);
create index if not exists idx_comments_item_created on comments(item_id, created_at);

-- timeline events (가능하면 node_id 사용, 없으면 fingerprint로 중복 방지)
create table if not exists timeline_events (
  id bigserial primary key,
  item_id bigint not null references items(id) on delete cascade,
  node_id text unique,
  event_type text not null,
  actor_user_id bigint references users(id),
  created_at timestamptz not null,
  payload jsonb
);
create index if not exists idx_timeline_item_created on timeline_events(item_id, created_at);

-- pull_requests: items(type='pr') 확장
create table if not exists pull_requests (
  item_id bigint primary key references items(id) on delete cascade,
  is_draft boolean,
  merged_at timestamptz,
  merged_by_user_id bigint references users(id),
  merge_commit_sha text,
  base_ref_name text,
  head_ref_name text,
  head_ref_oid text,
  additions int,
  deletions int,
  changed_files int,
  raw_json jsonb
);
create index if not exists idx_prs_merged_at on pull_requests(merged_at);

-- PR reviews
create table if not exists pr_reviews (
  id bigserial primary key,
  pr_item_id bigint not null references pull_requests(item_id) on delete cascade,
  node_id text unique,
  database_id bigint,
  author_user_id bigint references users(id),
  state text,
  body text,
  submitted_at timestamptz,
  raw_json jsonb
);
create index if not exists idx_pr_reviews_pr on pr_reviews(pr_item_id, submitted_at);

-- PR review comments (inline)
create table if not exists pr_review_comments (
  id bigserial primary key,
  pr_item_id bigint not null references pull_requests(item_id) on delete cascade,
  node_id text unique,
  database_id bigint,
  author_user_id bigint references users(id),
  path text,
  line int,
  position int,
  body text,
  created_at timestamptz,
  updated_at timestamptz,
  raw_json jsonb
);
create index if not exists idx_pr_review_comments_pr on pr_review_comments(pr_item_id, created_at);

-- PR files
create table if not exists pr_files (
  id bigserial primary key,
  pr_item_id bigint not null references pull_requests(item_id) on delete cascade,
  path text not null,
  status text,
  additions int,
  deletions int,
  changes int,
  patch text,
  raw_json jsonb,
  unique (pr_item_id, path)
);

-- raw payloads (요청 단위 스냅샷)
create table if not exists raw_github_payloads (
  id bigserial primary key,
  fetched_at timestamptz not null default now(),
  source text not null check (source in ('rest','graphql')),
  repo_owner text not null,
  repo_name text not null,
  entity_type text not null,
  entity_key text,
  request_fingerprint text,
  payload jsonb not null
);
create index if not exists idx_raw_repo_time on raw_github_payloads(repo_owner, repo_name, fetched_at);

-- ingestion runs + errors
create table if not exists ingestion_runs (
  id bigserial primary key,
  repo_owner text not null,
  repo_name text not null,
  window_start timestamptz not null,
  window_end timestamptz not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running',
  stats jsonb
);

create table if not exists ingestion_errors (
  id bigserial primary key,
  run_id bigint references ingestion_runs(id) on delete cascade,
  occurred_at timestamptz not null default now(),
  stage text not null,
  entity_type text,
  entity_key text,
  error text not null,
  context jsonb
);

-- contributor daily stats
create table if not exists contributor_stats_daily (
  repo_id bigint not null references repos(id) on delete cascade,
  user_id bigint not null references users(id) on delete cascade,
  date date not null,
  prs_closed int not null default 0,
  prs_merged int not null default 0,
  issues_closed int not null default 0,
  issues_opened int not null default 0,
  comments int not null default 0,
  reviews int not null default 0,
  review_comments int not null default 0,
  lines_added int not null default 0,
  lines_deleted int not null default 0,
  primary key (repo_id, user_id, date)
);

-- KB documents (chunk 단위)
create table if not exists kb_documents (
  id bigserial primary key,
  repo_id bigint not null references repos(id) on delete cascade,
  item_id bigint references items(id) on delete cascade,
  chunk_type text not null, -- e.g. pr_summary, issue_summary, review_thread, file_diff_summary
  title text,
  content text not null,
  meta jsonb,
  created_at timestamptz not null default now()
);
```

---

## 5) 파생 로직(정의) — 컨트리뷰터 테이블 산출 규칙

> 일 단위(date)는 UTC 기준으로 `createdAt/submittedAt/closedAt` 등의 timestamp를 `date(created_at at time zone 'UTC')`로 절삭해 집계한다.

- `prs_closed`: `items.type='pr'`이고 `closed_at`이 해당 date인 건수
- `prs_merged`: `pull_requests.merged_at`이 해당 date인 건수
- `issues_closed`: `items.type='issue'`이고 `closed_at`이 해당 date인 건수
- `issues_opened`: `items.type='issue'`이고 `created_at`이 해당 date인 건수
- `comments`: `comments.created_at` 기준
- `reviews`: `pr_reviews.submitted_at` 기준
- `review_comments`: `pr_review_comments.created_at` 기준
- `lines_added/lines_deleted`: `pr_files(additions/deletions)`의 합(해당 PR이 merge된 date로 귀속하거나, PR closed date로 귀속 중 하나를 선택)
  - 권장: **merge된 date로 귀속**(실제 반영 시점과 일치)

---

## 6) KB/요약 생성 규격(초안)

### 6.1 PR 단위 요약(JSON 스키마 예시)

```json
{
  "type": "pr_summary",
  "repo": "openai/openai-agents-python",
  "number": 123,
  "closedAt": "2026-01-18T12:34:56Z",
  "mergedAt": "2026-01-18T12:34:56Z",
  "title": "...",
  "summary": "무엇이 바뀌었는지 3~5문장",
  "user_impact": ["사용자에게 보이는 변화", "마이그레이션 필요 여부"],
  "breaking_changes": [],
  "risk_notes": ["성능/호환성/보안 관련"],
  "follow_ups": ["남은 TODO/이슈 링크"],
  "files_touched": ["path/a.py", "path/b.md"],
  "references": [
    {"kind": "pr", "url": "https://github.com/.../pull/123"}
  ]
}
```

### 6.2 Issue 단위 요약(JSON 스키마 예시)

```json
{
  "type": "issue_summary",
  "repo": "openai/openai-agents-python",
  "number": 456,
  "closedAt": "2026-01-10T01:02:03Z",
  "title": "...",
  "problem": "문제 정의",
  "resolution": "해결/미해결/워크어라운드",
  "repro": "재현 조건(있으면)",
  "labels": ["bug", "docs"],
  "references": [
    {"kind": "issue", "url": "https://github.com/.../issues/456"}
  ]
}
```

### 6.3 에이전트 프롬프트(초안)

> 아래 프롬프트는 “RDB 조회 + 필요 시 원문(raw) 확인 + 근거(PR/Issue 링크/번호) 포함”을 기본 원칙으로 한다.  
> 실제 구현 시에는 “툴 호출(예: SQL/VectorSearch)”을 프로젝트 환경에 맞게 매핑한다.

#### 6.3.1 ReleaseNotesAgent (최근 기간 릴리즈 노트)

```text
SYSTEM
너는 openai/openai-agents-python 레포의 최근 변경사항을 사용자 영향 중심으로 요약하는 에이전트다.
반드시 근거가 되는 PR 번호/링크를 references로 포함한다.
추측 금지. 데이터가 없으면 "unknown"으로 표기한다.

INPUT
- window_start(UTC), window_end(UTC)  # closedAt 기준
- optional: label_filter[], only_breaking(boolean)

TOOLS
- sql(query): RDB에서 items/pull_requests/pr_files/comments/reviews 등을 조회
- raw(item_number): raw_github_payloads에서 원문(JSON) 스냅샷을 조회(필요 시)

OUTPUT(JSON)
- summary(짧게)
- highlights[]
- breaking_changes[]
- migration_notes[]
- references[{number,url}]

RULES
- closedAt이 window 내인 PR만 포함한다.
- mergedAt이 null인 PR(그냥 closed)은 "not merged"로 분리 표기한다.
- 변경 파일이 많은 PR은 file diff를 나열하지 말고 “영향 영역”으로 묶어 요약한다.
```

#### 6.3.2 TriageAgent (이슈/PR 분류 및 후속 작업)

```text
SYSTEM
너는 최근에 닫힌 Issue를 분류하고, 재발 방지/문서화/테스트 보강 같은 후속 작업을 제안한다.
제안은 반드시 근거 텍스트(이슈 본문/댓글) 또는 라벨/타임라인 이벤트에 기반해야 한다.

INPUT
- issue_number

TOOLS
- sql(query)
- raw(issue_number)

OUTPUT(JSON)
- classification: {type: bug|feature|docs|question|chore|unknown, confidence: 0..1}
- root_cause_hypothesis
- resolution_status: fixed|wontfix|duplicate|cannot_reproduce|unknown
- follow_ups[]
- references[]
```

#### 6.3.3 KBQAAgent (질의응답: 근거 포함)

```text
SYSTEM
너는 KB(벡터 검색) + RDB(필터/집계)를 이용해 질문에 답한다.
답변은 간결하게, 근거 references를 반드시 포함한다.

INPUT
- question
- optional: window_start/window_end (closedAt 기준)

TOOLS
- vector_search(query, filters): kb_documents에서 관련 chunk 검색
- sql(query)

OUTPUT
- answer
- references[{kind,number,url}]
```

### 6.4 에이전트 카드(템플릿)

```markdown
---
name: ReleaseNotesAgent
repo: openai/openai-agents-python
coverage:
  - closedAt-window PRs
inputs:
  - window_start (UTC)
  - window_end (UTC)
outputs:
  - JSON (summary/highlights/breaking_changes/migration_notes/references)
limitations:
  - Deleted/edited history may be unavailable from GitHub API; uses snapshot-at-ingestion
examples:
  - input: "2026-01-06..2026-01-20"
    output: "highlights + references"
---

## Purpose
최근(ClosedAt 기준) PR의 사용자 영향 요약 및 릴리즈 노트 생성.

## Data Sources
- RDB: items/pull_requests/pr_files/pr_reviews/comments/timeline_events
- Raw snapshot: raw_github_payloads (필요 시)

## Safety/Quality
- No speculation
- Always include references
```

---

## 7) 검증 체크(수집 품질)

- [ ] Discovery 결과(PR/Issue 각각)의 `count`와 `items` 테이블 `closed_at in window`의 건수가 일치
- [ ] 각 item에 대해:
  - [ ] `comments.totalCount == comments rows count` (가능한 범위에서)
  - [ ] PR: `changedFiles` vs `pr_files` count 일치(페이지네이션 누락 검출)
  - [ ] PR: `reviews.totalCount` vs `pr_reviews` count 대조
- [ ] raw payload 저장률(요청 수 대비 저장 수) 100%
- [ ] 실패 요청은 `ingestion_errors`에 stage/entity_key와 함께 기록

---

## 8) 실행 파라미터(운영)

- repo: `openai/openai-agents-python`
- window:
  - start: `2026-01-06T00:00:00Z`
  - end: `2026-01-20T23:59:59Z`
- discovery query:
  - PR: `repo:openai/openai-agents-python is:pr state:closed closed:2026-01-06..2026-01-20`
  - Issue: `repo:openai/openai-agents-python is:issue state:closed closed:2026-01-06..2026-01-20`
- page size: `100`
- concurrency: (권장) 2~5 workers로 시작, secondary rate limit 발생 시 자동 감속
