/**
 * Business Opportunity Analyzer — Multi-Vertical AI Sales Engine
 *
 * Turns a vertical + real evidence into a complete, explainable
 * opportunity: the 20-point business profile, a recommended offer,
 * deal size, outreach angle, and the WHO/WHY/WHAT/WHY-NOW narrative.
 *
 * Nothing is invented — every narrative field is derived from evidence
 * and the vertical's configuration.
 */

import type {
  BusinessEvidence,
  CompanySizeIndicators,
  DealSizeRange,
  DecisionMakerEvidence,
  OpportunityOutput,
  TopCallRecord,
  VerticalDefinition,
  VerticalScoreResult,
} from './types';
import { detectSignal } from './scoring';

function defaultIndicators(evidence: BusinessEvidence): CompanySizeIndicators {
  return {
    employees: evidence.companySizeIndicators?.employees ?? null,
    locations: evidence.companySizeIndicators?.locations ?? null,
    technicians: evidence.companySizeIndicators?.technicians ?? null,
    instructors: evidence.companySizeIndicators?.instructors ?? null,
    reviewCount:
      evidence.companySizeIndicators?.reviewCount ??
      evidence.reviewActivity?.reviewCount ??
      null,
  };
}

function defaultDecisionMaker(evidence: BusinessEvidence): DecisionMakerEvidence {
  return {
    name: evidence.decisionMaker?.name ?? null,
    title: evidence.decisionMaker?.title ?? null,
    source: evidence.decisionMaker?.source ?? null,
  };
}

export function pickRecommendedOffer(
  vertical: VerticalDefinition,
  evidence: BusinessEvidence,
): string {
  const aiMatched = vertical.aiOpportunitySignals.filter((s) => detectSignal(s, evidence));
  const autoMatched = vertical.automationOpportunitySignals.filter((s) => detectSignal(s, evidence));
  const appMatched = vertical.appSoftwareOpportunitySignals.filter((s) => detectSignal(s, evidence));
  const webMatched = vertical.websiteOpportunitySignals.filter((s) => detectSignal(s, evidence));

  const offers = vertical.recommendedOffers;
  const noWebsite = !evidence.website;
  const bookingGap = evidence.digitalMaturity?.hasOnlineBooking === false;

  // Deterministic, signal-driven selection across the offer catalog.
  if (aiMatched.length >= 2 && offers.includes('AI voice receptionist')) return 'AI voice receptionist';
  if (aiMatched.length >= 2 && offers.includes('AI front-desk')) return 'AI front-desk';
  if (bookingGap && offers.includes('appointment automation')) return 'appointment automation';
  if (aiMatched.length >= 1 && offers.includes('AI sales agent')) return 'AI sales agent';
  if (aiMatched.length >= 1 && offers.includes('missed-call recovery')) return 'missed-call recovery';
  if (noWebsite && offers.includes('custom website')) return 'custom website';
  if (bookingGap && offers.includes('booking app')) return 'booking app';
  if (appMatched.length >= 1 && offers.includes('client portal')) return 'client portal';
  if (appMatched.length >= 1 && offers.includes('ConTech software')) return 'ConTech software';
  if (webMatched.length >= 1 && offers.includes('custom website')) return 'custom website';
  if (autoMatched.length >= 1 && offers.includes('workflow automation')) return 'workflow automation';
  return offers[0];
}

export function formatDealSize(size: DealSizeRange): string {
  const fmt = (n: number) => `$${n.toLocaleString('en-US')}`;
  return `${fmt(size.min)}–${fmt(size.max)} ${size.currency} · ${size.unit}`;
}

export interface OpportunityInput {
  vertical: VerticalDefinition;
  evidence: BusinessEvidence;
  score: VerticalScoreResult;
}

