export type LeadGrade = 'A+' | 'A' | 'B' | 'C' | 'Reject';

export interface ScoringSignals {
  ownershipConfidence: number;    // 0-1
  recordFreshness: number;       // 0-1
  absenteeSignal: number;        // 0-1
  vacancyIndicators: number;     // 0-1
  violationSeverity: number;     // 0-1
  taxDelinquency: number;        // 0-1
  equityProxy: number;           // 0-1
  commercialOpportunity: number; // 0-1
  dataCompleteness: number;      // 0-1
  duplicatePenalty: number;      // 0-1 (negative signal)
}

export interface ScoringWeights {
  ownershipConfidence: number;
  recordFreshness: number;
  absenteeSignal: number;
  vacancyIndicators: number;
  violationSeverity: number;
  taxDelinquency: number;
  equityProxy: number;
  commercialOpportunity: number;
  dataCompleteness: number;
  duplicatePenalty: number;
}

export interface ScoredLead {
  leadId: string;
  signals: ScoringSignals;
  weights: ScoringWeights;
  overallScore: number;     // 0-100
  grade: LeadGrade;
  breakdown: Record<string, number>;
  calculatedAt: Date;
}
