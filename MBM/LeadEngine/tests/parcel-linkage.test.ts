import { describe, it, expect } from 'vitest';
import { ParcelLinkageService } from '../src/property-intel';
import type { PropertyDraft } from '../src/property-intel/types';

const PROPERTY: PropertyDraft = {
  parcelId: '045-882-019-A',
  addressLine1: '1420 Ocean Drive',
  city: 'Miami Beach',
  state: 'FL',
  zip: '33139',
  county: 'Miami-Dade',
  propertyType: 'SINGLE_FAMILY',
  estimatedValue: 1250000,
};

describe('Parcel / APN Linkage — property → parcel → ownership evidence', () => {
  it('builds the parcel + ownership evidence chain with provenance', () => {
    const service = new ParcelLinkageService();
    const result = service.linkPropertyToParcel(
      PROPERTY,
      {
        parcelId: '045-882-019-A',
        county: 'Miami-Dade',
        state: 'FL',
        legalDescription: 'LOT 12 BLK 4',
        source: 'MIAMI_DADE_AP',
        sourceType: 'COUNTY_ASSESSOR',
        sourceUrl: 'https://miamidade.gov/property/search/045882019A',
        sourceReference: 'FOLIO-045882019A',
        verificationStatus: 'VERIFIED',
        confidence: 0.98,
        lastVerified: new Date('2026-08-01T00:00:00Z'),
      },
      [
        {
          ownerName: 'Marcus Vance',
          ownerType: 'INDIVIDUAL',
          mailingAddress: '1420 Ocean Drive, Miami Beach, FL 33139',
          isAbsentee: false,
          source: 'MIAMI_DADE_AP',
          sourceType: 'COUNTY_ASSESSOR',
          sourceReference: 'OWNER-SEQ-01',
          verificationStatus: 'VERIFIED',
          confidence: 0.95,
        },
      ],
      'prop-001',
    );

    expect(result.parcel.parcelId).toBe('045882019A');
    expect(result.parcel.propertyId).toBe('prop-001');
    expect(result.parcel.sourceUrl).toBe('https://miamidade.gov/property/search/045882019A');
    expect(result.parcel.verificationStatus).toBe('VERIFIED');
    expect(result.parcel.lastVerified).toBeInstanceOf(Date);

    expect(result.owners).toHaveLength(1);
    expect(result.owners[0].name).toBe('Marcus Vance');
    expect(result.owners[0].verificationStatus).toBe('VERIFIED');
    expect(result.owners[0].sourceReference).toBe('OWNER-SEQ-01');

    // Evidence: parcel evidence + owner evidence, each with transitions.
    expect(result.evidence).toHaveLength(2);
    expect(result.evidence[0].descriptor.source).toBe('MIAMI_DADE_AP');
    expect(result.evidence[0].descriptor.rawPayloadHash).toBeTruthy();
    expect(result.evidence[0].transitions[0].fromStage).toBe('NORMALIZE');
    expect(result.evidence[0].transitions[0].toStage).toBe('PARCEL_APN');
    expect(result.evidence[1].descriptor.ownerId).toBeNull();
    expect(result.evidence[1].transitions[0].toStage).toBe('OWNERSHIP_VERIFICATION');
  });

  it('marks owners UNVERIFIED when no evidence source confirms them', () => {
    const service = new ParcelLinkageService();
    const result = service.linkPropertyToParcel(
      PROPERTY,
      { parcelId: 'X-1', county: 'Dallas', state: 'TX', source: 'UNKNOWN', sourceType: 'OPEN_RECORDS' },
      [{ ownerName: 'John Doe', ownerType: 'INDIVIDUAL', mailingAddress: '1 St', source: 'UNKNOWN', sourceType: 'OPEN_RECORDS' }],
      'prop-002',
    );
    expect(result.parcel.verificationStatus).toBe('UNVERIFIED');
    expect(result.owners[0].verificationStatus).toBe('UNVERIFIED');
    expect(result.owners[0].verifiedAt).toBeNull();
  });
});