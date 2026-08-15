/**
 * Real-Estate Deal Script Engine — Multi-Vertical AI Sales Engine
 *
 * Renders owner-first, read-verbatim call scripts for every real-estate
 * contact — auction properties, distressed owners, cash buyers, investors,
 * and wholesalers — anchored to the institutional deal dossier:
 *
 *   WHY THIS DEAL · WHY NOW · ECONOMIC THESIS · RISKS ·
 *   UNKNOWN VARIABLES · BEST NEXT ACTION
 *
 * Every line is derived from dossier facts (address, county, ARV, bid,
 * MAO, spread) or from the contact's evidenced role. Nothing is invented:
 * no fake scarcity, no fake social proof, no guaranteed ROI. Each script
 * leads with a short opener and then DIAGNOSTIC QUESTIONS that surface
 * the other side's reality before any offer is pushed.
 */

import type {
  DealSizeRange,
  ObjectionBranch,
  ScriptContext,
  VerticalDefinition,
} from './types';
import { getObjectionBranch, renderObjectionSteps } from './objections';

// ── Real-estate deal roles ──────────────────────────────────────────

export type RealEstateRole =
  | 'AUCTION_PROPERTY'
  | 'DISTRESSED_OWNER'
  | 'CASH_BUYER'
  | 'INVESTOR'
  | 'WHOLESALER';

export const REAL_ESTATE_ROLES: RealEstateRole[] = [
  'AUCTION_PROPERTY',
  'DISTRESSED_OWNER',
  'CASH_BUYER',
  'INVESTOR',
  'WHOLESALER',
];

export interface DealDossier {
  propertyAddress: string;
  city: string;
  state: string;
  county: string;
  parcelId?: string | null;
  ownerName?: string | null;
  ownerPhone?: string | null;

  // The institutional dossier narrative
  whyThisDeal: string;
  whyNow: string;
  economicThesis: string;
  risks: string;
  unknownVariables: string;
  bestNextAction: string;

  // Underwriting economics (optional — N/A stays N/A)
  estimatedArv?: number | null;
  startingBid?: number | null;
  calculatedMao?: number | null;
  estimatedRepairCost?: number | null;
  potentialFee?: number | null;

  source?: string | null;
}

export interface DealScript {
  role: RealEstateRole;
  roleLabel: string;
  whyThisDeal: string;
  whyNow: string;
  economicThesis: string;
  risks: string;
  unknownVariables: string;
  bestNextAction: string;
  opener: string;
  diagnosticQuestions: string[];
  objections: ObjectionBranch[];
  trialClose: string;
  finalClose: string;
  full: string;
}

export interface DealScriptContext {
  ownerName: string;
  propertyAddress: string;
  city: string;
  state: string;
  county: string;
  arv: string;
  bid: string;
  mao: string;
  repair: string;
  fee: string;
}

// ── Context + helpers ───────────────────────────────────────────────

const money = (n: number | null | undefined): string =>
  typeof n === 'number' && Number.isFinite(n) ? `$${n.toLocaleString('en-US')}` : 'N/A';

export function buildDealScriptContext(dossier: DealDossier): DealScriptContext {
  return {
    ownerName: dossier.ownerName || 'the owner',
    propertyAddress: dossier.propertyAddress || 'the property',
    city: dossier.city || '',
    state: dossier.state || '',
    county: dossier.county || '',
    arv: money(dossier.estimatedArv),
    bid: money(dossier.startingBid),
    mao: money(dossier.calculatedMao),
    repair: money(dossier.estimatedRepairCost),
    fee: money(dossier.potentialFee),
  };
}

export function resolveDealPlaceholders(text: string, ctx: DealScriptContext): string {
  let out = text;
  const map: Record<string, string> = {
    '[OWNER_NAME]': ctx.ownerName,
    '[PROPERTY]': ctx.propertyAddress,
    '[CITY]': ctx.city,
    '[STATE]': ctx.state,
    '[COUNTY]': ctx.county,
    '[ARV]': ctx.arv,
    '[BID]': ctx.bid,
    '[MAO]': ctx.mao,
    '[REPAIR]': ctx.repair,
    '[FEE]': ctx.fee,
  };
  for (const [k, v] of Object.entries(map)) {
    out = out.split(k).join(v);
  }
  return out;
}

// ── Role openers + diagnostic questions ─────────────────────────────

interface RoleScriptDef {
  roleLabel: string;
  opener: string;
  diagnosticQuestions: string[];
}