export function analyzeOpportunity({
  vertical,
  evidence,
  score,
}: OpportunityInput): TopCallRecord {
  const indicators = defaultIndicators(evidence);
  const dm = defaultDecisionMaker(evidence);
  const recommendedOffer = pickRecommendedOffer(vertical, evidence);
  const dealSize = vertical.estimatedDealSize;

  const aiOpportunitySignals = vertical.aiOpportunitySignals
    .filter((s) => detectSignal(s, evidence))
    .map((s) => s.label);
  const automationOpportunitySignals = vertical.automationOpportunitySignals
    .filter((s) => detectSignal(s, evidence))
    .map((s) => s.label);
  const appSoftwareOpportunitySignals = vertical.appSoftwareOpportunitySignals
    .filter((s) => detectSignal(s, evidence))
    .map((s) => s.label);

  const gapParts: string[] = [];
  const wq = evidence.websiteQuality;
  if (evidence.website === null || wq?.hasWebsite === false) gapParts.push('no website');
  else if (wq?.outdated || wq?.templateSite) gapParts.push('outdated website');
  if (evidence.digitalMaturity?.hasOnlineBooking === false) gapParts.push('no online booking');
  if (evidence.digitalMaturity?.leadCaptureForm === false) gapParts.push('no lead capture');
  const digitalGap = gapParts.length > 0 ? gapParts.join(', ') : 'site present';

  const scaleParts: string[] = [];
  if (indicators.employees) scaleParts.push(`${indicators.employees} employees`);
  if (indicators.locations) scaleParts.push(`${indicators.locations} locations`);
  if (indicators.technicians) scaleParts.push(`${indicators.technicians} technicians`);
  if (indicators.instructors) scaleParts.push(`${indicators.instructors} instructors`);
  if (indicators.reviewCount) scaleParts.push(`${indicators.reviewCount} reviews`);
  const scale = scaleParts.length > 0 ? scaleParts.join(', ') : 'size not evidenced';

  const topPain = score.dimensionScores.pain;
  const topBuying = score.dimensionScores.buyingSignal;
  const topDigital = score.dimensionScores.digitalGap;
  const topAutomation = score.dimensionScores.automationPotential;

  const who =
    dm.name
      ? `${evidence.company} — ${dm.name} (${dm.title ?? 'decision maker'})`
      : evidence.company;

  const whyThem =
    `Category: ${vertical.name}. ${topPain.reason}. ${topBuying.reason}. Scale: ${scale}.`;
  const whatProblem = `${digitalGap}; ${topAutomation.reason}`;
  const whatWeSell =
    `Recommended: ${recommendedOffer}. Fits: ${aiOpportunitySignals.length > 0 ? `AI opportunity (${aiOpportunitySignals[0]}…)` : 'no AI signal evidenced'}, ` +
    `${automationOpportunitySignals.length > 0 ? 'automation opportunity' : 'no automation evidenced'}.`;
  const whyNow =
    `Digital gap "${digitalGap}" plus ${topPain.reason.toLowerCase()}; ` +
    `${score.reasonTrace[7]}`;

  const bestOutreachAngle =
    `Lead with the "${digitalGap}" gap: "${vertical.outreachAngle}" ` +
    `Deal ceiling ${formatDealSize(dealSize)}.`;

  return {
    verticalId: vertical.id,
    verticalName: vertical.name,
    category: vertical.category,
    company: evidence.company,
    website: evidence.website ?? null,
    location: {
      city: evidence.location?.city ?? null,
      state: evidence.location?.state ?? null,
      country: evidence.location?.country ?? null,
    },
    industry: evidence.industry ?? null,
    companySizeIndicators: indicators,
    decisionMaker: dm,
    contact: evidence.contact ?? { phone: null, email: null, source: null },
    websiteQuality: wq ?? {},
    digitalMaturity: evidence.digitalMaturity ?? {},
    bookingWorkflow: evidence.bookingWorkflow ?? {},
    reviewActivity: evidence.reviewActivity ?? {},
    aiOpportunitySignals,
    automationOpportunitySignals,
    appSoftwareOpportunitySignals,
    leadGenOpportunity:
      aiOpportunitySignals.length > 0 || automationOpportunitySignals.length > 0
        ? `New lead generation + follow-up automation unlocked by ${recommendedOffer}`
        : 'Lead-gen potential not evidenced yet',
    recommendedOffer,
    estimatedDealSize: dealSize,
    leadScore: score.leadScore,
    contactabilityScore: score.contactabilityScore,
    buyingProbability: score.buyingProbabilityScore,
    outreachAngle: bestOutreachAngle,
    reasonTrace: score.reasonTrace,
    provenance: {
      source: evidence.source,
      sourceUrl: evidence.sourceUrl ?? null,
      retrievedAt: evidence.retrievedAt,
    },
    who,
    whyThem,
    whatProblem,
    whatWeSell,
    whyNow,
    estimatedValue: formatDealSize(dealSize),
    bestOutreachAngle,
  };
}