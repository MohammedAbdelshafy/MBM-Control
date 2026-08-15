import { describe, it, expect } from 'vitest';
import {
  VerticalRegistry,
  computeVerticalScore,
  detectSignal,
  computeContactabilityScore,
} from '../src/verticals';
import type { BusinessEvidence, SignalDef } from '../src/verticals';
import { SCORE_DIMENSIONS } from '../src/verticals/types';

const registry = new VerticalRegistry();

function hvacHighOpportunity(): BusinessEvidence {
  return {
    company: 'Arctic Breeze Heating & Air',
    website: 'https://arcticbreeze.example',
    location: { city: 'Dallas', state: 'TX' },
    websiteQuality: { hasWebsite: true, outdated: true, mobileResponsive: false },
    digitalMaturity: { hasOnlineBooking: false, leadCaptureForm: false, liveChat: false },
    bookingWorkflow: { manualOnly: true, responseTimeHours: 9 },
    companySizeIndicators: { employees: 12, technicians: 8, locations: 3, reviewCount: 240 },
    reviewActivity: { reviewCount: 240, rating: 4.6, recencyDays: 21 },
    automationOpportunitySignals: [
      'manual dispatch',
      'manual estimate',
      'no crm',
      'missed after-hours calls',
      'no maintenance plan follow-up',
    ],
    source: 'County Business Registry',
    sourceUrl: 'https://registry.example/arctic-breeze',
    retrievedAt: new Date().toISOString(),
  };
}

function hvacLowOpportunity(): BusinessEvidence {
  return {
    company: 'Prestige Climate Systems',
    website: 'https://prestigeclimate.example',
    location: { city: 'Frisco', state: 'TX' },
    websiteQuality: { hasWebsite: true, outdated: false, mobileResponsive: true },
    digitalMaturity: { hasOnlineBooking: true, leadCaptureForm: true, liveChat: true, crmInUse: true },
    bookingWorkflow: { manualOnly: false, responseTimeHours: 1 },
    companySizeIndicators: { employees: 2, locations: 1, reviewCount: 5 },
    reviewActivity: { reviewCount: 5, rating: 4.1, recencyDays: 200 },
    source: 'County Business Registry',
    sourceUrl: 'https://registry.example/prestige-climate',
    retrievedAt: new Date().toISOString(),
  };
}

describe('Vertical Scoring Engine — buying probability, not industry', () => {
  it('scores all eight dimensions with a reason trace', () => {
    const vertical = registry.require('hvac');
    const score = computeVerticalScore(vertical, hvacHighOpportunity());
    for (const dim of SCORE_DIMENSIONS) {
      const ds = score.dimensionScores[dim];
      expect(ds.score).toBeGreaterThanOrEqual(0);
      expect(ds.score).toBeLessThanOrEqual(100);
      expect(typeof ds.reason).toBe('string');
    }
    expect(score.reasonTrace.length).toBe(8);
    expect(score.buyingProbabilityScore).toBeGreaterThanOrEqual(0);
    expect(score.buyingProbabilityScore).toBeLessThanOrEqual(100);
    expect(score.leadScore).toBe(score.buyingProbabilityScore);
  });

  it('ranks a high digital-gap, high-pain HVAC company above a modern low-pain one', () => {
    const vertical = registry.require('hvac');
    const high = computeVerticalScore(vertical, hvacHighOpportunity());
    const low = computeVerticalScore(vertical, hvacLowOpportunity());
    expect(high.buyingProbabilityScore).toBeGreaterThan(low.buyingProbabilityScore);
  });

  it('scores pain, digital gap, and automation higher when signals are evidenced', () => {
    const vertical = registry.require('hvac');
    const high = computeVerticalScore(vertical, hvacHighOpportunity());
    const low = computeVerticalScore(vertical, hvacLowOpportunity());
    expect(high.dimensionScores.pain.score).toBeGreaterThan(low.dimensionScores.pain.score);
    expect(high.dimensionScores.digitalGap.score).toBeGreaterThan(low.dimensionScores.digitalGap.score);
    expect(high.dimensionScores.automationPotential.score).toBeGreaterThan(low.dimensionScores.automationPotential.score);
  });

  it('detects concrete signals from evidence deterministically', () => {
    const sig = (id: string, label: string, weight = 1): SignalDef => ({ id, label, weight });
    const high = hvacHighOpportunity();
    expect(detectSignal(sig('no_online_booking', 'No online booking'), high)).toBe(true);
    expect(detectSignal(sig('outdated_site', 'Outdated website'), high)).toBe(true);
    expect(detectSignal(sig('high_review_volume', 'Strong review volume'), high)).toBe(true);
    expect(detectSignal(sig('multiple_locations', 'Multiple locations'), high)).toBe(true);
    expect(detectSignal(sig('growing_labor', 'Growing labor'), high)).toBe(true);
    expect(detectSignal(sig('emergency_demand', 'Emergency demand'), high)).toBe(true);
    expect(detectSignal(sig('no_crm', 'No CRM'), high)).toBe(true);

    const low = hvacLowOpportunity();
    expect(detectSignal(sig('outdated_site', 'Outdated website'), low)).toBe(false);
    expect(detectSignal(sig('high_review_volume', 'Strong review volume'), low)).toBe(false);
    expect(detectSignal(sig('multiple_locations', 'Multiple locations'), low)).toBe(false);
  });

  it('contactability reflects the strength of the verified contact path', () => {
    const full: BusinessEvidence = {
      company: 'X',
      contact: { phone: '+12145551234', email: 'x@example.com', source: 'STATE_REGISTRY' },
      decisionMaker: { name: 'Jane Doe', title: 'Owner' },
      source: 'STATE_REGISTRY',
      retrievedAt: new Date().toISOString(),
    };
    const bare: BusinessEvidence = {
      company: 'Y',
      source: 'UNKNOWN',
      retrievedAt: new Date().toISOString(),
    };
    expect(computeContactabilityScore(full)).toBeGreaterThan(computeContactabilityScore(bare));
    expect(computeContactabilityScore(full)).toBe(100);
  });

  it('stays deterministic for identical evidence', () => {
    const vertical = registry.require('hvac');
    const a = computeVerticalScore(vertical, hvacHighOpportunity());
    const b = computeVerticalScore(vertical, hvacHighOpportunity());
    expect(a.buyingProbabilityScore).toBe(b.buyingProbabilityScore);
    expect(a.reasonTrace).toEqual(b.reasonTrace);
  });
});