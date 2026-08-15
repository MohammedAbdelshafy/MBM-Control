import { describe, it, expect } from 'vitest';
import { NegativeLearningEngine } from '../src/pipeline/negative-learning';
import { PreDialGateEngine } from '../src/pipeline/predial-gate';
import { PropertyDedupeRegistry } from '../src/property-intel/dedupe';
import { JarvisQAGateAuditEngine } from '../src/pipeline/qa-gate-audit';
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

function contact(phone: string): ContactEvidence {
  return {
    contactName: 'Marcus Vance',
    phone,
    email: 'marcus.vance@example.com',
    source: 'CMS_NPI',
    carrierType: 'MOBILE',
    lineStatus: 'ACTIVE',
    dncStatus: 'CLEAN',
    confidenceScore: 0.96,
    extractedAt: new Date().toISOString(),
  };
}

function disp(engine: NegativeLearningEngine, phone: string, disposition: Parameters<NegativeLearningEngine['recordDisposition']>[0]['disposition'], callbackAt?: string | null) {
  return engine.recordDisposition({
    id: `disp-${Math.random()}`,
    leadId: 'lead-1',
    propertyId: '045-882-019-A',
    phone,
    ownerName: 'Marcus Vance',
    disposition,
    timestamp: new Date().toISOString(),
    scheduledCallbackAt: callbackAt ?? null,
  });
}

describe('Dialer QA — the nine dispositions behave exactly as specified', () => {
  it('1. BAD_NUMBER globally suppresses the phone, removes it, and hits -100', () => {
    const engine = new NegativeLearningEngine();
    const outcome = disp(engine, '+13057684901', 'BAD_NUMBER');
    expect(outcome.shouldRemoveFromActiveQueue).toBe(true);
    expect(outcome.priorityDelta).toBe(-100);
    expect(engine.isPhoneSuppressed('3057684901')).toBe(true);
  });

  it('2. WRONG_PERSON invalidates only the phone→person linkage, not the owner', () => {
    const engine = new NegativeLearningEngine();
    const outcome = disp(engine, '+13057684902', 'WRONG_PERSON');
    expect(outcome.shouldRemoveFromActiveQueue).toBe(true);
    expect(outcome.priorityDelta).toBe(-50);
    // A different number for the same owner stays dialable.
    const gate = new PreDialGateEngine();
    const other = gate.evaluateGate(property, owner, contact('3057684999'), 'lead-other');
    expect(other.isCallable).toBe(true);
    expect(engine.isOwnerInvalidated('045-882-019-A', 'Marcus Vance')).toBe(false);
  });

  it('3. NON_OWNER invalidates the owner and triggers re-verification', () => {
    const engine = new NegativeLearningEngine();
    const outcome = disp(engine, '+13057684903', 'NON_OWNER');
    expect(outcome.shouldRemoveFromActiveQueue).toBe(true);
    expect(outcome.priorityDelta).toBe(-75);
    expect(engine.isOwnerInvalidated('045-882-019-A', 'Marcus Vance')).toBe(true);
  });

  it('4. DNC hard-suppresses the phone with a legal compliance lock', () => {
    const engine = new NegativeLearningEngine();
    const outcome = disp(engine, '+13057684904', 'DNC');
    expect(outcome.shouldRemoveFromActiveQueue).toBe(true);
    expect(outcome.priorityDelta).toBe(-100);
    expect(engine.isPhoneSuppressed('3057684904')).toBe(true);

    const gate = new PreDialGateEngine();
    gate.applyPermanentDispositions([{ phone: '+13057684904', type: 'DNC', permanent: true }]);
    const blocked = gate.evaluateGate(property, owner, contact('3057684904'), 'lead-dnc');
    expect(blocked.isCallable).toBe(false);
    expect(blocked.noSuppression).toBe(false);
  });

  it('5. DUPLICATE blocks a re-import of the same property identity', async () => {
    const dedupe = new PropertyDedupeRegistry();
    const first = await dedupe.checkAndRegister(property, 'lead-dup-1');
    expect(first.isDuplicate).toBe(false);
    const second = await dedupe.checkAndRegister(
      { ...property, addressLine1: '1420 Ocean Dr' }, // address variant collapses
      'lead-dup-2',
    );
    expect(second.isDuplicate).toBe(true);
  });

  it('6. PREVIOUSLY_REJECTED gives permanent re-import immunity', () => {
    const qa = new JarvisQAGateAuditEngine();
    qa.recordDisposition('lead-rej-1', '045-882-019-A', '+13057684906', 'Marcus Vance', 'BAD_NUMBER');

    const audited = qa.auditLead({
      leadId: 'lead-rej-1',
      property,
      ownership: owner,
      contact: contact('3057684906'),
    });
    expect(audited.isEligibleForProductionDialer).toBe(false);
    expect(audited.rejectionReasons[0]).toMatch(/PERMANENT_REJECTION_RECORDED/);
  });

  it('7. NO_ANSWER is NOT a bad disposition — exponential backoff, then cooling pool', () => {
    const engine = new NegativeLearningEngine();
    const first = disp(engine, '+13057684907', 'NO_ANSWER');
    expect(first.shouldRemoveFromActiveQueue).toBe(false);
    expect(first.priorityDelta).toBe(-5);
    expect(engine.isPhoneSuppressed('3057684907')).toBe(false);

    // Attempt 4 → cooling pool (removed from active queue, never suppressed).
    for (let i = 2; i <= 4; i++) {
      const outcome = disp(engine, '+13057684907', 'NO_ANSWER');
      if (i === 4) {
        expect(outcome.shouldRemoveFromActiveQueue).toBe(true);
        expect(outcome.actionTaken).toMatch(/cooling pool/);
      } else {
        expect(outcome.shouldRemoveFromActiveQueue).toBe(false);
        expect(outcome.actionTaken).toMatch(/Backoff scheduled/);
      }
    }
  });

  it('8. INTERESTED boosts priority +30 and stays in the active queue', () => {
    const engine = new NegativeLearningEngine();
    const outcome = disp(engine, '+13057684908', 'INTERESTED');
    expect(outcome.shouldRemoveFromActiveQueue).toBe(false);
    expect(outcome.priorityDelta).toBe(30);
    expect(engine.getLeadPriorityModifier('lead-1')).toBe(30);
  });

  it('9. CALLBACK boosts +15 and schedules a follow-up', () => {
    const engine = new NegativeLearningEngine();
    const when = new Date(Date.now() + 86400000).toISOString();
    const outcome = engine.recordDisposition({
      id: 'cb-1',
      leadId: 'lead-cb',
      propertyId: '045-882-019-A',
      phone: '+13057684909',
      ownerName: 'Marcus Vance',
      disposition: 'CALLBACK',
      timestamp: new Date().toISOString(),
      scheduledCallbackAt: when,
    });
    expect(outcome.shouldRemoveFromActiveQueue).toBe(false);
    expect(outcome.priorityDelta).toBe(15);
    expect(engine.getLeadPriorityModifier('lead-cb')).toBe(15);
    expect(outcome.actionTaken).toContain(when);
  });
});