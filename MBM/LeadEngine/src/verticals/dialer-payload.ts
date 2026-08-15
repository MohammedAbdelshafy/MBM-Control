/**
 * One-Screen Dialer Payload — Multi-Vertical AI Sales Engine
 *
 * Assembles everything a caller needs on ONE screen — owner, company,
 * vertical, why this lead, recommended offer, opener, discovery, the
 * most likely objection branch, close, callability and lead score.
 *
 * The caller never needs a separate research screen: this is the payload
 * the dialer renders directly.
 */

import type {
  BusinessEvidence,
  DialerPayload,
  ObjectionBranchId,
  OwnerRoutingResult,
  RenderedScript,
  TopCallRecord,
  VerticalDefinition,
} from './types';
import { routeEvidenceOwner } from './owner-routing';
import { renderPrimeScript } from './script-engine';
import { getObjectionBranch, renderObjectionSteps } from './objections';
import { computeContactabilityScore } from './scoring';

export interface BuildDialerPayloadInput {
  vertical: VerticalDefinition;
  opportunity: TopCallRecord;
  evidence: BusinessEvidence;
  /** Force the routed objection branch (default: auto-routed). */
  objectionBranchId?: ObjectionBranchId;
}

export function buildDialerPayload(input: BuildDialerPayloadInput): DialerPayload {
  const { vertical, opportunity, evidence } = input;
  const ownerRouting: OwnerRoutingResult = routeEvidenceOwner(evidence);
  const script: RenderedScript = renderPrimeScript(vertical, opportunity, evidence);

  // The caller's most likely live objection — derived from evidence:
  // a partner/business title routes to PARTNER, a generic owner routes to
  // HAVE_SOMEONE (the most common live pull).
  const objectionId =
    input.objectionBranchId ??
    (/partner|associate|co[- ]owner|LLC\b|principal/i.test(ownerRouting.title ?? '') &&
    ownerRouting.tier !== 'OWNER'
      ? 'PARTNER'
      : 'HAVE_SOMEONE');
  const objection = getObjectionBranch(objectionId);
  const objectionSteps = renderObjectionSteps(objection, script.context);

  const callability = computeContactabilityScore(evidence);

  return {
    owner: opportunity.decisionMaker?.name ?? 'Decision maker',
    company: opportunity.company,
    vertical: vertical.name,
    verticalId: vertical.id,
    whyThisLead: script.sections.WHY_THIS_LEAD,
    recommendedOffer: opportunity.recommendedOffer,
    opener: script.sections.OPENING,
    discovery: script.sections.DISCOVERY,
    objection: objectionSteps.respond,
    close: script.sections.FINAL_CLOSE,
    callability,
    leadScore: opportunity.leadScore,
    phone: opportunity.contact?.phone ?? null,
    email: opportunity.contact?.email ?? null,
    ownerRouting,
    script,
  };
}

export function serializeDialerPayload(payload: DialerPayload): string {
  return [
    `OWNER: ${payload.owner}`,
    `COMPANY: ${payload.company}`,
    `VERTICAL: ${payload.vertical}`,
    `ROUTE: ${payload.ownerRouting.routeLabel}`,
    `CALLABILITY: ${payload.callability}/100`,
    `LEAD SCORE: ${payload.leadScore}/100`,
    '',
    `WHY THIS LEAD: ${payload.whyThisLead}`,
    `RECOMMENDED OFFER: ${payload.recommendedOffer}`,
    '',
    `OPENER: ${payload.opener}`,
    `DISCOVERY: ${payload.discovery}`,
    `OBJECTION: ${payload.objection}`,
    `CLOSE: ${payload.close}`,
  ].join('\n');
}