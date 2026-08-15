import { describe, it, expect } from 'vitest';
import {
  PropertyIntelSyncService,
  InMemoryEvidenceRepository,
  InMemoryLeadPersistence,
  PropertyDedupeRegistry,
  InMemoryDispositionRepository,
  DispositionRegistry,
  RejectionLedger,
  InMemoryRejectionLedgerRepository,
} from '../src/property-intel';
import type { PropertyIntelSyncInput } from '../src/property-intel/property-intel-sync';
import { MasterPipelineOrchestrator } from '../src/pipeline';

function syncInput(overrides?: Partial<PropertyIntelSyncInput>): PropertyIntelSyncInput {
  return {
    sourceSystem: 'MIAMI_DADE_COUNTY',
    sourceType: 'COUNTY_ASSESSOR',
    sourceReference: 'FOLIO-045882019A',
    sourceUrl: 'https://miamidade.gov/property/search/045882019A',
    rawPayload: { folio: '045882019A', owner: 'Marcus Vance' },
    property: {
      parcelId: '045-882-019-A',
      addressLine1: '1420 Ocean Drive',
      normalizedAddress: '1420 OCEAN DR, MIAMI BEACH, FL 33139',
      dedupeKey: 'abc123',
      city: 'Miami Beach',
      state: 'FL',
      zip: '33139',
      county: 'Miami-Dade',
      propertyType: 'SINGLE_FAMILY',
      estimatedValue: 1250000,
    },
    parcel: {
      parcelId: '045-882-019-A',
      county: 'Miami-Dade',
      state: 'FL',
      legalDescription: 'LOT 12 BLK 4',
      source: 'MIAMI_DADE_AP',
      sourceType: 'COUNTY_ASSESSOR',
      sourceReference: 'FOLIO-045882019A',
      verificationStatus: 'VERIFIED',
      confidence: 0.98,
    },
    owners: [
      {
        ownerName: 'Marcus Vance',
        ownerType: 'INDIVIDUAL',
        mailingAddress: '1420 Ocean Drive, Miami Beach, FL 33139',
        isAbsentee: false,
        source: 'MIAMI_DADE_AP',
        sourceType: 'COUNTY_ASSESSOR',
        verificationStatus: 'VERIFIED',
        confidence: 0.95,
      },
    ],
    lead: {
      propertyId: '',
      niche: 'HIGH_EQUITY',
      status: 'NEW',
      score: 88,
      callabilityScore: 72,
      confidence: 0.9,
      phone: '3057684905',
      contactName: 'Marcus Vance',
    },
    leadScore: {
      leadId: '',
      overallScore: 88,
      callabilityScore: 72,
      ownershipConfidence: 0.95,
      recordFreshness: 0.8,
      absenteeSignal: 0,
      vacancyIndicators: 0,
      violationSeverity: 0,
      taxDelinquency: 0,
      equityProxy: 0.5,
      commercialOpportunity: 0,
      dataCompleteness: 0.7,
      duplicatePenalty: 0,
    },
    provenanceTransitions: [
      { fromStage: 'EVIDENCE', toStage: 'LEAD_SCORE', workerId: 'WORKER_3_COMMANDER', status: 'SUCCESS' },
      { fromStage: 'LEAD_SCORE', toStage: 'CALLABILITY_SCORE', workerId: 'WORKER_3_COMMANDER', status: 'SUCCESS' },
      { fromStage: 'CALLABILITY_SCORE', toStage: 'DIALER', workerId: 'WORKER_3_COMMANDER', status: 'SUCCESS' },
    ],
    ...overrides,
  };
}

describe('PropertyIntelSyncService — canonical Supabase write path', () => {
  it('persists property, parcel, owner, evidence, lead and score atomically', async () => {
    const persistence = new InMemoryLeadPersistence();
    const evidence = new InMemoryEvidenceRepository();
    const sync = new PropertyIntelSyncService(persistence, evidence, new PropertyDedupeRegistry(null));

    const result = await sync.sync(syncInput());

    expect(result.propertyId).toBeTruthy();
    expect(result.parcelId).toBeTruthy();
    expect(result.ownerIds).toHaveLength(1);
    expect(result.leadId).toBeTruthy();
    expect(result.evidenceIds).toHaveLength(2); // parcel + owner evidence

    // Lead score attached.
    expect(persistence.leadScores.has(result.leadId)).toBe(true);
    expect(persistence.leadScores.get(result.leadId)!.callabilityScore).toBe(72);

    // Provenance transitions persisted on the parcel evidence.
    const allEvidence = evidence.getAll();
    expect(allEvidence[0].transitions.length).toBeGreaterThanOrEqual(1);
  });

  it('does not store the same property twice (dedupe + dedupeKey)', async () => {
    const persistence = new InMemoryLeadPersistence();
    const dedupe = new PropertyDedupeRegistry(null);
    const sync = new PropertyIntelSyncService(persistence, new InMemoryEvidenceRepository(), dedupe);

    const first = await sync.sync(syncInput());
    const second = await sync.sync(syncInput({ property: { ...syncInput().property, parcelId: '045882019A' } }));

    expect(persistence.properties.size).toBe(1);
    expect(second.propertyId).toBe(first.propertyId);
  });

  it('records dispositions and previous rejections through the registry + ledger', async () => {
    const dispositionRepo = new InMemoryDispositionRepository();
    const dispositionRegistry = new DispositionRegistry(dispositionRepo);
    const ledger = new RejectionLedger(new InMemoryRejectionLedgerRepository());

    // A previous rejection on the same identity must block a new run.
    await ledger.recordRejection({
      phone: '3057684905',
      parcelId: '045-882-019-A',
      addressKey: 'abc123',
      reasons: ['INVALID_CONTACT_SOURCE'],
    });
    const codes = await ledger.rejectionCodesFor({
      phone: '3057684905',
      parcelId: '045-882-019-A',
      addressKey: 'abc123',
    });
    expect(codes).toContain('INVALID_CONTACT_SOURCE');

    // And the disposition registry blocks a DNC phone.
    await dispositionRegistry.record({ phone: '3057684905', type: 'DNC' });
    const blocked = await dispositionRegistry.suppressionCodesFor('3057684905');
    expect(blocked).toContain('DNC');
  });

  it('integrates with the orchestrator to reject previously rejected garbage', async () => {
    const ledger = new RejectionLedger(new InMemoryRejectionLedgerRepository());
    const orchestrator = new MasterPipelineOrchestrator({ rejectionLedger: ledger });

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
      rawOwner: { name: 'Action Required Owner' },
      rawContact: { name: 'Action Required Owner', phone: '5551234567', source: 'SKIP_TRACE' },
    };

    const first = await orchestrator.processPipeline(fakeLead);
    expect(first.stageReached).toBe('HUMAN_REVIEW');

    // Re-import the SAME lead — must be blocked again, automatically.
    const second = await orchestrator.processPipeline(fakeLead);
    expect(second.stageReached).toBe('HUMAN_REVIEW');
    expect(second.rejectedReason).toContain('PREVIOUSLY_REJECTED');
  });
});