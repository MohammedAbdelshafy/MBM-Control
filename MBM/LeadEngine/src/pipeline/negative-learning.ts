/**
 * Negative Learning & Feedback Loop Engine — MBM Lead Quality v3 (P1)
 * Ingests call/outreach dispositions to dynamically adapt ranking, enforce suppressions,
 * invalidate faulty linkages, and prevent bad records from cycling back into the dialer.
 */

import { normalizeDialerPhone } from './types';

export type CallDisposition =
  | 'NO_ANSWER'
  | 'BAD_NUMBER'
  | 'WRONG_PERSON'
  | 'NON_OWNER'
  | 'NOT_INTERESTED'
  | 'CALLBACK'
  | 'INTERESTED'
  | 'DNC'
  | 'SOLD'
  | 'DUPLICATE'
  | 'UNVERIFIED';

export interface DispositionEvent {
  id: string;
  leadId: string;
  propertyId: string;
  phone: string;
  ownerName: string;
  disposition: CallDisposition;
  timestamp: string;
  agentId?: string;
  notes?: string;
  scheduledCallbackAt?: string | null;
}

export interface NegativeLearningState {
  suppressedPhones: Set<string>;
  suppressedDNC: Set<string>;
  invalidatedOwners: Set<string>;
  invalidatedContacts: Set<string>;
  soldProperties: Set<string>;
  retryQueue: Map<string, { attempts: number; nextRetryAt: string }>;
  priorityBoosts: Map<string, number>;
}

export class NegativeLearningEngine {
  private state: NegativeLearningState = {
    suppressedPhones: new Set(),
    suppressedDNC: new Set(),
    invalidatedOwners: new Set(),
    invalidatedContacts: new Set(),
    soldProperties: new Set(),
    retryQueue: new Map(),
    priorityBoosts: new Map(),
  };

  public recordDisposition(event: DispositionEvent): {
    actionTaken: string;
    shouldRemoveFromActiveQueue: boolean;
    priorityDelta: number;
  } {
    const normPhone = normalizeDialerPhone(event.phone);
    const ownerKey = `${event.propertyId}::${event.ownerName.trim().toLowerCase()}`;
    const contactKey = `${event.propertyId}::${normPhone}`;

    switch (event.disposition) {
      case 'BAD_NUMBER': {
        this.state.suppressedPhones.add(normPhone);
        return {
          actionTaken: `Suppressed phone ${normPhone} globally and flagged invalid line.`,
          shouldRemoveFromActiveQueue: true,
          priorityDelta: -100,
        };
      }

      case 'DNC': {
        this.state.suppressedDNC.add(normPhone);
        return {
          actionTaken: `Hard DNC suppression recorded for ${normPhone}. Legal compliance lock active.`,
          shouldRemoveFromActiveQueue: true,
          priorityDelta: -100,
        };
      }

      case 'WRONG_PERSON': {
        this.state.invalidatedContacts.add(contactKey);
        return {
          actionTaken: `Invalidated phone-to-person linkage for ${normPhone} on property ${event.propertyId}.`,
          shouldRemoveFromActiveQueue: true,
          priorityDelta: -50,
        };
      }

      case 'NON_OWNER': {
        this.state.invalidatedOwners.add(ownerKey);
        return {
          actionTaken: `Invalidated owner record ${event.ownerName} for property ${event.propertyId}. Triggering title re-verification.`,
          shouldRemoveFromActiveQueue: true,
          priorityDelta: -75,
        };
      }

      case 'SOLD': {
        this.state.soldProperties.add(event.propertyId);
        return {
          actionTaken: `Property ${event.propertyId} marked SOLD. Closed out of active acquisition pipeline.`,
          shouldRemoveFromActiveQueue: true,
          priorityDelta: -100,
        };
      }

      case 'INTERESTED': {
        const currentBoost = this.state.priorityBoosts.get(event.leadId) || 0;
        this.state.priorityBoosts.set(event.leadId, currentBoost + 30);
        return {
          actionTaken: `High-intent seller response recorded. Priority boosted +30.`,
          shouldRemoveFromActiveQueue: false,
          priorityDelta: 30,
        };
      }

      case 'CALLBACK': {
        const currentBoost = this.state.priorityBoosts.get(event.leadId) || 0;
        this.state.priorityBoosts.set(event.leadId, currentBoost + 15);
        return {
          actionTaken: `Callback scheduled for ${event.scheduledCallbackAt || 'next business morning'}. Priority boosted +15.`,
          shouldRemoveFromActiveQueue: false,
          priorityDelta: 15,
        };
      }

      case 'NO_ANSWER': {
        const retry = this.state.retryQueue.get(normPhone) || { attempts: 0, nextRetryAt: '' };
        retry.attempts += 1;

        if (retry.attempts >= 4) {
          return {
            actionTaken: `Max no-answer retries (4/4) reached. Moving lead to cooling pool for 14 days.`,
            shouldRemoveFromActiveQueue: true,
            priorityDelta: -25,
          };
        } else {
          // Exponential backoff: attempt 1 -> 4h, attempt 2 -> 24h, attempt 3 -> 72h
          const delayHours = retry.attempts === 1 ? 4 : retry.attempts === 2 ? 24 : 72;
          const nextRetry = new Date(Date.now() + delayHours * 60 * 60 * 1000).toISOString();
          retry.nextRetryAt = nextRetry;
          this.state.retryQueue.set(normPhone, retry);

          return {
            actionTaken: `No answer recorded (Attempt ${retry.attempts}/4). Backoff scheduled for ${nextRetry}.`,
            shouldRemoveFromActiveQueue: false,
            priorityDelta: -5,
          };
        }
      }

      case 'NOT_INTERESTED': {
        return {
          actionTaken: `Owner expressed not interested. Lead placed in 90-day passive nurture.`,
          shouldRemoveFromActiveQueue: true,
          priorityDelta: -40,
        };
      }

      default: {
        return {
          actionTaken: `Disposition ${event.disposition} recorded.`,
          shouldRemoveFromActiveQueue: false,
          priorityDelta: 0,
        };
      }
    }
  }

  public isPhoneSuppressed(phone: string): boolean {
    const norm = normalizeDialerPhone(phone);
    return this.state.suppressedPhones.has(norm) || this.state.suppressedDNC.has(norm);
  }

  public isOwnerInvalidated(propertyId: string, ownerName: string): boolean {
    return this.state.invalidatedOwners.has(`${propertyId}::${ownerName.trim().toLowerCase()}`);
  }

  public isPropertySold(propertyId: string): boolean {
    return this.state.soldProperties.has(propertyId);
  }

  public getLeadPriorityModifier(leadId: string): number {
    return this.state.priorityBoosts.get(leadId) || 0;
  }
}