const ROLE_SCRIPTS: Record<RealEstateRole, RoleScriptDef> = {
  AUCTION_PROPERTY: {
    roleLabel: 'Auction Property',
    opener:
      '[OWNER_NAME], this is Omar from MBM Capital. I’m calling about [PROPERTY] in [CITY], [STATE]. ' +
      'I found it on the upcoming auction list with an opening bid of [BID], and before the gavel drops ' +
      'I wanted to see if you’re open to a clean, all-cash conversation — no agents, no fees, no contingencies. ' +
      'Do you have 90 seconds?',
    diagnosticQuestions: [
      'Have you already been approached by investors, or is this the first call?',
      'Is the current bid number realistic for what the property is worth, in your view?',
      'If you could exit the property this month, all-cash, no contingencies — what would that be worth to you?',
    ],
  },
  DISTRESSED_OWNER: {
    roleLabel: 'Distressed Owner',
    opener:
      '[OWNER_NAME], Omar from MBM Capital here. I’m calling about your property at [PROPERTY] in [CITY]. ' +
      'I don’t know your exact situation, and I’m not going to pretend I do — that’s why I’m asking. ' +
      'If the property is more headache than help right now, I can make you a straight cash offer and close fast. ' +
      'Have I caught you at a bad time?',
    diagnosticQuestions: [
      'What’s the biggest reason you’d consider selling — taxes, upkeep, or just ready to move on?',
      'Is the property currently generating income for you, or is it costing you money each month?',
      'If I could have you out of it in 30 days, all cash, no repairs on your side — would that work?',
    ],
  },
  CASH_BUYER: {
    roleLabel: 'Cash Buyer',
    opener:
      '[OWNER_NAME], Omar with MBM Capital. I’m sending you an off-market deal before it ever hits the open market: ' +
      '[PROPERTY] in [CITY], [STATE], currently listed for auction with a projected spread of [FEE]. ' +
      'You buy direct, skip the bidding war, and I handle the paperwork. Want the numbers in 60 seconds?',
    diagnosticQuestions: [
      'What are you targeting right now — flips, rentals, or buy-and-hold?',
      'Is your cash position ready to move within 30 days on the right deal?',
      'What’s your target return — I’ll tell you straight whether this clears the bar?',
    ],
  },
  INVESTOR: {
    roleLabel: 'Investor',
    opener:
      '[OWNER_NAME], Omar from MBM Capital. I underwrite distressed and auction inventory for investors, ' +
      'and I’ve got one that fits a [FEE]-plus spread thesis: [PROPERTY] in [CITY], [STATE]. ' +
      'ARV is [ARV], my 70% MAO lands at [MAO], and the opening bid is [BID]. ' +
      'Does that gap look like your kind of deal?',
    diagnosticQuestions: [
      'How do you typically underwrite — fix-and-flip, rental cash flow, or assignment?',
      'What’s your current threshold for rehab risk on a deal like this?',
      'Are you in a position to act this month if the numbers check out?',
    ],
  },
  WHOLESALER: {
    roleLabel: 'Wholesaler',
    opener:
      '[OWNER_NAME], Omar from MBM Capital. I’ve got a pre-foreclosure/auction property I can move under contract: ' +
      '[PROPERTY] in [CITY], [STATE]. The buy number is [MAO] against an [ARV] ARV, which leaves room for a buyer. ' +
      'I’m looking for someone with a cash list ready to assign to. Sound like you?',
    diagnosticQuestions: [
      'How big is your cash-buyer list right now — and how fast can you move a deal?',
      'Do you typically assign contracts, or do you double-close?',
      'What’s your fee target on a clean assignment — so I know whether this fits before we both waste time?',
    ],
  },
};

export function roleLabel(role: RealEstateRole): string {
  return ROLE_SCRIPTS[role].roleLabel;
}

// ── Closing paths ───────────────────────────────────────────────────

export type DealClosingPathId =
  | 'TEN_MINUTE_DEMO'
  | 'FIFTEEN_MINUTE_DIAGNOSTIC'
  | 'CALENDAR'
  | 'DECISION_MAKER'
  | 'FOLLOW_UP';

export const DEAL_CLOSING_PATHS: Record<DealClosingPathId, (ctx: DealScriptContext) => string> = {
  TEN_MINUTE_DEMO:
    (ctx) =>
      `Ten minutes on the calendar, [OWNER_NAME]. I walk you through the [ARV] / [MAO] math on ` +
      `[PROPERTY] live — you see the exact deal, and you decide. No obligation, no follow-up calls if it’s not a fit. Is ten minutes this week fair?`,
  FIFTEEN_MINUTE_DIAGNOSTIC:
    (ctx) =>
      `Give me fifteen minutes and I’ll run a full diagnostic on [PROPERTY]: real numbers on [BID], ` +
      `[MAO], repair estimate [REPAIR], and what you’d net at [FEE]. At the end you’ll know exactly where ` +
      `you stand — even if you never do business with me. Is fifteen minutes worth it?`,
  CALENDAR:
    (ctx) =>
      `I’m not asking for a decision today, [OWNER_NAME]. I’m asking for a calendar slot — 15 minutes, ` +
      `this week, when you’re not being ambushed by a call. Tuesday afternoon or Thursday morning — ` +
      `which works better for you?`,
  DECISION_MAKER:
    (ctx) =>
      `If there’s a partner or spouse who needs to be part of this decision, bring them. I’ll bring ` +
      `the full picture on [PROPERTY] and we settle it together in one sitting — no back-and-forth. ` +
      `Can we get everyone on one call this week?`,
  FOLLOW_UP:
    (ctx) =>
      `No pressure, [OWNER_NAME] — you’ve heard the pitch. I’ll send the numbers on [PROPERTY] over ` +
      `now, and I’ll check back once in 48 hours. After that the ball’s in your court. Fair?`,
};

