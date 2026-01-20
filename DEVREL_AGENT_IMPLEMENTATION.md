# DevRel Agent 구현 계획서

> **목표**: GitHub 이슈를 분석하고 적절한 DevRel 액션을 수행하는 AI Agent

---

## 1. 개요

### 1.1 핵심 기능

```
┌─────────────────────────────────────────────────────────────┐
│  DevRel Agent 4대 기능                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 🎯 이슈 할당 (Assignment)                               │
│     - 이슈 분석 → 적합한 기여자 매칭 → 컨텍스트 제공        │
│                                                             │
│  2. 📝 문서 수정 제안 (Doc Suggestion)                      │
│     - 반복 질문 패턴 감지 → 문서 갭 식별 → PR/이슈 생성     │
│                                                             │
│  3. 💬 이슈 답변 (Response)                                 │
│     - 미답변 이슈 감지 → 답변 생성 또는 정보 요청           │
│                                                             │
│  4. 👑 승격 제안 (Promotion)                                │
│     - 기여자 활동 분석 → 성장 신호 감지 → 승격 추천         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 기술 스택

| 구분 | 선택 | 이유 |
|------|------|------|
| 언어 | Python 3.11+ | 빠른 개발, AI 라이브러리 풍부 |
| LLM | **OpenAI GPT-4.1/5 시리즈** | Structured Outputs, 작업별 최적화 |
| Embedding | **OpenAI text-embedding-3-large** | 최고 성능 유사도 검색, $0.13/1M |
| Vector DB | **Chroma (in-memory)** | 로컬, 빠른 세팅, 해커톤에 적합 |
| GitHub | PyGithub + REST API | 이슈/PR/기여자 데이터 접근 |
| CLI/UI | Rich + Typer | 터미널 UI, 빠른 CLI 구축 |
| 데이터 | **GitHub API (100%)** | 이슈 + 기여자 모두 GitHub에서 자동 수집 |

### 1.3 모델 가격표 (2026년 1월 기준)

| 모델 | 입력 ($/1M) | 출력 ($/1M) | 컨텍스트 | 특징 |
|------|------------|------------|----------|------|
| **GPT-5.2** | $1.75 | $14 | 400K | 최신, Thinking 모드 |
| GPT-5 | $1.25 | $10 | 400K | 추론/에이전트 |
| GPT-5 mini | $0.25 | $2 | 400K | 비용 효율 추론 |
| GPT-5 nano | $0.05 | $0.40 | - | 초저비용 |
| **GPT-4.1** | $2 | $8 | 1M | 코딩/도구 호출 최적화 |
| GPT-4.1 mini | $0.40 | $1.60 | 1M | 빠른 응답, 좋은 균형 |
| GPT-4.1 nano | $0.10 | $0.40 | - | 간단한 작업 |

### 1.4 작업별 모델 선택 (품질 우선)

| 작업 | 모델 | 이유 | 예상 비용 |
|------|------|------|----------|
| **이슈 분류/분석** | `gpt-4.1-mini` | 정확한 분류, 빠른 응답 | $0.40/$1.60 |
| **할당 제안** | `gpt-4.1` | Tool calling + 컨텍스트 생성 품질 | $2/$8 |
| **답변 생성** | `gpt-5-mini` | 추론 기반 고품질 답변 | $0.25/$2 |
| **문서 갭 분석** | `gpt-4.1` | 패턴 인식 + 아웃라인 생성 | $2/$8 |
| **승격 평가** | `gpt-5` | 복잡한 다중 요소 판단 | $1.25/$10 |
| **Embedding** | `text-embedding-3-large` | 최고 성능 유사도 검색 | $0.13/1M |

> **품질 우선 전략**: 데모 품질이 중요하므로 상위 모델 사용. 해커톤 전체 비용 ~$5 예상

---

## 2. 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                      DEVREL AGENT v2                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  DATA LAYER                                          │   │
│  │  ┌─────────────────────────────┐ ┌─────────────┐    │   │
│  │  │        GitHub API           │ │  Vector DB  │    │   │
│  │  │  (이슈 / PR / 기여자 수집)  │ │  (Chroma)   │    │   │
│  │  └─────────────────────────────┘ └─────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  EMBEDDING LAYER (OpenAI text-embedding-3-large)    │   │
│  │  • 이슈 임베딩 → 유사 이슈 검색                      │   │
│  │  • 문서 임베딩 → 관련 문서 검색                      │   │
│  │  • 기여자 전문성 임베딩 → 이슈-기여자 매칭           │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  AGENT LAYER (품질 우선 모델 선택)                  │   │
│  │  ┌───────────────┐ ┌───────────────┐               │   │
│  │  │ Issue Triage  │ │ Assignment    │               │   │
│  │  │ gpt-4.1-mini  │ │ gpt-4.1       │               │   │
│  │  └───────────────┘ └───────────────┘               │   │
│  │  ┌───────────────┐ ┌───────────────┐               │   │
│  │  │ Response      │ │ Docs          │               │   │
│  │  │ gpt-5-mini    │ │ gpt-4.1       │               │   │
│  │  └───────────────┘ └───────────────┘               │   │
│  │  ┌───────────────┐                                 │   │
│  │  │ Promotion     │ ← 복잡한 판단은 gpt-5           │   │
│  │  │ gpt-5         │                                 │   │
│  │  └───────────────┘                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ACTION LAYER                                        │   │
│  │  • GitHub 코멘트 작성                                │   │
│  │  • 이슈 할당 제안                                    │   │
│  │  • 알림 생성                                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 모듈 구조

```
prism-devrel/
├── pyproject.toml
├── README.md
├── .env.example
│
├── src/
│   └── devrel/
│       ├── __init__.py
│       ├── cli.py                 # CLI 엔트리포인트 ✅
│       ├── config.py              # 설정 관리 ✅
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   └── engine.py          # 메인 엔진 ✅
│       │
│       ├── github/
│       │   ├── __init__.py
│       │   └── client.py          # GitHub API 클라이언트 ✅ (이슈 + 기여자 수집)
│       │
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── client.py          # OpenAI 클라이언트 ✅
│       │   └── schemas.py         # Structured Output 스키마 ✅
│       │
│       ├── vector/
│       │   ├── __init__.py
│       │   └── store.py           # Chroma Vector Store ✅
│       │
│       └── agents/
│           ├── __init__.py
│           ├── assignment.py      # 할당 Agent ✅
│           ├── response.py        # 답변 Agent ✅
│           ├── docs.py            # 문서 제안 Agent ✅
│           └── promotion.py       # 승격 제안 Agent ✅
```

> ✅ 표시: 이 문서에 구현 코드 포함됨
> **Note**: Mock 데이터 없음 - 모든 데이터는 GitHub API에서 수집

---

## 3. 데이터 레이어

### 3.1 데이터 모델

```python
# src/devrel/github/models.py

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime

class ContributorStage(str, Enum):
    """기여자 단계 - PR 수 기반 자동 분류"""
    FIRST_TIMER = "first_timer"   # 1개 PR
    REGULAR = "regular"           # 2-9개 PR
    CORE = "core"                 # 10-29개 PR
    MAINTAINER = "maintainer"     # 30개+ PR

@dataclass
class Contributor:
    """GitHub에서 수집한 기여자 프로필"""
    username: str
    stage: ContributorStage
    prs_merged: int
    reviews_given: int
    expertise_areas: list[str]    # 수정한 파일 경로/라벨에서 추론
    active_months: int            # 첫 PR부터 마지막 활동까지
    issues_commented: int         # 이슈 코멘트 수
    first_contribution: Optional[datetime]
    last_activity: Optional[datetime]

    @classmethod
    def determine_stage(cls, prs_merged: int) -> ContributorStage:
        """PR 수 기반 단계 결정"""
        if prs_merged >= 30:
            return ContributorStage.MAINTAINER
        elif prs_merged >= 10:
            return ContributorStage.CORE
        elif prs_merged >= 2:
            return ContributorStage.REGULAR
        else:
            return ContributorStage.FIRST_TIMER

@dataclass
class GitHubIssue:
    """GitHub 이슈 데이터 모델"""
    number: int
    title: str
    body: str
    labels: list[str]
    author: str
    assignee: Optional[str]
    created_at: datetime
    comments_count: int
    state: str  # "open", "closed"
```

### 3.2 Vector Store (Chroma)

```python
# src/devrel/vector/store.py

import chromadb
from openai import OpenAI
from typing import Optional
import hashlib
import os

