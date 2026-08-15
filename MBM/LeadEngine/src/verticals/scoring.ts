/**
 * Vertical Scoring Engine — Multi-Vertical AI Sales Engine
 *
 * Ranks businesses by BUYING PROBABILITY, not industry. Each vertical's
 * signal definitions are matched against real evidence and scored across
 * eight weighted dimensions:
 *
 *   Pain + Buying Signal + Company Size + Digital Gap +
 *   Automation Potential + Revenue Potential + Contactability + Recency
 *
 * Every score carries a reason trace so no number is unexplained.
 */

import type {
  BusinessEvidence,
  DimensionScore,
  ScoreDimension,
  SignalDef,
  VerticalDefinition,
  VerticalScoreResult,
} from './types';
import { SCORE_DIMENSIONS } from './types';
import { scoreDimensionLabel } from './registry';
import type { ScoreWeights } from './types';

// ── Signal detection (deterministic, evidence-driven) ──────────────

function evidenceText(evidence: BusinessEvidence): string {
  const parts: string[] = [];
  for (const key of [
    'aiOpportunitySignals',
    'automationOpportunitySignals',
    'appSoftwareOpportunitySignals',
  ] as const) {
    const arr = evidence[key];
    if (Array.isArray(arr)) parts.push(...arr.map((x) => String(x).toLowerCase()));
  }
  return parts.join(' ').toLowerCase();
}

function signalTokens(signal: SignalDef): string {
  return `${signal.id} ${signal.label}`.toLowerCase();
}

function sizeIndicators(evidence: BusinessEvidence) {
  const s = evidence.companySizeIndicators ?? {};
  return {
    employees: s.employees ?? null,
    locations: s.locations ?? null,
    technicians: s.technicians ?? null,
    instructors: s.instructors ?? null,
    reviewCount: s.reviewCount ?? evidence.reviewActivity?.reviewCount ?? null,
  };
}

function noBooking(evidence: BusinessEvidence): boolean {
  const dm = evidence.digitalMaturity;
  if (dm && dm.hasOnlineBooking === false) return true;
  if (evidence.bookingWorkflow?.manualOnly === true) return true;
  const text = evidenceText(evidence);
  return /no online booking|manual booking|manual scheduling|manual only/i.test(text);
}

function hasOutdatedSite(evidence: BusinessEvidence): boolean {
  const wq = evidence.websiteQuality;
  if (wq && (wq.outdated === true || wq.templateSite === true)) return true;
  const text = evidenceText(evidence);
  return /outdated|template site|template|no website|wordpress/i.test(text);
}

function hasManualWorkflow(evidence: BusinessEvidence): boolean {
  const text = evidenceText(evidence);
  return /manual|paper|spreadsheet|phone tag|pen and paper|no crm|no automation/i.test(text);
}

/**
 * Deterministic signal presence check. New signals can be added by
 * registering a detector; existing verticals reuse detection for free.
 */
