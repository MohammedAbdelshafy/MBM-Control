import { describe, it, expect } from 'vitest';
import { EvidenceProvenanceTracker } from '../src/pipeline/evidence-provenance';

describe('EvidenceProvenanceTracker — Supabase Truth & Provenance Integrity', () => {
  it('creates evidence record and tracks stage transitions without data loss', () => {
    const tracker = new EvidenceProvenanceTracker();
    const leadId = 'lead-provenance-01';
    const propertyId = 'prop-01';
    const rawPayload = {
      npi: '1982736450',
      clinic: 'Lonestar Wellness Clinic',
      phone: '2147891234',
    };

    const evidence = tracker.createEvidence(
      leadId,
      propertyId,
      'CMS_NPI_REGISTRY',
      rawPayload,
      'NPI-1982736450'
    );

    expect(evidence.leadId).toBe(leadId);
    expect(evidence.sourceSystem).toBe('CMS_NPI_REGISTRY');
    expect(evidence.provenanceTrail.length).toBe(1);
    expect(evidence.rawPayloadHash).toBeDefined();

    // Record Worker 1 transition
    tracker.recordTransition(
      leadId,
      'NORMALIZE',
      'PROPERTY_IDENTITY',
      'WORKER_1',
      'SUCCESS',
      { resolvedAPN: 'TX-DAL-101' }
    );

    // Record Worker 2 transition
    tracker.recordTransition(
      leadId,
      'PROPERTY_IDENTITY',
      'ENRICHMENT',
      'WORKER_2',
      'SUCCESS',
      { verifiedPhone: '2147891234' }
    );

    // Record Worker 3 Commander gate validation
    tracker.recordTransition(
      leadId,
      'ENRICHMENT',
      'DIALER',
      'WORKER_3_COMMANDER',
      'SUCCESS',
      { gateStatus: 'PASSED' }
    );

    const updated = tracker.getEvidence(leadId)!;
    expect(updated.provenanceTrail.length).toBe(4);

    const check = tracker.verifyEvidenceIntegrity(updated);
    expect(check.isValid).toBe(true);
    expect(check.tamperDetected).toBe(false);
    expect(check.transitionCount).toBe(4);
  });

  it('marks evidence synced to Supabase as source of truth', () => {
    const tracker = new EvidenceProvenanceTracker();
    const leadId = 'lead-supabase-02';
    tracker.createEvidence(leadId, 'prop-02', 'COUNTY_RECORDS', { apn: 'APN-999' });

    const synced = tracker.markSupabaseSynced(leadId);
    expect(synced.supabaseSyncedAt).toBeDefined();
    expect(new Date(synced.supabaseSyncedAt!).getTime()).toBeGreaterThan(0);
  });
});