class VectorStore:
    """Chroma 기반 Vector Store (Chroma 0.5+ API)"""

    def __init__(self, openai_client: OpenAI):
        self.openai = openai_client

        # Chroma 클라이언트 (in-memory) - EphemeralClient 사용 (0.4.0+ 권장)
        # 텔레메트리 비활성화는 환경변수로 설정
        os.environ["ANONYMIZED_TELEMETRY"] = "False"
        self.chroma = chromadb.EphemeralClient()

        # 컬렉션 생성
        self.issues = self.chroma.get_or_create_collection(
            name="issues",
            metadata={"description": "GitHub 이슈 임베딩"}
        )
        self.docs = self.chroma.get_or_create_collection(
            name="docs",
            metadata={"description": "문서 임베딩"}
        )
        self.contributors = self.chroma.get_or_create_collection(
            name="contributors",
            metadata={"description": "기여자 전문성 임베딩"}
        )

    def _embed(self, text: str) -> list[float]:
        """텍스트를 임베딩 벡터로 변환 (text-embedding-3-large 사용)"""
        response = self.openai.embeddings.create(
            model="text-embedding-3-large",
            input=text
        )
        return response.data[0].embedding

    def _hash_id(self, text: str) -> str:
        """텍스트에서 고유 ID 생성"""
        return hashlib.md5(text.encode()).hexdigest()

    # === Issues ===

    def index_issue(self, issue_number: int, title: str, body: str, labels: list[str]):
        """이슈 인덱싱"""
        text = f"{title}\n{body}\nLabels: {', '.join(labels)}"
        embedding = self._embed(text)

        self.issues.upsert(
            ids=[str(issue_number)],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{
                "number": issue_number,
                "title": title,
                "labels": ",".join(labels)
            }]
        )

    def find_similar_issues(self, query: str, k: int = 5) -> list[dict]:
        """유사 이슈 검색"""
        embedding = self._embed(query)

        results = self.issues.query(
            query_embeddings=[embedding],
            n_results=k
        )

        similar = []
        for i, doc_id in enumerate(results['ids'][0]):
            similar.append({
                "issue_number": int(doc_id),
                "title": results['metadatas'][0][i].get('title', ''),
                "distance": results['distances'][0][i] if results['distances'] else 0
            })

        return similar

    # === Documents ===

    def index_document(self, path: str, content: str):
        """문서 인덱싱"""
        # 문서를 청크로 나누어 인덱싱
        chunks = self._chunk_text(content, chunk_size=500)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{path}_{i}"
            embedding = self._embed(chunk)

            self.docs.upsert(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "path": path,
                    "chunk_index": i
                }]
            )

    def find_relevant_docs(self, query: str, k: int = 3) -> list[dict]:
        """관련 문서 검색"""
        embedding = self._embed(query)

        results = self.docs.query(
            query_embeddings=[embedding],
            n_results=k
        )

        relevant = []
        seen_paths = set()

        for i, doc_id in enumerate(results['ids'][0]):
            path = results['metadatas'][0][i].get('path', '')
            if path not in seen_paths:
                seen_paths.add(path)
                relevant.append({
                    "path": path,
                    "snippet": results['documents'][0][i][:200],
                    "distance": results['distances'][0][i] if results['distances'] else 0
                })

        return relevant

    # === Contributors ===

    def index_contributor(self, username: str, expertise_areas: list[str], description: str = ""):
        """기여자 전문성 인덱싱"""
        text = f"{username}: {', '.join(expertise_areas)}. {description}"
        embedding = self._embed(text)

        self.contributors.upsert(
            ids=[username],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{
                "username": username,
                "expertise": ",".join(expertise_areas)
            }]
        )

    def find_matching_contributors(self, issue_text: str, k: int = 3) -> list[dict]:
        """이슈에 맞는 기여자 검색"""
        embedding = self._embed(issue_text)

        results = self.contributors.query(
            query_embeddings=[embedding],
            n_results=k
        )

        matches = []
        for i, username in enumerate(results['ids'][0]):
            matches.append({
                "username": username,
                "expertise": results['metadatas'][0][i].get('expertise', '').split(','),
                "distance": results['distances'][0][i] if results['distances'] else 0
            })

        return matches

    def _chunk_text(self, text: str, chunk_size: int = 500) -> list[str]:
        """텍스트를 청크로 분할"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_size = 0

        for word in words:
            current_chunk.append(word)
            current_size += len(word) + 1

            if current_size >= chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_size = 0

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks
```

### 3.3 GitHub Client (이슈 + 기여자 수집)

```python
# src/devrel/github/client.py

from github import Github
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from enum import Enum

# === Enums ===

class ContributorStage(str, Enum):
    """기여자 단계 - PR 수 기반 자동 분류"""
    FIRST_TIMER = "first_timer"   # 1개 PR
    REGULAR = "regular"           # 2-9개 PR
    CORE = "core"                 # 10-29개 PR
    MAINTAINER = "maintainer"     # 30개+ PR

# === Data Models ===

@dataclass
class GitHubIssue:
    """GitHub 이슈 데이터 모델"""
    number: int
    title: str
    body: str
    labels: list[str]
    author: str
    assignee: Optional[str]
    created_at: datetime
    comments_count: int
    state: str

    @classmethod
    def from_github(cls, issue: Issue) -> "GitHubIssue":
        """PyGithub Issue 객체에서 변환"""
        return cls(
            number=issue.number,
            title=issue.title,
            body=issue.body or "",
            labels=[label.name for label in issue.labels],
            author=issue.user.login if issue.user else "unknown",
            assignee=issue.assignee.login if issue.assignee else None,
            created_at=issue.created_at,
            comments_count=issue.comments,
            state=issue.state,
        )

@dataclass
class Contributor:
    """GitHub에서 수집한 기여자 프로필"""
    username: str
    stage: ContributorStage
    prs_merged: int
    reviews_given: int
    expertise_areas: list[str]    # 수정한 파일 경로/라벨에서 추론
    active_months: int
    issues_commented: int
    first_contribution: Optional[datetime]
    last_activity: Optional[datetime]

# === Client ===

class GitHubClient:
    """GitHub API 클라이언트 - 이슈 + 기여자 데이터 수집"""

    # 파일 경로 → 전문 영역 매핑
    PATH_TO_EXPERTISE = {
        "auth": ["auth", "security", "oauth", "jwt", "login"],
        "cache": ["cache", "redis", "session", "storage"],
        "api": ["api", "routes", "endpoints", "middleware", "controller"],
        "performance": ["perf", "benchmark", "optimize", "profil"],
        "docs": ["docs", "readme", "documentation", "example", "tutorial"],
        "test": ["test", "spec", "__test__", "e2e"],
        "config": ["config", "settings", "env", ".yaml", ".json"],
    }

    def __init__(self, token: str, repo_name: str):
        self.github = Github(token)
        self.repo: Repository = self.github.get_repo(repo_name)
        self.repo_name = repo_name

    # === Issue Methods ===

    def get_issue(self, number: int) -> Optional[GitHubIssue]:
        """이슈 번호로 조회"""
        try:
            issue = self.repo.get_issue(number)
            return GitHubIssue.from_github(issue)
        except Exception as e:
            print(f"Error fetching issue #{number}: {e}")
            return None

    def get_open_issues(self, limit: int = 100) -> list[GitHubIssue]:
        """열린 이슈 목록"""
        issues = self.repo.get_issues(state="open")
        return [GitHubIssue.from_github(i) for i in list(issues)[:limit]]

    def get_issues_by_label(self, label: str, state: str = "all") -> list[GitHubIssue]:
        """라벨로 이슈 필터링"""
        issues = self.repo.get_issues(state=state, labels=[label])
        return [GitHubIssue.from_github(i) for i in issues]

    def get_unanswered_issues(self, days: int = 3) -> list[GitHubIssue]:
        """N일 이상 답변 없는 이슈"""
        from datetime import timedelta
        threshold = datetime.now() - timedelta(days=days)
        issues = self.get_open_issues()
        return [
            i for i in issues
            if i.comments_count == 0 and i.created_at.replace(tzinfo=None) < threshold
        ]

    def get_unassigned_issues(self) -> list[GitHubIssue]:
        """미할당 이슈"""
        issues = self.get_open_issues()
        return [i for i in issues if i.assignee is None]

    # === Contributor Methods ===

    def get_contributors(self, limit: int = 50) -> list[Contributor]:
        """기여자 목록 수집 (PR 기반)"""
        contributors = {}
        now = datetime.now()

        # 1. Merged PR에서 기여자 수집
        pulls = self.repo.get_pulls(state="closed", sort="updated", direction="desc")

        for pr in list(pulls)[:200]:  # 최근 200개 PR 분석
            if not pr.merged:
                continue

            author = pr.user.login if pr.user else None
            if not author:
                continue

            if author not in contributors:
                contributors[author] = {
                    "prs_merged": 0,
                    "reviews_given": 0,
                    "expertise_set": set(),
                    "first_contribution": pr.merged_at,
                    "last_activity": pr.merged_at,
                    "issues_commented": 0,
                }

            contributors[author]["prs_merged"] += 1

            # 첫 기여일/마지막 활동일 업데이트
            if pr.merged_at < contributors[author]["first_contribution"]:
                contributors[author]["first_contribution"] = pr.merged_at
            if pr.merged_at > contributors[author]["last_activity"]:
                contributors[author]["last_activity"] = pr.merged_at

            # 파일 경로에서 전문 영역 추론
            try:
                for file in pr.get_files():
                    expertise = self._infer_expertise(file.filename)
                    if expertise:
                        contributors[author]["expertise_set"].add(expertise)
            except:
                pass  # 파일 접근 실패 시 무시

            # 라벨에서 전문 영역 추론
            for label in pr.labels:
                label_name = label.name.lower()
                for expertise, keywords in self.PATH_TO_EXPERTISE.items():
                    if any(kw in label_name for kw in keywords):
                        contributors[author]["expertise_set"].add(expertise)

        # 2. PR 리뷰 수 수집
        for pr in list(pulls)[:100]:
            try:
                for review in pr.get_reviews():
                    reviewer = review.user.login if review.user else None
                    if reviewer and reviewer in contributors:
                        contributors[reviewer]["reviews_given"] += 1
            except:
                pass

        # 3. Contributor 객체로 변환
        result = []
        for username, data in contributors.items():
            # 활동 기간 계산
            if data["first_contribution"] and data["last_activity"]:
                delta = relativedelta(data["last_activity"], data["first_contribution"])
                active_months = delta.years * 12 + delta.months
            else:
                active_months = 0

            # 단계 결정
            prs = data["prs_merged"]
            if prs >= 30:
                stage = ContributorStage.MAINTAINER
            elif prs >= 10:
                stage = ContributorStage.CORE
            elif prs >= 2:
                stage = ContributorStage.REGULAR
            else:
                stage = ContributorStage.FIRST_TIMER

            result.append(Contributor(
                username=username,
                stage=stage,
                prs_merged=prs,
                reviews_given=data["reviews_given"],
                expertise_areas=list(data["expertise_set"]),
                active_months=active_months,
                issues_commented=data["issues_commented"],
                first_contribution=data["first_contribution"],
                last_activity=data["last_activity"],
            ))

        # PR 수 기준 정렬
        result.sort(key=lambda c: c.prs_merged, reverse=True)
        return result[:limit]

    def get_contributor(self, username: str) -> Optional[Contributor]:
        """특정 기여자 정보 조회"""
        contributors = self.get_contributors(limit=100)
        for c in contributors:
            if c.username == username:
                return c
        return None

    def find_contributors_by_expertise(
        self, skills: list[str], limit: int = 5
    ) -> list[tuple[Contributor, int]]:
        """전문성 기반 기여자 검색"""
        contributors = self.get_contributors()
        results = []

        for contrib in contributors:
            overlap = set(skills) & set(contrib.expertise_areas)
            if overlap:
                results.append((contrib, len(overlap)))

        results.sort(key=lambda x: (x[1], x[0].prs_merged), reverse=True)
        return results[:limit]

    def _infer_expertise(self, filepath: str) -> Optional[str]:
        """파일 경로에서 전문 영역 추론"""
        filepath_lower = filepath.lower()
        for expertise, keywords in self.PATH_TO_EXPERTISE.items():
            if any(kw in filepath_lower for kw in keywords):
                return expertise
        return None

    # === Action Methods ===

    def add_comment(self, issue_number: int, body: str) -> bool:
        """이슈에 코멘트 추가"""
        try:
            issue = self.repo.get_issue(issue_number)
            issue.create_comment(body)
            return True
        except Exception as e:
            print(f"Error adding comment to #{issue_number}: {e}")
            return False

    def add_label(self, issue_number: int, label: str) -> bool:
        """이슈에 라벨 추가"""
        try:
            issue = self.repo.get_issue(issue_number)
            issue.add_to_labels(label)
            return True
        except Exception as e:
            print(f"Error adding label to #{issue_number}: {e}")
            return False

    def create_issue(self, title: str, body: str, labels: list[str] = None) -> Optional[int]:
        """새 이슈 생성"""
        try:
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels or []
            )
            return issue.number
        except Exception as e:
            print(f"Error creating issue: {e}")
            return None

    # === Documentation Methods ===

    def get_docs_content(self, docs_path: str = "docs") -> dict[str, str]:
        """docs/ 폴더의 문서 내용 로드"""
        docs = {}
        try:
            contents = self.repo.get_contents(docs_path)
            for content in contents:
                if content.type == "file" and content.name.endswith(".md"):
                    file_content = content.decoded_content.decode("utf-8")
                    docs[content.path] = file_content
        except Exception as e:
            print(f"Error loading docs from {docs_path}: {e}")
            # 폴백: 기본 문서 구조 반환
            docs = {
                "docs/getting-started.md": "",
                "docs/configuration.md": "",
                "docs/api-reference.md": "",
            }
        return docs
```

### 3.5 Config

```python
# src/devrel/config.py

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    """애플리케이션 설정"""

    # OpenAI
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")

    # GitHub
    github_token: str = Field(..., env="GITHUB_TOKEN")
    github_repo: str = Field(..., env="GITHUB_REPO")  # "owner/repo"

    # 실행 모드
    # dry_run=True: GitHub에 코멘트/이슈 작성 안함 (미리보기만)
    # dry_run=False: 실제 GitHub에 작성
    dry_run: bool = Field(default=True, env="DRY_RUN")

    # 모델 설정 (선택적 오버라이드)
    model_triage: Optional[str] = Field(default=None, env="MODEL_TRIAGE")
    model_assignment: Optional[str] = Field(default=None, env="MODEL_ASSIGNMENT")
    model_response: Optional[str] = Field(default=None, env="MODEL_RESPONSE")
    model_doc_gap: Optional[str] = Field(default=None, env="MODEL_DOC_GAP")
    model_promotion: Optional[str] = Field(default=None, env="MODEL_PROMOTION")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def load_config() -> Settings:
    """설정 로드"""
    return Settings()
```

### 3.6 Engine (Core)

```python
# src/devrel/core/engine.py

from openai import OpenAI

from ..config import Settings
from ..github.client import GitHubClient, GitHubIssue, Contributor
from ..vector.store import VectorStore
from ..llm.client import LLMClient
from ..llm.schemas import DocGapOutput
from ..agents.assignment import AssignmentAgent
from ..agents.response import ResponseAgent
from ..agents.docs import DocsAgent
from ..agents.promotion import PromotionAgent


class ContributorStore:
    """GitHub API로 수집한 기여자 데이터 관리"""

    def __init__(self, contributors: list[Contributor]):
        self._contributors = {c.username: c for c in contributors}

    def get_all(self) -> list[Contributor]:
        return list(self._contributors.values())

    def get(self, username: str) -> Contributor | None:
        return self._contributors.get(username)

    def get_by_expertise(self, expertise: str) -> list[Contributor]:
        return [
            c for c in self._contributors.values()
            if expertise in c.expertise_areas
        ]

    def get_by_stage(self, stage: str) -> list[Contributor]:
        return [
            c for c in self._contributors.values()
            if c.stage == stage
        ]


class DevRelEngine:
    """DevRel Agent 메인 엔진 - GitHub API 전용"""

    def __init__(self, config: Settings):
        self.config = config

        # OpenAI 클라이언트
        openai_client = OpenAI(api_key=config.openai_api_key)

        # LLM 클라이언트
        self.llm = LLMClient(api_key=config.openai_api_key)

        # Vector Store
        self.vector = VectorStore(openai_client)

        # GitHub 클라이언트
        self.github = GitHubClient(config.github_token, config.github_repo)

        # 기여자 데이터 수집 및 저장소 초기화
        contributors = self.github.get_contributors(limit=100)
        self.contributor_store = ContributorStore(contributors)

        # 데이터 인덱싱
        self._init_data()

        # Agents
        self.assignment_agent = AssignmentAgent(
            self.llm, self.vector, self.contributor_store
        )
        self.response_agent = ResponseAgent(self.llm, self.vector)
        self.docs_agent = DocsAgent(self.llm)
        self.promotion_agent = PromotionAgent(self.llm, self.contributor_store)

    def _init_data(self):
        """GitHub 데이터를 Vector Store에 인덱싱"""
        # 기여자 인덱싱
        for contributor in self.contributor_store.get_all():
            description = (
                f"{contributor.prs_merged} PRs merged, "
                f"{contributor.reviews_given} reviews, "
                f"stage: {contributor.stage}"
            )
            self.vector.index_contributor(
                contributor.username,
                contributor.expertise_areas,
                description
            )

        # GitHub 이슈 인덱싱
        issues = self.github.get_open_issues(limit=50)
        for issue in issues:
            self.vector.index_issue(
                issue.number,
                issue.title,
                issue.body,
                issue.labels
            )

        # 문서 인덱싱 (GitHub docs/ 폴더에서 로드)
        docs = self.github.get_docs_content()
        for path, content in docs.items():
            self.vector.index_document(path, content)

    # === Public API ===

    def analyze_repository(self) -> dict:
        """저장소 전체 상태 분석"""
        issues = self.github.get_open_issues()
        unanswered = [i for i in issues if i.comments_count == 0]
        unassigned = [i for i in issues if i.assignee is None]

        # 문서 갭 분석
        doc_gap = self.detect_doc_gaps()

        # 승격 후보
        promotion_candidates = self.promotion_agent.find_candidates()

        return {
            "total_issues": len(issues),
            "open_issues": len(issues),
            "unanswered": len(unanswered),
            "unanswered_issue_numbers": [i.number for i in unanswered],
            "unassigned_bugs": len([
                i for i in unassigned if "bug" in i.labels
            ]),
            "unassigned_issue_numbers": [i.number for i in unassigned],
            "doc_gaps": 1 if doc_gap.has_gap else 0,
            "promotion_candidates": len(promotion_candidates),
        }

    def suggest_assignment(self, issue_number: int) -> dict | None:
        """이슈에 담당자 제안"""
        issue = self.github.get_issue(issue_number)
        if not issue:
            return None

        # Agent 호출
        result = self.assignment_agent.suggest_assignment(
            issue_number, issue.title, issue.body, issue.labels
        )

        # 실제 GitHub에 코멘트 작성 (dry_run이 아닐 때)
        if not self.config.dry_run:
            self.github.add_comment(issue_number, result['comment'])

        return result

    def generate_response(self, issue_number: int) -> dict | None:
        """이슈에 답변 생성"""
        issue = self.github.get_issue(issue_number)
        if not issue:
            return None

        # Agent 호출
        result = self.response_agent.generate_response(
            issue_number, issue.title, issue.body, issue.labels
        )

        # 실제 GitHub에 코멘트 작성
        if not self.config.dry_run:
            self.github.add_comment(issue_number, result['comment'])

        return result

    def detect_doc_gaps(self) -> DocGapOutput:
        """문서 갭 감지"""
        # 현재 문서 목록 (GitHub에서 로드)
        docs = self.github.get_docs_content()
        existing_docs = list(docs.keys())

        # 질문 유형 이슈 수집
        question_issues = self.github.get_issues_by_label("question")
        issues_data = [
            {"number": i.number, "title": i.title, "body": i.body}
            for i in question_issues
        ]

        return self.docs_agent.detect_gaps(issues_data, existing_docs)

    def find_promotion_candidates(self) -> list[dict]:
        """승격 후보 탐색"""
        return self.promotion_agent.find_candidates()

    def create_doc_gap_issue(self, gap: DocGapOutput) -> int | None:
        """문서 갭 이슈 생성"""
        if not gap.has_gap:
            return None

        body = self.docs_agent.generate_issue_body(gap)

        if self.config.dry_run:
            print(f"[DRY RUN] Would create issue: {gap.gap_topic}")
            return None

        return self.github.create_issue(
            title=f"📝 문서 개선: {gap.gap_topic}",
            body=body,
            labels=["documentation", "enhancement"]
        )
```

---

## 4. LLM 레이어

### 4.1 OpenAI Structured Output 스키마

```python
# src/devrel/llm/schemas.py

from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

# === Enums ===

class IssueType(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    QUESTION = "question"
    DOCUMENTATION = "documentation"
    OTHER = "other"

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ResponseStrategy(str, Enum):
    DIRECT_ANSWER = "direct_answer"
    REQUEST_INFO = "request_info"
    LINK_DOCS = "link_docs"
    ESCALATE = "escalate"

# === Issue Analysis ===

class IssueAnalysisOutput(BaseModel):
    """이슈 분석 결과"""
    issue_type: IssueType = Field(description="이슈 유형")
    priority: Priority = Field(description="우선순위")
    required_skills: list[str] = Field(description="필요한 기술/전문 영역")
    keywords: list[str] = Field(description="핵심 키워드")
    summary: str = Field(description="이슈 요약 (1-2문장)")
    needs_more_info: bool = Field(description="추가 정보 필요 여부")
    suggested_action: ResponseStrategy = Field(description="권장 대응 방식")

# === Assignment ===

class AssignmentReason(BaseModel):
    """할당 이유"""
    factor: str = Field(description="매칭 요소")
    explanation: str = Field(description="설명")
    score: float = Field(description="점수 (0-1)")

class AssignmentOutput(BaseModel):
    """할당 제안 결과"""
    recommended_assignee: str = Field(description="추천 담당자 username")
    confidence: float = Field(description="확신도 (0-1)")
    reasons: list[AssignmentReason] = Field(description="추천 이유들")
    context_for_assignee: str = Field(description="담당자를 위한 컨텍스트 요약")
    alternative_assignees: list[str] = Field(description="대안 담당자들")

# === Response ===

class ResponseOutput(BaseModel):
    """답변 생성 결과"""
    strategy: ResponseStrategy = Field(description="답변 전략")
    response_text: str = Field(description="답변 내용")
    confidence: float = Field(description="답변 확신도 (0-1)")
    references: list[str] = Field(description="참조 문서/링크")
    follow_up_needed: bool = Field(description="후속 조치 필요 여부")

# === Documentation Gap ===

class DocGapOutput(BaseModel):
    """문서 갭 분석 결과"""
    has_gap: bool = Field(description="문서 갭 존재 여부")
    gap_topic: str = Field(description="갭 주제")
    affected_issues: list[int] = Field(description="영향받는 이슈 번호들")
    suggested_doc_path: str = Field(description="문서 추가/수정 위치")
    suggested_outline: list[str] = Field(description="제안 문서 아웃라인")
    priority: Priority = Field(description="우선순위")

# === Promotion ===

class PromotionEvidence(BaseModel):
    """승격 근거"""
    criterion: str = Field(description="평가 기준")
    status: str = Field(description="충족/미충족")
    detail: str = Field(description="상세 내용")

class PromotionOutput(BaseModel):
    """승격 제안 결과"""
    is_candidate: bool = Field(description="승격 후보 여부")
    current_stage: str = Field(description="현재 단계")
    suggested_stage: str = Field(description="제안 단계")
    confidence: float = Field(description="확신도 (0-1)")
    evidence: list[PromotionEvidence] = Field(description="근거 목록")
    recommendation: str = Field(description="권장 사항")
```

### 4.2 OpenAI 클라이언트

```python
# src/devrel/llm/client.py

from openai import OpenAI
from typing import TypeVar, Type
from pydantic import BaseModel
from enum import Enum

from .schemas import (
    IssueAnalysisOutput,
    AssignmentOutput,
    ResponseOutput,
    DocGapOutput,
    PromotionOutput,
)

T = TypeVar('T', bound=BaseModel)

class ModelTier(str, Enum):
    """작업 복잡도에 따른 모델 티어 (품질 우선)"""
    MINI = "gpt-4.1-mini"         # 빠른 응답, 간단한 작업 ($0.40/$1.60)
    STANDARD = "gpt-4.1"          # 고품질 생성, tool calling ($2/$8)
    REASONING_MINI = "gpt-5-mini" # 추론 기반 답변 ($0.25/$2)
    REASONING = "gpt-5"           # 복잡한 추론 ($1.25/$10)

class LLMClient:
    """OpenAI LLM 클라이언트 - 품질 우선 모델 선택"""

    # 작업별 모델 매핑 (품질 우선)
    TASK_MODELS = {
        "issue_triage": ModelTier.MINI,           # 이슈 분류: 정확한 분류
        "assignment": ModelTier.STANDARD,         # 할당 제안: 컨텍스트 품질
        "response": ModelTier.REASONING_MINI,     # 답변 생성: 추론 기반
        "doc_gap": ModelTier.STANDARD,            # 문서 갭: 아웃라인 품질
        "promotion": ModelTier.REASONING,         # 승격 평가: 복잡한 판단
    }

    def __init__(self, api_key: str = None):
        self.client = OpenAI(api_key=api_key)

    def _get_model(self, task: str) -> str:
        """작업에 맞는 모델 반환"""
        return self.TASK_MODELS.get(task, ModelTier.MINI).value

    def _parse_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        task: str = "default"
    ) -> T:
        """Structured Output으로 응답 파싱 (작업별 모델 선택)

        Note: beta.chat.completions.parse()는 여전히 beta이지만 안정적으로 동작.
        새 프로젝트에는 Responses API 권장 (성능 3% 향상, 캐시 효율 40-80% 개선)
        하지만 Structured Outputs 기능은 현재 방식으로 충분히 지원됨.
        """
        model = self._get_model(task)

        response = self.client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=output_schema
        )
        return response.choices[0].message.parsed

    def analyze_issue(self, title: str, body: str, labels: list[str]) -> IssueAnalysisOutput:
        """이슈 분석 (gpt-4.1-mini 사용 - 정확한 분류)"""
        system_prompt = """당신은 오픈소스 프로젝트 "PRISM"의 DevRel Agent입니다.
