import { NextResponse } from 'next/server';
import { getAllContributorsWithEvaluations } from '@/lib/data';

export async function GET() {
  const evaluations = getAllContributorsWithEvaluations();
  return NextResponse.json(evaluations);
}
