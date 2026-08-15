/**
 * AI Vibe Prospecting Integration — Multi-Vertical AI Sales Engine
 *
 * Maps enriched business-owner payloads from AI Vibe Prospecting into MBM's
 * evidence model, classifies the vertical from the payload, and enforces
 * the dedupe + suppression gate BEFORE a payload can reach a dialer queue.
 *
 * No contact is ever fabricated: every payload field maps to evidence with
 * preserved provenance, and a suppressed/DNC/bad-number phone is rejected
 * with a reason instead of being dialed.
 */

import type {
  AiVibeMappingResult,
  AiVibePayload,
  BusinessEvidence,
  VerticalDefinition,
} from './types';
import { VerticalRegistry } from './registry';

const NON_DIGIT_REGEX = /\D/g;

export function normalizePhone(phone: string): string {
  const digits = phone.replace(NON_DIGIT_REGEX, '');
  if (digits.length === 11 && digits.startsWith('1')) return digits.substring(1);
  return digits;
}

const BAD_NUMBER_REGEX = /^(555\d{4}|\+?1?555\d{7}|000\d{7}|1234567|9999999)$/;

export function isPhoneDialable(phone: string): boolean {
  const norm = normalizePhone(phone);
  if (norm.length !== 10) return false;
  if (norm.startsWith('0') || norm.startsWith('1')) return false;
  const area = norm.substring(0, 3);
  const exchange = norm.substring(3, 6);
  if (area === '555' || exchange === '555' || exchange === '000') return false;
  if (BAD_NUMBER_REGEX.test(norm)) return false;
  if (/^(\d)\1{9}$/.test(norm)) return false;
  return true;
}

// ── Vertical classification from AI Vibe payload ────────────────────

const VERTICAL_NAME_MAP: Array<{ id: string; patterns: RegExp[] }> = [
  { id: 'hvac', patterns: [/hvac/i, /air condition/i, /heating and cooling/i, /\bac\b/i] },
  { id: 'plumbing', patterns: [/plumb/i] },
  { id: 'electrical', patterns: [/electrical|electrician|electrics/i] },
  { id: 'roofing', patterns: [/roof/i] },
  { id: 'solar', patterns: [/solar/i] },
  { id: 'landscaping', patterns: [/landscap|lawn care|lawn\b/i] },
  { id: 'pest_control', patterns: [/pest/i] },
  { id: 'cleaning', patterns: [/clean/i] },
  { id: 'restoration', patterns: [/restoration|water damage|flood/i] },
  { id: 'garage_door', patterns: [/garage door/i] },
  { id: 'pool_services', patterns: [/pool/i] },
  { id: 'painting', patterns: [/paint/i] },
  { id: 'flooring', patterns: [/floor/i] },
  { id: 'remodeling', patterns: [/remodel|renovat/i] },
  { id: 'general_contractors', patterns: [/contractor|construction company|general construction/i] },
  { id: 'yoga', patterns: [/yoga/i] },
  { id: 'pilates', patterns: [/pilates/i] },
  { id: 'gyms', patterns: [/gym|fitness center|health club/i] },
  { id: 'personal_training', patterns: [/personal train/i] },
  { id: 'med_spas', patterns: [/med spa|medical spa|aesthetic/i] },
  { id: 'chiropractors', patterns: [/chiro/i] },
  { id: 'physical_therapy', patterns: [/physical therap|physio/i] },
  { id: 'dental', patterns: [/dental|dentist|orthodont/i] },
  { id: 'aesthetic_clinics', patterns: [/aesthetic clinic|skin clinic|dermatolog/i] },
  { id: 'massage', patterns: [/massage/i] },
  { id: 'wellness', patterns: [/wellness|spa/i] },
  { id: 'nutrition', patterns: [/nutrition|dietician|dietitian/i] },
  { id: 'law_firms', patterns: [/law|attorney|lawyer|legal/i] },
  { id: 'accounting', patterns: [/account|bookkeep|cpa/i] },
  { id: 'tax', patterns: [/tax/i] },
  { id: 'insurance', patterns: [/insurance|agency\b/i] },
  { id: 'mortgage', patterns: [/mortgage/i] },
  { id: 'real_estate_brokerages', patterns: [/real estate|realtor|property broker/i] },
  { id: 'property_management', patterns: [/property management|property manager/i] },
  { id: 'architecture', patterns: [/architect/i] },
  { id: 'engineering', patterns: [/engineer/i] },
  { id: 'construction', patterns: [/construction/i] },
  { id: 'restaurants', patterns: [/restaurant|diner|caf[eé]/i] },
  { id: 'catering', patterns: [/cater/i] },
  { id: 'auto_repair', patterns: [/auto repair|mechanic|auto shop/i] },
  { id: 'auto_dealers', patterns: [/auto dealer|car dealer|dealership/i] },
  { id: 'detailing', patterns: [/detail/i] },
  { id: 'salons', patterns: [/salon/i] },
  { id: 'barbers', patterns: [/barber/i] },
  { id: 'beauty_studios', patterns: [/beauty/i] },
  { id: 'pet_grooming', patterns: [/pet groom|grooming/i] },
  { id: 'veterinary', patterns: [/veterin|vet\b|animal hospital/i] },
  { id: 'moving', patterns: [/moving|mover/i] },
  { id: 'storage', patterns: [/storage|self.storage/i] },
  { id: 'manufacturing', patterns: [/manufactur/i] },
  { id: 'distribution', patterns: [/distribution|distributor/i] },
  { id: 'logistics', patterns: [/logistic|freight|trucking/i] },
  { id: 'staffing', patterns: [/staffing|recruit/i] },
  { id: 'commercial_contractors', patterns: [/commercial contractor/i] },
  { id: 'industrial_suppliers', patterns: [/industrial supply|industrial\b/i] },
  { id: 'security', patterns: [/security/i] },
  { id: 'equipment_rental', patterns: [/equipment rental|rental\b/i] },
  { id: 'wholesale', patterns: [/wholesale/i] },
];