PRISM은 API 서버 프레임워크로, auth, cache, api, performance 모듈로 구성됩니다.

## 당신의 역할
GitHub 이슈를 분석하여 유형, 우선순위, 필요 기술을 파악합니다.

## 분류 기준

### 이슈 유형 (issue_type)
- bug: 기존 기능이 의도대로 동작하지 않음 (에러, 크래시, 잘못된 결과)
- feature: 새로운 기능 요청
- question: 사용법, 설정, 동작 방식에 대한 질문
- documentation: 문서 개선 요청 또는 문서 관련 질문
- other: 위에 해당하지 않는 경우

### 우선순위 (priority)
- critical: 보안 취약점, 데이터 손실, 전체 서비스 중단
- high: 주요 기능 장애, 많은 사용자 영향, "high-priority" 라벨
- medium: 일반적인 버그, 기능 요청
- low: 사소한 개선, 문서 오타

### 대응 방식 (suggested_action)
- direct_answer: 문서나 지식으로 바로 답변 가능
- request_info: 재현 단계, 환경 정보 등 추가 정보 필요
- link_docs: 관련 문서 링크로 안내
- escalate: 코어 팀 검토 필요 (보안, 아키텍처 변경)

## 기술 영역 키워드
- auth/security: OAuth, JWT, 인증, 권한, 로그인
- cache/redis: 캐시, Redis, 세션, 성능
- api: REST, 엔드포인트, 라우팅, 미들웨어
- performance: 속도, 최적화, 메모리, 프로파일링
- documentation: 문서, 예제, 튜토리얼

