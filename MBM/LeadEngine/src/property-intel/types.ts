/**
 * Property Intelligence Engine — Shared Contracts
 * JARVIS Worker 1
 */

import type { SourceType } from '@prisma/client';

export type VerificationStatus =
  | 'UNVERIFIED'
  | 'PENDING'
  | 'VERIFIED'
  | 'REJECTED'
  | 'EXPIRED';

export type NegativeDisposition =
  | 'BAD_NUMBER'
  | 'WRONG_PERSON'
  | 'NON_OWNER'
  | 'DUPLICATE'
  | 'DNC'
  | 'SOLD'
  | 'NOT_INTERESTED';

export type DispositionType = NegativeDisposition | 'OTHER';

/** All negative dispositions are permanent suppression by default. */
export const NEGATIVE_DISPOSITIONS: readonly NegativeDisposition[] = [
  'BAD_NUMBER',
  'WRONG_PERSON',
  'NON_OWNER',
  'DUPLICATE',
  'DNC',
  'SOLD',
  'NOT_INTERESTED',
];

export const PERMANENT_DISPOSITIONS: ReadonlySet<NegativeDisposition> =
  new Set(NEGATIVE_DISPOSITIONS);

export interface EvidenceDraft {
  leadId?: string | null;
  propertyId?: string | null;
  parcelId?: string | null;
  ownerId?: string | null;
  source: string;
  sourceType: SourceType;
  sourceReference?: string | null;
  sourceUrl?: string | null;
  rawPayloadHash: string;
  verificationStatus: VerificationStatus;
  confidence: number;
  retrievedAt: Date;
  lastVerified?: Date | null;
}

export interface ProvenanceTransitionDraft {
  fromStage: string;
  toStage: string;
  workerId?: string | null;
  status: 'SUCCESS' | 'WARNING' | 'REJECTED';
  metadata?: Record<string, unknown> | null;
}

export interface DispositionDraft {
  leadId?: string | null;
  propertyId?: string | null;
  phone: string;
  type: DispositionType;
  reason?: string | null;
  permanent?: boolean;
  source?: string;
  recordedBy?: string | null;
  expiresAt?: Date | null;
}

export interface ScoringConfigDraft {
  name: string;
  scope: string;
  scopeValue?: string | null;
  weights: Record<string, number>;
  enabled: boolean;
}

export interface RejectionRecordDraft {
  rejectionKey: string;
  phone: string;
  parcelId?: string | null;
  addressKey?: string | null;
  reasons: string[];
  permanent: boolean;
  source?: string;
  recordedAt: Date;
}

export interface PropertyDraft {
  parcelId: string;
  addressLine1: string;
  addressLine2?: string | null;
  normalizedAddress?: string | null;
  dedupeKey?: string | null;
  city: string;
  state: string;
  zip: string;
  county: string;
  propertyType: string;
  estimatedValue?: number | null;
  assessedValue?: number | null;
  lastSalePrice?: number | null;
}

export interface ParcelDraft {
  parcelId: string;
  apnNormalized?: string | null;
  county: string;
  state: string;
  legalDescription?: string | null;
  propertyId: string;
  source?: string | null;
  sourceUrl?: string | null;
  sourceReference?: string | null;
  verificationStatus: VerificationStatus;
  confidence: number;
  lastVerified?: Date | null;
}

export interface OwnerDraft {
  propertyId: string;
  name: string;
  ownerType: string;
  mailingAddress: string;
  isAbsentee: boolean;
  confidenceScore: number;
  verificationStatus: VerificationStatus;
  source?: string | null;
  sourceUrl?: string | null;
  sourceReference?: string | null;
  verifiedAt?: Date | null;
  lastVerified?: Date | null;
}

export interface LeadDraft {
  propertyId: string;
  niche: string;
  status: string;
  grade?: string | null;
  score: number;
  callabilityScore?: number | null;
  confidence: number;
  signals?: Record<string, unknown> | null;
  phone?: string | null;
  email?: string | null;
  contactName?: string | null;
}

export interface LeadScoreDraft {
  leadId: string;
  overallScore: number;
  callabilityScore?: number | null;
  callabilityBreakdown?: Record<string, unknown> | null;
  ownershipConfidence: number;
  recordFreshness: number;
  absenteeSignal: number;
  vacancyIndicators: number;
  violationSeverity: number;
  taxDelinquency: number;
  equityProxy: number;
  commercialOpportunity: number;
  dataCompleteness: number;
  duplicatePenalty: number;
}