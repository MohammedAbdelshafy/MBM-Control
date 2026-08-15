/**
 * Evidence & Provenance Repository — JARVIS Worker 1
 *
 * Persists the evidence/provenance trail to the canonical Supabase
 * Postgres layer. Every evidence record carries:
 *   source, sourceReference/source_url, retrievedAt, verificationStatus,
 *   confidence, lastVerified, rawPayloadHash.
 *
 * The interface is DB-agnostic so unit tests run against an in-memory
 * implementation while production uses the Prisma/Supabase backend.
 */

import crypto from 'node:crypto';
import type { PrismaClient } from '@prisma/client';
import type { SourceType } from '@prisma/client';
import type { EvidenceDraft, ProvenanceTransitionDraft, VerificationStatus } from './types';

export interface EvidenceRecordView {
  id: string;
  leadId: string | null;
  propertyId: string | null;
  parcelId: string | null;
  ownerId: string | null;
  source: string;
  sourceType: SourceType;
  sourceReference: string | null;
  sourceUrl: string | null;
  rawPayloadHash: string;
  verificationStatus: VerificationStatus;
  confidence: number;
  retrievedAt: Date;
  lastVerified: Date | null;
}

export interface EvidenceRepository {
  createEvidence(evidence: EvidenceDraft): Promise<{ id: string }>;
  appendTransition(
    evidenceId: string,
    transition: ProvenanceTransitionDraft,
  ): Promise<void>;
  markVerified(
    evidenceId: string,
    confidence: number,
    lastVerified?: Date,
  ): Promise<void>;
  findEvidenceByLead(leadId: string): Promise<EvidenceRecordView[]>;
  findEvidenceByProperty(propertyId: string): Promise<EvidenceRecordView[]>;
}

/** Deterministic SHA-256 hash of a raw payload (key order normalized). */
export function hashRawPayload(payload: Record<string, unknown>): string {
  const stable = JSON.stringify(payload, Object.keys(payload).sort());
  return crypto.createHash('sha256').update(stable).digest('hex');
}

export class PrismaEvidenceRepository implements EvidenceRepository {
  constructor(private readonly db: PrismaClient) {}

  async createEvidence(evidence: EvidenceDraft): Promise<{ id: string }> {
    const record = await this.db.evidenceRecord.create({
      data: {
        leadId: evidence.leadId ?? null,
        propertyId: evidence.propertyId ?? null,
        parcelId: evidence.parcelId ?? null,
        ownerId: evidence.ownerId ?? null,
        source: evidence.source,
        sourceType: evidence.sourceType,
        sourceReference: evidence.sourceReference ?? null,
        sourceUrl: evidence.sourceUrl ?? null,
        rawPayloadHash: evidence.rawPayloadHash,
        verificationStatus: toPrismaVerification(evidence.verificationStatus),
        confidence: evidence.confidence,
        retrievedAt: evidence.retrievedAt,
        lastVerified: evidence.lastVerified ?? null,
      },
      select: { id: true },
    });
    return record;
  }

  async appendTransition(
    evidenceId: string,
    transition: ProvenanceTransitionDraft,
  ): Promise<void> {
    await this.db.provenanceEvent.create({
      data: {
        evidenceId,
        fromStage: transition.fromStage,
        toStage: transition.toStage,
        workerId: transition.workerId ?? null,
        status: transition.status,
        metadata: transition.metadata as never,
      },
    });
  }

  async markVerified(
    evidenceId: string,
    confidence: number,
    lastVerified?: Date,
  ): Promise<void> {
    await this.db.evidenceRecord.update({
      where: { id: evidenceId },
      data: {
        verificationStatus: 'VERIFIED',
        confidence,
        lastVerified: lastVerified ?? new Date(),
      },
    });
  }

  async findEvidenceByLead(leadId: string): Promise<EvidenceRecordView[]> {
    return this.mapRows(
      await this.db.evidenceRecord.findMany({
        where: { leadId },
        orderBy: { retrievedAt: 'desc' },
      }),
    );
  }

