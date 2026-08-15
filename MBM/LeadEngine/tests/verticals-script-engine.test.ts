import { describe, it, expect } from 'vitest';
import {
  VerticalRegistry,
  computeVerticalScore,
  analyzeOpportunity,
  renderPrimeScript,
  buildScriptContext,
  renderPlaceholders,
  hasUnrenderedPlaceholders,
  formatValueHypothesis,
} from '../src/verticals';
import { SCRIPT_SECTION_IDS, scriptSectionLabel } from '../src/verticals';
import type { BusinessEvidence, RenderedScript, TopCallRecord } from '../src/verticals';

const registry = new VerticalRegistry();

function runVertical(verticalId: string, evidence: BusinessEvidence): TopCallRecord {
  const vertical = registry.require(verticalId);
  const score = computeVerticalScore(vertical, evidence);
  return analyzeOpportunity({ vertical, evidence, score });
}

function evidenceFor(company: string, overrides: Partial<BusinessEvidence> = {}): BusinessEvidence {
  return {
    company,
    website: 'https://example.test',
    location: { city: 'Austin', state: 'TX' },
    decisionMaker: { name: 'Riley Owner', title: 'Owner', source: 'NPI' },
    contact: { phone: '+15125551234', email: 'owner@example.test', source: 'NPI' },
    websiteQuality: { hasWebsite: true, outdated: true, templateSite: true },
    digitalMaturity: { hasOnlineBooking: false, leadCaptureForm: false },
    bookingWorkflow: { manualOnly: true, responseTimeHours: 6 },
    aiOpportunitySignals: ['manual booking via phone', 'missed calls after hours', '24/7 demand'],
    automationOpportunitySignals: ['manual scheduling', 'no crm', 'paper intake'],
    source: 'CMS NPI Registry API v2.1',
    retrievedAt: new Date().toISOString(),
    ...overrides,
  };
}

const VERTICAL_IDS = ['hvac', 'pilates', 'med_spas', 'dental', 'law_firms', 'insurance', 'property_management', 'construction'];