export function detectSignal(signal: SignalDef, evidence: BusinessEvidence): boolean {
  const id = signal.id;
  const text = evidenceText(evidence);
  const tokens = signalTokens(signal);
  const s = sizeIndicators(evidence);
  const dm = evidence.digitalMaturity ?? {};
  const wq = evidence.websiteQuality ?? {};

  // Company size / headcount signals
  if (/(employees|headcount|growing_labor)/.test(id)) return (s.employees ?? 0) >= 5;
  if (/(technicians|instructors|multiple_staff)/.test(id))
    return (s.technicians ?? s.instructors ?? 0) >= 3;
  if (/(locations|branches|multi_branch)/.test(id)) return (s.locations ?? 0) >= 2;
  if (/(review_volume|review_density|reviews)/.test(id)) return (s.reviewCount ?? 0) >= 50;
  if (/(client_volume|team_size)/.test(id)) return (s.employees ?? 0) >= 5;

  // Website & digital gap signals
  if (/(outdated_site|outdated)/.test(id)) return hasOutdatedSite(evidence) || wq.hasWebsite === false;
  if (/(no_mobile)/.test(id)) return wq.mobileResponsive === false || /no mobile/i.test(text);
  if (/(no_lead_form|no_lead_capture)/.test(id))
    return dm.leadCaptureForm === false || /no lead capture|no lead form/i.test(text);
  if (/(no_seo|no_local_seo)/.test(id)) return /no seo|weak seo/i.test(text);
  if (/(no_online_sched|no_online_booking|no_online_ordering|no_ordering|no_booking)/.test(id))
    return noBooking(evidence) || dm.hasOnlineBooking === false;
  if (/(no_catalog|no_pos_integration)/.test(id)) return dm.leadCaptureForm === false || /no catalog|no integration/i.test(text);
  if (/(weak_landing)/.test(id)) return /weak landing|low converting/i.test(text);

  // Booking / intake / operations signals
  if (/(manual_booking|manual_scheduling|manual_orders|manual_intake|manual_forms|manual_invoicing|manual_quoting|manual_rfq|manual_quoting|manual_scheduling_local)/.test(id))
    return noBooking(evidence) || /manual book|manual sched|manual order|manual intake|manual form|manual invoic|manual quote|manual rfq/i.test(text);
  if (/(staff_scheduling|manual_staff_sched)/.test(id))
    return /staff schedul|manual staff/i.test(text) || hasManualWorkflow(evidence);
  if (/(no_crm|no_erp|no_crm_pro|no_crm_hw|no_followup|no_lead_system|no_lead_pipeline)/.test(id))
    return dm.crmInUse === false || /no crm|no erp|spreadsheet|no follow|no pipeline|no lead system/i.test(text);
  if (/(manual_dispatch|dispatch|dispatch_automation)/.test(id))
    return /dispatch|manual tech|paper est/i.test(text) || noBooking(evidence);
  if (/(paper_workflow|paper_ops|paper_intake|admin_burden|admin_overhead)/.test(id))
    return hasManualWorkflow(evidence) || /admin|back-office|overhead|paper/i.test(text);
  if (/(reporting_manual|manual_reporting|manual_reminders)/.test(id))
    return /manual report|manual reminder/i.test(text) || hasManualWorkflow(evidence);
  if (/(doc_automation|document_app)/.test(id)) return /document|paper|form|intake|contract/i.test(text);
  if (/(intake_automation|ai_intake)/.test(id)) return /intake|triage|form/i.test(text);

  // Demand / revenue leakage signals
  if (/(emergency_demand|phone_demand|missed_calls|missed_revenue|after.hours)/.test(id))
    return /emergency|after.hours|missed|phone call|call volume/i.test(text);
  if (/(missed_calls|missed_revenue)/.test(id)) return /missed call|missed revenue/i.test(text);

  // Retention / membership signals
  if (/(no_show)/.test(id)) return /no.show/i.test(text);
  if (/(membership_churn|active_memberships|retention_signals|recurring_service|recent_activity|repeat_contracts|recurring)/.test(id))
    return /member|churn|retention|recurring|repeat|rebook/i.test(text);
  if (/(foot_traffic|premium_position)/.test(id)) return /foot traffic|walk.in|premium|prime location/i.test(text);
  if (/(recent_activity|recent_activity)/.test(id))
    return (evidence.reviewActivity?.recencyDays ?? 365) <= 60 || /recent activity|grow/i.test(text);

  // AI / automation opportunity signals
  if (/(ai_receptionist|ai_frontdesk|ai_reception_local|ai_support)/.test(id))
    return /reception|front.desk|missed|voice|24\/7/i.test(text) || noBooking(evidence);
  if (/(booking_automation|appointment_automation|followup_automation|followup_automation_hw|followup_local|lead_followup_pro)/.test(id))
    return noBooking(evidence) || /follow.up|followup|nurture|rebook/i.test(text);
  if (/(estimate_assist|quote_automation|order_assist)/.test(id))
    return /quote|estimate|order|rfq/i.test(text);
  if (/(review_reply_ai)/.test(id)) return /review/i.test(text) && (s.reviewCount ?? 0) > 0;
  if (/(ai_sales_agent|ai_ops|ai_admin|ai_internal|ai_support)/.test(id))
    return /admin|back.office|support|bdr|sales|overhead/i.test(text);
  if (/(no_show_reduction)/.test(id)) return /no.show/i.test(text);

  // App / software opportunity signals
  if (/(portal|booking_app|client_portal|b2b_portal|ordering_app|loyalty_app|member_app|client_app|wellness_app)/.test(id))
    return wq.hasWebsite === false || /no app|no portal|no online|manual/i.test(text);
  if (/(field_app|staff_app|ops_app|practice_tool|internal_tool|ops_dashboard|recruiter_tool|contech_tool)/.test(id))
    return hasManualWorkflow(evidence) || /manual|paper|spreadsheet/i.test(text);

  // Generic fallback: keyword overlap between signal and evidence text
  const keywords = tokens.split(/[^a-z0-9_]/).filter((k) => k.length > 3);
  return keywords.some((k) => text.includes(k));
}

