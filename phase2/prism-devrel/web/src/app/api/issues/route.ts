import { NextResponse } from 'next/server';
import { GitHubIssue } from '@/types';

const GITHUB_REPO = 'GSN-OMG/Prism';
const GITHUB_API = 'https://api.github.com';

export async function GET() {
  try {
    const token = process.env.GITHUB_TOKEN;

    const headers: HeadersInit = {
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'DevRel-Agent-Demo',
    };

    if (token) {
      headers['Authorization'] = `token ${token}`;
    }

    const response = await fetch(
      `${GITHUB_API}/repos/${GITHUB_REPO}/issues?state=open&per_page=10`,
      { headers, next: { revalidate: 60 } }
    );

    if (!response.ok) {
      // If GitHub API fails, return mock data for demo
      return NextResponse.json(getMockIssues());
    }

    const rawIssues = await response.json();

    const issues: GitHubIssue[] = rawIssues
      .filter((issue: { pull_request?: unknown }) => !issue.pull_request) // Exclude PRs
      .map((issue: {
        number: number;
        title: string;
        body: string | null;
        labels: { name: string }[];
        state: 'open' | 'closed';
        created_at: string;
        user: { login: string; avatar_url: string };
        html_url: string;
      }) => ({
        number: issue.number,
        title: issue.title,
        body: issue.body || '',
        labels: issue.labels.map((l) => l.name),
        state: issue.state,
        created_at: issue.created_at,
        user: {
          login: issue.user.login,
          avatar_url: issue.user.avatar_url,
        },
        html_url: issue.html_url,
      }));

    return NextResponse.json(issues);
  } catch (error) {
    console.error('Failed to fetch GitHub issues:', error);
    // Return mock data for demo
    return NextResponse.json(getMockIssues());
  }
}

// Mock issues for demo purposes
function getMockIssues(): GitHubIssue[] {
  return [
    {
      number: 1,
      title: 'Add support for Redis caching',
      body: 'We need to add Redis caching support to improve performance. The current implementation is too slow for production workloads.\n\nExpected behavior:\n- Support Redis connection\n- Cache API responses\n- Configurable TTL',
      labels: ['feature', 'enhancement'],
      state: 'open',
      created_at: new Date().toISOString(),
      user: {
        login: 'demo-user',
        avatar_url: 'https://avatars.githubusercontent.com/u/1?v=4',
      },
      html_url: `https://github.com/${GITHUB_REPO}/issues/1`,
    },
    {
      number: 2,
      title: 'Bug: Authentication fails with special characters in password',
      body: 'When using special characters like @, #, $ in the password, authentication fails with a 500 error.\n\nSteps to reproduce:\n1. Create account with password containing @\n2. Try to login\n3. See error',
      labels: ['bug', 'critical'],
      state: 'open',
      created_at: new Date(Date.now() - 86400000).toISOString(),
      user: {
        login: 'bug-reporter',
        avatar_url: 'https://avatars.githubusercontent.com/u/2?v=4',
      },
      html_url: `https://github.com/${GITHUB_REPO}/issues/2`,
    },
    {
      number: 3,
      title: 'Question: How to configure logging levels?',
      body: 'I cannot figure out how to set different logging levels for different modules. The documentation seems incomplete.',
      labels: ['question', 'documentation'],
      state: 'open',
      created_at: new Date(Date.now() - 172800000).toISOString(),
      user: {
        login: 'new-user',
        avatar_url: 'https://avatars.githubusercontent.com/u/3?v=4',
      },
      html_url: `https://github.com/${GITHUB_REPO}/issues/3`,
    },
  ];
}
