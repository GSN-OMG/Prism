import { NextRequest, NextResponse } from 'next/server';
import {
  GitHubIssue,
  AgentType,
  AgentResult,
  IssueAnalysisOutput,
  AssignmentOutput,
  ResponseOutput,
  DocGapOutput,
  PromotionOutput,
  DecisionStep,
} from '@/types';
import { getContributors, getAllContributorsWithEvaluations } from '@/lib/data';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { issue, agent } = body as { issue: GitHubIssue; agent: AgentType };

    // Simulate processing time
    await new Promise((resolve) => setTimeout(resolve, 1000 + Math.random() * 2000));

    const startTime = new Date().toISOString();
    const result = await runAgent(agent, issue);
    const endTime = new Date().toISOString();

    const agentResult: AgentResult = {
      agent,
      status: 'completed',
      startTime,
      endTime,
      durationMs: new Date(endTime).getTime() - new Date(startTime).getTime(),
      output: result.output,
      decisionTrace: result.decisionTrace,
    };

    return NextResponse.json(agentResult);
  } catch (error) {
    console.error('Agent execution failed:', error);
    return NextResponse.json(
      { error: 'Agent execution failed' },
      { status: 500 }
    );
  }
}

async function runAgent(
  agent: AgentType,
  issue: GitHubIssue
): Promise<{ output: AgentResult['output']; decisionTrace: DecisionStep[] }> {
  switch (agent) {
    case 'issue_analysis':
      return runIssueAnalysis(issue);
    case 'assignment':
      return runAssignment(issue);
    case 'response':
      return runResponse(issue);
    case 'docs_gap':
      return runDocsGap(issue);
    case 'promotion':
      return runPromotion(issue);
    default:
      throw new Error(`Unknown agent type: ${agent}`);
  }
}

function runIssueAnalysis(issue: GitHubIssue): { output: IssueAnalysisOutput; decisionTrace: DecisionStep[] } {
  const titleLower = issue.title.toLowerCase();
  const bodyLower = issue.body.toLowerCase();
  const labels = issue.labels.map((l) => l.toLowerCase());

  // Determine issue type
  let issueType: IssueAnalysisOutput['issue_type'] = 'other';
  if (labels.includes('bug') || titleLower.includes('bug') || titleLower.includes('error') || titleLower.includes('fail')) {
    issueType = 'bug';
  } else if (labels.includes('feature') || titleLower.includes('feature') || titleLower.includes('add ')) {
    issueType = 'feature';
  } else if (labels.includes('question') || titleLower.includes('?') || titleLower.includes('how')) {
    issueType = 'question';
  } else if (labels.includes('documentation') || titleLower.includes('doc')) {
    issueType = 'documentation';
  }

  // Determine priority
  let priority: IssueAnalysisOutput['priority'] = 'medium';
  if (labels.includes('critical') || bodyLower.includes('critical') || bodyLower.includes('security')) {
    priority = 'critical';
  } else if (labels.includes('high') || bodyLower.includes('crash') || bodyLower.includes('urgent')) {
    priority = 'high';
  } else if (labels.includes('low') || issueType === 'question') {
    priority = 'low';
  }

  // Extract keywords
  const keywords: string[] = [];
  const keywordPatterns = ['redis', 'cache', 'auth', 'logging', 'debug', 'api', 'oauth', 'timeout', 'performance'];
  for (const pattern of keywordPatterns) {
    if (titleLower.includes(pattern) || bodyLower.includes(pattern)) {
      keywords.push(pattern);
    }
  }

  // Determine required skills
  const requiredSkills: string[] = [];
  if (issueType === 'documentation') requiredSkills.push('docs');
  if (issueType === 'bug') requiredSkills.push('debugging');
  if (keywords.includes('redis') || keywords.includes('cache')) requiredSkills.push('cache');
  if (keywords.includes('auth') || keywords.includes('oauth')) requiredSkills.push('auth');
  if (keywords.includes('api')) requiredSkills.push('api');

  const needsMoreInfo = !issue.body.trim();
  const suggestedAction: IssueAnalysisOutput['suggested_action'] = needsMoreInfo
    ? 'request_info'
    : issueType === 'question'
    ? 'link_docs'
    : 'direct_answer';

  const output: IssueAnalysisOutput = {
    issue_type: issueType,
    priority,
    required_skills: requiredSkills,
    keywords,
    summary: issue.title,
    needs_more_info: needsMoreInfo,
    suggested_action: suggestedAction,
  };

  const decisionTrace: DecisionStep[] = [
    {
      step_number: 1,
      step_name: 'Parse Issue Content',
      input: { title: issue.title, labels: issue.labels },
      output: { parsed: true },
      reasoning: `Extracted title, body, and labels from issue #${issue.number}`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 2,
      step_name: 'Classify Issue Type',
      input: { titleLower, labels },
      output: { issueType },
      reasoning: `Based on labels [${labels.join(', ')}] and title keywords, classified as "${issueType}"`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 3,
      step_name: 'Determine Priority',
      input: { labels, bodyKeywords: keywords },
      output: { priority },
      reasoning: `Analyzed severity indicators. Priority set to "${priority}" based on content analysis`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 4,
      step_name: 'Extract Keywords & Skills',
      input: { body: issue.body.substring(0, 100) },
      output: { keywords, requiredSkills },
      reasoning: `Identified ${keywords.length} keywords and ${requiredSkills.length} required skills`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 5,
      step_name: 'Recommend Action',
      input: { issueType, needsMoreInfo },
      output: { suggestedAction },
      reasoning: `Recommended "${suggestedAction}" based on issue type and information completeness`,
      timestamp: new Date().toISOString(),
    },
  ];

  return { output, decisionTrace };
}

