/**
 * Callability Scoring Engine
 * Evaluates real-time dialability, answer likelihood, and contact viability.
 * JARVIS Worker 3 — Integration / QA / Deployment Commander
 */

import type {
  PropertyIdentity,
  OwnershipRecord,
  ContactEvidence,
} from './types';

export interface CallabilityBreakdown {
  phoneQualityWeight: number; // 30%
  contactOwnerMatchWeight: number; // 25%
  triggerFreshnessWeight: number; // 20%
  timezoneWindowWeight: number; // 15%
  historicalAnswerWeight: number; // 10%
  totalScore: number; // 0 - 100
  recommendedDialTime: string;
  isPeakCallingHour: boolean;
}

export class CallabilityEngine {
  public calculateCallability(
    property: PropertyIdentity,
    ownership: OwnershipRecord,
    contact: ContactEvidence,
    leadScore: number,
    options?: {
      targetTimezone?: string;
      currentHourLocal?: number;
      daysSinceTrigger?: number;
    }
  ): CallabilityBreakdown {
    // 1. Phone Quality (Max 30)
    let phoneScore = 0;
    if (contact.carrierType === 'MOBILE') {
      phoneScore += 25;
    } else if (contact.carrierType === 'LANDLINE') {
      phoneScore += 18;
    } else {
      phoneScore += 10;
    }
    if (contact.lineStatus === 'ACTIVE') {
      phoneScore += 5;
    }
    const phoneQualityWeight = Math.min(30, phoneScore);

    // 2. Contact-to-Owner Match (Max 25)
    let matchScore = 0;
    const cleanOwner = ownership.ownerName.trim().toLowerCase();
    const cleanContact = contact.contactName.trim().toLowerCase();
    if (cleanOwner === cleanContact) {
      matchScore = 25;
    } else if (
      ownership.corporateOfficerName &&
      ownership.corporateOfficerName.trim().toLowerCase() === cleanContact
    ) {
      matchScore = 24;
    } else if (cleanOwner.includes(cleanContact) || cleanContact.includes(cleanOwner)) {
      matchScore = 20;
    } else {
      matchScore = Math.round(contact.confidenceScore * 18);
    }
    const contactOwnerMatchWeight = Math.min(25, matchScore);

    // 3. Trigger Freshness (Max 20)
    const days = options?.daysSinceTrigger ?? 7;
    let freshnessScore = 0;
    if (days <= 3) freshnessScore = 20;
    else if (days <= 7) freshnessScore = 18;
    else if (days <= 14) freshnessScore = 15;
    else if (days <= 30) freshnessScore = 10;
    else freshnessScore = 5;
    const triggerFreshnessWeight = Math.min(20, freshnessScore);

    // 4. Timezone & Calling Window (Max 15)
    const currentHour = options?.currentHourLocal ?? new Date().getUTCHours() - 5; // Default US EST
    const isPeak = (currentHour >= 9 && currentHour <= 11) || (currentHour >= 16 && currentHour <= 18);
    const isAllowed = currentHour >= 8 && currentHour <= 20;
    let timeScore = 0;
    if (isPeak) timeScore = 15;
    else if (isAllowed) timeScore = 10;
    else timeScore = 2;
    const timezoneWindowWeight = timeScore;

    // 5. Historical Answer Rate Probability (Max 10)
    let answerProb = 5;
    if (contact.source === 'CMS_NPI') answerProb = 9;
    else if (contact.source === 'COUNTY_TAX') answerProb = 8;
    else if (contact.source === 'SKIP_TRACE') answerProb = 7;
    const historicalAnswerWeight = answerProb;

    const totalScore =
      phoneQualityWeight +
      contactOwnerMatchWeight +
      triggerFreshnessWeight +
      timezoneWindowWeight +
      historicalAnswerWeight;

    return {
      phoneQualityWeight,
      contactOwnerMatchWeight,
      triggerFreshnessWeight,
      timezoneWindowWeight,
      historicalAnswerWeight,
      totalScore: Math.min(100, Math.max(0, totalScore)),
      recommendedDialTime: isPeak ? 'IMMEDIATE_PEAK_WINDOW' : 'SCHEDULE_MORNING_WINDOW_0900_EST',
      isPeakCallingHour: isPeak,
    };
  }
}
