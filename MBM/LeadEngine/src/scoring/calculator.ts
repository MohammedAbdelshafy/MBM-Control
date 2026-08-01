import type { LeadGrade, ScoredLead, ScoringSignals, ScoringWeights } from './types';
import { DEFAULT_WEIGHTS } from './weights';

const LEAD_GRADE_CUTOFFS: { max: number; grade: LeadGrade }[] = [
  { max: 100, grade: 'A+' },
  { max: 89, grade: 'A' },
  { max: 74, grade: 'B' },
  { max: 49, grade: 'C' },
  { max: 24, grade: 'Reject' },
];

export function gradeFromScore(score: number): LeadGrade {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  for (const cutoff of LEAD_GRADE_CUTOFFS) {
    if (clamped <= cutoff.max) return cutoff.grade;
  }
  return 'Reject';
}

export function calculateSignalConfidence(signals: ScoringSignals): number {
  const nonPenaltyKeys: (keyof ScoringSignals)[] = [
    'ownershipConfidence',
    'recordFreshness',
    'absenteeSignal',
    'vacancyIndicators',
    'violationSeverity',
    'taxDelinquency',
    'equityProxy',
    'commercialOpportunity',
    'dataCompleteness',
  ];

  let sum = 0;
  for (const key of nonPenaltyKeys) {
    sum += signals[key];
  }
  return sum / nonPenaltyKeys.length;
}

export function calculateLeadScore(
  leadId: string,
  signals: ScoringSignals,
  weights?: Partial<ScoringWeights>,
): ScoredLead {
  const mergedWeights: ScoringWeights = { ...DEFAULT_WEIGHTS, ...weights };

  const breakdown: Record<string, number> = {};
  let weightedSum = 0;

  const additiveKeys: (keyof ScoringSignals)[] = [
    'ownershipConfidence',
    'recordFreshness',
    'absenteeSignal',
    'vacancyIndicators',
    'violationSeverity',
    'taxDelinquency',
    'equityProxy',
    'commercialOpportunity',
    'dataCompleteness',
  ];

  for (const key of additiveKeys) {
    const contribution = signals[key] * mergedWeights[key];
    breakdown[key] = Math.round(contribution * 1000) / 1000;
    weightedSum += contribution;
  }

  const penalty = signals.duplicatePenalty * mergedWeights.duplicatePenalty;
  breakdown.duplicatePenalty = -(Math.round(penalty * 1000) / 1000);
  weightedSum -= penalty;

  const overallScore = Math.round(weightedSum * 100);
  const grade = gradeFromScore(overallScore);

  return {
    leadId,
    signals,
    weights: mergedWeights,
    overallScore,
    grade,
    breakdown,
    calculatedAt: new Date(),
  };
}