function matchedSignals(
  signals: SignalDef[],
  evidence: BusinessEvidence,
): { matched: SignalDef[]; matchedWeight: number; totalWeight: number } {
  const matched: SignalDef[] = [];
  let matchedWeight = 0;
  let totalWeight = 0;
  for (const signal of signals) {
    totalWeight += signal.weight;
    if (detectSignal(signal, evidence)) {
      matched.push(signal);
      matchedWeight += signal.weight;
    }
  }
  return { matched, matchedWeight, totalWeight: totalWeight || 1 };
}

function fractionScore(matchedWeight: number, totalWeight: number, base = 0): number {
  return Math.round(Math.min(100, base + (matchedWeight / totalWeight) * (100 - base)));
}

// ── Dimension scoring ───────────────────────────────────────────────

function scorePain(vertical: VerticalDefinition, evidence: BusinessEvidence): DimensionScore {
  const { matched, matchedWeight, totalWeight } = matchedSignals(vertical.painSignals, evidence);
  const score = fractionScore(matchedWeight, totalWeight, 25);
  const reason =
    matched.length > 0
      ? `Detected pain: ${matched.map((m) => m.label).join('; ')}`
      : 'No vertical-specific pain signals observed in evidence';
  return { dimension: 'pain', score, reason };
}

function scoreBuyingSignal(vertical: VerticalDefinition, evidence: BusinessEvidence): DimensionScore {
  const { matched, matchedWeight, totalWeight } = matchedSignals(vertical.buyingSignals, evidence);
  const score = fractionScore(matchedWeight, totalWeight, 15);
  const reason =
    matched.length > 0
      ? `Buying signals present: ${matched.map((m) => m.label).join('; ')}`
      : 'Weak buying-signal evidence';
  return { dimension: 'buyingSignal', score, reason };
}

function scoreCompanySize(evidence: BusinessEvidence): DimensionScore {
  const s = sizeIndicators(evidence);
  let score = 30;
  const parts: string[] = [];
  if ((s.employees ?? 0) >= 50) { score += 40; parts.push(`${s.employees} employees`); }
  else if ((s.employees ?? 0) >= 20) { score += 30; parts.push(`${s.employees} employees`); }
  else if ((s.employees ?? 0) >= 5) { score += 15; parts.push(`${s.employees} employees`); }
  if ((s.locations ?? 0) >= 3) { score += 10; parts.push(`${s.locations} locations`); }
  if ((s.technicians ?? s.instructors ?? 0) >= 5) { score += 10; parts.push('large field/instructor team'); }
  if ((s.reviewCount ?? 0) >= 100) { score += 10; parts.push(`${s.reviewCount} reviews`); }
  const final = Math.min(100, score);
  const reason = parts.length > 0 ? parts.join(', ') : 'No size indicators in evidence';
  return { dimension: 'companySize', score: final, reason };
}

function scoreDigitalGap(vertical: VerticalDefinition, evidence: BusinessEvidence): DimensionScore {
  const { matched, matchedWeight, totalWeight } = matchedSignals(
    vertical.websiteOpportunitySignals,
    evidence,
  );
  const base = evidence.websiteQuality?.hasWebsite === false || evidence.website === null ? 45 : 10;
  const score = fractionScore(matchedWeight, totalWeight, base);
  const reason =
    matched.length > 0
      ? `Digital gap: ${matched.map((m) => m.label).join('; ')}`
      : 'Site appears current or gap not evidenced';
  return { dimension: 'digitalGap', score, reason };
}

function scoreAutomationPotential(
  vertical: VerticalDefinition,
  evidence: BusinessEvidence,
): DimensionScore {
  const { matched, matchedWeight, totalWeight } = matchedSignals(
    vertical.automationOpportunitySignals,
    evidence,
  );
  const base = noBooking(evidence) ? 30 : 15;
  const score = fractionScore(matchedWeight, totalWeight, base);
  const reason =
    matched.length > 0
      ? `Automation opportunities: ${matched.map((m) => m.label).join('; ')}`
      : 'No automation signals evidenced';
  return { dimension: 'automationPotential', score, reason };
}

