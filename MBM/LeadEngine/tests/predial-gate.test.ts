import { describe, it, expect } from 'vitest';
import { PreDialGateEngine } from '../src/pipeline/predial-gate';
import type { PropertyIdentity, OwnershipRecord, ContactEvidence } from '../src/pipeline/types';

describe('PreDialGateEngine — Hard Pre-Dial Verification Gate', () => {
  const validProperty: PropertyIdentity = {
    parcelId: '045-882-019-A',
    addressLine1: '1420 Ocean Drive',
    city: 'Miami Beach',
    state: 'FL',
    zip: '33139',
    county: 'Miami-Dade',
    propertyType: 'SINGLE_FAMILY',
    estimatedValue: 1250000,
  };

  const validOwner: OwnershipRecord = {
    ownerName: 'Marcus Vance',
    ownerType: 'INDIVIDUAL',
    mailingAddress: '1420 Ocean Drive, Miami Beach, FL 33139',
    isAbsentee: false,
    confidenceScore: 0.95,
    verifiedAt: new Date().toISOString(),
  };

  const validContact: ContactEvidence = {
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

  it('passes a fully verified, valid lead through the gate', () => {
    const engine = new PreDialGateEngine();
    const result = engine.evaluateGate(validProperty, validOwner, validContact, 'lead-1');

    expect(result.isCallable).toBe(true);
    expect(result.validProperty).toBe(true);
    expect(result.validOwnerEntity).toBe(true);
    expect(result.validContactSource).toBe(true);
    expect(result.phoneQualityPass).toBe(true);
    expect(result.noDuplicate).toBe(true);
    expect(result.noSuppression).toBe(true);
    expect(result.noBadNumberHistory).toBe(true);
    expect(result.rejectionReasons.length).toBe(0);
  });

  it('rejects fake/placeholder phone numbers (555 exchanges & repeating digits)', () => {
    const engine = new PreDialGateEngine();
    const fakeContact: ContactEvidence = {
      ...validContact,
      phone: '3055551234',
    };

    const result = engine.evaluateGate(validProperty, validOwner, fakeContact, 'lead-2');
    expect(result.isCallable).toBe(false);
    expect(result.phoneQualityPass).toBe(false);
    expect(result.rejectionReasons.some((r) => r.includes('PHONE_QUALITY_FAILED'))).toBe(true);
  });

  it('rejects fake/placeholder owner names', () => {
    const engine = new PreDialGateEngine();
    const fakeOwner: OwnershipRecord = {
      ...validOwner,
      ownerName: 'Property Owner Action Required',
    };

    const result = engine.evaluateGate(validProperty, fakeOwner, validContact, 'lead-3');
    expect(result.isCallable).toBe(false);
    expect(result.validOwnerEntity).toBe(false);
    expect(result.rejectionReasons.some((r) => r.includes('INVALID_OWNER'))).toBe(true);
  });

  it('rejects leads matching account suppression list', () => {
    const engine = new PreDialGateEngine({
      suppressionList: ['3057684905'],
    });

    const result = engine.evaluateGate(validProperty, validOwner, validContact, 'lead-4');
    expect(result.isCallable).toBe(false);
    expect(result.noSuppression).toBe(false);
    expect(result.rejectionReasons.some((r) => r.includes('SUPPRESSION_MATCH'))).toBe(true);
  });

  it('rejects numbers with previous bad-number/disconnected history', () => {
    const engine = new PreDialGateEngine({
      badNumbers: ['3057684905'],
    });

    const result = engine.evaluateGate(validProperty, validOwner, validContact, 'lead-5');
    expect(result.isCallable).toBe(false);
    expect(result.noBadNumberHistory).toBe(false);
    expect(result.rejectionReasons.some((r) => r.includes('BAD_NUMBER_HISTORY'))).toBe(true);
  });

  it('blocks duplicates from entering the active dial queue twice', () => {
    const engine = new PreDialGateEngine();
    const firstAttempt = engine.evaluateGate(validProperty, validOwner, validContact, 'lead-6');
    expect(firstAttempt.isCallable).toBe(true);

    const secondAttempt = engine.evaluateGate(validProperty, validOwner, validContact, 'lead-7');
    expect(secondAttempt.isCallable).toBe(false);
    expect(secondAttempt.noDuplicate).toBe(false);
    expect(secondAttempt.rejectionReasons.some((r) => r.includes('DUPLICATE_DETECTED'))).toBe(true);
  });
});
