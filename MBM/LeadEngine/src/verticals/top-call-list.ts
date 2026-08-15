/**
 * Top-Call List Builder — Multi-Vertical AI Sales Engine
 *
 * Ranks opportunities by BUYING PROBABILITY across all configured
 * verticals and returns the TOP N businesses to call today. Only records
 * derived from real, provenance-preserved evidence are ranked.
 */

import type {
  BusinessEvidence,
  OpportunityOutput,
  TopCallRecord,
  VerticalDefinition,
} from './types';
import { computeVerticalScore, DEFAULT_DIMENSION_WEIGHTS } from './scoring';
import { analyzeOpportunity } from './opportunity';
import { VerticalRegistry } from './registry';

export interface RankedOpportunity {
  vertical: VerticalDefinition;
  evidence: BusinessEvidence;
  opportunity: OpportunityOutput;
}

export interface BuildTopCallListOptions {
  limit?: number;
  /** Optional filter: only these vertical ids. */
  verticalIds?: string[];
  /** Optional minimum buying probability to include. */
  minBuyingProbability?: number;
  /** Require a contact path (phone/email) for call-readiness. */
  requireContactPath?: boolean;
}

export function rankOpportunities(
  records: Array<{ vertical: VerticalDefinition; evidence: BusinessEvidence }>,
  options?: BuildTopCallListOptions,
): RankedOpportunity[] {
  const ranked: RankedOpportunity[] = [];
  for (const { vertical, evidence } of records) {
    const weights = vertical.weightOverrides
      ? { ...DEFAULT_DIMENSION_WEIGHTS, ...vertical.weightOverrides }
      : DEFAULT_DIMENSION_WEIGHTS;
    const score = computeVerticalScore(vertical, evidence, weights);
    const opportunity = analyzeOpportunity({ vertical, evidence, score });
    if (options?.minBuyingProbability !== undefined && opportunity.buyingProbability < options.minBuyingProbability) {
      continue;
    }
    if (options?.requireContactPath && !opportunity.contact.phone && !opportunity.contact.email) {
      continue;
    }
    ranked.push({ vertical, evidence, opportunity });
  }
  return ranked.sort(
    (a, b) =>
      b.opportunity.buyingProbability - a.opportunity.buyingProbability ||
      b.opportunity.contactabilityScore - a.opportunity.contactabilityScore,
  );
}

export function buildTopCallList(
  registry: VerticalRegistry,
  records: Array<{ verticalId: string; evidence: BusinessEvidence }>,
  options?: BuildTopCallListOptions,
): TopCallRecord[] {
  const resolved = records
    .filter((r) => !options?.verticalIds || options.verticalIds.includes(r.verticalId))
    .map((r) => ({ vertical: registry.require(r.verticalId), evidence: r.evidence }));

  const ranked = rankOpportunities(resolved, options);
  const limit = options?.limit ?? ranked.length;
  return ranked.slice(0, limit).map((r) => r.opportunity as TopCallRecord);
}