/**
 * Classify a business name + optional vertical hint into a catalog
 * vertical id. Returns null when nothing matches (never guesses).
 */
export function classifyAiVibeVertical(
  company: string | null | undefined,
  hint?: string | null,
): string | null {
  const haystack = `${company ?? ''} ${hint ?? ''}`;
  for (const entry of VERTICAL_NAME_MAP) {
    for (const pattern of entry.patterns) {
      if (pattern.test(haystack)) return entry.id;
    }
  }
  return null;
}

// ── Dedupe + suppression gate ───────────────────────────────────────

export class AiVibeDedupeGate {
  private readonly seenPhones = new Set<string>();
  private readonly seenCompanies = new Set<string>();
  private readonly suppression = new Set<string>();
  private readonly badNumbers = new Set<string>();

  constructor(options?: {
    existingPhones?: string[];
    existingCompanies?: string[];
    suppressionList?: string[];
    badNumbers?: string[];
  }) {
    for (const p of options?.existingPhones ?? []) this.seenPhones.add(normalizePhone(p));
    for (const c of options?.existingCompanies ?? []) this.seenCompanies.add(c.trim().toLowerCase());
    for (const p of options?.suppressionList ?? []) this.suppression.add(normalizePhone(p));
    for (const p of options?.badNumbers ?? []) this.badNumbers.add(normalizePhone(p));
  }

  public seedPhone(phone: string): void {
    this.seenPhones.add(normalizePhone(phone));
  }

  public seedCompany(company: string): void {
    this.seenCompanies.add(company.trim().toLowerCase());
  }