한국어로 분석 결과를 작성하세요."""

        user_prompt = f"""다음 GitHub 이슈를 분석해주세요.

## Issue
**Title:** {title}
**Labels:** {', '.join(labels) if labels else '없음'}

**Body:**
{body}

---
위 이슈를 분석하여 유형, 우선순위, 필요 기술 영역, 핵심 키워드, 요약, 추가 정보 필요 여부, 권장 대응 방식을 판단해주세요."""

        return self._parse_structured(
            system_prompt, user_prompt, IssueAnalysisOutput,
            task="issue_triage"  # gpt-4.1-mini
        )

    def suggest_assignment(
        self,
        issue_title: str,
        issue_body: str,
        issue_analysis: IssueAnalysisOutput,
        candidates: list[dict]
    ) -> AssignmentOutput:
        """담당자 할당 제안"""
        system_prompt = """당신은 오픈소스 프로젝트 "PRISM"의 DevRel Agent입니다.
이슈에 가장 적합한 기여자를 매칭하여 할당을 제안합니다.

## 매칭 원칙

### 1. 전문성 매칭 (가장 중요)
- 이슈가 요구하는 기술 영역과 기여자의 expertise_areas 일치도
- 관련 모듈 경험 (auth, cache, api, performance)

### 2. 가용성 고려
- 응답 시간이 짧은 기여자 우선 (avg_response_time_hours)
- 현재 활동 중인 기여자 우선 (active_months)

### 3. 성장 기회 제공
- 너무 쉬운 이슈는 newcomer에게 할당하여 성장 기회 제공
- 복잡한 이슈는 경험 많은 기여자에게

### 4. 번아웃 방지
- 한 사람에게 과도하게 할당하지 않도록 주의
- PR 수가 많은 기여자는 이미 바쁠 수 있음

