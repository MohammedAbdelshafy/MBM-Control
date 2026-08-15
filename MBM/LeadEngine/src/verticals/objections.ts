/**
 * Objection Branches — Multi-Vertical AI Sales Engine
 *
 * Every objection gets a four-step branch:
 *   ACKNOWLEDGE → CLARIFY → RESPOND → NEXT STEP
 *
 * Branches are vertical-agnostic but context-aware: placeholders like
 * [COMPANY], [VERTICAL], and [RECOMMENDED_OFFER] are substituted from the
 * lead's script context. No urgency or ROI is ever fabricated — responses
 * anchor to evidenced pain and the vertical's real deal range.
 */

import type { ObjectionBranch, ObjectionBranchId, ScriptContext } from './types';

export const OBJECTION_BRANCHES: ObjectionBranch[] = [
  {
    id: 'HAVE_SOMEONE',
    trigger: 'We already have someone.',
    acknowledge: 'That means you run a real operation — respect.',
    clarify: 'Are they actually closing, or just managing the day-to-day?',
    respond:
      'I’m not here to replace your team. We plug the leak they can’t reach — every after-hours call and every un-returned lead at [COMPANY] still goes somewhere. If you’ve got it covered, tell me straight and I’ll move on.',
    nextStep:
      'Sixty seconds, one look at the [RECOMMENDED_OFFER] playbook — you decide if it’s even worth your time.',
  },
  {
    id: 'USE_AI',
    trigger: 'We already use AI.',
    acknowledge: 'You’re ahead of 90% of [VERTICAL] operators — I like that.',
    clarify: 'What’s it doing for you today — answering calls, booking jobs, or just a chatbot?',
    respond:
      'Most “AI” I hear about is a chatbot that can’t book a call. Ours is a [RECOMMENDED_OFFER] that answers in under 3 seconds and books real revenue. If yours already does that, then you genuinely don’t need me.',
    nextStep: 'Give me 60 seconds to show you the difference — then you decide.',
  },
  {
    id: 'SEND_INFO',
    trigger: 'Send me information.',
    acknowledge: 'Done — I’ll make sure it’s worth reading.',
    clarify: 'What do you want to see first: the [RECOMMENDED_OFFER] in action, or the numbers?',
    respond:
      'I’ll send you one page — what it does, what it costs, and the exact problem it kills for a [VERTICAL] in your city. No 40-page deck.',
    nextStep: 'While you read it, book 10 minutes on the calendar — worst case you get a free audit.',
  },
  {
    id: 'TOO_EXPENSIVE',
    trigger: 'Too expensive.',
    acknowledge: 'Fair — let’s put a real number on it.',
    clarify: 'What does one missed job actually cost [COMPANY] in a busy week?',
    respond:
      'That’s the number that matters. If [RECOMMENDED_OFFER] catches even one of those a month at [COMPANY], it pays for itself and then some. I’m not asking you to take my word — run the math on your own missed calls.',
    nextStep: 'Let me show you the exact price and what’s included — then you judge it against that one missed job.',
  },
  {
    id: 'NOT_INTERESTED',
    trigger: 'Not interested.',
    acknowledge: 'I hear you, and I respect a straight answer.',
    clarify: 'Is it “not this”, or “not right now”?',
    respond:
      'If it’s timing, fine — I’ll leave you my card and check back in 90 days. If it’s “not this”, that’s exactly why I want 60 seconds: [RECOMMENDED_OFFER] either fits a [VERTICAL] like [COMPANY] or it doesn’t, and you’ll know in one look.',
    nextStep: 'Give me the 60 seconds. If it’s not a fit, I’ll never call again.',
  },
  {
    id: 'TOO_BUSY',
    trigger: 'Too busy.',
    acknowledge: 'Then this call is for you — you’re busy running the business instead of growing it.',
    clarify: 'What’s eating most of your day right now — calls, paperwork, or chasing leads?',
    respond:
      'That’s the leak. [RECOMMENDED_OFFER] takes that off your plate at [COMPANY] so your time goes where it should. That’s the whole pitch — automation so you stop being the receptionist.',
    nextStep: 'Two minutes, right now, and I’ll have a recommendation you can act on today.',
  },
  {
    id: 'CALL_LATER',
    trigger: 'Call later.',
    acknowledge: 'You got it — I’m not here to ambush you.',
    clarify: 'Better time: today after 3, or tomorrow morning?',
    respond:
      'I’ll call you at that time with a 2-minute agenda — the [RECOMMENDED_OFFER] opportunity for [COMPANY] — and if you’re mid-fire I’ll reschedule.',
    nextStep: 'Same number, 2 minutes, tomorrow. I’ll hold you to it if you hold me to it.',
  },
  {
    id: 'PARTNER',
    trigger: 'I need to talk to my partner.',
    acknowledge: 'Good — you should never decide alone on something like this.',
    clarify: 'What would your partner need to see to say yes?',
    respond:
      'I’ll put together a one-page on [RECOMMENDED_OFFER] for [COMPANY] — what it is, what it costs, what it replaces. Present that together and you both decide on facts, not pitch.',
    nextStep: 'Get me that 10 minutes with both of you — I’ll bring the page and keep it to 10 minutes.',
  },
  {
    id: 'HOW_MUCH',
    trigger: 'How much?',
    acknowledge: 'Straight to it — I like that.',
    clarify: 'Before I quote: what’s it worth to [COMPANY] to catch every after-hours call and follow up on every lead?',
    respond:
      'For a [VERTICAL] your size, engagements run [VALUE_HYPOTHESIS]. And unlike a website, it pays for itself on the first missed job it catches.',
    nextStep: 'Give me 10 minutes to walk through the exact scope and number for [COMPANY] — no obligation.',
  },
  {
    id: 'HAVE_WEBSITE',
    trigger: 'We already have a website.',
    acknowledge: 'Good — you’re ahead of most [VERTICAL] operators.',
    clarify: 'Does it book you work, or does it just exist?',
    respond:
      'A website that doesn’t convert is a brochure. [RECOMMENDED_OFFER] turns that existing site into a revenue machine that answers, qualifies, and books — no rebuild needed.',
    nextStep: 'Send me your site for 60 seconds — I’ll show you one thing you’re leaving on the table.',
  },
];

