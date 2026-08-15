/**
 * Lead Persistence — JARVIS Worker 1
 *
 * Canonical Supabase/Postgres write path for the property intelligence
 * engine: property, parcel, owner, lead, and lead-score rows.
 *
 * Upserts are keyed deterministically:
 *   - property by dedupeKey (or parcelId unique),
 *   - parcel by (parcelId, county, state),
 *   - lead-score by leadId.
 */

import crypto from 'node:crypto';
import type { PrismaClient } from '@prisma/client';
import type {
  LeadDraft,
  LeadScoreDraft,
  OwnerDraft,
  ParcelDraft,
  PropertyDraft,
} from './types';

export interface PropertyRow {
  id: string;
  created: boolean;
}

export interface LeadPersistence {
  upsertProperty(p: PropertyDraft): Promise<PropertyRow>;
  upsertParcel(p: ParcelDraft): Promise<{ id: string }>;
  upsertOwner(o: OwnerDraft): Promise<{ id: string }>;
  upsertLead(l: LeadDraft): Promise<{ id: string }>;
  upsertLeadScore(s: LeadScoreDraft): Promise<void>;
}

export class PrismaLeadPersistence implements LeadPersistence {
  constructor(private readonly db: PrismaClient) {}

  async upsertProperty(p: PropertyDraft): Promise<PropertyRow> {
    const existing = p.dedupeKey
      ? await this.db.property.findUnique({ where: { dedupeKey: p.dedupeKey } })
      : null;

    if (existing) {
      await this.db.property.update({
        where: { id: existing.id },
        data: {
          addressLine1: p.addressLine1,
          addressLine2: p.addressLine2 ?? null,
          normalizedAddress: p.normalizedAddress ?? null,
          city: p.city,
          state: p.state,
          zip: p.zip,
          county: p.county,
          propertyType: p.propertyType as never,
          estimatedValue: p.estimatedValue ?? null,
          assessedValue: p.assessedValue ?? null,
          lastSalePrice: p.lastSalePrice ?? null,
        },
      });
      return { id: existing.id, created: false };
    }

    const created = await this.db.property.create({
      data: {
        parcelId: p.parcelId,
        addressLine1: p.addressLine1,
        addressLine2: p.addressLine2 ?? null,
        normalizedAddress: p.normalizedAddress ?? null,
        dedupeKey: p.dedupeKey ?? null,
        city: p.city,
        state: p.state,
        zip: p.zip,
        county: p.county,
        propertyType: p.propertyType as never,
        estimatedValue: p.estimatedValue ?? null,
        assessedValue: p.assessedValue ?? null,
        lastSalePrice: p.lastSalePrice ?? null,
      },
      select: { id: true },
    });
    return { id: created.id, created: true };
  }

  async upsertParcel(p: ParcelDraft): Promise<{ id: string }> {
    const parcel = await this.db.parcel.upsert({
      where: {
        parcelId_county_state: {
          parcelId: p.parcelId,
          county: p.county,
          state: p.state,
        },
      },
      create: {
        parcelId: p.parcelId,
        apnNormalized: p.apnNormalized ?? p.parcelId,
        county: p.county,
        state: p.state,
        legalDescription: p.legalDescription ?? null,
        propertyId: p.propertyId,
        source: p.source ?? null,
        sourceUrl: p.sourceUrl ?? null,
        sourceReference: p.sourceReference ?? null,
        verificationStatus: p.verificationStatus as never,
        confidence: p.confidence,
        lastVerified: p.lastVerified ?? null,
      },
      update: {
        apnNormalized: p.apnNormalized ?? p.parcelId,
        propertyId: p.propertyId,
        source: p.source ?? null,
        sourceUrl: p.sourceUrl ?? null,
        sourceReference: p.sourceReference ?? null,
        verificationStatus: p.verificationStatus as never,
        confidence: p.confidence,
        lastVerified: p.lastVerified ?? null,
      },
      select: { id: true },
    });
    return parcel;
  }