function runAssignment(issue: GitHubIssue): { output: AssignmentOutput; decisionTrace: DecisionStep[] } {
  const contributors = getContributors();

  // Score contributors
  const scores = contributors.map((c) => {
    let score = c.recent_activity_score;
    score += Math.min(c.merged_prs, 10) * 0.1;
    score += Math.min(c.reviews, 20) * 0.05;

    // Bonus for relevant areas
    const titleLower = issue.title.toLowerCase();
    for (const area of c.areas) {
      if (titleLower.includes(area.toLowerCase())) {
        score += 2;
      }
    }

    return { contributor: c, score };
  });

  scores.sort((a, b) => b.score - a.score);

  const top = scores[0];
  const second = scores[1];

  const confidence = top.score > 0
    ? Math.min(1, 0.5 + (top.score - (second?.score || 0)) / Math.max(top.score, 1))
    : 0.5;

  const output: AssignmentOutput = {
    recommended_assignee: top.contributor.login,
    confidence,
    reasons: [
      {
        factor: 'recent_activity',
        explanation: `Activity score: ${top.contributor.recent_activity_score.toFixed(2)}`,
        score: Math.min(1, top.contributor.recent_activity_score / 5),
      },
      {
        factor: 'merged_prs',
        explanation: `${top.contributor.merged_prs} merged PRs`,
        score: Math.min(1, top.contributor.merged_prs / 20),
      },
      {
        factor: 'code_reviews',
        explanation: `${top.contributor.reviews} code reviews`,
        score: Math.min(1, top.contributor.reviews / 40),
      },
    ],
    context_for_assignee: `Issue Type: ${issue.labels.join(', ') || 'general'}\nTitle: ${issue.title}`,
    alternative_assignees: scores.slice(1, 4).map((s) => s.contributor.login),
  };

  const decisionTrace: DecisionStep[] = [
    {
      step_number: 1,
      step_name: 'Load Contributors',
      input: {},
      output: { count: contributors.length },
      reasoning: `Loaded ${contributors.length} active contributors from raw_data`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 2,
      step_name: 'Score Contributors',
      input: { issueTitle: issue.title },
      output: { topScores: scores.slice(0, 3).map((s) => ({ login: s.contributor.login, score: s.score.toFixed(2) })) },
      reasoning: `Calculated scores based on activity, PRs, reviews, and area match`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 3,
      step_name: 'Select Best Match',
      input: { topCandidate: top.contributor.login, topScore: top.score.toFixed(2) },
      output: { recommended: top.contributor.login, confidence: confidence.toFixed(2) },
      reasoning: `Selected @${top.contributor.login} with confidence ${(confidence * 100).toFixed(0)}%`,
      timestamp: new Date().toISOString(),
    },
  ];

  return { output, decisionTrace };
}

