import type { ScoringWeights } from './types';

export const DEFAULT_WEIGHTS: ScoringWeights = {
  ownershipConfidence: 0.20,
  recordFreshness: 0.10,
  absenteeSignal: 0.15,
  vacancyIndicators: 0.12,
  violationSeverity: 0.10,
  taxDelinquency: 0.10,
  equityProxy: 0.08,
  commercialOpportunity: 0.05,
  dataCompleteness: 0.05,
  duplicatePenalty: 0.05,
};

export type { ScoringWeights };
