import { describe, it, expect } from 'vitest';
import {
  InMemoryEvidenceRepository,
  hashRawPayload,
  type EvidenceDraft,
} from '../src/property-intel';

function evidenceDraft(): EvidenceDraft {
  return {
    leadId: 'lead-1',
    propertyId: 'prop-1',
    source: 'CMS_NPI_REGISTRY',
    sourceType: 'API_CONNECTOR',
    sourceReference: 'NPI-1982736450',
    sourceUrl: 'https://npiregistry.cms.hhs.gov/api/?number=1982736450',
    rawPayloadHash: hashRawPayload({ npi: '1982736450' }),
    verificationStatus: 'PENDING',
    confidence: 0.9,
    retrievedAt: new Date('2026-08-01T00:00:00Z'),
  };
}

describe('Evidence & Provenance Repository', () => {
  it('persists evidence with full provenance fields', async () => {
    const repo = new InMemoryEvidenceRepository();
    const created = await repo.createEvidence(evidenceDraft());
    const rows = await repo.findEvidenceByLead('lead-1');

    expect(created.id).toBeTruthy();
    expect(rows).toHaveLength(1);
    expect(rows[0].source).toBe('CMS_NPI_REGISTRY');
    expect(rows[0].sourceReference).toBe('NPI-1982736450');
    expect(rows[0].sourceUrl).toBe('https://npiregistry.cms.hhs.gov/api/?number=1982736450');
    expect(rows[0].verificationStatus).toBe('PENDING');
    expect(rows[0].retrievedAt).toBeInstanceOf(Date);
    expect(rows[0].lastVerified).toBeNull();
    expect(rows[0].rawPayloadHash).toHaveLength(64);
  });

  it('appends provenance transitions to the evidence trail', async () => {
    const repo = new InMemoryEvidenceRepository();
    const { id } = await repo.createEvidence(evidenceDraft());

    await repo.appendTransition(id, {
      fromStage: 'NORMALIZE',
      toStage: 'PROPERTY_IDENTITY',
      workerId: 'WORKER_1',
      status: 'SUCCESS',
      metadata: { resolvedAPN: 'TX-DAL-101' },
    });

    const all = repo.getAll();
    expect(all[0].transitions).toHaveLength(1);
    expect(all[0].transitions[0].toStage).toBe('PROPERTY_IDENTITY');
  });

  it('marks evidence VERIFIED with lastVerified and confidence', async () => {
    const repo = new InMemoryEvidenceRepository();
    const { id } = await repo.createEvidence(evidenceDraft());

    await repo.markVerified(id, 0.99, new Date('2026-08-10T00:00:00Z'));

    const rows = await repo.findEvidenceByLead('lead-1');
    expect(rows[0].verificationStatus).toBe('VERIFIED');
    expect(rows[0].confidence).toBe(0.99);
    expect(rows[0].lastVerified!.toISOString()).toContain('2026-08-10');
  });

  it('computes a stable raw payload hash regardless of key order', () => {
    const a = hashRawPayload({ npi: '1', clinic: 'x' });
    const b = hashRawPayload({ clinic: 'x', npi: '1' });
    expect(a).toBe(b);
  });
});