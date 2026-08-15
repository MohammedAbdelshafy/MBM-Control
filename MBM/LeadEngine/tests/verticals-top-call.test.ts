import { describe, it, expect } from 'vitest';
import {
  VerticalRegistry,
  rankOpportunities,
  buildTopCallList,
} from '../src/verticals';
import type { BusinessEvidence } from '../src/verticals';

const registry = new VerticalRegistry();

function evidence(
  company: string,
  opts: Partial<BusinessEvidence> = {},
): BusinessEvidence {
  return {
    company,
    website: opts.website ?? 'https://example.com',
    location: { city: 'Dallas', state: 'TX' },
    websiteQuality: opts.websiteQuality ?? { hasWebsite: true },
    digitalMaturity: opts.digitalMaturity ?? {},
    companySizeIndicators: opts.companySizeIndicators ?? { employees: 5 },
    reviewActivity: opts.reviewActivity ?? { reviewCount: 10, rating: 4.2, recencyDays: 30 },
    contact: opts.contact ?? { phone: '+12145550101', source: 'STATE_REGISTRY' },
    source: opts.source ?? 'STATE_REGISTRY',
    retrievedAt: opts.retrievedAt ?? new Date().toISOString(),
    ...opts,
  };
}

function highOpp(company: string): BusinessEvidence {
  return evidence(company, {
    websiteQuality: { hasWebsite: true, outdated: true, mobileResponsive: false },
    digitalMaturity: { hasOnlineBooking: false, leadCaptureForm: false },
    bookingWorkflow: { manualOnly: true, responseTimeHours: 8 },
    companySizeIndicators: { employees: 15, technicians: 9, locations: 3, reviewCount: 300 },
    reviewActivity: { reviewCount: 300, rating: 4.7, recencyDays: 10 },
    aiOpportunitySignals: ['missed after-hours calls', 'no online booking', '24/7 demand'],
    automationOpportunitySignals: ['manual dispatch', 'manual estimate', 'no crm'],
  });
}

function lowOpp(company: string): BusinessEvidence {
  return evidence(company, {
    websiteQuality: { hasWebsite: true, outdated: false, mobileResponsive: true },
    digitalMaturity: { hasOnlineBooking: true, leadCaptureForm: true, liveChat: true, crmInUse: true },
    bookingWorkflow: { manualOnly: false, responseTimeHours: 1 },
    companySizeIndicators: { employees: 2, locations: 1, reviewCount: 6 },
    reviewActivity: { reviewCount: 6, rating: 4.0, recencyDays: 300 },
  });
}

describe('Top-100 Call List — ranks by buying probability', () => {
  it('ranks high-opportunity businesses above low-opportunity ones regardless of order', () => {
    const records = [
      { verticalId: 'hvac', evidence: lowOpp('Prestige Climate') },
      { verticalId: 'hvac', evidence: highOpp('Arctic Breeze') },
      { verticalId: 'hvac', evidence: highOpp('Summit Air') },
    ];
    const ranked = rankOpportunities(
      records.map((r) => ({ vertical: registry.require(r.verticalId), evidence: r.evidence })),
    );
    const names = ranked.map((r) => r.evidence.company);
    expect(names[0]).toBe('Arctic Breeze');
    expect(names[1]).toBe('Summit Air');
    expect(names[2]).toBe('Prestige Climate');
  });

  it('builds a top-N list with every call-ready narrative field', () => {
    const records = [
      { verticalId: 'plumbing', evidence: highOpp('Rooter Express') },
      { verticalId: 'hvac', evidence: highOpp('Arctic Breeze') },
      { verticalId: 'roofing', evidence: highOpp('Summit Roofing') },
      { verticalId: 'pilates', evidence: evidence('Core Balance', {
        digitalMaturity: { hasOnlineBooking: false },
        bookingWorkflow: { manualOnly: true },
        aiOpportunitySignals: ['manual booking', 'membership churn'],
      }) },
      { verticalId: 'logistics', evidence: evidence('Fast Freight', {
        digitalMaturity: { hasOnlineBooking: false },
        aiOpportunitySignals: ['manual quoting'],
        automationOpportunitySignals: ['manual rfq'],
      }) },
    ];
    const top = buildTopCallList(registry, records, { limit: 3 });
    expect(top.length).toBe(3);
    for (const record of top) {
      expect(record.buyingProbability).toBeGreaterThanOrEqual(0);
      expect(record.who.length).toBeGreaterThan(0);
      expect(record.whyThem.length).toBeGreaterThan(0);
      expect(record.whatProblem.length).toBeGreaterThan(0);
      expect(record.whatWeSell.length).toBeGreaterThan(0);
      expect(record.whyNow.length).toBeGreaterThan(0);
      expect(record.estimatedValue.length).toBeGreaterThan(0);
      expect(record.bestOutreachAngle.length).toBeGreaterThan(0);
      expect(record.provenance.source).toBeTruthy();
    }
  });

  it('respects the min buying probability and contact-path filters', () => {
    const records = [
      { verticalId: 'hvac', evidence: highOpp('Arctic Breeze') },
      { verticalId: 'hvac', evidence: lowOpp('Prestige Climate') },
    ];
    const noContact = evidence('No Phone Co', { contact: { phone: null, email: null, source: null } });
    const withContact = highOpp('Has Phone Co');
    const filtered = buildTopCallList(registry, [...records, { verticalId: 'hvac', evidence: noContact }, { verticalId: 'hvac', evidence: withContact }], {
      minBuyingProbability: 60,
      requireContactPath: true,
    });
    const names = filtered.map((r) => r.company);
    expect(names).not.toContain('No Phone Co');
    expect(names).not.toContain('Prestige Climate');
  });

  it('can filter to specific vertical ids', () => {
    const records = [
      { verticalId: 'hvac', evidence: highOpp('Arctic Breeze') },
      { verticalId: 'pilates', evidence: highOpp('Core Balance') },
    ];
    const onlyHvac = buildTopCallList(registry, records, { verticalIds: ['hvac'] });
    expect(onlyHvac.every((r) => r.verticalId === 'hvac')).toBe(true);
  });
});