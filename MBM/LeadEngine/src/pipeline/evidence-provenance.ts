/**
 * Evidence & Provenance Tracking Subsystem
 * Ensures evidence/provenance survives every pipeline transition.
 * Supabase remains the source of truth.
 * JARVIS Worker 3 — Integration / QA / Deployment Commander
 */

import crypto from 'node:crypto';
import type {
  EvidenceRecord,
  ProvenanceTransition,
  PipelineStage,
} from './types';

export class EvidenceProvenanceTracker {
  private evidenceStore: Map<string, EvidenceRecord> = new Map();

  public createEvidence(
    leadId: string,
    propertyId: string,
    sourceSystem: string,
    rawPayload: Record<string, unknown>,
    sourceRecordId?: string | null
  ): EvidenceRecord {
    const rawPayloadString = JSON.stringify(rawPayload, Object.keys(rawPayload).sort());
    const hash = crypto.createHash('sha256').update(rawPayloadString).digest('hex');

    const initialTransition: ProvenanceTransition = {
      fromStage: 'SOURCE',
      toStage: 'NORMALIZE',
      timestamp: new Date().toISOString(),
      workerId: 'WORKER_1',
      status: 'SUCCESS',
      metadata: { sourceSystem, sourceRecordId },
    };

    const signature = this.generateValidatorSignature(leadId, hash, [initialTransition]);

    const evidence: EvidenceRecord = {
      id: crypto.randomUUID(),
      leadId,
      propertyId,
      sourceSystem,
      sourceRecordId,
      rawPayloadHash: hash,
      provenanceTrail: [initialTransition],
      validatorSignature: signature,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    this.evidenceStore.set(leadId, evidence);
    return evidence;
  }

  public recordTransition(
    leadId: string,
    fromStage: PipelineStage,
    toStage: PipelineStage,
    workerId: 'WORKER_1' | 'WORKER_2' | 'WORKER_3_COMMANDER',
    status: 'SUCCESS' | 'WARNING' | 'REJECTED',
    metadata?: Record<string, unknown>
  ): EvidenceRecord {
    const evidence = this.evidenceStore.get(leadId);
    if (!evidence) {
      throw new Error(`Evidence record not found for lead ID: ${leadId}`);
    }

    const transition: ProvenanceTransition = {
      fromStage,
      toStage,
      timestamp: new Date().toISOString(),
      workerId,
      status,
      metadata,
    };

    evidence.provenanceTrail.push(transition);
    evidence.updatedAt = new Date().toISOString();
    evidence.validatorSignature = this.generateValidatorSignature(
      evidence.leadId,
      evidence.rawPayloadHash,
      evidence.provenanceTrail
    );

    return evidence;
  }

  public verifyEvidenceIntegrity(evidence: EvidenceRecord): {
    isValid: boolean;
    transitionCount: number;
    tamperDetected: boolean;
  } {
    const calculatedSignature = this.generateValidatorSignature(
      evidence.leadId,
      evidence.rawPayloadHash,
      evidence.provenanceTrail
    );

    const isValid = calculatedSignature === evidence.validatorSignature;
    return {
      isValid,
      transitionCount: evidence.provenanceTrail.length,
      tamperDetected: !isValid,
    };
  }

  public getEvidence(leadId: string): EvidenceRecord | undefined {
    return this.evidenceStore.get(leadId);
  }

  public markSupabaseSynced(leadId: string): EvidenceRecord {
    const evidence = this.evidenceStore.get(leadId);
    if (!evidence) {
      throw new Error(`Evidence record not found for lead ID: ${leadId}`);
    }
    evidence.supabaseSyncedAt = new Date().toISOString();
    return evidence;
  }

  private generateValidatorSignature(
    leadId: string,
    hash: string,
    trail: ProvenanceTransition[]
  ): string {
    const trailStr = JSON.stringify(trail);
    return crypto
      .createHmac('sha256', 'JARVIS_INTEGRATION_KEY_SUPABASE_ROOT')
      .update(`${leadId}:${hash}:${trailStr}`)
      .digest('hex');
  }
}
