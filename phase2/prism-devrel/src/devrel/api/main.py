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


# =============================================================================
# Phase 3: Retrospective Court API with Real LLM Integration
# =============================================================================

import asyncio
import json
import uuid
from openai import AsyncOpenAI

class CourtInput(BaseModel):
    """Input for running retrospective court on a single agent result."""
    agent: str  # agent type: issue_analysis, assignment, response, docs_gap, promotion
    agent_output: dict[str, Any]
    human_feedback: dict[str, Any]
    issue: IssueInput


class CourtStageOutput(BaseModel):
    """Output from a single court stage (prosecutor, defense, jury, judge)."""
    stage: str
    content: str
    reasoning: str


class PromptUpdateProposal(BaseModel):
    """Judge's proposal for prompt update."""
    role: str
    from_version: int | None
    proposal: str
    reason: str
    status: str = "proposed"


class CourtResult(BaseModel):
    """Full result from retrospective court."""
    agent: str
    case_id: str
    court_run_id: str
    status: str
    stages: dict[str, CourtStageOutput]
    lessons: list[dict[str, Any]]
    prompt_updates: list[PromptUpdateProposal]


# Court agent prompts for each stage
COURT_PROMPTS = {
    "prosecutor": """You are the PROSECUTOR in a retrospective court evaluating an AI agent's output.

Your role is to CRITICIZE the agent's output and identify potential issues, mistakes, or areas for improvement.

## Case Information
Agent Type: {agent_type}
Agent Name: {agent_name}

## Original Issue
Title: {issue_title}
Body: {issue_body}

## Agent Output
{agent_output}

## Human Feedback
Approved: {approved}
Comment: {comment}

## Your Task
1. Identify weaknesses, errors, or suboptimal decisions in the agent's output
2. Consider if the output fully addresses the issue
3. Evaluate if the reasoning is sound
4. Propose lessons that highlight what the agent should NOT do

Respond in JSON format:
{{
    "criticisms": ["criticism 1", "criticism 2", ...],
    "candidate_lessons": [
        {{
            "role": "{agent_type}",
            "polarity": "dont",
            "title": "lesson title",
            "content": "lesson content",
            "rationale": "why this lesson matters",
            "confidence": 0.8,
            "tags": ["tag1", "tag2"],
            "evidence_event_ids": []
        }}
    ]
}}""",

    "defense": """You are the DEFENSE in a retrospective court evaluating an AI agent's output.

Your role is to DEFEND the agent's output and highlight its strengths and correct decisions.

## Case Information
Agent Type: {agent_type}
Agent Name: {agent_name}

## Original Issue
Title: {issue_title}
Body: {issue_body}

## Agent Output
{agent_output}

## Human Feedback
Approved: {approved}
Comment: {comment}

## Your Task
1. Identify strengths and positive aspects of the agent's output
2. Explain why certain decisions were reasonable
3. Highlight any best practices demonstrated
4. Propose lessons that highlight what the agent should continue doing

Respond in JSON format:
{{
    "praises": ["praise 1", "praise 2", ...],
    "candidate_lessons": [
        {{
            "role": "{agent_type}",
            "polarity": "do",
            "title": "lesson title",
            "content": "lesson content",
            "rationale": "why this lesson matters",
            "confidence": 0.8,
            "tags": ["tag1", "tag2"],
            "evidence_event_ids": []
        }}
    ]
}}""",

    "jury": """You are the JURY in a retrospective court evaluating an AI agent's output.

Your role is to OBSERVE and provide an unbiased assessment of the agent's performance.

## Case Information
Agent Type: {agent_type}
Agent Name: {agent_name}

## Original Issue
Title: {issue_title}
Body: {issue_body}

## Agent Output
{agent_output}

## Human Feedback
Approved: {approved}
Comment: {comment}

## Your Task
1. Make objective observations about the agent's output
2. Identify risks or concerns
3. Note any missing information that would help evaluation
4. Propose balanced lessons based on your observations

Respond in JSON format:
{{
    "observations": ["observation 1", "observation 2", ...],
    "risks": ["risk 1", "risk 2", ...],
    "missing_info": ["missing info 1", ...],
    "candidate_lessons": [
        {{
            "role": "{agent_type}",
            "polarity": "do" or "dont",
            "title": "lesson title",
            "content": "lesson content",
            "rationale": "why this lesson matters",
            "confidence": 0.8,
            "tags": ["tag1", "tag2"],
            "evidence_event_ids": []
        }}
    ]
}}""",

    "judge": """You are the JUDGE in a retrospective court. You make the final decision.

## Case Information
Agent Type: {agent_type}
Agent Name: {agent_name}

## Original Issue
Title: {issue_title}
Body: {issue_body}

## Agent Output
{agent_output}

## Human Feedback
Approved: {approved}
Comment: {comment}

## Prosecutor's Arguments
{prosecutor_output}

## Defense's Arguments
{defense_output}

## Jury's Observations
{jury_output}

## Your Task
1. Review all arguments from prosecutor, defense, and jury
2. Select the most valuable lessons to keep
3. Defer lessons that need more evidence
4. If the agent's performance was problematic, propose prompt updates

Respond in JSON format:
{{
    "selected_lessons": [
        {{
            "role": "{agent_type}",
            "polarity": "do" or "dont",
            "title": "lesson title",
            "content": "lesson content",
            "rationale": "why this lesson was selected",
            "confidence": 0.8,
            "tags": ["tag1", "tag2"],
            "evidence_event_ids": []
        }}
    ],
    "deferred_lessons": [
        {{
            "lesson": {{ ... lesson object ... }},
            "reason": "why this lesson was deferred"
        }}
    ],
    "prompt_update_proposals": [
        {{
            "role": "{agent_type}",
            "proposal": "proposed prompt improvement",
            "reason": "why this update is needed",
            "evidence_event_ids": []
        }}
    ],
    "user_improvement_suggestions": [],
    "system_improvement_suggestions": []
}}"""
}

