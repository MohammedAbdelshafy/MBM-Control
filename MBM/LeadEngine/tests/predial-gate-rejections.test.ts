import { describe, it, expect } from 'vitest';
import { PreDialGateEngine } from '../src/pipeline/predial-gate';
import type { PropertyIdentity, OwnershipRecord, ContactEvidence } from '../src/pipeline/types';

const property: PropertyIdentity = {
  parcelId: '045-882-019-A',
  addressLine1: '1420 Ocean Drive',
  city: 'Miami Beach',
  state: 'FL',
  zip: '33139',
  county: 'Miami-Dade',
  propertyType: 'SINGLE_FAMILY',
  estimatedValue: 1250000,
};

const owner: OwnershipRecord = {
  ownerName: 'Marcus Vance',
  ownerType: 'INDIVIDUAL',
  mailingAddress: '1420 Ocean Drive, Miami Beach, FL 33139',
  isAbsentee: false,
  confidenceScore: 0.95,
  verifiedAt: new Date().toISOString(),
};

const contact: ContactEvidence = {
  contactName: 'Marcus Vance',
  phone: '3057684905',
  email: 'marcus.vance@example.com',
  source: 'CMS_NPI',
  carrierType: 'MOBILE',
  lineStatus: 'ACTIVE',
  dncStatus: 'CLEAN',
  confidenceScore: 0.96,
  extractedAt: new Date().toISOString(),
};

describe('PreDialGateEngine — previous-rejection guard', () => {
  it('exposes the noPreviousRejection field as true for a clean lead', () => {
    const engine = new PreDialGateEngine();
    const result = engine.evaluateGate(property, owner, contact, 'lead-clean');
    expect(result.noPreviousRejection).toBe(true);
    expect(result.isCallable).toBe(true);
  });

  it('blocks a lead that carries a previous rejection code', () => {
    const engine = new PreDialGateEngine();
    const result = engine.evaluateGate(property, owner, contact, 'lead-prev', ['BAD_NUMBER']);
    expect(result.noPreviousRejection).toBe(false);
    expect(result.isCallable).toBe(false);
    expect(result.rejectionReasons.some((r) => r.includes('PREVIOUSLY_REJECTED'))).toBe(true);
  });

  it('blocks on permanent dispositions seeded via applyPermanentDispositions', () => {
    const engine = new PreDialGateEngine();
    engine.applyPermanentDispositions([
      { phone: '3057684905', type: 'DNC', permanent: true },
    ]);

    const result = engine.evaluateGate(property, owner, contact, 'lead-dnc');
    expect(result.noSuppression).toBe(false);
    expect(result.isCallable).toBe(false);
    expect(result.rejectionReasons.some((r) => r.includes('SUPPRESSION_MATCH'))).toBe(true);
  });

  it('marks a number bad from BAD_NUMBER history (no dial ever again)', () => {
    const engine = new PreDialGateEngine();
    engine.applyPermanentDispositions([
      { phone: '+13057684905', type: 'BAD_NUMBER', permanent: true },
    ]);

    const result = engine.evaluateGate(property, owner, contact, 'lead-badnum');
    expect(result.noBadNumberHistory).toBe(false);
    expect(result.isCallable).toBe(false);
    expect(result.rejectionReasons.some((r) => r.includes('BAD_NUMBER_HISTORY'))).toBe(true);
  });

  it('recordDialOutcome WRONG_NUMBER feeds the previous-rejection set', () => {
    const engine = new PreDialGateEngine();
    engine.recordDialOutcome('3057684905', 'WRONG_NUMBER');

    const result = engine.evaluateGate(property, owner, contact, 'lead-wrong');
    expect(result.isCallable).toBe(false);
    expect(result.rejectionReasons.some((r) => r.includes('PREVIOUSLY_REJECTED'))).toBe(true);
  });
});