  async upsertOwner(o: OwnerDraft): Promise<{ id: string }> {
    const created = await this.db.owner.create({
      data: {
        propertyId: o.propertyId,
        name: o.name,
        ownerType: o.ownerType as never,
        mailingAddress: o.mailingAddress,
        isAbsentee: o.isAbsentee,
        confidenceScore: o.confidenceScore,
        verificationStatus: o.verificationStatus as never,
        source: o.source ?? null,
        sourceUrl: o.sourceUrl ?? null,
        sourceReference: o.sourceReference ?? null,
        verifiedAt: o.verifiedAt ?? null,
        lastVerified: o.lastVerified ?? null,
      },
      select: { id: true },
    });
    return created;
  }

  async upsertLead(l: LeadDraft): Promise<{ id: string }> {
    const created = await this.db.lead.create({
      data: {
        propertyId: l.propertyId,
        niche: l.niche as never,
        status: l.status as never,
        grade: l.grade as never,
        score: l.score,
        callabilityScore: l.callabilityScore ?? null,
        confidence: l.confidence,
        signals: l.signals as never,
        phone: l.phone ?? null,
        email: l.email ?? null,
        contactName: l.contactName ?? null,
      },
      select: { id: true },
    });
    return created;
  }

  async upsertLeadScore(s: LeadScoreDraft): Promise<void> {
    await this.db.leadScore.upsert({
      where: { leadId: s.leadId },
      create: {
        leadId: s.leadId,
        overallScore: s.overallScore,
        callabilityScore: s.callabilityScore ?? null,
        callabilityBreakdown: s.callabilityBreakdown as never,
        ownershipConfidence: s.ownershipConfidence,
        recordFreshness: s.recordFreshness,
        absenteeSignal: s.absenteeSignal,
        vacancyIndicators: s.vacancyIndicators,
        violationSeverity: s.violationSeverity,
        taxDelinquency: s.taxDelinquency,
        equityProxy: s.equityProxy,
        commercialOpportunity: s.commercialOpportunity,
        dataCompleteness: s.dataCompleteness,
        duplicatePenalty: s.duplicatePenalty,
      },
      update: {
        overallScore: s.overallScore,
        callabilityScore: s.callabilityScore ?? null,
        callabilityBreakdown: s.callabilityBreakdown as never,
        ownershipConfidence: s.ownershipConfidence,
        recordFreshness: s.recordFreshness,
        absenteeSignal: s.absenteeSignal,
        vacancyIndicators: s.vacancyIndicators,
        violationSeverity: s.violationSeverity,
        taxDelinquency: s.taxDelinquency,
        equityProxy: s.equityProxy,
        commercialOpportunity: s.commercialOpportunity,
        dataCompleteness: s.dataCompleteness,
        duplicatePenalty: s.duplicatePenalty,
      },
    });
  }
}

export class InMemoryLeadPersistence implements LeadPersistence {
  properties: Map<string, { id: string } & PropertyDraft> = new Map();
  parcels: Map<string, { id: string } & ParcelDraft> = new Map();
  owners: Array<{ id: string } & OwnerDraft> = [];
  leads: Map<string, { id: string } & LeadDraft> = new Map();
  leadScores: Map<string, { leadId: string } & LeadScoreDraft> = new Map();

  async upsertProperty(p: PropertyDraft): Promise<PropertyRow> {
    if (p.dedupeKey) {
      for (const row of this.properties.values()) {
        if (row.dedupeKey === p.dedupeKey) {
          this.properties.set(row.id, { id: row.id, ...p });
          return { id: row.id, created: false };
        }
      }
    }
    const id = crypto.randomUUID();
    this.properties.set(id, { id, ...p });
    return { id, created: true };
  }

  async upsertParcel(p: ParcelDraft): Promise<{ id: string }> {
    const key = `${p.parcelId}::${p.county}::${p.state}`;
    const existing = this.parcels.get(key);
    if (existing) {
      this.parcels.set(key, { id: existing.id, ...p });
      return { id: existing.id };
    }
    const id = crypto.randomUUID();
    this.parcels.set(key, { id, ...p });
    return { id };
  }

  async upsertOwner(o: OwnerDraft): Promise<{ id: string }> {
    const id = crypto.randomUUID();
    this.owners.push({ id, ...o });
    return { id };
  }

  async upsertLead(l: LeadDraft): Promise<{ id: string }> {
    const id = crypto.randomUUID();
    this.leads.set(id, { id, ...l });
    return { id };
  }

  async upsertLeadScore(s: LeadScoreDraft): Promise<void> {
    this.leadScores.set(s.leadId, { ...s });
  }
}