AGENT_NAMES = {
    "issue_analysis": "Issue Analysis Agent",
    "assignment": "Assignment Agent",
    "response": "Response Agent",
    "docs_gap": "Documentation Gap Agent",
    "promotion": "Promotion Agent",
}


async def _run_court_stage_llm(
    openai_client: AsyncOpenAI,
    stage: str,
    agent_type: str,
    issue: IssueInput,
    agent_output: dict[str, Any],
    human_feedback: dict[str, Any],
    prosecutor_output: dict[str, Any] | None = None,
    defense_output: dict[str, Any] | None = None,
    jury_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a single court stage using OpenAI LLM."""
    agent_name = AGENT_NAMES.get(agent_type, agent_type)
    approved = human_feedback.get("approved", False)
    comment = human_feedback.get("comment", "")

    # Format the prompt
    prompt_template = COURT_PROMPTS[stage]
    prompt = prompt_template.format(
        agent_type=agent_type,
        agent_name=agent_name,
        issue_title=issue.title,
        issue_body=issue.body,
        agent_output=json.dumps(agent_output, ensure_ascii=False, indent=2),
        approved="Yes" if approved else "No",
        comment=comment or "No comment provided",
        prosecutor_output=json.dumps(prosecutor_output, ensure_ascii=False, indent=2) if prosecutor_output else "",
        defense_output=json.dumps(defense_output, ensure_ascii=False, indent=2) if defense_output else "",
        jury_output=json.dumps(jury_output, ensure_ascii=False, indent=2) if jury_output else "",
    )

    # Call OpenAI
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are a {stage} in a retrospective court evaluating AI agent outputs. Respond only with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Failed to parse LLM response", "raw": content}


async def _run_court_with_llm(
    agent: str,
    agent_output: dict[str, Any],
    human_feedback: dict[str, Any],
    issue: IssueInput,
) -> CourtResult:
    """Run the full court process using real LLM calls."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        # Fallback to mock if no API key
        return _generate_court_result_mock(agent, agent_output, human_feedback, issue)

    openai_client = AsyncOpenAI(api_key=openai_api_key)
    case_id = str(uuid.uuid4())
    court_run_id = str(uuid.uuid4())

    # Run prosecutor, defense, jury in parallel
    prosecutor_task = _run_court_stage_llm(
        openai_client, "prosecutor", agent, issue, agent_output, human_feedback
    )
    defense_task = _run_court_stage_llm(
        openai_client, "defense", agent, issue, agent_output, human_feedback
    )
    jury_task = _run_court_stage_llm(
        openai_client, "jury", agent, issue, agent_output, human_feedback
    )

    prosecutor_output, defense_output, jury_output = await asyncio.gather(
        prosecutor_task, defense_task, jury_task
    )

    # Run judge with all outputs
    judge_output = await _run_court_stage_llm(
        openai_client, "judge", agent, issue, agent_output, human_feedback,
        prosecutor_output=prosecutor_output,
        defense_output=defense_output,
        jury_output=jury_output,
    )

    # Build stage outputs
    agent_name = AGENT_NAMES.get(agent, agent)

    stages = {
        "prosecutor": CourtStageOutput(
            stage="prosecutor",
            content=f"Criticism of {agent_name} output",
            reasoning="; ".join(prosecutor_output.get("criticisms", ["No criticisms provided"]))[:500]
        ),
        "defense": CourtStageOutput(
            stage="defense",
            content=f"Defense of {agent_name} output",
            reasoning="; ".join(defense_output.get("praises", ["No praises provided"]))[:500]
        ),
        "jury": CourtStageOutput(
            stage="jury",
            content=f"Jury assessment of {agent_name}",
            reasoning="; ".join(jury_output.get("observations", ["No observations provided"]))[:500]
        ),
        "judge": CourtStageOutput(
            stage="judge",
            content=f"Final verdict for {agent_name}",
            reasoning=f"Selected {len(judge_output.get('selected_lessons', []))} lessons, "
                      f"proposed {len(judge_output.get('prompt_update_proposals', []))} prompt updates."
        ),
    }

    # Extract lessons
    lessons = []
    for lesson in judge_output.get("selected_lessons", []):
        lessons.append({
            "role": lesson.get("role", agent),
            "polarity": lesson.get("polarity", "do"),
            "title": lesson.get("title", "Untitled lesson"),
            "content": lesson.get("content", ""),
        })

    # Extract prompt updates
    prompt_updates = []
    for proposal in judge_output.get("prompt_update_proposals", []):
        prompt_updates.append(PromptUpdateProposal(
            role=proposal.get("role", agent),
            from_version=1,
            proposal=proposal.get("proposal", ""),
            reason=proposal.get("reason", ""),
            status="proposed",
        ))

    return CourtResult(
        agent=agent,
        case_id=case_id,
        court_run_id=court_run_id,
        status="completed",
        stages=stages,
        lessons=lessons,
        prompt_updates=prompt_updates,
    )


def _generate_court_result_mock(
    agent: str,
    agent_output: dict[str, Any],
    human_feedback: dict[str, Any],
    issue: IssueInput,
) -> CourtResult:
    """Generate court result for an agent (fallback mock implementation)."""
    case_id = str(uuid.uuid4())
    court_run_id = str(uuid.uuid4())

    agent_name = AGENT_NAMES.get(agent, agent)
    approved = human_feedback.get("approved", False)
    comment = human_feedback.get("comment", "")

    prosecutor = CourtStageOutput(
        stage="prosecutor",
        content=f"Criticism of {agent_name} output",
        reasoning=f"The agent output {'was approved but could be improved' if approved else 'was rejected'} by the human reviewer. "
                  f"{'Comment: ' + comment if comment else 'No specific feedback provided.'}"
    )

    defense = CourtStageOutput(
        stage="defense",
        content=f"Defense of {agent_name} output",
        reasoning=f"The {agent_name} followed its designated protocol and produced a structured output. "
                  f"The output contains all required fields and demonstrates logical reasoning."
    )

    jury = CourtStageOutput(
        stage="jury",
        content=f"Jury assessment of {agent_name}",
        reasoning=f"Based on the evidence, the {agent_name}'s output is {'satisfactory' if approved else 'needs improvement'}. "
                  f"Key observation: Human feedback indicates {'approval' if approved else 'rejection'}."
    )

    lessons = []
    prompt_updates = []

    if not approved:
        lessons.append({
            "role": agent,
            "polarity": "dont",
            "title": f"Improve {agent_name} accuracy",
            "content": f"Based on human feedback, the {agent_name} should be improved to address: {comment or 'unspecified concerns'}",
        })
        prompt_updates.append(PromptUpdateProposal(
            role=agent,
            from_version=1,
            proposal=f"Enhanced prompt for {agent_name} that addresses human feedback: {comment or 'general improvement needed'}",
            reason=f"Human reviewer rejected the output. Feedback: {comment or 'No specific feedback'}",
            status="proposed",
        ))
    else:
        lessons.append({
            "role": agent,
            "polarity": "do",
            "title": f"{agent_name} best practice",
            "content": f"The {agent_name}'s approach was validated by human review. Continue this pattern.",
        })

    judge = CourtStageOutput(
        stage="judge",
        content=f"Final verdict for {agent_name}",
        reasoning=f"After reviewing prosecutor, defense, and jury inputs, the verdict is: "
                  f"{'APPROVED - Output meets quality standards' if approved else 'IMPROVEMENT NEEDED - Output requires refinement'}. "
                  f"{'Prompt update proposal generated.' if prompt_updates else 'No prompt updates required.'}"
    )

    return CourtResult(
        agent=agent,
        case_id=case_id,
        court_run_id=court_run_id,
        status="completed",
        stages={
            "prosecutor": prosecutor,
            "defense": defense,
            "jury": jury,
            "judge": judge,
        },
        lessons=lessons,
        prompt_updates=prompt_updates,
    )


@app.post("/api/court/run", response_model=CourtResult)
async def run_retrospective_court(input: CourtInput):
    """
    Run retrospective court for a single agent after human review.

    Uses real LLM calls (OpenAI) for prosecutor, defense, jury, and judge agents
    to evaluate the agent output and human feedback.
    """
    return await _run_court_with_llm(
        agent=input.agent,
        agent_output=input.agent_output,
        human_feedback=input.human_feedback,
        issue=input.issue,
    )


# =============================================================================
# SSE Streaming Court Endpoint
# =============================================================================
from fastapi.responses import StreamingResponse


async def _stream_court_stages(
    agent: str,
    agent_output: dict[str, Any],
    human_feedback: dict[str, Any],
    issue: IssueInput,
):
    """Generator that yields SSE events for each court stage."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    case_id = str(uuid.uuid4())
    court_run_id = str(uuid.uuid4())
    agent_name = AGENT_NAMES.get(agent, agent)

    # Send initial event
    yield f"data: {json.dumps({'type': 'start', 'case_id': case_id, 'court_run_id': court_run_id})}\n\n"

    if not openai_api_key:
        # Mock mode - simulate delays for each stage
        stages_data = [
            ("prosecutor", "Criticizing agent output...", 1.5),
            ("defense", "Defending agent decisions...", 1.5),
            ("jury", "Observing and assessing...", 1.5),
            ("judge", "Rendering final verdict...", 2.0),
        ]

        for stage, description, delay in stages_data:
            yield f"data: {json.dumps({'type': 'stage_start', 'stage': stage, 'description': description})}\n\n"
            await asyncio.sleep(delay)

            mock_result = _generate_court_result_mock(agent, agent_output, human_feedback, issue)
            stage_output = mock_result.stages[stage]

            yield f"data: {json.dumps({'type': 'stage_complete', 'stage': stage, 'output': {'content': stage_output.content, 'reasoning': stage_output.reasoning}})}\n\n"

        # Send final result
        yield f"data: {json.dumps({'type': 'complete', 'result': mock_result.model_dump()})}\n\n"
        return

    # Real LLM mode
    openai_client = AsyncOpenAI(api_key=openai_api_key)

    # Stage 1-3: Prosecutor, Defense, Jury (parallel)
    yield f"data: {json.dumps({'type': 'stage_start', 'stage': 'prosecutor', 'description': 'Analyzing agent weaknesses...'})}\n\n"
    yield f"data: {json.dumps({'type': 'stage_start', 'stage': 'defense', 'description': 'Identifying agent strengths...'})}\n\n"
    yield f"data: {json.dumps({'type': 'stage_start', 'stage': 'jury', 'description': 'Making objective observations...'})}\n\n"

    prosecutor_task = _run_court_stage_llm(
        openai_client, "prosecutor", agent, issue, agent_output, human_feedback
    )
    defense_task = _run_court_stage_llm(
        openai_client, "defense", agent, issue, agent_output, human_feedback
    )
    jury_task = _run_court_stage_llm(
        openai_client, "jury", agent, issue, agent_output, human_feedback
    )

    prosecutor_output, defense_output, jury_output = await asyncio.gather(
        prosecutor_task, defense_task, jury_task
    )

    # Send stage complete events
    yield f"data: {json.dumps({'type': 'stage_complete', 'stage': 'prosecutor', 'output': {'content': f'Criticism of {agent_name}', 'reasoning': '; '.join(prosecutor_output.get('criticisms', ['Analysis complete']))[:300]}})}\n\n"
    yield f"data: {json.dumps({'type': 'stage_complete', 'stage': 'defense', 'output': {'content': f'Defense of {agent_name}', 'reasoning': '; '.join(defense_output.get('praises', ['Analysis complete']))[:300]}})}\n\n"
    yield f"data: {json.dumps({'type': 'stage_complete', 'stage': 'jury', 'output': {'content': f'Jury assessment of {agent_name}', 'reasoning': '; '.join(jury_output.get('observations', ['Assessment complete']))[:300]}})}\n\n"

    # Stage 4: Judge
    yield f"data: {json.dumps({'type': 'stage_start', 'stage': 'judge', 'description': 'Rendering final verdict...'})}\n\n"

    judge_output = await _run_court_stage_llm(
        openai_client, "judge", agent, issue, agent_output, human_feedback,
        prosecutor_output=prosecutor_output,
        defense_output=defense_output,
        jury_output=jury_output,
    )

    # Build final result
    stages = {
        "prosecutor": CourtStageOutput(
            stage="prosecutor",
            content=f"Criticism of {agent_name} output",
            reasoning="; ".join(prosecutor_output.get("criticisms", ["No criticisms"]))[:500]
        ),
        "defense": CourtStageOutput(
            stage="defense",
            content=f"Defense of {agent_name} output",
            reasoning="; ".join(defense_output.get("praises", ["No praises"]))[:500]
        ),
        "jury": CourtStageOutput(
            stage="jury",
            content=f"Jury assessment of {agent_name}",
            reasoning="; ".join(jury_output.get("observations", ["No observations"]))[:500]
        ),
        "judge": CourtStageOutput(
            stage="judge",
            content=f"Final verdict for {agent_name}",
            reasoning=f"Selected {len(judge_output.get('selected_lessons', []))} lessons, "
                      f"proposed {len(judge_output.get('prompt_update_proposals', []))} prompt updates."
        ),
    }

    lessons = []
    for lesson in judge_output.get("selected_lessons", []):
        lessons.append({
            "role": lesson.get("role", agent),
            "polarity": lesson.get("polarity", "do"),
            "title": lesson.get("title", "Untitled"),
            "content": lesson.get("content", ""),
        })

    prompt_updates = []
    for proposal in judge_output.get("prompt_update_proposals", []):
        prompt_updates.append(PromptUpdateProposal(
            role=proposal.get("role", agent),
            from_version=1,
            proposal=proposal.get("proposal", ""),
            reason=proposal.get("reason", ""),
            status="proposed",
        ))

    result = CourtResult(
        agent=agent,
        case_id=case_id,
        court_run_id=court_run_id,
        status="completed",
        stages=stages,
        lessons=lessons,
        prompt_updates=prompt_updates,
    )

    yield f"data: {json.dumps({'type': 'stage_complete', 'stage': 'judge', 'output': {'content': stages['judge'].content, 'reasoning': stages['judge'].reasoning}})}\n\n"
    yield f"data: {json.dumps({'type': 'complete', 'result': result.model_dump()})}\n\n"


@app.post("/api/court/run/stream")
async def run_retrospective_court_stream(input: CourtInput):
    """
    Run retrospective court with SSE streaming for real-time stage updates.

    Returns Server-Sent Events (SSE) for each court stage:
    - stage_start: When a stage begins
    - stage_complete: When a stage finishes
    - complete: Final result with all data
    """
    return StreamingResponse(
        _stream_court_stages(
            agent=input.agent,
            agent_output=input.agent_output,
            human_feedback=input.human_feedback,
            issue=input.issue,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/court/prompt-updates/{update_id}/review")
async def review_prompt_update(update_id: str, action: str, comment: str = ""):
    """Review a prompt update proposal (approve/reject)."""
    return {
        "id": update_id,
        "action": action,
        "status": "approved" if action == "approve" else "rejected",
        "comment": comment,
    }


@app.post("/api/court/prompt-updates/{update_id}/apply")
async def apply_prompt_update(update_id: str):
    """Apply an approved prompt update."""
    return {
        "id": update_id,
        "status": "applied",
        "message": "Prompt update applied successfully",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