function runResponse(issue: GitHubIssue): { output: ResponseOutput; decisionTrace: DecisionStep[] } {
  const titleLower = issue.title.toLowerCase();
  const labels = issue.labels.map((l) => l.toLowerCase());

  let strategy: ResponseOutput['strategy'] = 'direct_answer';
  let responseText = '';
  const references: string[] = [];

  if (!issue.body.trim()) {
    strategy = 'request_info';
    responseText = `Thank you for opening this issue. Could you please provide more details about:\n\n1. Steps to reproduce (if applicable)\n2. Expected behavior\n3. Actual behavior\n4. Environment details (OS, version, etc.)\n\nThis will help us better understand and address your concern.`;
  } else if (labels.includes('question') || titleLower.includes('how')) {
    strategy = 'link_docs';
    responseText = `Thank you for your question! Here are some resources that might help:\n\n- Check our documentation at docs/\n- See the FAQ section\n- Review related issues in this repository\n\nIf you still need assistance after reviewing these resources, please let us know!`;
    references.push('docs/README.md', 'docs/FAQ.md');
  } else if (labels.includes('bug') || labels.includes('critical')) {
    strategy = 'direct_answer';
    responseText = `Thank you for reporting this issue. We've analyzed the problem and here's what we found:\n\n**Analysis:**\n- Issue Type: Bug Report\n- Severity: ${labels.includes('critical') ? 'Critical' : 'Normal'}\n\n**Next Steps:**\n1. We're investigating the root cause\n2. A fix is being worked on\n3. We'll update this issue with progress\n\nExpected resolution in the next sprint.`;
  } else {
    responseText = `Thank you for your submission. We've received your request and will review it shortly.\n\n**Summary:** ${issue.title}\n\nOur team will follow up with more details.`;
  }

  const output: ResponseOutput = {
    strategy,
    response_text: responseText,
    confidence: 0.85,
    references,
    follow_up_needed: strategy === 'request_info',
  };

  const decisionTrace: DecisionStep[] = [
    {
      step_number: 1,
      step_name: 'Analyze Issue Context',
      input: { labels: issue.labels, hasBody: !!issue.body.trim() },
      output: { needsInfo: !issue.body.trim() },
      reasoning: `Analyzed issue content and labels to determine response strategy`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 2,
      step_name: 'Select Response Strategy',
      input: { labels },
      output: { strategy },
      reasoning: `Selected "${strategy}" strategy based on issue type and content`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 3,
      step_name: 'Generate Response',
      input: { strategy },
      output: { responseLength: responseText.length },
      reasoning: `Generated ${responseText.split('\n').length} line response with ${references.length} references`,
      timestamp: new Date().toISOString(),
    },
  ];

  return { output, decisionTrace };
}

