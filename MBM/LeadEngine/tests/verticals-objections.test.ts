import { describe, it, expect } from 'vitest';
import {
  OBJECTION_BRANCHES,
  getObjectionBranch,
  matchObjection,
  renderObjectionSteps,
} from '../src/verticals';
import type { ObjectionBranchId, ScriptContext } from '../src/verticals';

const CONTEXT: ScriptContext = {
  ownerName: 'Dan',
  company: 'Summit HVAC',
  vertical: 'HVAC & Air Conditioning',
  city: 'Austin',
  knownPain: 'missed after-hours calls',
  observedSignal: 'manual booking workflow',
  recommendedOffer: 'AI voice receptionist',
  valueHypothesis: '$4,997–$15,000 USD · monthly retainer',
};

describe('Objection Branches — ACKNOWLEDGE → CLARIFY → RESPOND → NEXT STEP', () => {
  it('ships all ten required branches', () => {
    const ids = OBJECTION_BRANCHES.map((b) => b.id);
    expect(ids).toEqual(
      expect.arrayContaining([
        'HAVE_SOMEONE',
        'USE_AI',
        'SEND_INFO',
        'TOO_EXPENSIVE',
        'NOT_INTERESTED',
        'TOO_BUSY',
        'CALL_LATER',
        'PARTNER',
        'HOW_MUCH',
        'HAVE_WEBSITE',
      ]),
    );
    expect(OBJECTION_BRANCHES).toHaveLength(10);
  });

  it('every branch has all four steps populated', () => {
    for (const branch of OBJECTION_BRANCHES) {
      expect(branch.acknowledge.length).toBeGreaterThan(0);
      expect(branch.clarify.length).toBeGreaterThan(0);
      expect(branch.respond.length).toBeGreaterThan(0);
      expect(branch.nextStep.length).toBeGreaterThan(0);
    }
  });

  it('matches spoken objections to the closest branch', () => {
    expect(matchObjection('We already have someone doing this')?.id).toBe('HAVE_SOMEONE');
    expect(matchObjection('We already use AI for everything')?.id).toBe('USE_AI');
    expect(matchObjection('Just send me information')?.id).toBe('SEND_INFO');
    expect(matchObjection('That is too expensive for us')?.id).toBe('TOO_EXPENSIVE');
    expect(matchObjection('Honestly not interested')?.id).toBe('NOT_INTERESTED');
    expect(matchObjection('I am too busy right now')?.id).toBe('TOO_BUSY');
    expect(matchObjection('Call me back later this week')?.id).toBe('CALL_LATER');
    expect(matchObjection('I need to talk to my partner')?.id).toBe('PARTNER');
    expect(matchObjection('How much does it cost?')?.id).toBe('HOW_MUCH');
    expect(matchObjection('We already have a website')?.id).toBe('HAVE_WEBSITE');
  });

  it('returns null (no forced script) for unmatched objections', () => {
    expect(matchObjection('I am literally in a meeting with the fire department')).toBeNull();
    expect(matchObjection('')).toBeNull();
  });

  it('looks up branches by id and rejects unknown ids', () => {
    expect(getObjectionBranch('TOO_BUSY').id).toBe('TOO_BUSY');
    expect(() => getObjectionBranch('NOPE' as ObjectionBranchId)).toThrow();
  });

  it('renders steps with dynamic placeholders substituted', () => {
    const branch = getObjectionBranch('TOO_EXPENSIVE');
    const steps = renderObjectionSteps(branch, CONTEXT);
    expect(steps.respond).toContain('Summit HVAC');
    expect(steps.respond).toContain('AI voice receptionist');
    expect(steps.respond).not.toContain('[COMPANY]');
    expect(steps.respond).not.toContain('[RECOMMENDED_OFFER]');
  });

  it('renders the offer value hypothesis into pricing objection responses', () => {
    const steps = renderObjectionSteps(getObjectionBranch('HOW_MUCH'), CONTEXT);
    expect(steps.respond).toContain('$4,997–$15,000');
    expect(steps.clarify).toContain('Summit HVAC');
  });
});