import { describe, it, expect } from 'vitest';
import { PreDialGateEngine } from '../src/pipeline/predial-gate';
import type { PropertyIdentity, OwnershipRecord, ContactEvidence } from '../src/pipeline/types';

describe('FiveWhysExplainability Engine', () => {
  const property: PropertyIdentity = {
    parcelId: 'TX-DAL-99214',
    addressLine1: '4820 Elm Street',
    city: 'Dallas',
    state: 'TX',
    zip: '75201',
    county: 'Dallas',
    propertyType: 'COMMERCIAL',
    estimatedValue: 2400000,
  };

  const owner: OwnershipRecord = {
    ownerName: 'Apex Health Holdings LLC',
    ownerType: 'LLC',
    mailingAddress: '100 Main St, Austin, TX 78701',
    isAbsentee: true,
    confidenceScore: 0.96,
    corporateOfficerName: 'Dr. Sarah Jenkins',
    corporateOfficerTitle: 'Managing Partner',
    verifiedAt: new Date().toISOString(),
  };

  const contact: ContactEvidence = {
    contactName: 'Dr. Sarah Jenkins',
    phone: '2145558912', // Note: 555 here is just mock text for explainability format test
    email: 'sjenkins@apexhealth.com',
    source: 'CMS_NPI',
    carrierType: 'MOBILE',
    lineStatus: 'ACTIVE',
    dncStatus: 'CLEAN',
    confidenceScore: 0.98,
    extractedAt: new Date().toISOString(),
  };

  it('generates clear, comprehensive 5 Whys responses for all top queue leads', () => {
    const engine = new PreDialGateEngine();
    const explainability = engine.generateExplainability(
      property,
      owner,
      contact,
      88,
      'COMMERCIAL_DISTRESS',
      {
        equityPercent: 72,
        triggerEvent: 'Pre-foreclosure notice filed with Dallas county registrar',
      }
    );

    // 1. Why this lead?
    expect(explainability.whyThisLead).toContain('Dallas, TX');
    expect(explainability.whyThisLead).toContain('72% estimated equity');
    expect(explainability.whyThisLead).toContain('Lead Score: 88/100');

    // 2. Why this owner?
    expect(explainability.whyThisOwner).toContain('Apex Health Holdings LLC');
    expect(explainability.whyThisOwner).toContain('confirmed absentee status');

    // 3. Why this contact?
    expect(explainability.whyThisContact).toContain('Dr. Sarah Jenkins');
    expect(explainability.whyThisContact).toContain('CMS_NPI');
    expect(explainability.whyThisContact).toContain('98% verified provenance');

    // 4. Why now?
    expect(explainability.whyNow).toContain('Pre-foreclosure notice filed');

    // 5. Why call?
    expect(explainability.whyCall).toContain('passed carrier verification');
    expect(explainability.whyCall).toContain('clean DNC status');

    expect(explainability.confidenceScore).toBeGreaterThanOrEqual(0.95);
  });
});
