/**
 * NPI Clinic → Vertical Evidence Mapper
 *
 * Maps real CMS NPI Registry clinic records from `leads_database.json` into
 * `BusinessEvidence` for the Multi-Vertical AI Sales Engine. Provenance is
 * preserved verbatim (CMS NPI Registry API v2.1, NPI number, source URL).
 *
 * Honesty rules:
 * - Never fabricate business facts. The NPI registry supplies identity,
 *   location, phone, and the authorized official — NOT website/digital/
 *   booking/headcount signals. Those fields are left UNKNOWN (undefined),
 *   and the scoring engine will NOT assert a "no website"/"no online booking"
 *   gap from missing data.
 * - Unrecognized taxonomies are skipped (never force-mapped into a vertical).
 */

import type { BusinessEvidence, DecisionMakerEvidence } from './types';

export interface NpiClinicRecord {
  id?: string;
  name?: string;
  company?: string;
  phone?: string;
  alt_phone?: string;
  email?: string;
  website?: string;
  npi?: string;
  npi_number?: string;
  source?: string;
  authorized_official_name?: string;
  details?: {
    taxonomy?: string;
    vertical_tag?: string;
    authorized_official_title?: string;
    authorized_official_phone?: string;
    city?: string;
    state?: string;
    address?: string;
    source?: string;
    Owner_Name?: string;
    Owner_Title?: string;
  };
  [k: string]: unknown;
}

/** Taxonomy → vertical catalog id. Unknown taxonomies are intentionally absent. */
export const NPI_TAXONOMY_VERTICAL_MAP: Record<string, string> = {
  'Physical Therapist': 'physical_therapy',
  'Physical Therapy Assistant': 'physical_therapy',
  'Physical Medicine & Rehabilitation, Sports Medicine': 'physical_therapy',
  'Physical Therapist, Hand': 'physical_therapy',
  'Physical Therapist, Orthopedic': 'physical_therapy',
  'Physical Therapist, Sports': 'physical_therapy',
  'Physical Therapist, Neurology': 'physical_therapy',
  'Physical Therapist, Pediatrics': 'physical_therapy',
  'Physical Therapist, Geriatrics': 'physical_therapy',
  'Occupational Therapist': 'physical_therapy',
  'Occupational Therapy Assistant': 'physical_therapy',
  'Occupational Therapist, Pediatrics': 'physical_therapy',
  'Speech-Language Pathologist,': 'physical_therapy',
  'Specialist/Technologist, Athletic Trainer': 'physical_therapy',
  'Clinic/Center, Rehabilitation': 'physical_therapy',
  Chiropractor: 'chiropractors',
  'Chiropractor, Rehabilitation': 'chiropractors',
  'Chiropractor, Sports Physician': 'chiropractors',
  'Chiropractor, Orthopedic': 'chiropractors',
  'Chiropractor, Nutrition': 'chiropractors',
  'Chiropractor, Independent Medical Examiner': 'chiropractors',
  'Chiropractor, Neurology': 'chiropractors',
  Acupuncturist: 'wellness',
  'Dietitian, Registered': 'nutrition',
  Counselor: 'wellness',
  'Behavior Analyst': 'wellness',
};

export const NPI_SOURCE = 'CMS NPI Registry API v2.1';
export const NPI_SOURCE_URL = 'https://npiregistry.cms.hhs.gov/api/';

export interface NpiMappingResult {
  verticalId: string;
  evidence: BusinessEvidence;
  record: NpiClinicRecord;
}

export interface NpiMapperReport {
  totalRecords: number;
  mappedCount: number;
  skippedUnmappedCount: number;
  skippedNoPhoneCount: number;
  skippedTaxonomies: Record<string, number>;
  verticalCounts: Record<string, number>;
}

/**
 * Map a single NPI clinic record. Returns null when the record cannot be
 * honestly mapped (no phone, or taxonomy outside the catalog).
 */
export function mapNpiRecord(record: NpiClinicRecord): NpiMappingResult | null {
  const taxonomy = record.details?.taxonomy;
  const verticalId = taxonomy ? NPI_TAXONOMY_VERTICAL_MAP[taxonomy] : undefined;
  if (!verticalId) return null;

  const phone = normalizeNpiPhone(record.phone ?? record.details?.authorized_official_phone ?? '');
  if (!phone) return null;

  const officialName = record.details?.Owner_Name || record.authorized_official_name || undefined;
  const officialTitle = record.details?.Owner_Title || record.details?.authorized_official_title || undefined;
  const decisionMaker: DecisionMakerEvidence | undefined =
    officialName || officialTitle
      ? { name: officialName ?? null, title: officialTitle ?? null }
      : undefined;

  const npiNumber = record.npi_number || record.npi || null;
  const retrievedAt = new Date().toISOString();

  const evidence: BusinessEvidence = {
    company: record.company || record.name || `NPI ${npiNumber ?? 'unknown'}`,
    industry: taxonomy,
    location:
      record.details?.city && record.details?.state
        ? { city: record.details.city, state: record.details.state }
        : undefined,
    contact: {
      phone,
      email: record.email?.trim() || null,
      source: NPI_SOURCE,
    },
    decisionMaker,
    source: record.details?.source || record.source || NPI_SOURCE,
    sourceUrl: NPI_SOURCE_URL,
    retrievedAt,
    // NPI supplies no website/digital/booking/headcount data — leave unknown.
    website: undefined,
    websiteQuality: undefined,
    digitalMaturity: undefined,
    bookingWorkflow: undefined,
    companySizeIndicators: undefined,
    reviewActivity: undefined,
    extra: {
      npi: npiNumber,
      taxonomy,
      address: record.details?.address ?? null,
      id: record.id ?? null,
      evidenceLimitation: 'NPI registry provides identity/contact only — digital-gap, buying, and automation signals are NOT evidencable from this source and were not asserted.',
    },
  };

  return { verticalId, evidence, record };
}

export function normalizeNpiPhone(raw: string): string | null {
  const digits = raw.replace(/\D/g, '');
  if (digits.length !== 10 && digits.length !== 11) return null;
  const ten = digits.length === 11 && digits.startsWith('1') ? digits.slice(1) : digits;
  if (ten.length !== 10 || ten.startsWith('0')) return null;
  return `+1${ten}`;
}

/** Map an entire lead database into vertical-scored evidence with a report. */
export function mapNpiLeads(records: NpiClinicRecord[]): {
  results: NpiMappingResult[];
  report: NpiMapperReport;
} {
  const report: NpiMapperReport = {
    totalRecords: records.length,
    mappedCount: 0,
    skippedUnmappedCount: 0,
    skippedNoPhoneCount: 0,
    skippedTaxonomies: {},
    verticalCounts: {},
  };

  const results: NpiMappingResult[] = [];
  for (const record of records) {
    const taxonomy = record.details?.taxonomy ?? '(none)';
    if (!NPI_TAXONOMY_VERTICAL_MAP[taxonomy]) {
      report.skippedUnmappedCount++;
      report.skippedTaxonomies[taxonomy] = (report.skippedTaxonomies[taxonomy] ?? 0) + 1;
      continue;
    }
    const mapped = mapNpiRecord(record);
    if (!mapped) {
      report.skippedNoPhoneCount++;
      continue;
    }
    report.mappedCount++;
    report.verticalCounts[mapped.verticalId] = (report.verticalCounts[mapped.verticalId] ?? 0) + 1;
    results.push(mapped);
  }
  return { results, report };
}