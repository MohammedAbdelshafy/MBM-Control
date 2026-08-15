/**
 * Owner-First Routing — Multi-Vertical AI Sales Engine
 *
 * Every prime dialer slot is reserved for a qualified decision maker.
 * We never waste a premium position on an irrelevant employee when an
 * owner, founder, CEO, or principal is evidenced for the same business.
 *
 * Priority (highest → lowest): Owner > Founder > CEO > President >
 * Principal > Managing Member > Managing Partner > Decision Maker.
 *
 * Routing is derived ONLY from evidenced decision-maker titles — a missing
 * title stays UNKNOWN and is never guessed.
 */

import type {
  BusinessEvidence,
  DecisionMakerEvidence,
  OwnerRoutingResult,
  OwnerTier,
  TopCallRecord,
} from './types';

const OWNER_TITLE_PATTERNS: Array<{ tier: OwnerTier; label: string; patterns: RegExp[] }> = [
  {
    tier: 'MANAGING_MEMBER',
    label: 'Managing Member',
    patterns: [/\bmanaging member\b/i],
  },
  {
    tier: 'MANAGING_PARTNER',
    label: 'Managing Partner',
    patterns: [/\bmanaging partner\b/i],
  },
  {
    tier: 'FOUNDER',
    label: 'Founder',
    patterns: [/\bfounder\b/i, /\bco-founder\b/i],
  },
  {
    tier: 'CEO',
    label: 'CEO',
    patterns: [/\bCEO\b/i, /\bchief executive\b/i],
  },
  {
    tier: 'PRESIDENT',
    label: 'President',
    patterns: [/\bpresident\b/i, /\bVP\b/i, /\bvice president\b/i],
  },
  {
    tier: 'PRINCIPAL',
    label: 'Principal',
    patterns: [/\bprincipal\b/i],
  },
  {
    tier: 'OWNER',
    label: 'Owner',
    patterns: [
      /\bowner\b/i,
      /\bco-owner\b/i,
      /\bproprietor\b/i,
      /\bprincipal owner\b/i,
      /\bowner[- ]operator\b/i,
      /\bdoctor\b/i,
      /\bDDS\b/i,
      /\bDMD\b/i,
      /\bMD\b/i,
      /\bDO\b/i,
      /\bDC\b/i,
      /\battorney\b/i,
      /\besq\.?\b/i,
      /\bpartner\b/i,
    ],
  },
  {
    tier: 'DIRECTOR',
    label: 'Director',
    patterns: [/\bdirector\b/i, /\bgeneral manager\b/i, /\boffice manager\b/i, /\bservice manager\b/i],
  },
  {
    tier: 'MANAGER',
    label: 'Manager',
    patterns: [/\bmanager\b/i],
  },
  {
    tier: 'STAFF',
    label: 'Staff',
    patterns: [
      /\breceptionist\b/i,
      /\bfront desk\b/i,
      /\badmin\b/i,
      /\bassistant\b/i,
      /\btechnician\b/i,
      /\bclerk\b/i,
      /\bcoordinator\b/i,
      /\bspecialist\b/i,
      /\brepresentative\b/i,
      /\bagent\b/i,
      /\bassociate\b/i,
    ],
  },
];

/**
 * Classify an evidenced decision-maker title into an owner tier.
 * Returns UNKNOWN (never a guess) when nothing matches.
 */
export function classifyOwnerTitle(title: string | null | undefined): OwnerTier {
  if (!title || !title.trim()) return 'UNKNOWN';
  for (const rule of OWNER_TITLE_PATTERNS) {
    for (const pattern of rule.patterns) {
      if (pattern.test(title)) return rule.tier;
    }
  }
  return 'UNKNOWN';
}

const DECISION_MAKER_TIERS = new Set<OwnerTier>([
  'OWNER',
  'FOUNDER',
  'CEO',
  'PRESIDENT',
  'PRINCIPAL',
  'MANAGING_MEMBER',
  'MANAGING_PARTNER',
]);

const TIER_RANK: Record<OwnerTier, number> = {
  OWNER: 10,
  FOUNDER: 9,
  CEO: 8,
  PRESIDENT: 7,
  PRINCIPAL: 6,
  MANAGING_MEMBER: 5,
  MANAGING_PARTNER: 4,
  DIRECTOR: 3,
  MANAGER: 2,
  STAFF: 1,
  UNKNOWN: 0,
};

export function tierRank(tier: OwnerTier): number {
  return TIER_RANK[tier];
}

/** Route a decision-maker evidence block to an owner tier. */
export function routeDecisionMaker(
  decisionMaker: DecisionMakerEvidence | null | undefined,
): OwnerRoutingResult {
  const name = decisionMaker?.name ?? null;
  const title = decisionMaker?.title ?? null;
  const tier = classifyOwnerTitle(title);
  const isDecisionMaker = DECISION_MAKER_TIERS.has(tier);
  const routeLabel =
    title && title.trim()
      ? `${title.trim()}${isDecisionMaker ? ' · decision maker' : ''}`
      : isDecisionMaker
        ? 'Decision maker'
        : 'Unknown contact';
  return { tier, isDecisionMaker, ownerName: name, title, routeLabel };
}

/** Route an evidence block, preferring the decision maker field. */
export function routeEvidenceOwner(evidence: BusinessEvidence): OwnerRoutingResult {
  return routeDecisionMaker(evidence.decisionMaker);
}

/**
 * Owner-first sort: qualified decision makers rise to the top of the dialer,
 * staff/unknown contacts sink. Ties break on buying probability, then
 * contactability.
 */
export function ownerFirstSort<T extends Pick<TopCallRecord, 'decisionMaker' | 'buyingProbability' | 'contactabilityScore'>>(
  records: T[],
): T[] {
  return [...records].sort((a, b) => {
    const aTier = routeDecisionMaker(a.decisionMaker);
    const bTier = routeDecisionMaker(b.decisionMaker);
    const aIsDM = aTier.isDecisionMaker ? 1 : 0;
    const bIsDM = bTier.isDecisionMaker ? 1 : 0;
    return (
      bIsDM - aIsDM ||
      tierRank(bTier.tier) - tierRank(aTier.tier) ||
      b.buyingProbability - a.buyingProbability ||
      b.contactabilityScore - a.contactabilityScore
    );
  });
}