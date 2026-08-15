import { describe, it, expect } from 'vitest';
import {
  classifyOwnerTitle,
  routeDecisionMaker,
  routeEvidenceOwner,
  ownerFirstSort,
  tierRank,
} from '../src/verticals';
import type { BusinessEvidence, TopCallRecord } from '../src/verticals';

describe('Owner-First Routing — qualified decision makers win dialer slots', () => {
  it('classifies owner-tier titles in priority order', () => {
    expect(classifyOwnerTitle('Owner')).toBe('OWNER');
    expect(classifyOwnerTitle('Co-Founder & CEO')).toBe('FOUNDER');
    expect(classifyOwnerTitle('CEO')).toBe('CEO');
    expect(classifyOwnerTitle('President')).toBe('PRESIDENT');
    expect(classifyOwnerTitle('Principal')).toBe('PRINCIPAL');
    expect(classifyOwnerTitle('Managing Member')).toBe('MANAGING_MEMBER');
    expect(classifyOwnerTitle('Managing Partner')).toBe('MANAGING_PARTNER');
    expect(classifyOwnerTitle('DMD')).toBe('OWNER');
    expect(classifyOwnerTitle('Attorney')).toBe('OWNER');
  });

  it('sinks staff titles below decision makers', () => {
    expect(classifyOwnerTitle('Receptionist')).toBe('STAFF');
    expect(classifyOwnerTitle('Front Desk')).toBe('STAFF');
    expect(classifyOwnerTitle('Service Manager')).toBe('DIRECTOR');
    expect(classifyOwnerTitle('Office Manager')).toBe('DIRECTOR');
    expect(classifyOwnerTitle('Sales Associate')).toBe('STAFF');
    expect(classifyOwnerTitle('')).toBe('UNKNOWN');
    expect(classifyOwnerTitle(null)).toBe('UNKNOWN');
  });

  it('routes decision-maker evidence to a decision-maker result', () => {
    const result = routeDecisionMaker({ name: 'Jane Roe', title: 'Owner', source: 'STATE_LICENSE' });
    expect(result.tier).toBe('OWNER');
    expect(result.isDecisionMaker).toBe(true);
    expect(result.ownerName).toBe('Jane Roe');
    expect(result.routeLabel).toContain('decision maker');
  });

  it('never guesses an unknown title', () => {
    const result = routeDecisionMaker({ name: 'Pat', title: null, source: 'NPI' });
    expect(result.tier).toBe('UNKNOWN');
    expect(result.isDecisionMaker).toBe(false);
    expect(result.routeLabel).toBe('Unknown contact');
  });

  it('routes evidence via its decision maker field', () => {
    const evidence: BusinessEvidence = {
      company: 'Peak Pilates',
      decisionMaker: { name: 'Amy', title: 'Founder', source: 'NPI' },
      source: 'NPI',
      retrievedAt: new Date().toISOString(),
    };
    const result = routeEvidenceOwner(evidence);
    expect(result.tier).toBe('FOUNDER');
    expect(result.isDecisionMaker).toBe(true);
  });

  it('sorts owner-first, sinking staff and unknown contacts', () => {
    const make = (over: Partial<TopCallRecord> & { company: string }): TopCallRecord =>
      ({ ...baseRecord(), ...over }) as TopCallRecord;

    const owner = make({
      company: 'Owner HVAC',
      decisionMaker: { name: 'Al', title: 'Owner', source: 'NPI' },
      buyingProbability: 40,
      contactabilityScore: 50,
    });
    const staff = make({
      company: 'Staff HVAC',
      decisionMaker: { name: 'Sam', title: 'Receptionist', source: 'NPI' },
      buyingProbability: 90,
      contactabilityScore: 95,
    });
    const unknown = make({
      company: 'Unknown HVAC',
      decisionMaker: { name: 'U', title: null, source: 'NPI' },
      buyingProbability: 85,
      contactabilityScore: 85,
    });

    const sorted = ownerFirstSort([staff, unknown, owner]);
    expect(sorted[0].company).toBe('Owner HVAC');
    expect(sorted[1].company).toBe('Staff HVAC');
    expect(sorted[2].company).toBe('Unknown HVAC');
  });

  it('ranks owner above CEO above principal by tier weight', () => {
    expect(tierRank('OWNER')).toBeGreaterThan(tierRank('CEO'));
    expect(tierRank('CEO')).toBeGreaterThan(tierRank('PRESIDENT'));
    expect(tierRank('MANAGING_MEMBER')).toBeGreaterThan(tierRank('MANAGER'));
    expect(tierRank('UNKNOWN')).toBe(0);
  });
});

function baseRecord(): Partial<TopCallRecord> {
  return {
    verticalId: 'hvac',
    verticalName: 'HVAC & Air Conditioning',
    category: 'HOME_SERVICES',
    company: 'x',
    website: null,
    location: { city: null, state: null, country: null },
    industry: null,
    companySizeIndicators: {},
    decisionMaker: {},
    contact: {},
    websiteQuality: {},
    digitalMaturity: {},
    bookingWorkflow: {},
    reviewActivity: {},
    aiOpportunitySignals: [],
    automationOpportunitySignals: [],
    appSoftwareOpportunitySignals: [],
    leadGenOpportunity: '',
    recommendedOffer: '',
    estimatedDealSize: { min: 0, max: 0, currency: 'USD', unit: 'x' },
    leadScore: 0,
    contactabilityScore: 0,
    buyingProbability: 0,
    outreachAngle: '',
    reasonTrace: [],
    provenance: { source: '', sourceUrl: null, retrievedAt: new Date().toISOString() },
    who: '',
    whyThem: '',
    whatProblem: '',
    whatWeSell: '',
    whyNow: '',
    estimatedValue: '',
    bestOutreachAngle: '',
  };
}