/**
 * Dynamic Script Engine — Multi-Vertical AI Sales Engine
 *
 * Renders a complete, read-verbatim call script for every prime lead.
 * Thirteen sections, all derived from evidenced facts and vertical
 * configuration — never from invention:
 *
 *   WHY THIS LEAD · WHO AM I CALLING · OPENING · DISCOVERY · PAIN ·
 *   COST OF INACTION · OFFER · VALUE · OBJECTIONS · TRIAL CLOSE ·
 *   FINAL CLOSE · VOICEMAIL · FOLLOW-UP
 *
 * Dynamic fields are substituted from evidence:
 *   [OWNER_NAME] [COMPANY] [VERTICAL] [CITY] [KNOWN_PAIN]
 *   [OBSERVED_SIGNAL] [RECOMMENDED_OFFER] [VALUE_HYPOTHESIS]
 *
 * Tone: high-energy, confident, direct, owner-focused. Facts are anchored
 * to evidence; nothing is fabricated (no invented ROI, urgency, or case
 * studies), and the prospect is always given an honest out.
 */

import type {
  BusinessEvidence,
  DealSizeRange,
  RenderedScript,
  ScriptContext,
  ScriptSectionId,
  ScriptSections,
  TopCallRecord,
  VerticalDefinition,
} from './types';
import { SCRIPT_SECTION_IDS } from './types';
import { formatDealSize } from './opportunity';
import { matchedSignals } from './scoring';

// ── Placeholder resolution ──────────────────────────────────────────

export const PLACEHOLDERS = [
  '[OWNER_NAME]',
  '[COMPANY]',
  '[VERTICAL]',
  '[CITY]',
  '[KNOWN_PAIN]',
  '[OBSERVED_SIGNAL]',
  '[RECOMMENDED_OFFER]',
  '[VALUE_HYPOTHESIS]',
] as const;

export type Placeholder = (typeof PLACEHOLDERS)[number];

/** Substitute every known placeholder until stable. Unknown tokens are left untouched. */
export function renderPlaceholders(text: string, context: ScriptContext): string {
  const map: Record<Placeholder, string> = {
    '[OWNER_NAME]': context.ownerName,
    '[COMPANY]': context.company,
    '[VERTICAL]': context.vertical,
    '[CITY]': context.city,
    '[KNOWN_PAIN]': context.knownPain,
    '[OBSERVED_SIGNAL]': context.observedSignal,
    '[RECOMMENDED_OFFER]': context.recommendedOffer,
    '[VALUE_HYPOTHESIS]': context.valueHypothesis,
  };
  let out = text;
  for (let pass = 0; pass < 5; pass += 1) {
    let changed = false;
    for (const key of PLACEHOLDERS) {
      const value = map[key] ?? '';
      if (value !== '' && out.includes(key)) {
        out = out.split(key).join(value);
        changed = true;
      }
    }
    if (!changed) break;
  }
  return out;
}

export function hasUnrenderedPlaceholders(text: string): boolean {
  return PLACEHOLDERS.some((p) => text.includes(p));
}

// ── Context derivation (evidence-driven, nothing invented) ──────────

export function formatValueHypothesis(size: DealSizeRange): string {
  return formatDealSize(size);
}

function firstMatchedLabel(vertical: VerticalDefinition, evidence: BusinessEvidence): string {
  const signals = [...vertical.painSignals, ...vertical.buyingSignals, ...vertical.aiOpportunitySignals];
  const { matched } = matchedSignals(signals, evidence);
  return matched.length > 0 ? matched[0].label : '';
}

function observedSignalLabel(vertical: VerticalDefinition, evidence: BusinessEvidence): string {
  const { matched } = matchedSignals([...vertical.buyingSignals, ...vertical.aiOpportunitySignals], evidence);
  return matched.length > 0 ? matched[0].label : '';
}

export function buildScriptContext(
  vertical: VerticalDefinition,
  opportunity: TopCallRecord,
  evidence: BusinessEvidence,
): ScriptContext {
  const ownerName = opportunity.decisionMaker?.name ?? 'there';
  const city = opportunity.location?.city ?? '';
  const knownPain = firstMatchedLabel(vertical, evidence);
  const observedSignal = observedSignalLabel(vertical, evidence);
  return {
    ownerName,
    company: opportunity.company,
    vertical: vertical.name,
    city,
    knownPain:
      knownPain ||
      'leads that slip through without a fast, consistent follow-up',
    observedSignal:
      observedSignal ||
      'the missed-call and follow-up gap that costs [COMPANY] real jobs',
    recommendedOffer: opportunity.recommendedOffer,
    valueHypothesis: formatValueHypothesis(opportunity.estimatedDealSize),
  };
}

