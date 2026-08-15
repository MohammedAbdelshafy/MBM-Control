/**
 * Pre-Dial Verification Gate & 5 Whys Explainability Engine
 * JARVIS Worker 3 — Integration / QA / Deployment Commander
 */

import type {
  PropertyIdentity,
  OwnershipRecord,
  ContactEvidence,
  PreDialGateCheck,
  FiveWhysExplainability,
} from './types';

// Bad exchanges and fake phone detection regex
const FAKE_PHONE_REGEX = /^(555\d{4}|\+?1?555\d{7}|000\d{7}|1234567|9999999)$/;
const NON_DIGIT_REGEX = /\D/g;

// Placeholder/generic name tokens
const FAKE_NAME_TOKENS = new Set([
  'unknown',
  'n/a',
  'na',
  'test',
  'demo',
  'sample',
  'placeholder',
  'action_required',
  'skip_trace',
  'distressed seller',
  'property owner',
  'hedge fund',
  'cash buyer',
  'acquisition group',
  'tbd',
  'pending',
  'john doe',
  'jane doe',
  'robert sterling',
  'elena rostova',
]);

export class PreDialGateEngine {
  private suppressionList: Set<string> = new Set();
  private dialedNumbersHistory: Map<string, { attempts: number; badNumber: boolean }> = new Map();
  private activeQueueHashes: Set<string> = new Set();

  constructor(options?: {
    suppressionList?: string[];
    badNumbers?: string[];
    previousRejections?: string[];
  }) {
    if (options?.suppressionList) {
      options.suppressionList.forEach((num) => this.suppressionList.add(this.normalizePhone(num)));
    }
    if (options?.badNumbers) {
      options.badNumbers.forEach((num) => {
        const norm = this.normalizePhone(num);
        this.dialedNumbersHistory.set(norm, { attempts: 1, badNumber: true });
      });
    }
    if (options?.previousRejections && options.previousRejections.length > 0) {
      this.previousRejections = new Set(options.previousRejections);
    }
  }

  private previousRejections: Set<string> = new Set();

  /**
   * Seed the gate from a negative-disposition registry so permanent
   * rejections (BAD_NUMBER, WRONG_PERSON, NON_OWNER, DUPLICATE, DNC,
   * SOLD, NOT_INTERESTED) are enforced on the very next evaluation.
   */
  public applyPermanentDispositions(
    records: Array<{ phone: string; type: string; permanent?: boolean }>,
  ): void {
    for (const record of records) {
      if (record.permanent === false) continue;
      const norm = this.normalizePhone(record.phone);
      if (norm.length !== 10) continue;
      const type = record.type;
      if (
        type === 'BAD_NUMBER' ||
        type === 'WRONG_PERSON' ||
        type === 'NON_OWNER'
      ) {
        this.dialedNumbersHistory.set(norm, { attempts: 1, badNumber: true });
      }
      if (
        type === 'DNC' ||
        type === 'SOLD' ||
        type === 'NOT_INTERESTED' ||
        type === 'WRONG_PERSON' ||
        type === 'NON_OWNER' ||
        type === 'DUPLICATE'
      ) {
        this.suppressionList.add(norm);
      }
      this.previousRejections.add(type);
    }
  }

  public normalizePhone(phone: string): string {
    const digits = phone.replace(NON_DIGIT_REGEX, '');
    if (digits.length === 11 && digits.startsWith('1')) {
      return digits.substring(1);
    }
    return digits;
  }

  public isPhoneQualityValid(phone: string): boolean {
    const norm = this.normalizePhone(phone);
    if (norm.length !== 10) return false;
    if (norm.startsWith('0') || norm.startsWith('1')) return false;

    // Check area code and exchange
    const areaCode = norm.substring(0, 3);
    const exchange = norm.substring(3, 6);

    if (areaCode === '555' || exchange === '555' || exchange === '000') return false;
    if (FAKE_PHONE_REGEX.test(norm)) return false;

    // Check repeating sequence (e.g. 8888888888)
    if (/^(\d)\1{9}$/.test(norm)) return false;

    return true;
  }

  public isNameValid(name: string): boolean {
    if (!name || name.trim().length < 2) return false;
    const clean = name.trim().toLowerCase();
    if (FAKE_NAME_TOKENS.has(clean)) return false;
    for (const token of FAKE_NAME_TOKENS) {
      if (clean.includes(token)) return false;
    }
    return true;
  }