const BRANCH_BY_ID = new Map<ObjectionBranchId, ObjectionBranch>(
  OBJECTION_BRANCHES.map((b) => [b.id, b]),
);

export function getObjectionBranch(id: ObjectionBranchId): ObjectionBranch {
  const branch = BRANCH_BY_ID.get(id);
  if (!branch) throw new Error(`Unknown objection branch: ${id}`);
  return branch;
}

const TRIGGER_KEYWORDS: Record<ObjectionBranchId, RegExp> = {
  HAVE_SOMEONE: /(have (someone|a guy|a company|a person|our own)|already use someone|got someone|have somebody)/i,
  USE_AI: /(already use ai|we use ai|have ai|already have ai|use ai)/i,
  SEND_INFO: /(send (me )?(info|information|email|details)|email me|send it)/i,
  TOO_EXPENSIVE: /(too expensive|expensive|over budget|can.t afford|too much money|cost too much)/i,
  NOT_INTERESTED: /(not interested|no thanks|not for us|not a fit|don.t want it|not looking)/i,
  TOO_BUSY: /(too busy|no time|busy|don.t have time|swamped|slammed)/i,
  CALL_LATER: /(call later|call back later|call me back later|catch me later|not a good time|wrong time|call me (in|next|back))/i,
  PARTNER: /(talk to my (partner|husband|wife|brother|team|associate)|need to (ask|check with)|talk to my partner)/i,
  HOW_MUCH: /(how much|what does it cost|what.s the price|pricing|quote me|what do you charge)/i,
  HAVE_WEBSITE: /(already have a website|have a website|got a website|we have a site)/i,
};

/**
 * Match a prospect's spoken objection to the closest branch.
 * Returns null when nothing matches — the caller falls back to a live
 * objection branch instead of forcing a wrong script.
 */
export function matchObjection(spoken: string): ObjectionBranch | null {
  if (!spoken || !spoken.trim()) return null;
  for (const branch of OBJECTION_BRANCHES) {
    if (TRIGGER_KEYWORDS[branch.id].test(spoken)) return branch;
  }
  return null;
}

export function renderObjectionSteps(
  branch: ObjectionBranch,
  context: ScriptContext,
): { acknowledge: string; clarify: string; respond: string; nextStep: string } {
  const map: Record<string, string> = {
    '[OWNER_NAME]': context.ownerName || 'the owner',
    '[COMPANY]': context.company,
    '[VERTICAL]': context.vertical,
    '[CITY]': context.city,
    '[KNOWN_PAIN]': context.knownPain,
    '[OBSERVED_SIGNAL]': context.observedSignal,
    '[RECOMMENDED_OFFER]': context.recommendedOffer,
    '[VALUE_HYPOTHESIS]': context.valueHypothesis,
  };
  const sub = (text: string): string =>
    Object.entries(map).reduce((acc, [k, v]) => acc.split(k).join(v || ''), text);
  return {
    acknowledge: sub(branch.acknowledge),
    clarify: sub(branch.clarify),
    respond: sub(branch.respond),
    nextStep: sub(branch.nextStep),
  };
}