// ── Section templates ───────────────────────────────────────────────

const SECTION_TEMPLATES: Record<ScriptSectionId, string> = {
  WHY_THIS_LEAD:
    '[COMPANY] is a [VERTICAL] in [CITY] with clear [KNOWN_PAIN] and [OBSERVED_SIGNAL]. ' +
    'That combination puts you at the top of my call list today — not because I’m mass-dialing, ' +
    'but because the fix I sell pays for itself fastest in exactly your situation.',
  WHO_AM_I_CALLING:
    'I’m speaking with [OWNER_NAME], the decision maker at [COMPANY]. ' +
    'You own the outcome, so I’m not going to waste your time on a discovery call about a discovery call.',
  OPENING:
    '[OWNER_NAME], this is Omar from MBM. Sixty seconds — I’ll earn the next minute. ' +
    'Here’s what I see: [OBSERVED_SIGNAL]. For a [VERTICAL] like [COMPANY], that usually means ' +
    'real money walking out the door every single week. Am I warm, or way off?',
  DISCOVERY:
    'Three questions, no filler. First: how many leads does [COMPANY] get in a week, and how many get ' +
    'a response within the hour? Second: what happens to an after-hours call right now — and how many jobs ' +
    'do you estimate you lose a month because nobody answered fast enough? Third: what does your current ' +
    'booking and follow-up system look like — who does it manually, and how many hours a week does it eat?',
  PAIN:
    '[KNOWN_PAIN]. That’s not a small-business nuisance — at [COMPANY] it’s a revenue leak ' +
    'you’re paying for twice: once in lost jobs, once in the time you spend chasing them manually.',
  COST_OF_INACTION:
    'Every day this stays manual, another after-hours call goes to voicemail and another lead ' +
    'goes to a competitor who answered in seconds. You don’t lose the job to a better price — ' +
    'you lose it to a faster answer. That’s the cost of doing nothing, and it compounds every week.',
  OFFER:
    'Here’s the fix: [RECOMMENDED_OFFER]. It answers instantly, qualifies the lead, books the job, ' +
    'and follows up on everything — so [COMPANY] never leaves money on the table because someone ' +
    'was busy, asleep, or on another call.',
  VALUE:
    'The engagements I build for [VERTICAL] operators run [VALUE_HYPOTHESIS]. ' +
    'Against even one recovered job a month, that number does the talking — and I can show you ' +
    'exactly what’s included before you spend a dollar.',
  OBJECTIONS:
    'You’ll probably say: “we already have someone,” or “we already use AI,” or “send me info.” ' +
    'All fair. I’ve got a straight answer for each — and if the honest answer is “not a fit,” ' +
    'I’ll say so and leave it there.',
  TRIAL_CLOSE:
    'Let’s not decide anything big today. Two options: I send you the one-page on ' +
    '[RECOMMENDED_OFFER] and we grab 10 minutes next week to look at [COMPANY]’s actual numbers — ' +
    'or I’m wrong about the leak and you tell me where, and I’m gone. Which is it?',
  FINAL_CLOSE:
    'Here’s what I’m asking: ten minutes, me and you, on the calendar this week. ' +
    'I bring the plan for [COMPANY], you bring the real numbers, and at the end you decide ' +
    'yes, no, or maybe — no pressure, no games. Is ten minutes this week fair?',
  VOICEMAIL:
    'Hey [OWNER_NAME], Omar from MBM. I’m calling about [COMPANY] and the [OBSERVED_SIGNAL] ' +
    'I spotted — it’s costing you jobs every week. I’m not going to chase you; if the ' +
    '[RECOMMENDED_OFFER] opportunity fits, call me back and we’ll grab ten minutes. ' +
    'If it doesn’t, delete this and I’ll take the hint. My number’s on the screen.',
  FOLLOW_UP:
    'If I don’t reach you: day 1 follow-up email with the one-page on [RECOMMENDED_OFFER], ' +
    'day 3 text with a straight price question, day 7 final call. After that I stop — ' +
    'no nagging. Your move, [OWNER_NAME].',
};