## 컨텍스트 작성 가이드
담당자가 이슈를 빠르게 이해할 수 있도록:
- 문제의 핵심을 2-3문장으로 요약
- 관련 코드 영역이나 파일 힌트
- 예상되는 해결 방향 (있다면)

## 확신도 기준
- 0.9+: 전문성 완벽 일치 + 활동적
- 0.7-0.9: 전문성 일치하지만 다른 요소 미흡
- 0.5-0.7: 부분적 매칭
- 0.5 미만: 적합한 후보 없음

한국어로 작성하세요."""

        candidates_text = "\n".join([
            f"- @{c['username']}: 전문분야={c['expertise']}, PR수={c['prs']}, 평균응답={c['response_time']}시간"
            for c in candidates
        ])

        user_prompt = f"""다음 이슈에 가장 적합한 담당자를 추천해주세요.

## 이슈 정보
**제목:** {issue_title}

**내용:**
{issue_body}

**분석 결과:**
- 유형: {issue_analysis.issue_type.value}
- 우선순위: {issue_analysis.priority.value}
- 필요 기술: {', '.join(issue_analysis.required_skills)}
- 요약: {issue_analysis.summary}

## 후보 기여자
{candidates_text}

---
가장 적합한 담당자 1명을 선택하고:
1. 선택 이유를 구체적으로 설명 (reasons)
2. 담당자가 바로 작업 시작할 수 있는 컨텍스트 제공 (context_for_assignee)
3. 대안 후보 2-3명 제시 (alternative_assignees)"""

        return self._parse_structured(
            system_prompt, user_prompt, AssignmentOutput,
            task="assignment"  # gpt-4.1 (컨텍스트 품질)
        )

    def generate_response(
        self,
        issue_title: str,
        issue_body: str,
        issue_analysis: IssueAnalysisOutput,
        relevant_docs: list[dict]
    ) -> ResponseOutput:
        """이슈 답변 생성"""
        system_prompt = """당신은 오픈소스 프로젝트 "PRISM"의 DevRel Agent입니다.
GitHub 이슈에 친절하고 전문적인 답변을 작성합니다.

## PRISM 프로젝트 정보
- API 서버 프레임워크
- 주요 모듈: auth (인증), cache (Redis 캐시), api (라우팅), performance (최적화)
- 문서 위치: docs/ 폴더
- 설정 파일: config.yaml 또는 환경변수

## 답변 전략 선택 기준

### direct_answer (바로 답변)
- 문서에 답이 있거나, 일반적인 지식으로 해결 가능
- 예: 설정 방법, 사용법 질문

### request_info (추가 정보 요청)
- 재현 단계, 에러 메시지, 환경 정보가 부족할 때
- 버그 리포트인데 정보가 불충분할 때

### link_docs (문서 안내)
- 상세한 가이드가 문서에 있을 때
- 예: "Getting Started 문서를 참고해주세요"

### escalate (에스컬레이션)
- 보안 이슈, 아키텍처 변경 필요
- 코어 팀의 결정이 필요한 사안

## 톤 & 스타일 가이드
- 친절하지만 전문적으로
- "~입니다", "~해주세요" 존댓말 사용
- 기술 용어는 그대로 사용 (번역 X)
- 코드 예시는 마크다운 코드블록 사용
- 이모지 최소화 (👋, ✅ 정도만)

## 답변 구조
1. 인사 또는 문제 인식 표현
2. 핵심 답변 또는 해결 방법
3. 코드 예시 (해당 시)
4. 추가 참고 자료 링크
5. 후속 질문 환영 멘트

## 주의사항
- 확실하지 않은 정보는 추측하지 말 것
- 문서에 없는 내용은 "문서에서 확인이 필요합니다"로 안내
- 버그가 확실하면 "확인하여 수정하겠습니다" 멘트

한국어로 답변을 작성하세요."""

        docs_text = "\n".join([
            f"### {d['path']}\n```\n{d['snippet']}\n```"
            for d in relevant_docs
        ]) if relevant_docs else "관련 문서를 찾지 못했습니다."

        user_prompt = f"""다음 GitHub 이슈에 답변을 작성해주세요.

## 이슈
**제목:** {issue_title}

**내용:**
{issue_body}

## 이슈 분석 결과
- 유형: {issue_analysis.issue_type.value}
- 추가 정보 필요: {"예" if issue_analysis.needs_more_info else "아니오"}
- 권장 전략: {issue_analysis.suggested_action.value}
- 핵심 키워드: {', '.join(issue_analysis.keywords)}

## 참고 가능한 문서
{docs_text}

---
위 정보를 바탕으로:
1. 적절한 답변 전략(strategy)을 선택하세요
2. 답변 내용(response_text)을 작성하세요 - GitHub 마크다운 형식
3. 참조 문서가 있다면 references에 경로 포함
4. 후속 조치가 필요하면 follow_up_needed를 true로
5. 답변 확신도(confidence)를 0-1 사이로 평가"""

        return self._parse_structured(
            system_prompt, user_prompt, ResponseOutput,
            task="response"  # gpt-5-mini (추론 기반 답변)
        )

    def analyze_doc_gap(
        self,
        issues: list[dict],
        existing_docs: list[str]
    ) -> DocGapOutput:
        """문서 갭 분석"""
        system_prompt = """당신은 오픈소스 프로젝트 "PRISM"의 DevRel Agent입니다.
GitHub 이슈에서 반복되는 질문 패턴을 분석하여 문서 갭을 발견합니다.

## 문서 갭이란?
사용자들이 같은 주제에 대해 반복적으로 질문하면, 해당 내용이 문서에 부족하다는 신호입니다.

## 분석 방법

### 1. 패턴 감지
- 비슷한 키워드가 3개 이상의 이슈에서 반복되는가?
- 같은 기능/설정에 대한 질문이 반복되는가?
- "문서가 없다", "찾을 수 없다" 같은 표현이 있는가?

### 2. 갭 주제 식별
- Redis/캐시 설정
- 인증 설정 (OAuth, JWT)
- 디버그/로깅 설정
- 성능 튜닝
- 마이그레이션 가이드

### 3. 우선순위 결정
- critical: 5개 이상 반복 + 핵심 기능
- high: 3-4개 반복 + 일반 기능
- medium: 2개 반복
- low: 1개지만 중요한 주제

## 문서 위치 제안 기준
PRISM 프로젝트 문서 구조:
- docs/getting-started.md: 시작 가이드
- docs/configuration.md: 설정 가이드
- docs/api-reference.md: API 문서
- docs/debugging.md: 디버깅 가이드
- docs/guides/: 주제별 상세 가이드 (새 파일 제안 가능)

## 아웃라인 작성 가이드
문서에 포함되어야 할 섹션을 구체적으로 제안:
- 개요/소개
- 사전 요구사항
- 단계별 설정 방법
- 코드 예시
- 트러블슈팅
- FAQ

한국어로 분석하세요."""

        issues_text = "\n".join([
            f"- **#{i['number']}**: {i['title']}\n  > {i.get('body', '')[:100]}..."
            for i in issues
        ])

        user_prompt = f"""다음 이슈들에서 문서 갭 패턴을 분석해주세요.

## 최근 질문 이슈들
{issues_text}

## 현재 존재하는 문서
{', '.join(existing_docs)}

---
분석 결과:
1. 반복되는 패턴이 있는가? (has_gap)
2. 어떤 주제에 대한 갭인가? (gap_topic)
3. 영향받는 이슈 번호들 (affected_issues)
4. 문서를 어디에 추가/수정해야 하는가? (suggested_doc_path)
5. 문서에 포함될 내용 아웃라인 (suggested_outline) - 최소 4개 섹션
6. 우선순위 (priority)

패턴이 명확하지 않으면 has_gap을 false로 설정하세요."""

        return self._parse_structured(
            system_prompt, user_prompt, DocGapOutput,
            task="doc_gap"  # gpt-4.1 (아웃라인 품질)
        )

    def evaluate_promotion(
        self,
        contributor: dict,
        criteria: dict
    ) -> PromotionOutput:
        """승격 평가 (gpt-5 사용 - 복잡한 다중 요소 판단)"""
        system_prompt = """당신은 오픈소스 프로젝트 "PRISM"의 DevRel Agent입니다.
기여자의 성장을 평가하고 승격 여부를 판단합니다.

## PRISM 기여자 단계 (Contributor Ladder)

### 1. First-timer (첫 기여자)
- 첫 PR이 머지된 상태
- 아직 프로젝트에 익숙하지 않음

### 2. Regular (정규 기여자)
- 여러 PR 기여
- 프로젝트 컨벤션 이해
- 이슈 답변 참여 시작

### 3. Core (핵심 기여자)
- 특정 영역 전문성 보유
- 코드 리뷰 활발히 참여
- 신규 기여자 멘토링
- 커뮤니티(Discord) 활동

### 4. Maintainer (메인테이너)
- 프로젝트 방향성 결정 참여
- RFC 작성 경험
- 릴리스 프로세스 참여
- 다수의 기여자 멘토링

## 승격 평가 원칙

### 정량적 기준 (참고용)
기준은 참고사항이며, 정성적 판단도 중요합니다:
- PR 수, 리뷰 수, 활동 기간 등

### 정성적 기준 (더 중요)
- 코드 품질과 일관성
- 커뮤니케이션 스타일
- 문제 해결 능력
- 커뮤니티 기여도
- 신뢰성과 책임감

### 승격 시 주의사항
- 숫자만 채웠다고 자동 승격 아님
- 번아웃 위험이 있는 기여자는 승격 보류
- 본인이 원하지 않을 수 있음 (부담)
- 점진적 책임 증가가 바람직

