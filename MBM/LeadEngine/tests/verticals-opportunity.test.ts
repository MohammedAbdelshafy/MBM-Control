import { describe, it, expect } from 'vitest';
import {
  VerticalRegistry,
  computeVerticalScore,
  analyzeOpportunity,
  pickRecommendedOffer,
  formatDealSize,
} from '../src/verticals';
import type { BusinessEvidence } from '../src/verticals';

const registry = new VerticalRegistry();

function pilatesEvidence(): BusinessEvidence {
  return {
    company: 'Core Balance Pilates',
    website: 'https://corebalance.example',
    location: { city: 'Austin', state: 'TX' },
    industry: 'Pilates',
    websiteQuality: { hasWebsite: true, outdated: true, templateSite: true, mobileResponsive: false },
    digitalMaturity: { hasOnlineBooking: false, leadCaptureForm: false },
    bookingWorkflow: { manualOnly: true, responseTimeHours: 6 },
    companySizeIndicators: { employees: 6, instructors: 6, reviewCount: 180 },
    reviewActivity: { reviewCount: 180, rating: 4.8, recencyDays: 14 },
    aiOpportunitySignals: ['manual booking via phone', 'no online scheduling', 'membership churn'],
    automationOpportunitySignals: ['manual scheduling', 'no crm', 'paper intake'],
    source: 'CMS NPI Registry API v2.1',
    sourceUrl: 'https://npiregistry.cms.hhs.gov/api/',
    retrievedAt: new Date().toISOString(),
  };
}

describe('Business Opportunity Analyzer — 20-point profile, offers, provenance', () => {
  it('produces the full 20-point opportunity profile', () => {
    const vertical = registry.require('pilates');
    const score = computeVerticalScore(vertical, pilatesEvidence());
    const op = analyzeOpportunity({ vertical, evidence: pilatesEvidence(), score });

    expect(op.company).toBe('Core Balance Pilates');
    expect(op.website).toBe('https://corebalance.example');
    expect(op.location.city).toBe('Austin');
    expect(op.location.state).toBe('TX');
    expect(op.industry).toBe('Pilates');
    expect(op.companySizeIndicators.employees).toBe(6);
    expect(op.companySizeIndicators.instructors).toBe(6);
    expect(op.websiteQuality.outdated).toBe(true);
    expect(op.digitalMaturity.hasOnlineBooking).toBe(false);
    expect(op.bookingWorkflow.manualOnly).toBe(true);
    expect(op.reviewActivity.reviewCount).toBe(180);
    expect(op.aiOpportunitySignals.length).toBeGreaterThan(0);
    expect(op.automationOpportunitySignals.length).toBeGreaterThan(0);
    expect(op.leadGenOpportunity.length).toBeGreaterThan(0);
    expect(op.recommendedOffer.length).toBeGreaterThan(0);
    expect(op.estimatedDealSize.min).toBeLessThanOrEqual(op.estimatedDealSize.max);
    expect(typeof op.leadScore).toBe('number');
    expect(typeof op.contactabilityScore).toBe('number');
    expect(typeof op.buyingProbability).toBe('number');
    expect(op.outreachAngle.length).toBeGreaterThan(0);
    expect(op.reasonTrace.length).toBe(8);
  });

  it('preserves provenance exactly and fabricates nothing', () => {
    const vertical = registry.require('pilates');
    const evidence = pilatesEvidence();
    const score = computeVerticalScore(vertical, evidence);
    const op = analyzeOpportunity({ vertical, evidence, score });

    expect(op.provenance.source).toBe('CMS NPI Registry API v2.1');
    expect(op.provenance.sourceUrl).toBe('https://npiregistry.cms.hhs.gov/api/');
    expect(op.provenance.retrievedAt).toBe(evidence.retrievedAt);
    // The decision maker is absent from evidence → stays null (no fabrication).
    expect(op.decisionMaker.name).toBeNull();
    expect(op.contact.phone).toBeNull();
  });

  it('recommends the highest-fit offer based on evidenced signals', () => {
    const vertical = registry.require('pilates');
    const offer = pickRecommendedOffer(vertical, pilatesEvidence());
    // Manual booking + churn + no online scheduling → booking automation family.
    expect(['appointment automation', 'AI front-desk']).toContain(offer);
  });

  it('recommends AI voice receptionist for a missed-call home-services operation', () => {
    const vertical = registry.require('hvac');
    const evidence: BusinessEvidence = {
      company: 'Express Air',
      website: 'https://expressair.example',
      websiteQuality: { hasWebsite: true, outdated: true },
      digitalMaturity: { hasOnlineBooking: false },
      bookingWorkflow: { manualOnly: true },
      aiOpportunitySignals: ['missed calls after hours', '24/7 emergency demand', 'voice reception needed'],
      source: 'STATE_LICENSE',
      retrievedAt: new Date().toISOString(),
    };
    const offer = pickRecommendedOffer(vertical, evidence);
    expect(offer).toBe('AI voice receptionist');
  });

  it('formats deal sizes as currency ranges', () => {
    expect(formatDealSize({ min: 4997, max: 15000, currency: 'USD', unit: 'monthly retainer' }))
      .toBe('$4,997–$15,000 USD · monthly retainer');
  });

  it('derives the narrative fields from evidence + vertical config', () => {
    const vertical = registry.require('pilates');
    const score = computeVerticalScore(vertical, pilatesEvidence());
    const op = analyzeOpportunity({ vertical, evidence: pilatesEvidence(), score });

    expect(op.who).toContain('Core Balance Pilates');
    expect(op.whyThem).toContain('Category: Pilates Studios');
    expect(op.whatProblem).toContain('no online booking');
    expect(op.whatWeSell).toContain('Recommended:');
    expect(op.whyNow).toContain('Digital gap');
    expect(op.estimatedValue).toContain('USD');
    expect(op.bestOutreachAngle).toContain('Deal ceiling');
  });
});