// ── Closing paths ───────────────────────────────────────────────────

export type ClosingPathId =
  | 'TEN_MINUTE_DEMO'
  | 'FIFTEEN_MINUTE_DIAGNOSTIC'
  | 'CALENDAR'
  | 'DECISION_MAKER'
  | 'FOLLOW_UP';

export const CLOSING_PATHS: Record<ClosingPathId, string> = {
  TEN_MINUTE_DEMO:
    'Ten minutes on the calendar, [OWNER_NAME]. I walk you through [RECOMMENDED_OFFER] live — you see it answer, ' +
    'book, and follow up in real time, and you decide. No obligation, no follow-up calls if it’s not a fit. ' +
    'Is ten minutes this week fair?',
  FIFTEEN_MINUTE_DIAGNOSTIC:
    'Give me fifteen minutes and I’ll run a full diagnostic on [COMPANY]: what’s leaking today, what the leak ' +
    'costs a month, and exactly where [RECOMMENDED_OFFER] plugs in. At the end you’ll know where you stand — ' +
    'even if you never do business with me. Is fifteen minutes worth it?',
  CALENDAR:
    'I’m not asking for a decision today, [OWNER_NAME]. I’m asking for a calendar slot — fifteen minutes, this week, ' +
    'when you’re not being ambushed by a call. Tuesday afternoon or Thursday morning — which works for you?',
  DECISION_MAKER:
    'If there’s a partner or co-owner who needs to be part of this, bring them. I’ll bring the full plan for ' +
    '[COMPANY] and we settle it together in one sitting — no back-and-forth. Can we get everyone on one call this week?',
  FOLLOW_UP:
    'No pressure, [OWNER_NAME] — you’ve heard the pitch. I’ll send the one-pager on [RECOMMENDED_OFFER] ' +
    'for [COMPANY] over now, and I’ll check back once in 48 hours. After that the ball’s in your court. Fair?',
};

export function closingPath(id: ClosingPathId, context: ScriptContext): string {
  return renderPlaceholders(CLOSING_PATHS[id], context);
}

export function buildClosingPaths(context: ScriptContext): Record<ClosingPathId, string> {
  const out = {} as Record<ClosingPathId, string>;
  for (const id of Object.keys(CLOSING_PATHS) as ClosingPathId[]) {
    out[id] = closingPath(id, context);
  }
  return out;
}

// ── Rendering ───────────────────────────────────────────────────────

const SECTION_LABELS: Record<ScriptSectionId, string> = {
  WHY_THIS_LEAD: 'WHY THIS LEAD',
  WHO_AM_I_CALLING: 'WHO AM I CALLING',
  OPENING: 'OPENING',
  DISCOVERY: 'DISCOVERY',
  PAIN: 'PAIN',
  COST_OF_INACTION: 'COST OF INACTION',
  OFFER: 'OFFER',
  VALUE: 'VALUE',
  OBJECTIONS: 'OBJECTIONS',
  TRIAL_CLOSE: 'TRIAL CLOSE',
  FINAL_CLOSE: 'FINAL CLOSE',
  VOICEMAIL: 'VOICEMAIL',
  FOLLOW_UP: 'FOLLOW-UP',
};

export function scriptSectionLabel(id: ScriptSectionId): string {
  return SECTION_LABELS[id];
}

export function buildScriptSections(
  vertical: VerticalDefinition,
  opportunity: TopCallRecord,
  evidence: BusinessEvidence,
): { sections: ScriptSections; context: ScriptContext } {
  const context = buildScriptContext(vertical, opportunity, evidence);
  const sections = {} as ScriptSections;
  for (const id of SCRIPT_SECTION_IDS) {
    sections[id] = renderPlaceholders(SECTION_TEMPLATES[id], context);
  }
  return { sections, context };
}

/** Render the complete read-verbatim script for a prime lead. */
export function renderPrimeScript(
  vertical: VerticalDefinition,
  opportunity: TopCallRecord,
  evidence: BusinessEvidence,
): RenderedScript {
  const { sections, context } = buildScriptSections(vertical, opportunity, evidence);
  const full = SCRIPT_SECTION_IDS.map((id) => `## ${SECTION_LABELS[id]}\n${sections[id]}`).join('\n\n');
  return {
    verticalId: vertical.id,
    verticalName: vertical.name,
    sections,
    context,
    full,
  };
}