## 확신도 기준
- 0.9+: 모든 기준 충족 + 정성적으로도 준비됨
- 0.7-0.9: 대부분 충족, 일부 보완 필요
- 0.5-0.7: 기준 절반 정도 충족
- 0.5 미만: 아직 이름

## 권장사항 작성 가이드
승격 제안 시:
- 구체적인 강점 언급
- 다음 단계에서 기대되는 역할
- 부담 없이 거절 가능함을 명시

승격 보류 시:
- 부족한 부분 구체적으로
- 성장을 위한 제안
- 긍정적인 톤 유지

한국어로 평가하세요."""

        user_prompt = f"""다음 기여자의 승격 가능성을 평가해주세요.

## 기여자 프로필
- 사용자명: {contributor.get('username')}
- 현재 단계: {contributor.get('current_stage')}
- 머지된 PR: {contributor.get('prs_merged')}개
- 코드 리뷰: {contributor.get('reviews_given')}개
- 활동 기간: {contributor.get('active_months')}개월
- 전문 영역: {', '.join(contributor.get('expertise_areas', []))}
- 멘토링 횟수: {contributor.get('mentored_count')}명
- RFC 작성: {contributor.get('rfcs_authored')}개
- Discord 활동: {"활발" if contributor.get('discord_active') else "비활성"}

## 다음 단계 승격 기준
{criteria}

---
평가 항목:
1. 승격 후보 여부 (is_candidate)
2. 현재 단계 → 제안 단계
3. 각 기준별 충족 여부와 상세 근거 (evidence)
4. 확신도 (0-1)
5. 구체적인 권장사항 (recommendation)
   - 승격 추천 시: 강점, 기대 역할, 제안 방법
   - 보류 시: 부족한 점, 성장 방향"""

        return self._parse_structured(
            system_prompt, user_prompt, PromotionOutput,
            task="promotion"  # gpt-5 (복잡한 다중 요소 판단)
        )
```

---

## 5. Agent 구현

### 5.1 할당 Agent

```python
# src/devrel/agents/assignment.py

from typing import TYPE_CHECKING

from ..llm.client import LLMClient
from ..llm.schemas import IssueAnalysisOutput, AssignmentOutput
from ..vector.store import VectorStore

if TYPE_CHECKING:
    from ..core.engine import ContributorStore


class AssignmentAgent:
    """이슈 할당 Agent"""

    def __init__(
        self,
        llm: LLMClient,
        vector_store: VectorStore,
        contributor_store: "ContributorStore"
    ):
        self.llm = llm
        self.vector = vector_store
        self.contributors = contributor_store

    def suggest_assignment(
        self,
        issue_number: int,
        title: str,
        body: str,
        labels: list[str]
    ) -> dict:
        """이슈에 적합한 담당자 제안"""

        # 1. 이슈 분석
        analysis = self.llm.analyze_issue(title, body, labels)

        # 2. Vector 검색으로 매칭 기여자 찾기
        issue_text = f"{title}\n{body}"
        vector_matches = self.vector.find_matching_contributors(issue_text, k=5)

        # 3. GitHub 기여자 데이터에서 정보 보강
        candidates = []
        for match in vector_matches:
            contributor = self.contributors.get(match['username'])
            if contributor:
                candidates.append({
                    'username': contributor.username,
                    'expertise': contributor.expertise_areas,
                    'prs': contributor.prs_merged,
                    'reviews': contributor.reviews_given,
                    'stage': contributor.stage.value,
                    'vector_distance': match['distance']
                })

        # 4. 전문성 기반 추가 후보
        for skill in analysis.required_skills:
            skill_matches = self.contributors.get_by_expertise(skill)
            for contrib in skill_matches:
                if contrib.username not in [c['username'] for c in candidates]:
                    candidates.append({
                        'username': contrib.username,
                        'expertise': contrib.expertise_areas,
                        'prs': contrib.prs_merged,
                        'reviews': contrib.reviews_given,
                        'stage': contrib.stage.value,
                        'skill_match': skill
                    })

        # 5. LLM으로 최종 추천
        assignment = self.llm.suggest_assignment(
            issue_title=title,
            issue_body=body,
            issue_analysis=analysis,
            candidates=candidates[:5]  # 상위 5명만
        )

        return {
            'issue_number': issue_number,
            'analysis': analysis,
            'assignment': assignment,
            'comment': self._generate_comment(assignment)
        }

    def _generate_comment(self, assignment: AssignmentOutput) -> str:
        """GitHub 코멘트 생성"""
        reasons_text = "\n".join([
            f"- {r.factor}: {r.explanation}"
            for r in assignment.reasons
        ])

        return f"""👋 @{assignment.recommended_assignee} 님, 이 이슈 확인해주실 수 있을까요?

**왜 당신인가요?**
{reasons_text}

**빠른 컨텍스트:**
{assignment.context_for_assignee}

부담되시면 다른 분께 넘기셔도 됩니다!

---
🤖 *이 메시지는 DevRel Agent가 자동 생성했습니다.*
"""
```

### 5.2 답변 Agent

```python
# src/devrel/agents/response.py

from ..llm.client import LLMClient
from ..llm.schemas import ResponseOutput, ResponseStrategy
from ..vector.store import VectorStore

class ResponseAgent:
    """이슈 답변 Agent"""

    def __init__(self, llm: LLMClient, vector_store: VectorStore):
        self.llm = llm
        self.vector = vector_store

    def generate_response(
        self,
        issue_number: int,
        title: str,
        body: str,
        labels: list[str]
    ) -> dict:
        """이슈에 대한 답변 생성"""

        # 1. 이슈 분석
        analysis = self.llm.analyze_issue(title, body, labels)

        # 2. 관련 문서 검색
        issue_text = f"{title}\n{body}"
        relevant_docs = self.vector.find_relevant_docs(issue_text, k=3)

        # 3. 답변 생성
        response = self.llm.generate_response(
            issue_title=title,
            issue_body=body,
            issue_analysis=analysis,
            relevant_docs=relevant_docs
        )

        # 4. 전략에 따른 코멘트 포맷팅
        comment = self._format_response(response)

        return {
            'issue_number': issue_number,
            'analysis': analysis,
            'response': response,
            'comment': comment
        }

    def _format_response(self, response: ResponseOutput) -> str:
        """전략에 따른 코멘트 포맷팅"""

        base_response = response.response_text

        # 참조 문서 추가
        if response.references:
            refs = "\n".join([f"- {ref}" for ref in response.references])
            base_response += f"\n\n**📚 참고 문서:**\n{refs}"

        # 후속 조치 안내
        if response.follow_up_needed:
            base_response += "\n\n추가 질문이 있으시면 편하게 말씀해주세요! 🙌"

        # 서명
        base_response += "\n\n---\n🤖 *이 답변은 DevRel Agent가 생성했습니다. 부정확한 내용이 있다면 알려주세요.*"

        return base_response
```

### 5.3 문서 제안 Agent

```python
# src/devrel/agents/docs.py

from ..llm.client import LLMClient
from ..llm.schemas import DocGapOutput

class DocsAgent:
    """문서 갭 감지 및 제안 Agent"""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def detect_gaps(
        self,
        issues: list[dict],  # [{"number": int, "title": str, "body": str}]
        existing_docs: list[str]
    ) -> DocGapOutput:
        """문서 갭 감지

        Args:
            issues: 질문 유형 이슈 목록 (dict 형태)
            existing_docs: 현재 존재하는 문서 경로 목록
        """
        # LLM으로 패턴 분석
        gap_analysis = self.llm.analyze_doc_gap(
            issues=issues,
            existing_docs=existing_docs
        )

        return gap_analysis

    def generate_issue_body(self, gap: DocGapOutput) -> str:
        """문서 개선 이슈 본문 생성"""

        outline_text = "\n".join([f"- {item}" for item in gap.suggested_outline])
        issues_text = ", ".join([f"#{n}" for n in gap.affected_issues])

        return f"""## 📝 문서 개선 제안

### 배경
최근 {len(gap.affected_issues)}개의 이슈에서 **{gap.gap_topic}**에 대한 유사한 질문이 반복되고 있습니다.

**관련 이슈:** {issues_text}

### 제안
`{gap.suggested_doc_path}`에 다음 내용 추가를 제안합니다:

{outline_text}

### 우선순위
**{gap.priority.value.upper()}** - 반복 질문 {len(gap.affected_issues)}회 발생

