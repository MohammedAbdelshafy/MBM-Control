/**
 * Parcel / APN Linkage — JARVIS Worker 1
 *
 * Establishes the canonical chain:
 *
 *   Property ──▶ Parcel / APN ──▶ Ownership Record ──▶ Evidence
 *
 * Every parcel and every ownership record carries its own evidence
 * descriptor (source, source_reference/url, retrieved_at,
 * verification_status, confidence, last_verified) so nothing is
 * asserted without provenance.
 */

import { normalizeParcelId } from './dedupe';
import { hashRawPayload } from './evidence-repository';
import type { SourceType } from '@prisma/client';
import type {
  EvidenceDraft,
  OwnerDraft,
  ParcelDraft,
  PropertyDraft,
  VerificationStatus,
} from './types';

export interface EvidenceDescriptorInput {
  source: string;
  sourceType: SourceType;
  sourceReference?: string | null;
  sourceUrl?: string | null;
  retrievedAt?: Date;
  verificationStatus?: VerificationStatus;
  confidence?: number;
  lastVerified?: Date;
}

export interface ParcelEvidenceInput extends EvidenceDescriptorInput {
  parcelId: string;
  county: string;
  state: string;
  legalDescription?: string | null;
}

export interface OwnershipEvidenceInput extends EvidenceDescriptorInput {
  ownerName: string;
  ownerType: string;
  mailingAddress: string;
  isAbsentee?: boolean;
  corporateOfficerName?: string | null;
  corporateOfficerTitle?: string | null;
}

export interface ParcelLinkageResult {
  property: PropertyDraft;
  parcel: ParcelDraft;
  owners: OwnerDraft[];
  /** Parcel + ownership evidence descriptors (persisted as EvidenceRecord). */
  evidence: Array<{
    descriptor: EvidenceDraft;
    /** Transition trail for the evidence record. */
    transitions: Array<{
      fromStage: string;
      toStage: string;
      workerId: string;
      status: 'SUCCESS';
      metadata?: Record<string, unknown>;
    }>;
  }>;
}

/**
 * Build the property → parcel/APN → ownership evidence chain. Pure:
 * produces drafts ready for persistence.
 */
export class ParcelLinkageService {
  public linkPropertyToParcel(
    property: PropertyDraft,
    parcel: ParcelEvidenceInput,
    owners: OwnershipEvidenceInput[],
    propertyId: string,
  ): ParcelLinkageResult {
    const apnNormalized = normalizeParcelId(parcel.parcelId);
    const parcelEvidenceHash = hashRawPayload({
      parcelId: parcel.parcelId,
      county: parcel.county,
      state: parcel.state,
      legalDescription: parcel.legalDescription ?? null,
    });

    const parcelDraft: ParcelDraft = {
      parcelId: apnNormalized,
      apnNormalized,
      county: parcel.county,
      state: parcel.state,
      legalDescription: parcel.legalDescription ?? null,
      propertyId,
      source: parcel.source ?? null,
      sourceUrl: parcel.sourceUrl ?? null,
      sourceReference: parcel.sourceReference ?? null,
      verificationStatus: parcel.verificationStatus ?? 'UNVERIFIED',
      confidence: parcel.confidence ?? 0,
      lastVerified: parcel.lastVerified ?? null,
    };

    const parcelEvidence: EvidenceDraft = {
      parcelId: null, // parcelId assigned after parcel row persists
      propertyId,
      source: parcel.source,
      sourceType: parcel.sourceType,
      sourceReference: parcel.sourceReference ?? null,
      sourceUrl: parcel.sourceUrl ?? null,
      rawPayloadHash: parcelEvidenceHash,
      verificationStatus: parcel.verificationStatus ?? 'UNVERIFIED',
      confidence: parcel.confidence ?? 0,
      retrievedAt: parcel.retrievedAt ?? new Date(),
      lastVerified: parcel.lastVerified ?? null,
    };

    const ownerDrafts: OwnerDraft[] = [];
    const ownerEvidence: Array<ParcelLinkageResult['evidence'][number]> = [];

    for (const owner of owners) {
      const ownerHash = hashRawPayload({
        ownerName: owner.ownerName,
        ownerType: owner.ownerType,
        mailingAddress: owner.mailingAddress,
        corporateOfficerName: owner.corporateOfficerName ?? null,
      });

      ownerDrafts.push({
        propertyId,
        name: owner.ownerName,
        ownerType: owner.ownerType,
        mailingAddress: owner.mailingAddress,
        isAbsentee: owner.isAbsentee ?? false,
        confidenceScore: owner.confidence ?? 0,
        verificationStatus: owner.verificationStatus ?? 'UNVERIFIED',
        source: owner.source ?? null,
        sourceUrl: owner.sourceUrl ?? null,
        sourceReference: owner.sourceReference ?? null,
        verifiedAt: owner.lastVerified ?? (owner.verificationStatus === 'VERIFIED' ? new Date() : null),
        lastVerified: owner.lastVerified ?? null,
      });

      ownerEvidence.push({
        descriptor: {
          ownerId: null, // assigned after owner row persists
          propertyId,
          source: owner.source,
          sourceType: owner.sourceType,
          sourceReference: owner.sourceReference ?? null,
          sourceUrl: owner.sourceUrl ?? null,
          rawPayloadHash: ownerHash,
          verificationStatus: owner.verificationStatus ?? 'UNVERIFIED',
          confidence: owner.confidence ?? 0,
          retrievedAt: owner.retrievedAt ?? new Date(),
          lastVerified: owner.lastVerified ?? null,
        },
        transitions: [
          {
            fromStage: 'SOURCE',
            toStage: 'OWNERSHIP_VERIFICATION',
            workerId: 'WORKER_1',
            status: 'SUCCESS',
            metadata: {
              ownerName: owner.ownerName,
              source: owner.source,
            },
          },
        ],
      });
    }

    return {
      property,
      parcel: parcelDraft,
      owners: ownerDrafts,
      evidence: [
        {
          descriptor: parcelEvidence,
          transitions: [
            {
              fromStage: 'NORMALIZE',
              toStage: 'PARCEL_APN',
              workerId: 'WORKER_1',
              status: 'SUCCESS',
              metadata: {
                parcelId: apnNormalized,
                source: parcel.source,
                sourceReference: parcel.sourceReference ?? null,
                sourceUrl: parcel.sourceUrl ?? null,
              },
            },
          ],
        },
        ...ownerEvidence,
      ],
    };
  }
}