  async findEvidenceByProperty(propertyId: string): Promise<EvidenceRecordView[]> {
    return this.mapRows(
      await this.db.evidenceRecord.findMany({
        where: { propertyId },
        orderBy: { retrievedAt: 'desc' },
      }),
    );
  }

  private mapRows(
    rows: Array<{
      id: string;
      leadId: string | null;
      propertyId: string | null;
      parcelId: string | null;
      ownerId: string | null;
      source: string;
      sourceType: SourceType;
      sourceReference: string | null;
      sourceUrl: string | null;
      rawPayloadHash: string;
      verificationStatus: VerificationStatus;
      confidence: number;
      retrievedAt: Date;
      lastVerified: Date | null;
    }>,
  ): EvidenceRecordView[] {
    return rows.map((r) => ({
      id: r.id,
      leadId: r.leadId,
      propertyId: r.propertyId,
      parcelId: r.parcelId,
      ownerId: r.ownerId,
      source: r.source,
      sourceType: r.sourceType,
      sourceReference: r.sourceReference,
      sourceUrl: r.sourceUrl,
      rawPayloadHash: r.rawPayloadHash,
      verificationStatus: r.verificationStatus as VerificationStatus,
      confidence: r.confidence,
      retrievedAt: r.retrievedAt,
      lastVerified: r.lastVerified,
    }));
  }
}

function toPrismaVerification(
  status: VerificationStatus,
): 'UNVERIFIED' | 'PENDING' | 'VERIFIED' | 'REJECTED' | 'EXPIRED' {
  return status;
}

export class InMemoryEvidenceRepository implements EvidenceRepository {
  private evidence = new Map<string, EvidenceRecordView & { transitions: ProvenanceTransitionDraft[] }>();

  async createEvidence(evidence: EvidenceDraft): Promise<{ id: string }> {
    const id = crypto.randomUUID();
    this.evidence.set(id, {
      id,
      leadId: evidence.leadId ?? null,
      propertyId: evidence.propertyId ?? null,
      parcelId: evidence.parcelId ?? null,
      ownerId: evidence.ownerId ?? null,
      source: evidence.source,
      sourceType: evidence.sourceType,
      sourceReference: evidence.sourceReference ?? null,
      sourceUrl: evidence.sourceUrl ?? null,
      rawPayloadHash: evidence.rawPayloadHash,
      verificationStatus: evidence.verificationStatus,
      confidence: evidence.confidence,
      retrievedAt: evidence.retrievedAt,
      lastVerified: evidence.lastVerified ?? null,
      transitions: [],
    });
    return { id };
  }

  async appendTransition(
    evidenceId: string,
    transition: ProvenanceTransitionDraft,
  ): Promise<void> {
    const record = this.evidence.get(evidenceId);
    if (!record) throw new Error(`Evidence not found: ${evidenceId}`);
    record.transitions.push(transition);
  }

  async markVerified(
    evidenceId: string,
    confidence: number,
    lastVerified?: Date,
  ): Promise<void> {
    const record = this.evidence.get(evidenceId);
    if (!record) throw new Error(`Evidence not found: ${evidenceId}`);
    record.verificationStatus = 'VERIFIED';
    record.confidence = confidence;
    record.lastVerified = lastVerified ?? new Date();
  }

  async findEvidenceByLead(leadId: string): Promise<EvidenceRecordView[]> {
    return Array.from(this.evidence.values()).filter((e) => e.leadId === leadId);
  }

  async findEvidenceByProperty(propertyId: string): Promise<EvidenceRecordView[]> {
    return Array.from(this.evidence.values()).filter((e) => e.propertyId === propertyId);
  }

  getAll(): Array<EvidenceRecordView & { transitions: ProvenanceTransitionDraft[] }> {
    return Array.from(this.evidence.values());
  }
}