function runDocsGap(issue: GitHubIssue): { output: DocGapOutput; decisionTrace: DecisionStep[] } {
  const titleLower = issue.title.toLowerCase();
  const bodyLower = issue.body.toLowerCase();
  const labels = issue.labels.map((l) => l.toLowerCase());

  let hasGap = false;
  let gapTopic = '';
  let suggestedDocPath = '';
  let suggestedOutline: string[] = [];
  let priority: DocGapOutput['priority'] = 'medium';

  // Check for common documentation gap indicators
  if (titleLower.includes('redis') || bodyLower.includes('redis')) {
    hasGap = true;
    gapTopic = 'Redis Caching';
    suggestedDocPath = 'docs/cache/redis.md';
    suggestedOutline = ['Overview', 'Installation', 'Configuration', 'Common Errors', 'Example Config'];
    priority = 'high';
  } else if (titleLower.includes('logging') || bodyLower.includes('logging') || titleLower.includes('debug')) {
    hasGap = true;
    gapTopic = 'Logging & Debugging';
    suggestedDocPath = 'docs/debugging/logging.md';
    suggestedOutline = ['Enable Debug Logging', 'Log Locations', 'Log Levels', 'Troubleshooting'];
    priority = 'medium';
  } else if (labels.includes('documentation') || labels.includes('question')) {
    hasGap = true;
    gapTopic = 'General Documentation';
    suggestedDocPath = 'docs/guides/getting-started.md';
    suggestedOutline = ['Quick Start', 'Configuration', 'Common Use Cases', 'FAQ'];
    priority = 'low';
  } else if (titleLower.includes('auth') || bodyLower.includes('authentication')) {
    hasGap = true;
    gapTopic = 'Authentication';
    suggestedDocPath = 'docs/auth/authentication.md';
    suggestedOutline = ['Overview', 'OAuth Setup', 'Token Management', 'Security Best Practices'];
    priority = 'high';
  }

  const output: DocGapOutput = {
    has_gap: hasGap,
    gap_topic: gapTopic,
    affected_issues: hasGap ? [issue.number] : [],
    suggested_doc_path: suggestedDocPath,
    suggested_outline: suggestedOutline,
    priority,
  };

  const decisionTrace: DecisionStep[] = [
    {
      step_number: 1,
      step_name: 'Scan Issue Content',
      input: { title: issue.title, labels: issue.labels },
      output: { keywords: [gapTopic || 'none'] },
      reasoning: `Scanned issue for documentation-related keywords and patterns`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 2,
      step_name: 'Detect Documentation Gap',
      input: { hasLabels: labels.length > 0 },
      output: { hasGap, gapTopic },
      reasoning: hasGap
        ? `Detected documentation gap for "${gapTopic}"`
        : 'No documentation gap detected for this issue',
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 3,
      step_name: 'Generate Recommendations',
      input: { gapTopic },
      output: { suggestedDocPath, outlineItems: suggestedOutline.length },
      reasoning: hasGap
        ? `Suggested creating ${suggestedDocPath} with ${suggestedOutline.length} sections`
        : 'No recommendations needed',
      timestamp: new Date().toISOString(),
    },
  ];

  return { output, decisionTrace };
}

function runPromotion(_issue: GitHubIssue): { output: PromotionOutput; decisionTrace: DecisionStep[] } {
  // Get promotion evaluations from existing logic
  const evaluations = getAllContributorsWithEvaluations();

  // Find a promotion candidate for demo
  const candidate = evaluations.find((e) => e.evaluation.is_candidate);
  const evaluation = candidate ? candidate.evaluation : evaluations[0]?.evaluation;

  if (!evaluation) {
    const output: PromotionOutput = {
      is_candidate: false,
      current_stage: 'REGULAR',
      suggested_stage: 'REGULAR',
      confidence: 0.5,
      evidence: [],
      recommendation: 'No contributors available for evaluation',
    };

    return {
      output,
      decisionTrace: [
        {
          step_number: 1,
          step_name: 'Load Contributors',
          input: {},
          output: { count: 0 },
          reasoning: 'No contributors found in the dataset',
          timestamp: new Date().toISOString(),
        },
      ],
    };
  }

  const decisionTrace: DecisionStep[] = [
    {
      step_number: 1,
      step_name: 'Load Contributor Data',
      input: {},
      output: { totalContributors: evaluations.length },
      reasoning: `Loaded ${evaluations.length} contributors from raw_data`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 2,
      step_name: 'Evaluate Current Stage',
      input: {},
      output: { currentStage: evaluation.current_stage },
      reasoning: `Determined current stage based on merged PRs and contribution history`,
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 3,
      step_name: 'Check Promotion Criteria',
      input: { evidenceCount: evaluation.evidence.length },
      output: { isCandidate: evaluation.is_candidate },
      reasoning: evaluation.is_candidate
        ? `Met promotion criteria: ${evaluation.evidence.filter((e) => e.status === 'met' || e.status === 'exceeds').length} criteria satisfied`
        : 'Promotion criteria not fully met',
      timestamp: new Date().toISOString(),
    },
    {
      step_number: 4,
      step_name: 'Generate Recommendation',
      input: { isCandidate: evaluation.is_candidate },
      output: { suggestedStage: evaluation.suggested_stage },
      reasoning: evaluation.recommendation,
      timestamp: new Date().toISOString(),
    },
  ];

  return { output: evaluation, decisionTrace };
}
