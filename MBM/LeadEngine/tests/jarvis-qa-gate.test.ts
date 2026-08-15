import { describe, it, expect } from 'vitest';
import { JarvisQAGateAuditEngine, type AuditRecordInput } from '../src/pipeline/qa-gate-audit';

describe('JARVIS QA Gate & Pre-Dial Audit System (10-Point Gate)', () => {
  it('1. Confirms only 100% verified leads become PRIME_CALLABLE and eligible for dialer', () => {
    const engine = new JarvisQAGateAuditEngine();

    const validCandidate: AuditRecordInput = {
      leadId: 'lead-valid-01',
      property: {
        parcelId: 'PARCEL-FL-9021',
        addressLine1: '450 Ocean Dr',
        city: 'Miami Beach',
        state: 'FL',
        zip: '33139',
        county: 'Miami-Dade',
        propertyType: 'SINGLE_FAMILY',
        estimatedValue: 650000,
      },
      ownership: {
        ownerName: 'Apex Real Estate Holdings LLC',
        ownerType: 'LLC',
        mailingAddress: '450 Ocean Dr, Miami Beach, FL 33139',
        isAbsentee: true,
        confidenceScore: 0.95,
        corporateOfficerName: 'Marcus Vance',
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'Marcus Vance',
        phone: '3057684905',
        source: 'CMS_NPI',
        carrierType: 'MOBILE',
        lineStatus: 'ACTIVE',
        dncStatus: 'CLEAN',
        confidenceScore: 0.96,
        extractedAt: new Date().toISOString(),
      },
    };

    const result = engine.auditLead(validCandidate);

    expect(result.category).toBe('PRIME_CALLABLE');
    expect(result.isEligibleForProductionDialer).toBe(true);
    expect(result.gatePassed).toBe(true);
    expect(result.priorityScore).toBeGreaterThanOrEqual(75);
  });

  it('2. Flags OWNER_VERIFICATION_REQUIRED and CONTACT_VERIFICATION_REQUIRED correctly', () => {
    const engine = new JarvisQAGateAuditEngine();

    // Owner low confidence
    const lowOwnerCandidate: AuditRecordInput = {
      leadId: 'lead-low-owner',
      property: {
        parcelId: 'PARCEL-TX-101',
        addressLine1: '120 Main St',
        city: 'Dallas',
        state: 'TX',
        zip: '75201',
        county: 'Dallas',
        propertyType: 'SINGLE_FAMILY',
      },
      ownership: {
        ownerName: 'Unverified Owner',
        ownerType: 'INDIVIDUAL',
        mailingAddress: '120 Main St',
        isAbsentee: false,
        confidenceScore: 0.50, // Low confidence
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'Unverified Owner',
        phone: '2145551234',
        source: 'CMS_NPI',
        carrierType: 'MOBILE',
        dncStatus: 'CLEAN',
        confidenceScore: 0.90,
        extractedAt: new Date().toISOString(),
      },
    };

    // Contact invalid phone
    const badPhoneCandidate: AuditRecordInput = {
      leadId: 'lead-bad-phone',
      property: {
        parcelId: 'PARCEL-TX-102',
        addressLine1: '140 Main St',
        city: 'Dallas',
        state: 'TX',
        zip: '75201',
        county: 'Dallas',
        propertyType: 'SINGLE_FAMILY',
      },
      ownership: {
        ownerName: 'Verified Owner LLC',
        ownerType: 'LLC',
        mailingAddress: '140 Main St',
        isAbsentee: false,
        confidenceScore: 0.95,
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'Verified Owner LLC',
        phone: '5550199', // Fake / incomplete phone
        source: 'SCRAPED',
        dncStatus: 'CLEAN',
        confidenceScore: 0.20,
        extractedAt: new Date().toISOString(),
      },
    };

    const ownerRes = engine.auditLead(lowOwnerCandidate);
    const phoneRes = engine.auditLead(badPhoneCandidate);

    expect(ownerRes.category).toBe('OWNER_VERIFICATION_REQUIRED');
    expect(ownerRes.isEligibleForProductionDialer).toBe(false);

    expect(phoneRes.category).toBe('CONTACT_VERIFICATION_REQUIRED');
    expect(phoneRes.isEligibleForProductionDialer).toBe(false);
  });

  it('3. Verifies BAD_NUMBER and DNC are permanently suppressed', () => {
    const engine = new JarvisQAGateAuditEngine();

    // Record bad number
    engine.recordDisposition('l1', 'p1', '3057684905', 'Owner 1', 'BAD_NUMBER');

    // Attempt to audit lead with the suppressed phone
    const candidate: AuditRecordInput = {
      leadId: 'l2',
      property: {
        parcelId: 'PARCEL-NEW',
        addressLine1: '800 Elm St',
        city: 'Miami',
        state: 'FL',
        zip: '33101',
        county: 'Miami-Dade',
        propertyType: 'SINGLE_FAMILY',
      },
      ownership: {
        ownerName: 'New Entity LLC',
        ownerType: 'LLC',
        mailingAddress: '800 Elm St',
        isAbsentee: false,
        confidenceScore: 0.95,
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'New Entity LLC',
        phone: '3057684905', // Suppressed
        source: 'CMS_NPI',
        dncStatus: 'CLEAN',
        confidenceScore: 0.95,
        extractedAt: new Date().toISOString(),
      },
    };

    const audit = engine.auditLead(candidate);
    expect(audit.isEligibleForProductionDialer).toBe(false);
    expect(audit.category).toBe('BAD_NUMBER');
  });

  it('4. Confirms WRONG_PERSON and NON_OWNER invalidate entity linkages', () => {
    const engine = new JarvisQAGateAuditEngine();

    engine.recordDisposition('l1', 'PARCEL-MIA-55', '3059998888', 'Fake Landlord LLC', 'NON_OWNER');

    const candidate: AuditRecordInput = {
      leadId: 'l3',
      property: {
        parcelId: 'PARCEL-MIA-55',
        addressLine1: '900 Biscayne Blvd',
        city: 'Miami',
        state: 'FL',
        zip: '33132',
        county: 'Miami-Dade',
        propertyType: 'SINGLE_FAMILY',
      },
      ownership: {
        ownerName: 'Fake Landlord LLC', // Invalidated
        ownerType: 'LLC',
        mailingAddress: '900 Biscayne Blvd',
        isAbsentee: false,
        confidenceScore: 0.95,
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'Fake Landlord LLC',
        phone: '3051112222',
        source: 'CMS_NPI',
        dncStatus: 'CLEAN',
        confidenceScore: 0.95,
        extractedAt: new Date().toISOString(),
      },
    };

    const audit = engine.auditLead(candidate);
    expect(audit.isEligibleForProductionDialer).toBe(false);
    expect(audit.category).toBe('NON_OWNER');
  });

  it('5. Verifies NO_ANSWER is retryable and not classified as BAD_NUMBER', () => {
    const engine = new JarvisQAGateAuditEngine();

    const outcome = engine.recordDisposition('l1', 'p1', '3057774444', 'Busy Owner', 'NO_ANSWER');
    expect(outcome.shouldRemoveFromActiveQueue).toBe(false);
    expect(outcome.actionTaken).toContain('Attempt 1/4');

    // Audit remains callable
    const candidate: AuditRecordInput = {
      leadId: 'l1',
      property: {
        parcelId: 'PARCEL-RETRY-01',
        addressLine1: '200 Oak St',
        city: 'Austin',
        state: 'TX',
        zip: '78701',
        county: 'Travis',
        propertyType: 'SINGLE_FAMILY',
      },
      ownership: {
        ownerName: 'Busy Owner',
        ownerType: 'INDIVIDUAL',
        mailingAddress: '200 Oak St',
        isAbsentee: false,
        confidenceScore: 0.95,
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'Busy Owner',
        phone: '3057774444',
        source: 'CMS_NPI',
        carrierType: 'MOBILE',
        dncStatus: 'CLEAN',
        confidenceScore: 0.95,
        extractedAt: new Date().toISOString(),
      },
    };

    const audit = engine.auditLead(candidate);
    expect(audit.category).toBe('PRIME_CALLABLE');
    expect(audit.isEligibleForProductionDialer).toBe(true);
  });

  it('6. Verifies priority boosts are modifiers (+30, +15) and cannot override failed quality gates', () => {
    const engine = new JarvisQAGateAuditEngine();

    // Candidate with missing APN and bad phone but has INTERESTED disposition history (+30)
    const invalidWithBoost: AuditRecordInput = {
      leadId: 'l-boost-fail',
      property: {
        parcelId: '', // Blank APN -> Fails gate
        addressLine1: '300 Fake St',
        city: 'Houston',
        state: 'TX',
        zip: '77001',
        county: 'Harris',
        propertyType: 'SINGLE_FAMILY',
      },
      ownership: {
        ownerName: 'Owner Name',
        ownerType: 'INDIVIDUAL',
        mailingAddress: '300 Fake St',
        isAbsentee: false,
        confidenceScore: 0.95,
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'Owner Name',
        phone: '5550100', // Invalid
        source: 'SCRAPED',
        dncStatus: 'CLEAN',
        confidenceScore: 0.30,
        extractedAt: new Date().toISOString(),
      },
      dispositionHistory: [{ disposition: 'INTERESTED', timestamp: new Date().toISOString() }],
    };

    const audit = engine.auditLead(invalidWithBoost);

    // Modifier was calculated (+30)
    expect(audit.priorityBoostApplied).toBe(30);
    // BUT gate failure prevents eligibility
    expect(audit.isEligibleForProductionDialer).toBe(false);
    expect(audit.priorityScore).toBe(0);
    expect(audit.gatePassed).toBe(false);
  });

  it('7 & 8. Tests rejection persistence across restart and re-import immunity', () => {
    // Process 1: Record a rejection
    const engine1 = new JarvisQAGateAuditEngine();
    engine1.recordDisposition('lead-old', 'PARCEL-PERM-88', '3058889999', 'Prior Owner LLC', 'NON_OWNER');

    // Simulate export of persistent ledger to DB / storage
    const ledgerState = Array.from(engine1.getPersistentRejectionLedger().entries()).map(([key, val]) => ({
      key,
      category: val.category,
      reason: val.reason,
      timestamp: val.timestamp,
    }));

    // Process 2: Restart process and restore ledger
    const engine2 = new JarvisQAGateAuditEngine();
    engine2.seedRejectionLedger(ledgerState);

    // Re-import the exact same lead record in the new process
    const reImportedLead: AuditRecordInput = {
      leadId: 'lead-reimported-new-id',
      property: {
        parcelId: 'PARCEL-PERM-88',
        addressLine1: '1200 Brickell Ave',
        city: 'Miami',
        state: 'FL',
        zip: '33131',
        county: 'Miami-Dade',
        propertyType: 'SINGLE_FAMILY',
      },
      ownership: {
        ownerName: 'Prior Owner LLC',
        ownerType: 'LLC',
        mailingAddress: '1200 Brickell Ave',
        isAbsentee: false,
        confidenceScore: 0.95,
        verifiedAt: new Date().toISOString(),
      },
      contact: {
        contactName: 'Prior Owner LLC',
        phone: '3058889999',
        source: 'CMS_NPI',
        dncStatus: 'CLEAN',
        confidenceScore: 0.95,
        extractedAt: new Date().toISOString(),
      },
      isReImport: true,
    };

    const audit = engine2.auditLead(reImportedLead);

    // Re-import MUST BE BLOCKED
    expect(audit.isEligibleForProductionDialer).toBe(false);
    expect(audit.category).toBe('NON_OWNER');
    expect(audit.rejectionReasons[0]).toContain('PERMANENT_REJECTION_RECORDED');
    expect(audit.explanation).toContain('Re-import blocked');
  });

  it('9 & 10. Generates complete Pre-Dial Audit Summary with exact category counts', () => {
    const engine = new JarvisQAGateAuditEngine();

    const candidates: AuditRecordInput[] = [
      // 1. Prime
      {
        leadId: 'c1',
        property: { parcelId: 'PARCEL-P1', addressLine1: '100 Main St', city: 'Miami', state: 'FL', zip: '33101', county: 'Miami-Dade', propertyType: 'SINGLE_FAMILY' },
        ownership: { ownerName: 'Good Owner LLC', ownerType: 'LLC', mailingAddress: '100 Main St', isAbsentee: false, confidenceScore: 0.95, verifiedAt: new Date().toISOString() },
        contact: { contactName: 'Good Owner LLC', phone: '3057684905', source: 'CMS_NPI', carrierType: 'MOBILE', dncStatus: 'CLEAN', confidenceScore: 0.95, extractedAt: new Date().toISOString() },
      },
      // 2. Bad phone
      {
        leadId: 'c2',
        property: { parcelId: 'PARCEL-P2', addressLine1: '200 Main St', city: 'Miami', state: 'FL', zip: '33101', county: 'Miami-Dade', propertyType: 'SINGLE_FAMILY' },
        ownership: { ownerName: 'Good Owner 2 LLC', ownerType: 'LLC', mailingAddress: '200 Main St', isAbsentee: false, confidenceScore: 0.95, verifiedAt: new Date().toISOString() },
        contact: { contactName: 'Good Owner 2 LLC', phone: '5550199', source: 'SCRAPED', dncStatus: 'CLEAN', confidenceScore: 0.20, extractedAt: new Date().toISOString() },
      },
      // 3. Low owner confidence
      {
        leadId: 'c3',
        property: { parcelId: 'PARCEL-P3', addressLine1: '300 Main St', city: 'Miami', state: 'FL', zip: '33101', county: 'Miami-Dade', propertyType: 'SINGLE_FAMILY' },
        ownership: { ownerName: 'Unverified Entity', ownerType: 'LLC', mailingAddress: '300 Main St', isAbsentee: false, confidenceScore: 0.40, verifiedAt: new Date().toISOString() },
        contact: { contactName: 'Unverified Entity', phone: '3057684906', source: 'CMS_NPI', carrierType: 'MOBILE', dncStatus: 'CLEAN', confidenceScore: 0.95, extractedAt: new Date().toISOString() },
      },
    ];

    const summary = engine.generatePreDialAudit(candidates);

    expect(summary.totalAudited).toBe(3);
    expect(summary.primeCallableCount).toBe(1);
    expect(summary.contactVerificationRequiredCount).toBe(1);
    expect(summary.ownerVerificationRequiredCount).toBe(1);
    expect(summary.productionReady).toBe(true);
    expect(summary.rejectionPersistenceVerified).toBe(true);
    expect(summary.reImportImmunityVerified).toBe(true);
    expect(summary.modifierIntegrityVerified).toBe(true);
  });
});
