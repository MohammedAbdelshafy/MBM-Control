export { calculateLeadScore, gradeFromScore, calculateSignalConfidence } from './calculator';
export { DEFAULT_WEIGHTS } from './weights';
export {
  detectAbsentee,
  detectVacancy,
  detectViolationSeverity,
  detectTaxDelinquency,
  detectEquityProxy,
  detectRecordFreshness,
  detectCommercialOpportunity,
  detectDataCompleteness,
} from './signals';
export type { LeadGrade, ScoringSignals, ScoringWeights, ScoredLead } from './types';
