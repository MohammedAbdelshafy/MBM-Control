/**
 * Canonical Pipeline Interfaces & Data Contracts
 * JARVIS Worker 3 — Integration / QA / Deployment Commander
 */

export type PipelineStage =
  | 'SOURCE'
  | 'NORMALIZE'
  | 'DEDUPE'
  | 'PROPERTY_IDENTITY'
  | 'PARCEL_APN'
  | 'OWNERSHIP_VERIFICATION'
  | 'ENTITY_RESOLUTION'
  | 'ENRICHMENT'
  | 'EVIDENCE'
  | 'LEAD_SCORE'
  | 'CALLABILITY_SCORE'
  | 'HUMAN_REVIEW'
  | 'CRM'
  | 'DIALER'
  | 'OUTCOME'
  | 'FEEDBACK';

export interface PropertyIdentity {
  parcelId: string;
  addressLine1: string;
  addressLine2?: string | null;
  city: string;
  state: string;
  zip: string;
  county: string;
  lat?: number | null;
  lng?: number | null;
  propertyType: string;
  yearBuilt?: number | null;
  lotSizeSqft?: number | null;
  buildingSqft?: number | null;
  estimatedValue?: number | null;
  lastSaleDate?: string | null;
  lastSalePrice?: number | null;
  assessedValue?: number | null;
}

export interface OwnershipRecord {
  ownerName: string;
  ownerType: 'INDIVIDUAL' | 'LLC' | 'CORPORATION' | 'TRUST' | 'PARTNERSHIP' | 'GOVERNMENT' | 'OTHER';
  mailingAddress: string;
  isAbsentee: boolean;
  confidenceScore: number;
  deedBookPage?: string | null;
  corporateOfficerName?: string | null;
  corporateOfficerTitle?: string | null;
  verifiedAt: string;
}

export interface ContactEvidence {
  contactName: string;
  phone: string;
  email?: string | null;
  source: 'CMS_NPI' | 'COUNTY_TAX' | 'SKIP_TRACE' | 'SECRETARY_OF_STATE' | 'RAPIDAPI' | 'MANUAL_RESEARCH';
  sourceRecordId?: string | null;
  sourceUrl?: string | null;
  carrierType?: 'MOBILE' | 'LANDLINE' | 'VOIP' | 'UNKNOWN';
  lineStatus?: 'ACTIVE' | 'DISCONNECTED' | 'UNKNOWN';
  dncStatus: 'CLEAN' | 'LISTED' | 'EXEMPT';
  confidenceScore: number;
  extractedAt: string;
}

export interface FiveWhysExplainability {
  whyThisLead: string;
  whyThisOwner: string;
  whyThisContact: string;
  whyNow: string;
  whyCall: string;
  confidenceScore: number;
  calculatedAt: string;
}

export interface PreDialGateCheck {
  validProperty: boolean;
  validOwnerEntity: boolean;
  validContactSource: boolean;
  phoneQualityPass: boolean;
  noDuplicate: boolean;
  noSuppression: boolean;
  noBadNumberHistory: boolean;
  noPreviousRejection: boolean;
  isCallable: boolean;
  rejectionReasons: string[];
  evaluatedAt: string;
}

export interface ProvenanceTransition {
  fromStage: PipelineStage;
  toStage: PipelineStage;
  timestamp: string;
  workerId: 'WORKER_1' | 'WORKER_2' | 'WORKER_3_COMMANDER';
  status: 'SUCCESS' | 'WARNING' | 'REJECTED';
  metadata?: Record<string, unknown>;
}

export interface EvidenceRecord {
  id: string;
  leadId: string;
  propertyId: string;
  sourceSystem: string;
  sourceRecordId?: string | null;
  rawPayloadHash: string;
  provenanceTrail: ProvenanceTransition[];
  validatorSignature: string;
  supabaseSyncedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CallableDialerLead {
  leadId: string;
  property: PropertyIdentity;
  ownership: OwnershipRecord;
  contact: ContactEvidence;
  leadScore: number;
  callabilityScore: number;
  niche: string;
  explainability: FiveWhysExplainability;
  gateResult: PreDialGateCheck;
  evidence: EvidenceRecord;
  crmSynced: boolean;
  dialerStatus: 'READY_TO_DIAL' | 'DIALING' | 'ANSWERED' | 'NO_ANSWER' | 'VOICEMAIL' | 'CONVERTED' | 'DNC_SUPPRESSED';
  netellerCheckoutSku?: string | null;
}

/** Canonical dialer phone identity: digits only, US leading 1 dropped. */
export function normalizeDialerPhone(phone: string): string {
  const digits = phone.replace(/\D/g, '');
  return digits.length === 11 && digits.startsWith('1') ? digits.slice(1) : digits;
}