---
🤖 *이 이슈는 DevRel Agent가 자동 생성했습니다.*
"""
```

### 5.4 승격 제안 Agent

```python
# src/devrel/agents/promotion.py

from typing import TYPE_CHECKING

from ..llm.client import LLMClient
from ..llm.schemas import PromotionOutput
from ..github.client import ContributorStage

if TYPE_CHECKING:
    from ..core.engine import ContributorStore


class PromotionAgent:
    """승격 후보 발굴 Agent - GitHub 활동 기반"""

    # 단계별 승격 기준 (GitHub API로 수집 가능한 데이터 기반)
    CRITERIA = {
        ContributorStage.REGULAR: {
            "min_prs": 2,
            "min_active_months": 1,
            "description": "First-timer → Regular"
        },
        ContributorStage.CORE: {
            "min_prs": 10,
            "min_reviews": 5,
            "min_active_months": 3,
            "has_expertise": True,  # 2개 이상 영역
            "description": "Regular → Core"
        },
        ContributorStage.MAINTAINER: {
            "min_prs": 30,
            "min_reviews": 20,
            "min_active_months": 6,
            "min_expertise": 3,  # 3개 이상 영역
            "description": "Core → Maintainer"
        }
    }

    def __init__(self, llm: LLMClient, contributor_store: "ContributorStore"):
        self.llm = llm
        self.contributors = contributor_store

    def find_candidates(self) -> list[dict]:
        """승격 후보 탐색"""
        candidates = []

        for contributor in self.contributors.get_all():
            # 이미 Maintainer면 스킵
            if contributor.stage == ContributorStage.MAINTAINER:
                continue

            # 다음 단계 결정
            next_stage = self._get_next_stage(contributor.stage)
            if not next_stage:
                continue

            # 기준 충족 여부 평가 (GitHub 데이터만 사용)
            criteria = self.CRITERIA[next_stage]
            evaluation = self.llm.evaluate_promotion(
                contributor={
                    "username": contributor.username,
                    "current_stage": contributor.stage.value,
                    "prs_merged": contributor.prs_merged,
                    "reviews_given": contributor.reviews_given,
                    "active_months": contributor.active_months,
                    "expertise_areas": contributor.expertise_areas,
                    "issues_commented": contributor.issues_commented,
                    "first_contribution": str(contributor.first_contribution),
                    "last_activity": str(contributor.last_activity),
                },
                criteria=criteria
            )

            if evaluation.is_candidate:
                candidates.append({
                    "contributor": contributor,
                    "evaluation": evaluation,
                    "notification": self._generate_notification(contributor, evaluation)
                })

        # 확신도 순 정렬
        candidates.sort(key=lambda x: x['evaluation'].confidence, reverse=True)
        return candidates

    def _get_next_stage(self, current: ContributorStage) -> ContributorStage | None:
        """다음 단계 반환"""
        stages = [
            ContributorStage.FIRST_TIMER,
            ContributorStage.REGULAR,
            ContributorStage.CORE,
            ContributorStage.MAINTAINER
        ]
        try:
            idx = stages.index(current)
            return stages[idx + 1] if idx + 1 < len(stages) else None
        except ValueError:
            return None

    def _generate_notification(self, contributor, evaluation: PromotionOutput) -> str:
        """메인테이너 알림 메시지 생성"""

        evidence_text = "\n".join([
            f"- **{e.criterion}**: {e.status} - {e.detail}"
            for e in evaluation.evidence
        ])

        stage_emoji = {
            "first_timer": "👶",
            "regular": "🧑",
            "core": "🦸",
            "maintainer": "👑"
        }

        return f"""## 🎯 승격 후보 발견

### @{contributor.username}

{stage_emoji.get(evaluation.current_stage, "👤")} **{evaluation.current_stage}** → {stage_emoji.get(evaluation.suggested_stage, "👤")} **{evaluation.suggested_stage}**

### 평가 근거
{evidence_text}

### 확신도
**{evaluation.confidence * 100:.0f}%**

### 권장 사항
{evaluation.recommendation}

---
💡 **다음 단계:**
- 부담 없이 제안 형태로 전달
- 거절해도 괜찮다는 점 명시
- 역할과 기대치 설명

🤖 *이 분석은 DevRel Agent가 생성했습니다.*
"""
```

---

## 6. CLI 인터페이스

```python
# src/devrel/cli.py

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .core.engine import DevRelEngine
from .config import load_config

app = typer.Typer(
    name="prism-devrel",
    help="PRISM DevRel Agent - 오픈소스 커뮤니티 관리 AI"
)
console = Console()

def get_engine() -> DevRelEngine:
    config = load_config()
    return DevRelEngine(config)

@app.command()
def analyze():
    """저장소 전체 분석"""
    engine = get_engine()

    with console.status("[bold green]분석 중..."):
        result = engine.analyze_repository()

    # 결과 테이블
    table = Table(title="📊 Repository Health Check")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="white")
    table.add_column("상태", style="white")

    table.add_row("Open Issues", str(result['open_issues']), "")
    table.add_row(
        "Unanswered (3+ days)",
        str(result['unanswered']),
        "⚠️" if result['unanswered'] > 0 else "✅"
    )
    table.add_row(
        "Unassigned bugs",
        str(result['unassigned_bugs']),
        "⚠️" if result['unassigned_bugs'] > 0 else "✅"
    )
    table.add_row("Doc gaps detected", str(result['doc_gaps']), "")
    table.add_row("Promotion candidates", str(result['promotion_candidates']), "")

    console.print(table)

@app.command()
def assign(
    issue: int = typer.Argument(..., help="이슈 번호"),
    execute: bool = typer.Option(False, "--execute", "-e", help="실제로 GitHub에 코멘트 작성")
):
    """이슈에 담당자 제안"""
    engine = get_engine()

    with console.status("[bold green]분석 중..."):
        result = engine.suggest_assignment(issue)

    if not result:
        console.print("[yellow]적합한 담당자를 찾지 못했습니다.[/yellow]")
        return

    # 분석 결과
    analysis = result['analysis']
    assignment = result['assignment']

    console.print(Panel(
        f"""[bold]Issue #{issue} 분석[/bold]

유형: {analysis.issue_type.value}
우선순위: {analysis.priority.value}
필요 스킬: {', '.join(analysis.required_skills)}
""",
        title="🔍 Issue Analysis"
    ))

    # 할당 제안
    table = Table(title="🎯 Assignment Suggestion")
    table.add_column("항목", style="cyan")
    table.add_column("내용")

    table.add_row("추천 담당자", f"@{assignment.recommended_assignee}")
    table.add_row("확신도", f"{assignment.confidence * 100:.0f}%")
    table.add_row("대안", ", ".join([f"@{u}" for u in assignment.alternative_assignees]))

    console.print(table)

    # 코멘트 미리보기
    console.print(Panel(result['comment'], title="💬 생성될 코멘트"))

    if execute:
        console.print("[green]✅ GitHub에 코멘트를 작성했습니다.[/green]")
    else:
        console.print("[dim]--execute 옵션으로 실제 코멘트를 작성할 수 있습니다.[/dim]")

@app.command()
def respond(
    issue: int = typer.Argument(..., help="이슈 번호"),
    execute: bool = typer.Option(False, "--execute", "-e", help="실제로 GitHub에 코멘트 작성")
):
    """이슈에 답변 생성"""
    engine = get_engine()

    with console.status("[bold green]답변 생성 중..."):
        result = engine.generate_response(issue)

    response = result['response']

    console.print(Panel(
        f"""전략: {response.strategy.value}
확신도: {response.confidence * 100:.0f}%
후속 조치 필요: {"예" if response.follow_up_needed else "아니오"}
""",
        title="📋 Response Strategy"
    ))

    console.print(Panel(result['comment'], title="💬 생성된 답변"))

    if execute:
        console.print("[green]✅ GitHub에 답변을 작성했습니다.[/green]")
    else:
        console.print("[dim]--execute 옵션으로 실제 답변을 작성할 수 있습니다.[/dim]")

@app.command()
def docs():
    """문서 갭 분석"""
    engine = get_engine()

    with console.status("[bold green]문서 갭 분석 중..."):
        gap = engine.detect_doc_gaps()

    if not gap.has_gap:
        console.print("[green]✅ 문서 갭이 발견되지 않았습니다.[/green]")
        return

    console.print(Panel(
        f"""[bold]주제:[/bold] {gap.gap_topic}
[bold]영향 이슈:[/bold] {', '.join([f'#{n}' for n in gap.affected_issues])}
[bold]제안 위치:[/bold] {gap.suggested_doc_path}
[bold]우선순위:[/bold] {gap.priority.value}