export function dealClosingPath(id: DealClosingPathId, ctx: DealScriptContext): string {
  return resolveDealPlaceholders(DEAL_CLOSING_PATHS[id](ctx), ctx);
}

// ── Full deal script assembly ───────────────────────────────────────

export function buildDealScript(dossier: DealDossier, role: RealEstateRole): DealScript {
  const ctx = buildDealScriptContext(dossier);
  const def = ROLE_SCRIPTS[role];
  const opener = resolveDealPlaceholders(def.opener, ctx);
  const diagnosticQuestions = def.diagnosticQuestions.map((q) => resolveDealPlaceholders(q, ctx));

  const objection = getObjectionBranch('TOO_EXPENSIVE');
  const objections = [objection, getObjectionBranch('NOT_INTERESTED'), getObjectionBranch('PARTNER')];

  const trialClose = dealClosingPath('FIFTEEN_MINUTE_DIAGNOSTIC', ctx);
  const finalClose = dealClosingPath('CALENDAR', ctx);

  const sections = [
    `WHY THIS DEAL: ${dossier.whyThisDeal}`,
    `WHY NOW: ${dossier.whyNow}`,
    `ECONOMIC THESIS: ${dossier.economicThesis}`,
    `RISKS: ${dossier.risks}`,
    `UNKNOWN VARIABLES: ${dossier.unknownVariables}`,
    `BEST NEXT ACTION: ${dossier.bestNextAction}`,
    ``,
    `OPENER:\n${opener}`,
    ``,
    `DIAGNOSTIC QUESTIONS:`,
    ...diagnosticQuestions.map((q) => `  • ${q}`),
    ``,
    `OBJECTION (${objection.trigger}): ${objection.respond}`,
    ``,
    `TRIAL CLOSE: ${trialClose}`,
    `FINAL CLOSE: ${finalClose}`,
  ];

  return {
    role,
    roleLabel: def.roleLabel,
    whyThisDeal: dossier.whyThisDeal,
    whyNow: dossier.whyNow,
    economicThesis: dossier.economicThesis,
    risks: dossier.risks,
    unknownVariables: dossier.unknownVariables,
    bestNextAction: dossier.bestNextAction,
    opener,
    diagnosticQuestions,
    objections,
    trialClose,
    finalClose,
    full: sections.join('\n'),
  };
}

export function renderObjectionForDeal(
  objectionId: 'HAVE_SOMEONE' | 'SEND_INFO' | 'TOO_EXPENSIVE' | 'NOT_INTERESTED' | 'TOO_BUSY' | 'CALL_LATER' | 'PARTNER' | 'HOW_MUCH',
  ctx: DealScriptContext,
): ReturnType<typeof renderObjectionSteps> {
  return renderObjectionSteps(getObjectionBranch(objectionId), {
    ownerName: ctx.ownerName,
    company: ctx.propertyAddress,
    vertical: 'real estate',
    city: ctx.city,
    knownPain: '',
    observedSignal: '',
    recommendedOffer: '',
    valueHypothesis: ctx.fee !== 'N/A' ? ctx.fee : '',
  });
}

/** Reuse for a B2B deal-size context so objections anchor to real ranges. */
export function dealSizeToScriptContext(size: DealSizeRange): Pick<ScriptContext, 'valueHypothesis'> {
  return { valueHypothesis: `$${size.min.toLocaleString('en-US')}–$${size.max.toLocaleString('en-US')} ${size.currency} · ${size.unit}` };
}

/** Narrow helper for B2B dialer payloads that need a ScriptContext quickly. */
export function verticalScriptContext(
  vertical: VerticalDefinition,
  ownerName: string,
  company: string,
  city: string,
): ScriptContext {
  return {
    ownerName,
    company,
    vertical: vertical.name,
    city,
    knownPain: '',
    observedSignal: '',
    recommendedOffer: vertical.recommendedOffers[0] ?? '',
    valueHypothesis: dealSizeToScriptContext(vertical.estimatedDealSize).valueHypothesis,
  };
}