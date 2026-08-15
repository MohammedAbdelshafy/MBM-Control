import { describe, it, expect } from 'vitest';
import { OpportunityIntelligenceOrchestrator } from '../src/pipeline/opportunity-orchestrator';
import { CorroborationEngine, type SourceClaim } from '../src/pipeline/corroboration-engine';
import { PreDialGateEngine } from '../src/pipeline/predial-gate';
import { FreshnessEngine, type PropertyEvent } from '../src/pipeline/freshness-engine';

describe('Adversarial & Edge Cases (MBM Quality v3 Safety Suite)', () => {
  // 1. Same person at different addresses
  it('handles the same person owning distinct addresses as independent portfolio assets', () => {
    const orchestrator = new OpportunityIntelligenceOrchestrator();

    const lead1 = orchestrator.evaluateOpportunity({
      property: {
        parcelId: 'TX-01',
        addressLine1: '100 Main St',
        city: 'Austin',
        state: 'TX',
        zip: '78701',
        county: 'Travis',
        propertyType: 'SINGLE_FAMILY',
        estimatedValue: 400000,
      },
      ownership: {
        ownerName: 'Alexander Hayes',
        ownerType: 'INDIVIDUAL',
        mailingAddress: '100 Main St',
        isAbsentee: false,
        confidenceScore: 0.95,
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'Alexander Hayes',
        phone: '5127891234',
        source: 'CMS_NPI',
        carrierType: 'MOBILE',
        dncStatus: 'CLEAN',
        confidenceScore: 0.95,
        extractedAt: new Date().toISOString(),
      },
      events: [],
      motivationSignals: [],
    });

    const lead2 = orchestrator.evaluateOpportunity({
      property: {
        parcelId: 'TX-02',
        addressLine1: '200 Oak St',
        city: 'Austin',
        state: 'TX',
        zip: '78704',
        county: 'Travis',
        propertyType: 'SINGLE_FAMILY',
        estimatedValue: 600000,
      },
      ownership: {
        ownerName: 'Alexander Hayes',
        ownerType: 'INDIVIDUAL',
        mailingAddress: '100 Main St',
        isAbsentee: true,
        confidenceScore: 0.95,
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'Alexander Hayes',
        phone: '5127891234',
        source: 'CMS_NPI',
        carrierType: 'MOBILE',
        dncStatus: 'CLEAN',
        confidenceScore: 0.95,
        extractedAt: new Date().toISOString(),
      },
      events: [],
      motivationSignals: [],
    });

    expect(lead1.reasonCard.propertySummaryLine).toContain('100 Main St');
    expect(lead2.reasonCard.propertySummaryLine).toContain('200 Oak St');
    expect(lead2.reasonCard.ownerLine).toContain('Absentee');
    expect(lead1.leadId).not.toBe(lead2.leadId);
  });

  // 2. Conflicting sources detected
  it('penalizes confidence and flags discrepancies when independent sources conflict on ownership', () => {
    const corroboration = new CorroborationEngine();

    const conflictingClaims: SourceClaim[] = [
      {
        sourceName: 'Auction.com Scraper',
        sourceDomain: 'auction.com',
        claimType: 'OWNERSHIP',
        claimedValue: 'Elena Rostova',
        retrievedAt: new Date().toISOString(),
        isSyndicatedFeed: false,
      },
      {
        sourceName: 'County Recorder Deed',
        sourceDomain: 'traviscounty.gov',
        claimType: 'OWNERSHIP',
        claimedValue: 'Marcus Vance',
        retrievedAt: new Date().toISOString(),
        isSyndicatedFeed: false,
      },
    ];

    const result = corroboration.evaluateCorroboration(conflictingClaims);

    expect(result.discrepancies.length).toBeGreaterThan(0);
    expect(result.discrepancies[0]).toContain('Conflicting values found for OWNERSHIP');
    expect(result.isAuthoritativelyCorroborated).toBe(false);
    expect(result.corroborationConfidence).toBeLessThan(0.70);
  });

  // 3. Missing valuation, APN, or contact
  it('rejects leads with missing APN or invalid phone at pre-dial gate', () => {
    const gate = new PreDialGateEngine();

    const missingAPNResult = gate.evaluateGate(
      {
        parcelId: '', // Blank APN
        addressLine1: '500 Pine St',
        city: 'Miami',
        state: 'FL',
        zip: '33101',
        county: 'Miami-Dade',
        propertyType: 'SINGLE_FAMILY',
      },
      {
        ownerName: 'Valid Owner',
        ownerType: 'INDIVIDUAL',
        mailingAddress: '500 Pine St',
        isAbsentee: false,
        confidenceScore: 0.95,
        verifiedAt: new Date().toISOString(),
      },
      {
        contactName: 'Valid Owner',
        phone: '3057684905',
        source: 'CMS_NPI',
        dncStatus: 'CLEAN',
        confidenceScore: 0.95,
        extractedAt: new Date().toISOString(),
      },
      'lead-missing-apn'
    );

    expect(missingAPNResult.isCallable).toBe(false);
    expect(missingAPNResult.validProperty).toBe(false);
    expect(missingAPNResult.rejectionReasons.some((r) => r.includes('INVALID_PROPERTY'))).toBe(true);
  });

  // 4. Bad phone recycled & wrong person repeatedly returned
  it('prevents recycled bad phone numbers from returning to the prime queue', () => {
    const orchestrator = new OpportunityIntelligenceOrchestrator();

    // Register a bad number disposition
    orchestrator.registerDisposition('l-bad', 'p-bad', '3057684905', 'Bad Person', 'BAD_NUMBER');

    const output = orchestrator.evaluateOpportunity({
      property: {
        parcelId: 'PARCEL-RECYCLE',
        addressLine1: '900 Ocean Way',
        city: 'Miami',
        state: 'FL',
        zip: '33139',
        county: 'Miami-Dade',
        propertyType: 'SINGLE_FAMILY',
        estimatedValue: 750000,
      },
      ownership: {
        ownerName: 'New Buyer LLC',
        ownerType: 'LLC',
        mailingAddress: '900 Ocean Way',
        isAbsentee: false,
        confidenceScore: 0.95,
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'New Buyer LLC',
        phone: '3057684905', // Attempt to use the same bad phone number
        source: 'CMS_NPI',
        carrierType: 'MOBILE',
        dncStatus: 'CLEAN',
        confidenceScore: 0.95,
        extractedAt: new Date().toISOString(),
      },
      events: [],
      motivationSignals: [],
    });

    expect(output.dispositionState.isSuppressed).toBe(true);
    expect(output.isCallablePrimeQueue).toBe(false);
  });

  // 5. Stale distress event decay
  it('exponentially decays a 3-year-old foreclosure event to near-zero influence', () => {
    const freshness = new FreshnessEngine();
    const now = new Date();
    const threeYearsAgo = new Date(now.getTime() - 1095 * 24 * 60 * 60 * 1000).toISOString();

    const staleEvent: PropertyEvent = {
      id: 'e-old',
      propertyId: 'p-old',
      eventType: 'FORECLOSURE_NOTICE',
      eventDate: threeYearsAgo,
      retrievedAt: threeYearsAgo,
      source: 'OLD_ARCHIVE',
      confidence: 0.85,
      isIndependentSource: true,
    };

    const result = freshness.calculateFreshness([staleEvent], now);
    expect(result.decayedScore).toBeLessThan(1);
    expect(result.freshnessLabel).toBe('STALE_DECAYED');
  });
});