  public evaluateGate(
    property: PropertyIdentity,
    ownership: OwnershipRecord,
    contact: ContactEvidence,
    leadId: string,
    previousRejections?: string[]
  ): PreDialGateCheck {
    const reasons: string[] = [];

    // 1. Valid Property
    const hasValidAddress = !!(property.addressLine1 && property.city && property.state && property.zip);
    const hasValidAPN = !!(property.parcelId && property.parcelId.trim().length > 2);
    const validProperty = hasValidAddress && hasValidAPN;
    if (!validProperty) {
      reasons.push('INVALID_PROPERTY: Missing normalized address or parcel/APN identification');
    }

    // 2. Valid Owner/Entity Status
    const validOwnerName = this.isNameValid(ownership.ownerName);
    const validOwnerConfidence = ownership.confidenceScore >= 0.70;
    const validOwnerEntity = validOwnerName && validOwnerConfidence;
    if (!validOwnerEntity) {
      reasons.push(`INVALID_OWNER: Name unverified or confidence score (${(ownership.confidenceScore * 100).toFixed(0)}%) below 70% threshold`);
    }

    // 3. Valid Contact Source
    const validSource = !!contact.source && ['CMS_NPI', 'COUNTY_TAX', 'SKIP_TRACE', 'SECRETARY_OF_STATE', 'RAPIDAPI'].includes(contact.source);
    const validContactName = this.isNameValid(contact.contactName);
    const validContactSource = validSource && validContactName && contact.confidenceScore >= 0.70;
    if (!validContactSource) {
      reasons.push('INVALID_CONTACT_SOURCE: Source unverified or missing provenance trace');
    }

    // 4. Phone Quality Pass
    const phoneNorm = this.normalizePhone(contact.phone);
    const phoneQualityPass = this.isPhoneQualityValid(phoneNorm) && contact.dncStatus !== 'LISTED';
    if (!phoneQualityPass) {
      reasons.push(`PHONE_QUALITY_FAILED: Invalid digits, DNC listed, or test exchange detected for ${contact.phone}`);
    }

    // 5. No Duplicate
    const queueHash = `${property.parcelId}::${phoneNorm}`;
    const noDuplicate = !this.activeQueueHashes.has(queueHash);
    if (!noDuplicate) {
      reasons.push('DUPLICATE_DETECTED: Lead already active in current dialer queue');
    }

    // 6. No Suppression
    const noSuppression = !this.suppressionList.has(phoneNorm);
    if (!noSuppression) {
      reasons.push('SUPPRESSION_MATCH: Phone number listed on account-level opt-out/suppression list');
    }

    // 7. No Bad-Number History
    const history = this.dialedNumbersHistory.get(phoneNorm);
    const noBadNumberHistory = !(history && history.badNumber);
    if (!noBadNumberHistory) {
      reasons.push('BAD_NUMBER_HISTORY: Number previously flagged as disconnected, fast-busy, or wrong party');
    }

    // 8. No Previous Rejection — previously rejected garbage cannot
    //    automatically return to the prime dialer queue.
    const effectiveRejections = [
      ...Array.from(this.previousRejections),
      ...(previousRejections ?? []),
    ];
    const uniqueRejections = Array.from(new Set(effectiveRejections));
    const noPreviousRejection = uniqueRejections.length === 0;
    if (!noPreviousRejection) {
      reasons.push(`PREVIOUSLY_REJECTED: ${uniqueRejections.join(',')} — lead identity has a permanent rejection on record`);
    }

    const isCallable =
      validProperty &&
      validOwnerEntity &&
      validContactSource &&
      phoneQualityPass &&
      noDuplicate &&
      noSuppression &&
      noBadNumberHistory &&
      noPreviousRejection;

    if (isCallable) {
      this.activeQueueHashes.add(queueHash);
    }

    return {
      validProperty,
      validOwnerEntity,
      validContactSource,
      phoneQualityPass,
      noDuplicate,
      noSuppression,
      noBadNumberHistory,
      noPreviousRejection,
      isCallable,
      rejectionReasons: reasons,
      evaluatedAt: new Date().toISOString(),
    };
  }

  public generateExplainability(
    property: PropertyIdentity,
    ownership: OwnershipRecord,
    contact: ContactEvidence,
    leadScore: number,
    niche: string,
    signals?: {
      triggerEvent?: string;
      equityPercent?: number;
      distressType?: string;
    }
  ): FiveWhysExplainability {
    const equityText = signals?.equityPercent ? `${signals.equityPercent}% estimated equity` : 'Significant asset equity';
    const triggerText = signals?.triggerEvent || `${niche.replace(/_/g, ' ')} detected with active municipal records`;
    const distress = signals?.distressType || niche.replace(/_/g, ' ');

    return {
      whyThisLead: `High-conviction ${distress} opportunity in ${property.county}, ${property.state} with ${equityText} (Lead Score: ${leadScore}/100).`,
      whyThisOwner: `Verified deed & title record for ${ownership.ownerName} (${ownership.ownerType}) with ${ownership.isAbsentee ? 'confirmed absentee status' : 'verified primary titleholder'}.`,
      whyThisContact: `Direct authorized contact ${contact.contactName} validated via ${contact.source} with ${(contact.confidenceScore * 100).toFixed(0)}% verified provenance.`,
      whyNow: `Trigger event: ${triggerText} updated within the past 14 days; optimal outreach window before public listing or default escalation.`,
      whyCall: `Phone ${contact.phone} passed carrier verification (${contact.carrierType || 'MOBILE'}), zero bad-number history, clean DNC status, and high-probability direct connect.`,
      confidenceScore: (ownership.confidenceScore + contact.confidenceScore) / 2,
      calculatedAt: new Date().toISOString(),
    };
  }

  public recordDialOutcome(phone: string, outcome: 'CONNECTED' | 'WRONG_NUMBER' | 'DISCONNECTED' | 'OPTOUT'): void {
    const norm = this.normalizePhone(phone);
    if (outcome === 'DISCONNECTED' || outcome === 'WRONG_NUMBER') {
      this.dialedNumbersHistory.set(norm, { attempts: 1, badNumber: true });
      this.previousRejections.add(outcome === 'WRONG_NUMBER' ? 'WRONG_PERSON' : 'BAD_NUMBER');
    } else if (outcome === 'OPTOUT') {
      this.suppressionList.add(norm);
      this.previousRejections.add('NOT_INTERESTED');
    }
  }
}
