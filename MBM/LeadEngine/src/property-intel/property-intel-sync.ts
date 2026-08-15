/**
 * Property Intelligence Sync — JARVIS Worker 1
 *
 * Persists a pipeline-processed lead into the canonical Supabase
 * Postgres layer in one deterministic pass:
 *
 *   dedupe check → upsert property → link parcel/APN → attach
 *   ownership evidence → write evidence + provenance trail → upsert
 *   lead + callability + lead score.
 */

import type { SourceType } from '@prisma/client';
import { PropertyDedupeRegistry } from './dedupe';
import { ParcelLinkageService, type OwnershipEvidenceInput, type ParcelEvidenceInput } from './parcel-linkage';
import type { EvidenceRepository } from './evidence-repository';
import type { LeadDraft, LeadScoreDraft, PropertyDraft } from './types';
import type { LeadPersistence } from './lead-persistence';

export interface PropertyIntelSyncInput {
  sourceSystem: string;
  sourceType: SourceType;
  sourceReference?: string | null;
  sourceUrl?: string | null;
  rawPayload: Record<string, unknown>;
  property: PropertyDraft;
  parcel: ParcelEvidenceInput;
  owners: OwnershipEvidenceInput[];
  lead: LeadDraft;
  leadScore: LeadScoreDraft;
  /** Lead-level provenance transitions (after property identity). */
  provenanceTransitions: Array<{
    fromStage: string;
    toStage: string;
    workerId: string;
    status: 'SUCCESS' | 'WARNING' | 'REJECTED';
    metadata?: Record<string, unknown>;
  }>;
}

export interface PropertyIntelSyncResult {
  deduplicated: boolean;
  propertyId: string;
  parcelId: string;
  ownerIds: string[];
  leadId: string;
  evidenceIds: string[];
}

export class PropertyIntelSyncService {
  private readonly linkage: ParcelLinkageService;

  constructor(
    private readonly persistence: LeadPersistence,
    private readonly evidence: EvidenceRepository,
    private readonly dedupe?: PropertyDedupeRegistry | null,
  ) {
    this.linkage = new ParcelLinkageService();
  }

  public async sync(input: PropertyIntelSyncInput): Promise<PropertyIntelSyncResult> {
    // 1. Deterministic dedupe — same property never stored twice.
    let deduplicated = false;
    let propertyId: string | null = null;
    if (this.dedupe) {
      const dedupeResult = await this.dedupe.checkAndRegister(
        {
          parcelId: input.parcel.parcelId,
          addressLine1: input.property.addressLine1,
          addressLine2: input.property.addressLine2,
          city: input.property.city,
          state: input.property.state,
          zip: input.property.zip,
          county: input.property.county,
        },
        undefined,
      );
      deduplicated = dedupeResult.isDuplicate;
    }

    // 2. Upsert property (dedupe key ensures idempotent row).
    const propertyRow = await this.persistence.upsertProperty(input.property);
    propertyId = propertyRow.id;

    // 3. Property → parcel/APN → ownership evidence chain.
    const linkage = this.linkage.linkPropertyToParcel(
      input.property,
      input.parcel,
      input.owners,
      propertyId,
    );

    // 4. Persist parcel + owners.
    const parcelRow = await this.persistence.upsertParcel(linkage.parcel);
    const ownerIds: string[] = [];
    for (const owner of linkage.owners) {
      const row = await this.persistence.upsertOwner(owner);
      ownerIds.push(row.id);
    }

    // 5. Persist evidence + provenance transitions.
    const evidenceIds: string[] = [];
    for (let i = 0; i < linkage.evidence.length; i++) {
      const item = linkage.evidence[i];
      const descriptor = item.descriptor;
      const targetId =
        descriptor.ownerId !== undefined || i > 0
          ? ownerIds[i - 1] ?? null
          : null;
      const created = await this.evidence.createEvidence({
        ...descriptor,
        parcelId: descriptor.parcelId ?? (i === 0 ? parcelRow.id : null),
        ownerId: i > 0 ? ownerIds[i - 1] ?? null : null,
      });
      for (const transition of item.transitions) {
        await this.evidence.appendTransition(created.id, transition);
      }
      evidenceIds.push(created.id);
      void targetId;
    }

    // 6. Lead + lead score.
    const leadRow = await this.persistence.upsertLead({
      ...input.lead,
      propertyId,
    });
    await this.persistence.upsertLeadScore({
      ...input.leadScore,
      leadId: leadRow.id,
    });

    return {
      deduplicated,
      propertyId,
      parcelId: parcelRow.id,
      ownerIds,
      leadId: leadRow.id,
      evidenceIds,
    };
  }
}