"""FastAPI server exposing RAG-enhanced DevRel agents."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from devrel.agents.assignment import analyze_issue, analyze_issue_llm
from devrel.agents.response import draft_response, draft_response_llm, draft_response_with_rag
from devrel.agents.types import Issue, IssueType, Priority, ResponseStrategy
from devrel.llm.client import LlmClient
from devrel.search.rag_client import RAGClient

GITHUB_REPO = os.getenv("GITHUB_REPO", "GSN-OMG/Prism")


class IssueCreateInput(BaseModel):
    title: str
    body: str
    labels: list[str] = []


class IssueInput(BaseModel):
    number: int
    title: str
    body: str
    labels: list[str] = []


class SearchInput(BaseModel):
    query: str
    limit: int = 10
    repo_filter: str | None = None
    search_type: str = "hybrid"


class AgentRunInput(BaseModel):
    issue: IssueInput
    agent: str
    use_llm: bool = False
    use_rag: bool = True


class KBDocumentResponse(BaseModel):
    kb_id: str
    item_type: str
    item_number: int
    section: str
    source_ref: str
    text: str
    metadata: dict[str, Any]
    score: float | None


class IssueAnalysisResponse(BaseModel):
    issue_type: str
    priority: str
    required_skills: list[str]
    keywords: list[str]
    summary: str
    needs_more_info: bool
    suggested_action: str


class ResponseAgentResponse(BaseModel):
    strategy: str
    response_text: str
    confidence: float
    references: list[str]
    follow_up_needed: bool


_rag_client: RAGClient | None = None
_llm_client: LlmClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rag_client, _llm_client
    try:
        _rag_client = RAGClient()
    except Exception as e:
        print(f"Warning: RAG client not available: {e}")
        _rag_client = None

    if os.getenv("OPENAI_API_KEY"):
        try:
            _llm_client = LlmClient()
        except Exception as e:
            print(f"Warning: LLM client not available: {e}")
            _llm_client = None
    yield


app = FastAPI(
    title="PRISM DevRel Agent API",
    description="RAG-enhanced DevRel agents for GitHub issue triage and response",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "rag_available": _rag_client is not None,
        "llm_available": _llm_client is not None,
        "github_token_set": bool(os.getenv("GITHUB_TOKEN")),
    }


@app.post("/api/github/issues")
async def create_github_issue(input: IssueCreateInput):
    """Create a new GitHub issue in the target repository."""
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN not configured")

    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "title": input.title,
        "body": input.body,
    }
    if input.labels:
        payload["labels"] = input.labels

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code not in (200, 201):
        raise HTTPException(
            status_code=response.status_code,
            detail=f"GitHub API error: {response.text}",
        )

    issue_data = response.json()
    return {
        "number": issue_data["number"],
        "title": issue_data["title"],
        "body": issue_data.get("body", ""),
        "labels": [label["name"] for label in issue_data.get("labels", [])],
        "html_url": issue_data["html_url"],
        "user": {
            "login": issue_data["user"]["login"],
            "avatar_url": issue_data["user"]["avatar_url"],
        },
    }


@app.post("/api/search", response_model=list[KBDocumentResponse])
async def search_kb(input: SearchInput):
    if not _rag_client:
        raise HTTPException(status_code=503, detail="RAG client not available")

    if input.search_type == "keyword":
        docs = _rag_client.search_keyword(
            input.query, limit=input.limit, repo_filter=input.repo_filter
        )
    elif input.search_type == "vector":
        docs = _rag_client.search_vector(
            input.query, limit=input.limit, repo_filter=input.repo_filter
        )
    else:
        docs = _rag_client.search_hybrid(
            input.query, limit=input.limit, repo_filter=input.repo_filter
        )

    return [
        KBDocumentResponse(
            kb_id=d.kb_id,
            item_type=d.item_type,
            item_number=d.item_number,
            section=d.section,
            source_ref=d.source_ref,
            text=d.text,
            metadata=d.metadata,
            score=d.score,
        )
        for d in docs
    ]


@app.post("/api/agents/analyze", response_model=IssueAnalysisResponse)
async def analyze_issue_endpoint(input: IssueInput, use_llm: bool = False):
    issue = Issue(
        number=input.number,
        title=input.title,
        body=input.body,
        labels=tuple(input.labels),
    )

    if use_llm and _llm_client:
        analysis = analyze_issue_llm(_llm_client, issue)
    else:
        analysis = analyze_issue(issue)

    return IssueAnalysisResponse(
        issue_type=analysis.issue_type.value,
        priority=analysis.priority.value,
        required_skills=list(analysis.required_skills),
        keywords=list(analysis.keywords),
        summary=analysis.summary,
        needs_more_info=analysis.needs_more_info,
        suggested_action=analysis.suggested_action.value,
    )


@app.post("/api/agents/response", response_model=ResponseAgentResponse)
async def response_agent_endpoint(
    input: IssueInput,
    use_llm: bool = False,
    use_rag: bool = True,
):
    issue = Issue(
        number=input.number,
        title=input.title,
        body=input.body,
        labels=tuple(input.labels),
    )

    if use_llm and _llm_client:
        analysis = analyze_issue_llm(_llm_client, issue)
    else:
        analysis = analyze_issue(issue)

    if use_rag and use_llm and _rag_client and _llm_client:
        response = draft_response_with_rag(
            _llm_client,
            _rag_client,
            issue=issue,
            analysis=analysis,
        )
    elif use_llm and _llm_client:
        response = draft_response_llm(
            _llm_client,
            issue=issue,
            analysis=analysis,
        )
    else:
        response = draft_response(issue, analysis)

    return ResponseAgentResponse(
        strategy=response.strategy.value,
        response_text=response.response_text,
        confidence=response.confidence,
        references=list(response.references),
        follow_up_needed=response.follow_up_needed,
    )


@app.post("/api/agents/run")
async def run_agent_pipeline(input: AgentRunInput):
    """Run the full agent pipeline for an issue."""
    issue = Issue(
        number=input.issue.number,
        title=input.issue.title,
        body=input.issue.body,
        labels=tuple(input.issue.labels),
    )

    results: dict[str, Any] = {}

    if input.use_llm and _llm_client:
        analysis = analyze_issue_llm(_llm_client, issue)
    else:
        analysis = analyze_issue(issue)

    results["analysis"] = {
        "issue_type": analysis.issue_type.value,
        "priority": analysis.priority.value,
        "required_skills": list(analysis.required_skills),
        "keywords": list(analysis.keywords),
        "summary": analysis.summary,
        "needs_more_info": analysis.needs_more_info,
        "suggested_action": analysis.suggested_action.value,
    }

    kb_references: list[str] = []
    if input.use_rag and _rag_client:
        query_parts = [issue.title] + list(analysis.keywords[:3])
        search_query = " ".join(query_parts)
        kb_docs = _rag_client.search_hybrid(search_query, limit=5)
        kb_references = _rag_client.format_references(kb_docs)
        results["rag_results"] = [
            {
                "kb_id": d.kb_id,
                "item_type": d.item_type,
                "item_number": d.item_number,
                "section": d.section,
                "source_ref": d.source_ref,
                "text": d.text[:200],
                "score": d.score,
            }
            for d in kb_docs
        ]

    if input.use_llm and _llm_client:
        response = draft_response_llm(
            _llm_client,
            issue=issue,
            analysis=analysis,
            references=kb_references,
        )
    else:
        response = draft_response(issue, analysis)

    results["response"] = {
        "strategy": response.strategy.value,
        "response_text": response.response_text,
        "confidence": response.confidence,
        "references": list(response.references),
        "follow_up_needed": response.follow_up_needed,
    }

    return results


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