function scoreRevenuePotential(
  vertical: VerticalDefinition,
  evidence: BusinessEvidence,
): DimensionScore {
  const s = sizeIndicators(evidence);
  const dealCap = vertical.estimatedDealSize.max;
  let score = 40;
  const parts: string[] = [];
  if ((s.employees ?? 0) >= 20) { score += 20; parts.push('mid-size operator'); }
  if ((s.locations ?? 0) >= 2) { score += 15; parts.push('multi-location'); }
  if ((s.reviewCount ?? 0) >= 150) { score += 15; parts.push('high demand (reviews)'); }
  if (dealCap >= 20000) { score += 10; parts.push('high-ticket vertical'); }
  const final = Math.min(100, score);
  const reason =
    parts.length > 0
      ? `${parts.join(', ')}; deal ceiling ${vertical.estimatedDealSize.currency} ${dealCap}`
      : 'No revenue-scale indicators in evidence';
  return { dimension: 'revenuePotential', score: final, reason };
}

function scoreContactability(evidence: BusinessEvidence): DimensionScore {
  let score = 10;
  const parts: string[] = [];
  const phone = evidence.contact?.phone;
  if (phone) { score += 40; parts.push('phone'); }
  if (evidence.contact?.email) { score += 15; parts.push('email'); }
  if (evidence.decisionMaker?.name) { score += 15; parts.push(`decision maker: ${evidence.decisionMaker.name}`); }
  const source = evidence.contact?.source ?? evidence.decisionMaker?.source ?? evidence.source;
  if (source && !/unknown|none/i.test(source)) { score += 20; parts.push(`source: ${source}`); }
  const final = Math.min(100, score);
  return {
    dimension: 'contactability',
    score: final,
    reason: parts.length > 0 ? parts.join(', ') : 'No contact path in evidence',
  };
}

function scoreRecency(evidence: BusinessEvidence): DimensionScore {
  const days = ageInDays(evidence.retrievedAt) ?? ageInDaysFromSignals(evidence);
  let score = 20;
  if (days <= 3) score = 100;
  else if (days <= 7) score = 80;
  else if (days <= 14) score = 60;
  else if (days <= 30) score = 40;
  const reason =
    days <= 90
      ? `Evidence fresh (${days} day(s) old)`
      : `Evidence stale (${days} day(s) old)`;
  return { dimension: 'recency', score, reason };
}

function ageInDays(iso: string | undefined): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  return Math.max(0, Math.round((Date.now() - t) / 86400000));
}

function ageInDaysFromSignals(evidence: BusinessEvidence): number {
  const r = evidence.reviewActivity?.recencyDays ?? 365;
  return r;
}

// ── Composite scoring ───────────────────────────────────────────────

export function computeContactabilityScore(evidence: BusinessEvidence): number {
  return scoreContactability(evidence).score;
}

export function computeVerticalScore(
  vertical: VerticalDefinition,
  evidence: BusinessEvidence,
  weights?: ScoreWeights,
): VerticalScoreResult {
  const effectiveWeights = weights ?? DEFAULT_DIMENSION_WEIGHTS;
  const dimensionScores: Record<ScoreDimension, DimensionScore> = {
    pain: scorePain(vertical, evidence),
    buyingSignal: scoreBuyingSignal(vertical, evidence),
    companySize: scoreCompanySize(evidence),
    digitalGap: scoreDigitalGap(vertical, evidence),
    automationPotential: scoreAutomationPotential(vertical, evidence),
    revenuePotential: scoreRevenuePotential(vertical, evidence),
    contactability: scoreContactability(evidence),
    recency: scoreRecency(evidence),
  };

  let weighted = 0;
  const reasonTrace: string[] = [];
  for (const dim of SCORE_DIMENSIONS) {
    const w = effectiveWeights[dim];
    weighted += dimensionScores[dim].score * w;
    reasonTrace.push(
      `${scoreDimensionLabel(dim)} ${dimensionScores[dim].score}/100 · ${dimensionScores[dim].reason}`,
    );
  }

  const buyingProbabilityScore = Math.min(100, Math.max(0, Math.round(weighted)));
  const contactabilityScore = dimensionScores.contactability.score;

  return {
    dimensionScores,
    buyingProbabilityScore,
    leadScore: buyingProbabilityScore,
    contactabilityScore,
    reasonTrace,
  };
}

export const DEFAULT_DIMENSION_WEIGHTS: ScoreWeights = {
  pain: 0.2,
  buyingSignal: 0.15,
  companySize: 0.12,
  digitalGap: 0.15,
  automationPotential: 0.12,
  revenuePotential: 0.12,
  contactability: 0.09,
  recency: 0.05,
};

export { matchedSignals, fractionScore, sizeIndicators, noBooking, hasOutdatedSite };