[bold]제안 아웃라인:[/bold]
{chr(10).join(['• ' + item for item in gap.suggested_outline])}
""",
        title="📝 문서 갭 발견"
    ))

@app.command()
def promotions():
    """승격 후보 확인"""
    engine = get_engine()

    with console.status("[bold green]기여자 분석 중..."):
        candidates = engine.find_promotion_candidates()

    if not candidates:
        console.print("[yellow]현재 승격 후보가 없습니다.[/yellow]")
        return

    for candidate in candidates:
        console.print(Panel(
            candidate['notification'],
            title=f"👑 @{candidate['contributor'].username}"
        ))

@app.command()
def run():
    """전체 DevRel 워크플로우 실행"""
    engine = get_engine()

    console.print("[bold]🚀 PRISM DevRel Agent[/bold]\n")

    # 1. 분석
    console.print("[cyan]1/4[/cyan] 저장소 분석...")
    analysis = engine.analyze_repository()
    console.print(f"    → Open issues: {analysis['open_issues']}")
    console.print(f"    → Needs attention: {analysis['unanswered']}")

    # 2. 할당 제안
    console.print("\n[cyan]2/4[/cyan] 할당 제안...")
    for issue_num in analysis.get('unassigned_issue_numbers', [])[:3]:
        result = engine.suggest_assignment(issue_num)
        if result:
            console.print(f"    → #{issue_num} → @{result['assignment'].recommended_assignee}")

    # 3. 답변 생성
    console.print("\n[cyan]3/4[/cyan] 답변 생성...")
    for issue_num in analysis.get('unanswered_issue_numbers', [])[:3]:
        result = engine.generate_response(issue_num)
        console.print(f"    → #{issue_num}: {result['response'].strategy.value}")

    # 4. 승격 확인
    console.print("\n[cyan]4/4[/cyan] 승격 후보...")
    candidates = engine.find_promotion_candidates()
    for c in candidates:
        eval = c['evaluation']
        console.print(f"    → @{c['contributor'].username}: {eval.current_stage} → {eval.suggested_stage}")

    console.print("\n[green]✅ 분석 완료![/green]")
    console.print("[dim]--execute 옵션으로 실제 GitHub 액션을 수행할 수 있습니다.[/dim]")

if __name__ == "__main__":
    app()
```

---

## 7. 설정 및 의존성

### 7.1 환경 변수

```bash
# .env
OPENAI_API_KEY=sk-xxxxxxxxxxxx
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPO=owner/prism-demo-oss

# 모델 설정 (선택적 - 기본값 사용 가능)
MODEL_TRIAGE=gpt-4.1-mini
MODEL_ASSIGNMENT=gpt-4.1
MODEL_RESPONSE=gpt-5-mini
MODEL_DOC_GAP=gpt-4.1
MODEL_PROMOTION=gpt-5
MODEL_EMBEDDING=text-embedding-3-large
```

### 7.2 의존성

```toml
# pyproject.toml
[project]
name = "prism-devrel"
version = "0.1.0"
description = "PRISM DevRel Agent - AI-powered open source community management"
requires-python = ">=3.11"

dependencies = [
    # LLM (2026년 1월 최신 - GPT-5.x 지원)
    "openai>=2.8.0",

    # Vector DB (2026년 1월 - EphemeralClient 지원)
    "chromadb>=1.4.0",

    # GitHub
    "PyGithub>=2.2.0",

    # CLI
    "typer>=0.12.0",
    "rich>=13.7.0",

    # Data Validation & Settings
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",

    # Utils
    "python-dotenv>=1.0.0",
    "httpx>=0.27.0",
]

[project.scripts]
prism-devrel = "devrel.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 7.3 예상 비용 (데모 기준, 품질 우선)

| 작업 | 모델 | 예상 호출 | 토큰/호출 | 예상 비용 |
|------|------|----------|----------|----------|
| 이슈 분석 | gpt-4.1-mini | 10회 | ~500 | ~$0.01 |
| 할당 제안 | gpt-4.1 | 5회 | ~1500 | ~$0.08 |
| 답변 생성 | gpt-5-mini | 5회 | ~1500 | ~$0.02 |
| 문서 갭 | gpt-4.1 | 2회 | ~2000 | ~$0.03 |
| 승격 평가 | gpt-5 | 3회 | ~1500 | ~$0.05 |
| Embedding | embedding-3-large | 30회 | ~500 | ~$0.002 |
| **합계** | | | | **~$0.20** |

> 해커톤 전체 (개발 + 테스트 + 데모): **$3~5** 예상 - 충분히 여유 있음

---

## 8. Demo Repository

> **핵심**: GitHub에 실제 데모 레포를 만들고, 테스트 이슈를 미리 생성해둡니다.
> Agent는 **실제 GitHub API**로 이 데이터를 읽어옵니다.

### 8.1 데모 레포 세팅 단계

```bash
# 1. GitHub에서 새 레포 생성
#    이름: prism-demo-oss (또는 원하는 이름)
#    Public으로 설정

# 2. 레포 클론
git clone https://github.com/YOUR_USERNAME/prism-demo-oss
cd prism-demo-oss

# 3. 기본 구조 생성
mkdir -p docs src/auth src/cache src/api examples

# 4. 문서 파일 생성 (Redis 섹션 의도적 누락!)
echo "# Getting Started" > docs/getting-started.md
echo "# Configuration\n\n## Authentication\n..." > docs/configuration.md
echo "# API Reference" > docs/api-reference.md
echo "# Debugging\n\nSet LOG_LEVEL=debug" > docs/debugging.md

# 5. 커밋 & 푸시
git add . && git commit -m "Initial setup" && git push

# 6. GitHub 웹에서 테스트 이슈 생성 (아래 8.3 참조)
```

### 8.2 레포 구조

```
prism-demo-oss/
├── README.md
├── CONTRIBUTING.md
├── docs/
│   ├── getting-started.md
│   ├── configuration.md      # ⚠️ Redis 섹션 의도적 누락 (문서 갭 시연용)
│   ├── api-reference.md
│   └── debugging.md
├── src/
│   ├── auth/
│   ├── cache/
│   └── api/
└── examples/
    └── redis-config.example   # 존재하지만 문서에서 참조 안 함
```

### 8.3 사전 생성할 이슈 (GitHub 웹에서 직접 생성)

| # | 제목 | 라벨 | 목적 |
|---|------|------|------|
| 1 | OAuth2 authentication fails silently | `bug`, `auth` | 할당 시연 |
| 2 | How do I enable debug logging? | `question` | 답변 시연 |
| 3 | Redis cache setup guide? | `question`, `documentation` | 문서 갭 시연 |
| 4 | Redis configuration not working | `question`, `bug` | 문서 갭 시연 |
| 5 | Cache setup documentation needed | `question`, `documentation` | 문서 갭 시연 |
| 6 | Where is Redis config example? | `question` | 문서 갭 시연 |
| 7 | Performance regression in v2.3.0 | `bug`, `performance` | 추가 시연 |

### 8.4 환경 설정

```bash
# .env 파일
OPENAI_API_KEY=sk-xxxxxxxxxxxx
GITHUB_TOKEN=ghp_xxxxxxxxxxxx       # repo 권한 필요
GITHUB_REPO=YOUR_USERNAME/prism-demo-oss

# DRY_RUN 설정
DRY_RUN=true                         # 코멘트 미리보기만 (실제 작성 안함)
# DRY_RUN=false                      # 실제 GitHub에 코멘트 작성
```

### 8.5 기여자 데이터 수집

기여자 데이터는 GitHub API로 자동 수집됩니다:
- **수집 대상**: Merged PR, Code Review
- **추출 정보**: PR 수, 리뷰 수, 전문 영역, 활동 기간
- **전문 영역 추론**: PR에서 수정한 파일 경로 + 라벨 기반
- **기여 단계 분류**: PR 수 기준 자동 분류
  - FIRST_TIMER: 1개 PR
  - REGULAR: 2-9개 PR
  - CORE: 10-29개 PR
  - MAINTAINER: 30개+ PR

---

## 9. 데모 시나리오

### 9.1 전체 흐름 (3분)

```
0:00-0:30  상황 제시 + prism-devrel analyze
0:30-1:00  이슈 할당: prism-devrel assign 45
1:00-1:30  답변 생성: prism-devrel respond 67
1:30-2:00  문서 갭: prism-devrel docs
2:00-2:30  승격 제안: prism-devrel promotions
2:30-3:00  요약 및 마무리
```

### 9.2 CLI 명령어

```bash
# 전체 분석
prism-devrel analyze

# 이슈 할당 제안
prism-devrel assign 45
prism-devrel assign 45 --execute  # 실제 GitHub 반영

# 답변 생성
prism-devrel respond 67
prism-devrel respond 67 --execute

# 문서 갭 분석
prism-devrel docs

# 승격 후보 확인
prism-devrel promotions

# 전체 워크플로우
prism-devrel run
```

---

## 10. 구현 일정 (해커톤)

### Phase 1: 기반 세팅 (2시간)

- [ ] 프로젝트 구조 생성
- [ ] GitHub 데모 레포 세팅 (테스트 이슈/PR 생성)
- [ ] OpenAI 클라이언트 + Structured Outputs 스키마
- [ ] Vector Store (Chroma) 세팅
- [ ] GitHub 클라이언트 (이슈 + 기여자 수집)

### Phase 2: Agent 구현 (3시간)

- [ ] 이슈 분석 + 할당 Agent
- [ ] 답변 생성 Agent
- [ ] 문서 갭 감지 Agent
- [ ] 승격 제안 Agent

### Phase 3: CLI + 통합 (2시간)

- [ ] CLI 명령어 구현
- [ ] Rich UI 다듬기
- [ ] 전체 워크플로우 테스트

### Phase 4: 데모 준비 (1시간)

- [ ] Demo repo 세팅
- [ ] 시나리오 테스트
- [ ] 발표 준비

---

## 11. 핵심 차별점

```
┌─────────────────────────────────────────────────────────────┐
│  일반 자동화 vs PRISM DevRel Agent                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  일반 자동화              PRISM DevRel Agent                │
│  ─────────────────────    ─────────────────────             │
│  라벨만 붙임              AI가 이유와 함께 분석             │
│  무작위 할당              전문성 + 임베딩 매칭              │
│  템플릿 답변              맥락 이해한 맞춤 답변             │
│  규칙 기반                패턴 감지 (문서 갭)               │
│  단순 통계                성장 기회 제안                    │
│  단일 모델                작업별 최적 모델 선택             │
│                                                             │
│  "자동화를 넘어, 커뮤니티를 키운다"                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. 참고 자료

### OpenAI 모델 문서 (2026년 1월 기준)
- [GPT-4.1 Model](https://platform.openai.com/docs/models/gpt-4.1) - 코딩/도구 호출 최적화, 1M 컨텍스트
- [GPT-5 Model](https://platform.openai.com/docs/models/gpt-5) - 추론/에이전트 작업, 400K 컨텍스트
- [GPT-5 mini Model](https://platform.openai.com/docs/models/gpt-5-mini) - 비용 효율 추론
- [GPT-5.2 Model](https://platform.openai.com/docs/models/gpt-5.2) - 최신 플래그십, Thinking 모드
- [Structured Outputs Guide](https://platform.openai.com/docs/guides/structured-outputs)
- [Responses API vs Chat Completions](https://platform.openai.com/docs/guides/responses-vs-chat-completions) - API 비교
- [text-embedding-3-large](https://platform.openai.com/docs/models/text-embedding-3-large)
- [OpenAI Pricing](https://platform.openai.com/docs/pricing)

### 기술 스택
- [Chroma Vector DB](https://www.trychroma.com/) - [EphemeralClient Docs](https://docs.trychroma.com/docs/run-chroma/ephemeral-client)
- [Typer CLI](https://typer.tiangolo.com/)
- [Rich Terminal UI](https://rich.readthedocs.io/)
- [PyGithub](https://pygithub.readthedocs.io/)
