import { describe, it, expect } from 'vitest';
import {
  VerticalRegistry,
  mapNpiRecord,
  mapNpiLeads,
  NPI_TAXONOMY_VERTICAL_MAP,
  NPI_SOURCE,
  NPI_SOURCE_URL,
  computeVerticalScore,
  analyzeOpportunity,
  normalizeNpiPhone,
} from '../src/verticals';
import type { NpiClinicRecord } from '../src/verticals';

const registry = new VerticalRegistry();

const PT_RECORD: NpiClinicRecord = {
  id: 'Clinics-1',
  name: 'Ackerman Susan',
  company: 'Ackerman Susan',
  phone: '+12089362522',
  email: '',
  website: '',
  npi: '1437534781',
  npi_number: '1437534781',
  source: NPI_SOURCE,
  authorized_official_name: 'ACKERMAN SUSAN',
  details: {
    taxonomy: 'Physical Therapist',
    vertical_tag: 'PT',
    authorized_official_title: 'Practice Administrator',
    authorized_official_phone: '+12089362522',
    city: 'NAMPA',
    state: 'ID',
    address: '16211 N BRINSON ST STE 220, NAMPA, ID 836875525',
    source: NPI_SOURCE,
    Owner_Name: 'ACKERMAN SUSAN',
    Owner_Title: 'Practice Administrator',
  },
};

describe('NPI → Vertical Evidence Mapper — real clinics, preserved provenance', () => {
  it('maps a Physical Therapist to the physical_therapy vertical', () => {
    const mapped = mapNpiRecord(PT_RECORD);
    expect(mapped).not.toBeNull();
    expect(mapped!.verticalId).toBe('physical_therapy');
    expect(mapped!.evidence.company).toBe('Ackerman Susan');
    expect(mapped!.evidence.location).toEqual({ city: 'NAMPA', state: 'ID' });
    expect(mapped!.evidence.contact!.phone).toBe('+12089362522');
    expect(mapped!.evidence.decisionMaker).toEqual({
      name: 'ACKERMAN SUSAN',
      title: 'Practice Administrator',
    });
  });

  it('preserves provenance verbatim including the NPI number', () => {
    const mapped = mapNpiRecord(PT_RECORD)!;
    expect(mapped.evidence.source).toBe(NPI_SOURCE);
    expect(mapped.evidence.sourceUrl).toBe(NPI_SOURCE_URL);
    expect(mapped.evidence.industry).toBe('Physical Therapist');
    expect(mapped.evidence.extra!.npi).toBe('1437534781');
    expect(typeof mapped.evidence.retrievedAt).toBe('string');
  });

  it('NEVER fabricates website/digital/booking signals that NPI does not provide', () => {
    const mapped = mapNpiRecord(PT_RECORD)!;
    expect(mapped.evidence.website).toBeUndefined();
    expect(mapped.evidence.websiteQuality).toBeUndefined();
    expect(mapped.evidence.digitalMaturity).toBeUndefined();
    expect(mapped.evidence.companySizeIndicators).toBeUndefined();

    const score = computeVerticalScore(registry.require('physical_therapy'), mapped.evidence);
    // Digital gap must stay at base — no "outdated site"/"no website" assertion.
    expect(score.dimensionScores.digitalGap.score).toBeLessThan(40);

    const op = analyzeOpportunity({ vertical: registry.require('physical_therapy'), evidence: mapped.evidence, score });
    expect(op.whatProblem).not.toMatch(/no website/);
    expect(op.whatProblem).not.toMatch(/outdated website/);
  });

  it('skips records without a valid phone and unknown taxonomies', () => {
    const noPhone = { ...PT_RECORD, phone: '555', details: { ...PT_RECORD.details, authorized_official_phone: '' } };
    expect(mapNpiRecord(noPhone)).toBeNull();

    const unknownTax = { ...PT_RECORD, details: { ...PT_RECORD.details, taxonomy: 'Internal Medicine' } };
    expect(mapNpiRecord(unknownTax)).toBeNull();
  });

  it('maps a full lead database with an honest report', () => {
    const chiro: NpiClinicRecord = {
      ...PT_RECORD,
      id: 'Clinics-2',
      details: { ...PT_RECORD.details!, taxonomy: 'Chiropractor', vertical_tag: 'CHIRO' },
    };
    const unknown: NpiClinicRecord = {
      ...PT_RECORD,
      id: 'Clinics-3',
      details: { ...PT_RECORD.details!, taxonomy: 'General Acute Care Hospital, Critical Access' },
    };
    const { results, report } = mapNpiLeads([PT_RECORD, chiro, unknown]);
    expect(results.length).toBe(2);
    expect(report.totalRecords).toBe(3);
    expect(report.mappedCount).toBe(2);
    expect(report.skippedUnmappedCount).toBe(1);
    expect(report.verticalCounts.physical_therapy).toBe(1);
    expect(report.verticalCounts.chiropractors).toBe(1);
  });

  it('normalizes NPI phones to E.164 and rejects invalid ones', () => {
    expect(normalizeNpiPhone('2089362522')).toBe('+12089362522');
    expect(normalizeNpiPhone('12089362522')).toBe('+12089362522');
    expect(normalizeNpiPhone('555')).toBeNull();
    expect(normalizeNpiPhone('')).toBeNull();
  });

  it('maps all catalog taxonomies to catalog verticals', () => {
    const registry2 = new VerticalRegistry();
    for (const verticalId of Object.values(NPI_TAXONOMY_VERTICAL_MAP)) {
      expect(registry2.require(verticalId).id).toBe(verticalId);
    }
  });
});