import { NextRequest } from 'next/server';
import { GitHubIssue, AgentType } from '@/types';

const BACKEND_API_URL = process.env.BACKEND_API_URL || 'http://localhost:8000';

interface CourtStreamRequest {
  agent: AgentType;
  agentOutput: Record<string, unknown>;
  humanFeedback: {
    approved: boolean;
    comment: string;
  };
  issue: GitHubIssue;
}

export async function POST(request: NextRequest) {
  const body = await request.json() as CourtStreamRequest;
  const { agent, agentOutput, humanFeedback, issue } = body;

  // Call backend court streaming API
  const res = await fetch(`${BACKEND_API_URL}/api/court/run/stream`, {
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
    return new Response(JSON.stringify({ error: 'Backend court stream API error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Forward the SSE stream from backend to frontend
  const encoder = new TextEncoder();
  const readable = new ReadableStream({
    async start(controller) {
      const reader = res.body?.getReader();
      if (!reader) {
        controller.close();
        return;
      }

      const decoder = new TextDecoder();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          controller.enqueue(encoder.encode(chunk));
        }
      } catch (error) {
        console.error('Stream error:', error);
      } finally {
        controller.close();
      }
    },
  });

  return new Response(readable, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