describe('Dynamic Script Engine — 13 sections, evidence-driven, no fabrication', () => {
  it('renders all thirteen sections for every required vertical', () => {
    for (const id of VERTICAL_IDS) {
      const evidence = evidenceFor(`Case ${id} Co`);
      const record = runVertical(id, evidence);
      const vertical = registry.require(id);
      const script = renderPrimeScript(vertical, record, evidence);

      expect(SCRIPT_SECTION_IDS).toHaveLength(13);
      for (const section of SCRIPT_SECTION_IDS) {
        expect(script.sections[section].length, `${id}:${section}`).toBeGreaterThan(20);
      }
      expect(script.full).toContain('WHY THIS LEAD');
      expect(script.full).toContain('FINAL CLOSE');
    }
  });

  it('substitutes every dynamic placeholder from evidence', () => {
    for (const id of VERTICAL_IDS) {
      const evidence = evidenceFor(`${id} company`);
      const record = runVertical(id, evidence);
      const vertical = registry.require(id);
      const script = renderPrimeScript(vertical, record, evidence);

      expect(script.context.company).toBe(`${id} company`);
      expect(script.context.ownerName).toBe('Riley Owner');
      expect(script.context.vertical).toBe(vertical.name);
      expect(script.context.city).toBe('Austin');

      const all = Object.values(script.sections).join(' ');
      expect(all).toContain('Riley Owner');
      expect(all).toContain(`${id} company`);
      expect(all).toContain(vertical.name);
      expect(all).toContain('Austin');
      expect(hasUnrenderedPlaceholders(all)).toBe(false);
    }
  });

  it('renders the recommended offer into OFFER and VALUE sections', () => {
    const evidence = evidenceFor('Express Air');
    const record = runVertical('hvac', evidence);
    const vertical = registry.require('hvac');
    const script = renderPrimeScript(vertical, record, evidence);

    expect(script.sections.OFFER).toContain(record.recommendedOffer);
    expect(script.sections.VALUE).toContain(script.context.valueHypothesis);
    expect(script.sections.VALUE).toContain('USD');
  });

  it('renders an honest, high-energy opener that anchors to evidence', () => {
    const evidence = evidenceFor('Express Air');
    const record = runVertical('hvac', evidence);
    const vertical = registry.require('hvac');
    const script = renderPrimeScript(vertical, record, evidence);

    expect(script.sections.OPENING).toContain('Omar');
    expect(script.sections.OPENING).toContain('Express Air');
    expect(script.sections.OPENING).toMatch(/\?/);
    expect(script.sections.OPENING).not.toContain('[OWNER_NAME]');
  });

  it('falls back to a generic owner greeting when no owner name exists', () => {
    const evidence = evidenceFor('No Owner Inc', { decisionMaker: { name: null, title: null } });
    const record = runVertical('dental', evidence);
    const vertical = registry.require('dental');
    const script = renderPrimeScript(vertical, record, evidence);

    expect(script.context.ownerName).toBe('there');
    expect(script.sections.OPENING).toContain('there');
    expect(hasUnrenderedPlaceholders(script.full)).toBe(false);
  });

  it('never fabricates value — it anchors to the vertical deal range', () => {
    const evidence = evidenceFor('Peak Pilates');
    const record = runVertical('pilates', evidence);
    const vertical = registry.require('pilates');
    const context = buildScriptContext(vertical, record, evidence);

    expect(context.valueHypothesis).toContain('$');
    expect(context.valueHypothesis).toContain('USD');
    expect(context.valueHypothesis).toContain('·');
    expect(formatValueHypothesis(vertical.estimatedDealSize)).toBe(context.valueHypothesis);
  });

  it('renders placeholders deterministically and leaves unknown tokens alone', () => {
    const ctx = {
      ownerName: 'Sam',
      company: 'C',
      vertical: 'V',
      city: 'CT',
      knownPain: 'P',
      observedSignal: 'S',
      recommendedOffer: 'O',
      valueHypothesis: '$5k',
    };
    expect(renderPlaceholders('[OWNER_NAME] [COMPANY] [VERTICAL] [CITY]', ctx)).toBe('Sam C V CT');
    expect(renderPlaceholders('[KNOWN_PAIN] [OBSERVED_SIGNAL]', ctx)).toBe('P S');
    expect(renderPlaceholders('[RECOMMENDED_OFFER] [VALUE_HYPOTHESIS]', ctx)).toBe('O $5k');
    expect(renderPlaceholders('keep [UNKNOWN_TOKEN]', ctx)).toBe('keep [UNKNOWN_TOKEN]');
    expect(hasUnrenderedPlaceholders('[OWNER_NAME] left')).toBe(true);
  });

  it('resolves nested placeholders injected by fallback values (no leak in production)', () => {
    const ctx = {
      ownerName: 'Riley',
      company: 'Summit Air',
      vertical: 'HVAC & Air Conditioning',
      city: 'Dallas',
      knownPain: 'leads that slip through without follow-up',
      observedSignal: 'the missed-call gap that costs [COMPANY] real jobs',
      recommendedOffer: 'AI voice receptionist',
      valueHypothesis: '$4,997–$15,000 USD · monthly retainer',
    };
    const rendered = renderPlaceholders('[OBSERVED_SIGNAL] at [COMPANY]', ctx);
    expect(rendered).toContain('Summit Air');
    expect(rendered).not.toContain('[COMPANY]');
    expect(hasUnrenderedPlaceholders(rendered)).toBe(false);
  });

  it('produces a read-verbatim full script in section order', () => {
    const evidence = evidenceFor('Summit Law');
    const record = runVertical('law_firms', evidence);
    const vertical = registry.require('law_firms');
    const script: RenderedScript = renderPrimeScript(vertical, record, evidence);

    const order = script.full.split('\n').filter((l) => l.startsWith('## ')).map((l) => l.slice(3));
    expect(order).toEqual(SCRIPT_SECTION_IDS.map((id) => scriptSectionLabel(id)));
  });

  it('anchors PAIN to the top evidenced signal, not invented claims', () => {
    const evidence = evidenceFor('Core Balance', {
      aiOpportunitySignals: ['membership churn', 'manual booking via phone', 'no online scheduling'],
    });
    const record = runVertical('pilates', evidence);
    const vertical = registry.require('pilates');
    const script = renderPrimeScript(vertical, record, evidence);

    expect(script.sections.PAIN.length).toBeGreaterThan(20);
    expect(script.sections.PAIN).not.toContain('[KNOWN_PAIN]');
  });
});