  /**
   * Evaluate a payload against the gate WITHOUT registering it.
   * Deterministic: bad phone, suppressed number, or duplicate business/phone
   * yields a rejection reason; otherwise it passes.
   */
  public evaluate(payload: AiVibePayload): { pass: boolean; reason: string | null } {
    const phone = payload.phone;
    if (phone && !isPhoneDialable(phone)) {
      return { pass: false, reason: `BAD_NUMBER: "${phone}" is not a valid dialable US number` };
    }
    const normPhone = phone ? normalizePhone(phone) : '';
    if (normPhone && this.suppression.has(normPhone)) {
      return { pass: false, reason: 'SUPPRESSION: phone is on the opt-out/DNC suppression list' };
    }
    if (normPhone && this.badNumbers.has(normPhone)) {
      return { pass: false, reason: 'BAD_NUMBER_HISTORY: phone previously flagged disconnected/wrong party' };
    }
    if (normPhone && this.seenPhones.has(normPhone)) {
      return { pass: false, reason: 'DUPLICATE: phone already registered in the dialer' };
    }
    const company = payload.company?.trim().toLowerCase();
    if (company && this.seenCompanies.has(company)) {
      return { pass: false, reason: 'DUPLICATE: company already registered in the dialer' };
    }
    if (!normPhone && !payload.professional_email) {
      return { pass: false, reason: 'NO_CONTACT_PATH: no phone or email to reach the owner' };
    }
    return { pass: true, reason: null };
  }

  /** Evaluate AND register on pass (the actual admission path). */
  public admit(payload: AiVibePayload): { pass: boolean; reason: string | null } {
    const result = this.evaluate(payload);
    if (result.pass) {
      if (payload.phone) this.seenPhones.add(normalizePhone(payload.phone));
      if (payload.company) this.seenCompanies.add(payload.company.trim().toLowerCase());
    }
    return result;
  }
}

// ── Payload → evidence mapping ──────────────────────────────────────

function parseLocation(location: string | null | undefined): BusinessEvidence['location'] {
  if (!location || !location.trim()) return undefined;
  const parts = location.split(',').map((p) => p.trim());
  const city = parts[0] || undefined;
  const state = parts[1] || undefined;
  return { city, state, country: 'US' };
}

export function mapAiVibePayload(
  payload: AiVibePayload,
  registry: VerticalRegistry = new VerticalRegistry(),
): AiVibeMappingResult {
  const company = payload.company ?? 'Unknown business';
  const verticalId = classifyAiVibeVertical(company, payload.vertical);

  const evidence: BusinessEvidence = {
    company,
    website: payload.website ?? null,
    location: parseLocation(payload.location),
    industry: payload.vertical ?? null,
    decisionMaker: {
      name: payload.owner_name ?? null,
      title: payload.title ?? null,
      source: payload.source ?? 'AI_VIBE_PROSPECTING',
    },
    contact: {
      phone: payload.phone ?? null,
      email: payload.professional_email ?? null,
      source: payload.source ?? 'AI_VIBE_PROSPECTING',
    },
    source: payload.source ?? 'AI_VIBE_PROSPECTING',
    retrievedAt: new Date().toISOString(),
    extra: {
      linkedin: payload.linkedin ?? null,
      confidence: payload.confidence ?? null,
    },
  };

  return {
    verticalId,
    evidence,
    suppressed: false,
    duplicate: false,
    reason: null,
  };
}

export function mapAndAdmitAiVibe(
  payload: AiVibePayload,
  gate: AiVibeDedupeGate,
  registry: VerticalRegistry = new VerticalRegistry(),
): AiVibeMappingResult {
  const check = gate.admit(payload);
  const result = mapAiVibePayload(payload, registry);
  result.suppressed = check.pass === false && (check.reason ?? '').includes('SUPPRESSION');
  result.duplicate = check.pass === false && (check.reason ?? '').includes('DUPLICATE');
  result.reason = check.pass ? null : check.reason;
  return result;
}

export function verticalForId(
  registry: VerticalRegistry,
  verticalId: string | null,
): VerticalDefinition | null {
  if (!verticalId) return null;
  return registry.get(verticalId) ?? null;
}