/**
 * Multi-Vertical AI Sales Engine — Shared Contracts
 * JARVIS MBM — Vertical Marketplace
 *
 * Every vertical is defined by configuration (not code). New categories
 * can be added by registering a `VerticalDefinition`; the scoring engine
 * and opportunity analyzer adapt automatically.
 *
 * NO business facts or contact information are ever synthesized here —
 * all evidence flows in via `BusinessEvidence` with preserved provenance.
 */

export type VerticalCategoryId =
  | 'HOME_SERVICES'
  | 'HEALTH_WELLNESS'
  | 'PROFESSIONAL_SERVICES'
  | 'LOCAL_SERVICES'
  | 'B2B_INDUSTRIAL';

export const SCORE_DIMENSIONS = [
  'pain',
  'buyingSignal',
  'companySize',
  'digitalGap',
  'automationPotential',
  'revenuePotential',
  'contactability',
  'recency',
] as const;

export type ScoreDimension = (typeof SCORE_DIMENSIONS)[number];

export type ScoreWeights = Record<ScoreDimension, number>;

export interface SignalDef {
  id: string;
  label: string;
  /** Weight of this signal within its dimension, 0..1. */
  weight: number;
}

export interface DealSizeRange {
  min: number;
  max: number;
  currency: string;
  /** e.g. "monthly retainer", "one-time project" */
  unit: string;
}

export interface VerticalDefinition {
  /** Stable slug, e.g. "hvac". */
  id: string;
  name: string;
  category: VerticalCategoryId;
  /** Ideal customer profile — who we hunt in this vertical. */
  icp: string;
  decisionMakerProfile: string;
  painSignals: SignalDef[];
  buyingSignals: SignalDef[];
  aiOpportunitySignals: SignalDef[];
  websiteOpportunitySignals: SignalDef[];
  automationOpportunitySignals: SignalDef[];
  appSoftwareOpportunitySignals: SignalDef[];
  /** Recommended MBM offers for this vertical. */
  recommendedOffers: string[];
  estimatedDealSize: DealSizeRange;
  /** Primary outreach angle template. */
  outreachAngle: string;
  /** Optional per-vertical weight overrides (defaults applied otherwise). */
  weightOverrides?: Partial<ScoreWeights>;
}

export interface CompanySizeIndicators {
  employees?: number | null;
  locations?: number | null;
  technicians?: number | null;
  instructors?: number | null;
  reviewCount?: number | null;
}

export interface WebsiteQuality {
  /** True = confirmed present; false = confirmed absent; undefined = unknown. */
  hasWebsite?: boolean;
  outdated?: boolean;
  templateSite?: boolean;
  mobileResponsive?: boolean;
}

export interface DigitalMaturity {
  hasOnlineBooking?: boolean;
  leadCaptureForm?: boolean;
  liveChat?: boolean;
  crmInUse?: boolean;
}

export interface BookingWorkflow {
  manualOnly?: boolean;
  responseTimeHours?: number;
}

export interface ReviewActivity {
  reviewCount?: number | null;
  rating?: number | null;
  recencyDays?: number | null;
}

export interface DecisionMakerEvidence {
  name?: string | null;
  title?: string | null;
  source?: string | null;
}

export interface ContactEvidence {
  phone?: string | null;
  email?: string | null;
  source?: string | null;
}

/**
 * Raw, provenance-preserved evidence for a single business. Every field
 * maps to something actually observed from an authorized source.
 */
export interface BusinessEvidence {
  company: string;
  website?: string | null;
  location?: { city?: string; state?: string; country?: string } | null;
  industry?: string | null;
  companySizeIndicators?: CompanySizeIndicators;
  decisionMaker?: DecisionMakerEvidence;
  contact?: ContactEvidence;
  websiteQuality?: WebsiteQuality;
  digitalMaturity?: DigitalMaturity;
  bookingWorkflow?: BookingWorkflow;
  reviewActivity?: ReviewActivity;
  aiOpportunitySignals?: string[];
  automationOpportunitySignals?: string[];
  appSoftwareOpportunitySignals?: string[];
  /** Authorized source that produced this evidence. */
  source: string;
  sourceUrl?: string | null;
  retrievedAt: string;
  raw?: Record<string, unknown> | null;
  /** Free-form source-specific metadata (NPI, addresses, limitations). */
  extra?: Record<string, unknown> | null;
}

export interface DimensionScore {
  dimension: ScoreDimension;
  score: number;
  reason: string;
}

export interface VerticalScoreResult {
  dimensionScores: Record<ScoreDimension, DimensionScore>;
  /** Weighted buying-probability score, 0..100. */
  buyingProbabilityScore: number;
  /** Opportunity lead score, 0..100. */
  leadScore: number;
  /** Contactability score, 0..100. */
  contactabilityScore: number;
  reasonTrace: string[];
}

export interface OpportunityOutput {
  verticalId: string;
  verticalName: string;
  category: VerticalCategoryId;
  company: string;
  website: string | null;
  location: { city: string | null; state: string | null; country: string | null };
  industry: string | null;
  companySizeIndicators: CompanySizeIndicators;
  decisionMaker: DecisionMakerEvidence;
  contact: ContactEvidence;
  websiteQuality: WebsiteQuality;
  digitalMaturity: DigitalMaturity;
  bookingWorkflow: BookingWorkflow;
  reviewActivity: ReviewActivity;
  aiOpportunitySignals: string[];
  automationOpportunitySignals: string[];
  appSoftwareOpportunitySignals: string[];
  leadGenOpportunity: string;
  recommendedOffer: string;
  estimatedDealSize: DealSizeRange;
  leadScore: number;
  contactabilityScore: number;
  buyingProbability: number;
  outreachAngle: string;
  reasonTrace: string[];
  provenance: {
    source: string;
    sourceUrl: string | null;
    retrievedAt: string;
  };
}

/** The call-ready record — every field is explained, nothing fabricated. */
export interface TopCallRecord extends OpportunityOutput {
  who: string;
  whyThem: string;
  whatProblem: string;
  whatWeSell: string;
  whyNow: string;
  estimatedValue: string;
  bestOutreachAngle: string;
}