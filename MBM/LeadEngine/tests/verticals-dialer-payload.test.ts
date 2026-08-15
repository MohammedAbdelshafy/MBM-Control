import { describe, it, expect } from 'vitest';
import {
  VerticalRegistry,
  computeVerticalScore,
  analyzeOpportunity,
  buildDialerPayload,
  serializeDialerPayload,
} from '../src/verticals';
import type { BusinessEvidence, DialerPayload, TopCallRecord } from '../src/verticals';

const registry = new VerticalRegistry();

function recordFor(verticalId: string, overrides: Partial<BusinessEvidence> = {}): {
  evidence: BusinessEvidence;
  record: TopCallRecord;
} {
  const evidence: BusinessEvidence = {
    company: `${verticalId} example co`,
    website: 'https://example.test',
    location: { city: 'Dallas', state: 'TX' },
    decisionMaker: { name: 'Casey Owner', title: 'Owner', source: 'NPI' },
    contact: { phone: '+15125551234', email: 'casey@example.test', source: 'NPI' },
    websiteQuality: { hasWebsite: true, outdated: true },
    digitalMaturity: { hasOnlineBooking: false },
    bookingWorkflow: { manualOnly: true },
    aiOpportunitySignals: ['manual booking via phone', 'missed calls after hours'],
    automationOpportunitySignals: ['manual scheduling', 'no crm'],
    source: 'CMS NPI Registry API v2.1',
    retrievedAt: new Date().toISOString(),
    ...overrides,
  };
  const vertical = registry.require(verticalId);
  const score = computeVerticalScore(vertical, evidence);
  return { evidence, record: analyzeOpportunity({ vertical, evidence, score }) };
}

const VERTICAL_IDS = ['hvac', 'pilates', 'med_spas', 'dental', 'law_firms', 'insurance', 'property_management', 'construction'];

describe('One-Screen Dialer Payload — no research screen needed', () => {
  it('builds the full card for every required vertical', () => {
    for (const id of VERTICAL_IDS) {
      const { evidence, record } = recordFor(id);
      const payload = buildDialerPayload({ vertical: registry.require(id), opportunity: record, evidence });

      expect(payload.owner).toBe('Casey Owner');
      expect(payload.company).toBe(`${id} example co`);
      expect(payload.vertical).toBe(registry.require(id).name);
      expect(payload.verticalId).toBe(id);
      expect(payload.whyThisLead.length).toBeGreaterThan(20);
      expect(payload.recommendedOffer.length).toBeGreaterThan(0);
      expect(payload.opener.length).toBeGreaterThan(20);
      expect(payload.discovery.length).toBeGreaterThan(20);
      expect(payload.objection.length).toBeGreaterThan(20);
      expect(payload.close.length).toBeGreaterThan(20);
      expect(typeof payload.callability).toBe('number');
      expect(typeof payload.leadScore).toBe('number');
    }
  });

  it('carries phone, email, callability and lead score', () => {
    const { evidence, record } = recordFor('insurance');
    const payload = buildDialerPayload({ vertical: registry.require('insurance'), opportunity: record, evidence });

    expect(payload.phone).toBe('+15125551234');
    expect(payload.email).toBe('casey@example.test');
    expect(payload.callability).toBeGreaterThanOrEqual(0);
    expect(payload.callability).toBeLessThanOrEqual(100);
    expect(payload.leadScore).toBeGreaterThanOrEqual(0);
  });

  it('routes an OWNER title to a decision-maker route', () => {
    const { evidence, record } = recordFor('dental');
    const payload = buildDialerPayload({ vertical: registry.require('dental'), opportunity: record, evidence });

    expect(payload.ownerRouting.tier).toBe('OWNER');
    expect(payload.ownerRouting.isDecisionMaker).toBe(true);
  });

  it('routes a partner-title business to the PARTNER objection branch', () => {
    const { evidence, record } = recordFor('law_firms', {
      decisionMaker: { name: 'Pat Partner', title: 'Partner', source: 'NPI' },
    });
    const payload = buildDialerPayload({ vertical: registry.require('law_firms'), opportunity: record, evidence });

    expect(payload.ownerRouting.isDecisionMaker).toBe(true);
    expect(payload.objection.length).toBeGreaterThan(20);
    expect(payload.script.sections.OBJECTIONS).toContain('we already have someone');
  });

  it('honors an explicit objection branch override', () => {
    const { evidence, record } = recordFor('hvac');
    const payload = buildDialerPayload({
      vertical: registry.require('hvac'),
      opportunity: record,
      evidence,
      objectionBranchId: 'HOW_MUCH',
    });

    expect(payload.objection).toContain('USD');
  });

  it('embeds the full rendered script inside the payload', () => {
    const { evidence, record } = recordFor('construction');
    const payload: DialerPayload = buildDialerPayload({
      vertical: registry.require('construction'),
      opportunity: record,
      evidence,
    });

    expect(Object.keys(payload.script.sections)).toHaveLength(13);
    expect(payload.script.full).toContain('WHY THIS LEAD');
    expect(payload.script.full).toContain('FOLLOW-UP');
    expect(payload.opener).toBe(payload.script.sections.OPENING);
    expect(payload.close).toBe(payload.script.sections.FINAL_CLOSE);
  });

  it('serializes a one-screen card with the required labels', () => {
    const { evidence, record } = recordFor('med_spas');
    const payload = buildDialerPayload({ vertical: registry.require('med_spas'), opportunity: record, evidence });
    const text = serializeDialerPayload(payload);

    expect(text).toContain('OWNER:');
    expect(text).toContain('COMPANY:');
    expect(text).toContain('VERTICAL:');
    expect(text).toContain('WHY THIS LEAD:');
    expect(text).toContain('RECOMMENDED OFFER:');
    expect(text).toContain('OPENER:');
    expect(text).toContain('DISCOVERY:');
    expect(text).toContain('OBJECTION:');
    expect(text).toContain('CLOSE:');
    expect(text).toContain('CALLABILITY:');
    expect(text).toContain('LEAD SCORE:');
    expect(text).toContain('ROUTE:');
  });
});