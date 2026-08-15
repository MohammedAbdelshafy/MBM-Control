import { describe, it, expect } from 'vitest';
import { MasterPipelineOrchestrator } from '../src/pipeline/orchestrator';

describe('MasterPipelineOrchestrator — End-to-End Pipeline Integration', () => {
  it('processes a raw lead through all 16 pipeline stages to active dialer queue', async () => {
    const orchestrator = new MasterPipelineOrchestrator();

    const rawLead = {
      sourceSystem: 'CMS_NPI_REGISTRY',
      sourceRecordId: 'NPI-1049283719',
      rawProperty: {
        address: '742 Evergreen Terrace',
        city: 'Springfield',
        state: 'IL',
        zip: '62704',
        county: 'Sangamon',
        apn: 'IL-SAN-742-01',
        propertyType: 'SINGLE_FAMILY',
        estimatedValue: 380000,
      },
      rawOwner: {
        name: 'Homer Simpson',
        ownerType: 'INDIVIDUAL',
        mailingAddress: '742 Evergreen Terrace, Springfield, IL 62704',
        isAbsentee: false,
      },
      rawContact: {
        name: 'Homer Simpson',
        phone: '2174928172',
        email: 'homer@springfieldnuclear.com',
        source: 'CMS_NPI',
        carrierType: 'MOBILE',
      },
      distressSignals: {
        niche: 'HIGH_EQUITY_ABSENTEE',
        equityPercent: 78,
        violationType: 'Utility shutoff warning issued',
      },
    };

    const result = await orchestrator.processPipeline(rawLead);

    expect(result.stageReached).toBe('DIALER');
    expect(result.lead).toBeDefined();

    const lead = result.lead!;
    expect(lead.leadScore).toBeGreaterThan(50);
    expect(lead.callabilityScore).toBeGreaterThan(60);
    expect(lead.gateResult.isCallable).toBe(true);
    expect(lead.crmSynced).toBe(true);
    expect(lead.dialerStatus).toBe('READY_TO_DIAL');
    expect(lead.netellerCheckoutSku).toContain('DEAL-');

    // Verify 5 Whys
    expect(lead.explainability.whyThisLead).toBeDefined();
    expect(lead.explainability.whyThisOwner).toBeDefined();
    expect(lead.explainability.whyThisContact).toBeDefined();
    expect(lead.explainability.whyNow).toBeDefined();
    expect(lead.explainability.whyCall).toBeDefined();

    // Verify Evidence & Provenance Trail
    expect(lead.evidence.provenanceTrail.length).toBeGreaterThanOrEqual(7);
    expect(lead.evidence.supabaseSyncedAt).toBeDefined();
  });

  it('stops at HUMAN_REVIEW stage when a lead fails the hard pre-dial gate', async () => {
    const orchestrator = new MasterPipelineOrchestrator();

    const fakeLead = {
      sourceSystem: 'SCRAPED_PORTAL',
      rawProperty: {
        address: '100 Dummy Lane',
        city: 'Nowhere',
        state: 'NY',
        zip: '10001',
        county: 'New York',
        apn: 'NY-100',
      },
      rawOwner: {
        name: 'Action Required Owner',
      },
      rawContact: {
        name: 'Action Required Owner',
        phone: '5551234567', // Bad 555 number
        source: 'SKIP_TRACE',
      },
    };

    const result = await orchestrator.processPipeline(fakeLead);

    expect(result.stageReached).toBe('HUMAN_REVIEW');
    expect(result.lead).toBeUndefined();
    expect(result.rejectedReason).toBeDefined();
  });
});
