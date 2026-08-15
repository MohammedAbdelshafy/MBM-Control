import { describe, it, expect } from 'vitest';
import {
  AiVibeDedupeGate,
  classifyAiVibeVertical,
  isPhoneDialable,
  mapAiVibePayload,
  mapAndAdmitAiVibe,
  normalizePhone,
  verticalForId,
  VerticalRegistry,
} from '../src/verticals';
import type { AiVibePayload } from '../src/verticals';

const registry = new VerticalRegistry();

function vibePayload(overrides: Partial<AiVibePayload> = {}): AiVibePayload {
  return {
    owner_name: 'Riley Owner',
    company: 'Summit Dental',
    title: 'Owner',
    location: 'Austin, TX',
    phone: '+1 512 334 2233',
    professional_email: 'riley@summitdental.test',
    linkedin: 'https://linkedin.com/in/riley',
    website: 'https://summitdental.test',
    vertical: 'dental',
    source: 'AI_VIBE_PROSPECTING',
    confidence: 0.92,
    ...overrides,
  };
}

describe('AI Vibe Prospecting — classify, map, dedupe, suppress', () => {
  it('classifies verticals from company + hint across required verticals', () => {
    expect(classifyAiVibeVertical('Precision Air Conditioning', 'hvac')).toBe('hvac');
    expect(classifyAiVibeVertical('Core Pilates Studio')).toBe('pilates');
    expect(classifyAiVibeVertical('Glow Med Spa')).toBe('med_spas');
    expect(classifyAiVibeVertical('Austin Family Dental')).toBe('dental');
    expect(classifyAiVibeVertical('Roe & Partners Law', 'law')).toBe('law_firms');
    expect(classifyAiVibeVertical('Shield Insurance Agency')).toBe('insurance');
    expect(classifyAiVibeVertical('Rental Pro Property Management')).toBe('property_management');
    expect(classifyAiVibeVertical('BuildRight Construction')).toBe('construction');
  });

  it('returns null when the vertical is not classifiable (never guesses)', () => {
    expect(classifyAiVibeVertical('Unrelated Widget Co')).toBeNull();
    expect(classifyAiVibeVertical('')).toBeNull();
  });

  it('maps a payload into provenance-preserved BusinessEvidence', () => {
    const result = mapAiVibePayload(vibePayload(), registry);
    expect(result.verticalId).toBe('dental');
    expect(result.evidence.company).toBe('Summit Dental');
    expect(result.evidence.decisionMaker?.name).toBe('Riley Owner');
    expect(result.evidence.decisionMaker?.title).toBe('Owner');
    expect(result.evidence.contact?.phone).toBe('+1 512 334 2233');
    expect(result.evidence.contact?.email).toBe('riley@summitdental.test');
    expect(result.evidence.extra?.linkedin).toBe('https://linkedin.com/in/riley');
    expect(result.evidence.source).toBe('AI_VIBE_PROSPECTING');
    expect(result.suppressed).toBe(false);
    expect(result.duplicate).toBe(false);
  });

  it('keeps missing contacts missing — no fabrication', () => {
    const result = mapAiVibePayload({ company: 'Quiet Co', source: 'AI_VIBE_PROSPECTING' });
    expect(result.evidence.decisionMaker?.name).toBeNull();
    expect(result.evidence.contact?.phone).toBeNull();
    expect(result.evidence.decisionMaker?.title).toBeNull();
  });

  it('normalizes and validates dialable phone numbers', () => {
    expect(normalizePhone('+1 (512) 334-2233')).toBe('5123342233');
    expect(normalizePhone('15123342233')).toBe('5123342233');
    expect(isPhoneDialable('+1 512 334 2233')).toBe(true);
    expect(isPhoneDialable('555-0100')).toBe(false);
    expect(isPhoneDialable('000-000-0000')).toBe(false);
    expect(isPhoneDialable('123')).toBe(false);
    expect(isPhoneDialable('8888888888')).toBe(false);
  });

  it('rejects BAD_NUMBER and suppressed phones in the gate', () => {
    const gate = new AiVibeDedupeGate({
      suppressionList: ['+1 214 667 0101'],
      badNumbers: ['6463010202'],
    });

    const bad = gate.admit(vibePayload({ phone: '555-0000' }));
    expect(bad.pass).toBe(false);
    expect(bad.reason).toMatch(/BAD_NUMBER/);

    const suppressed = gate.admit(vibePayload({ phone: '+1 214 667 0101' }));
    expect(suppressed.pass).toBe(false);
    expect(suppressed.reason).toMatch(/SUPPRESSION/);

    const badHistory = gate.admit(vibePayload({ phone: '+1 646 301 0202' }));
    expect(badHistory.pass).toBe(false);
    expect(badHistory.reason).toMatch(/BAD_NUMBER_HISTORY/);
  });

  it('rejects duplicates by phone and by company', () => {
    const gate = new AiVibeDedupeGate();
    expect(gate.admit(vibePayload()).pass).toBe(true);

    const dupPhone = gate.admit(vibePayload());
    expect(dupPhone.pass).toBe(false);
    expect(dupPhone.reason).toMatch(/DUPLICATE/);

    const dupCompany = gate.admit(vibePayload({ phone: '+1 212 334 9090' }));
    expect(dupCompany.pass).toBe(false);
    expect(dupCompany.reason).toMatch(/DUPLICATE/);
  });

  it('rejects payloads with no contact path at all', () => {
    const gate = new AiVibeDedupeGate();
    const noContact = gate.admit(vibePayload({ phone: null, professional_email: null }));
    expect(noContact.pass).toBe(false);
    expect(noContact.reason).toMatch(/NO_CONTACT_PATH/);
  });

  it('admit-and-map marks suppressed/duplicate outcomes on the result', () => {
    const gate = new AiVibeDedupeGate();
    const first = mapAndAdmitAiVibe(vibePayload(), gate, registry);
    expect(first.suppressed).toBe(false);
    expect(first.duplicate).toBe(false);

    const second = mapAndAdmitAiVibe(vibePayload(), gate, registry);
    expect(second.duplicate).toBe(true);
    expect(second.reason).toMatch(/DUPLICATE/);

    const suppressedGate = new AiVibeDedupeGate({ suppressionList: ['5123342233'] });
    const suppressed = mapAndAdmitAiVibe(vibePayload(), suppressedGate, registry);
    expect(suppressed.suppressed).toBe(true);
    expect(suppressed.reason).toMatch(/SUPPRESSION/);
  });

  it('maps the classified vertical id to a catalog definition', () => {
    expect(verticalForId(registry, 'dental')?.name).toBe('Dental Practices');
    expect(verticalForId(registry, 'not_a_vertical')).toBeNull();
    expect(verticalForId(registry, null)).toBeNull();
  });
});