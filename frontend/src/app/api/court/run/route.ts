import { NextRequest, NextResponse } from 'next/server';
import { GitHubIssue, AgentType, CourtResult } from '@/types';

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000';

interface CourtRunRequest {
  agent: AgentType;
  agentOutput: Record<string, unknown>;
  humanFeedback: {
    approved: boolean;
    comment: string;
  };
  issue: GitHubIssue;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json() as CourtRunRequest;
    const { agent, agentOutput, humanFeedback, issue } = body;

    // Call backend court API
    const res = await fetch(`${BACKEND_API_URL}/api/court/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent,
        agent_output: agentOutput,
        human_feedback: humanFeedback,
        issue: {
          number: issue.number,
          title: issue.title,
          body: issue.body,
          labels: issue.labels,
        },
      }),
    });

    if (!res.ok) {
      throw new Error(`Backend court API error: ${res.status}`);
    }

    const result = await res.json() as CourtResult;
    return NextResponse.json(result);
  } catch (error) {
    console.error('Court execution failed:', error);
    return NextResponse.json(
      { error: 'Court execution failed' },
      { status: 500 }
    );
  }
}
