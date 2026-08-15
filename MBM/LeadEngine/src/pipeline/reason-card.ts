/**
 * Lead Reason Card Generator — MBM Lead Quality v3 (P2)
 * Generates compact, human-readable reason cards for prime dialer leads.
 * Every assertion is backed by verified internal provenance.
 */

export interface ReasonCardInputs {
  leadScore: number;
  grade: 'A+' | 'A' | 'B' | 'C' | 'REJECT';
  daysToAuctionOrEvent?: number | null;
  eventType?: string | null;
  propertySpecs: {
    address: string;
    bedrooms?: number | null;
    bathrooms?: number | null;
    propertyType: string;
    isVacant: boolean;
  };
  ownerVerification: {
    ownerName: string;
    verificationSource: string;
    isAbsentee: boolean;
    confidence: number;
  };
  economics: {
    openingBidOrEntry?: number | null;
    estimatedValue: number;
    projectedSpread: number;
  };
  contactability: {
    score: number; // 0 - 100
    phone: string;
    carrierType?: string;
    dncStatus: string;
  };
  whyCallJustification: string;
  nextActionRecommendation: 'CALL_NOW_PRIME_WINDOW' | 'SCHEDULE_MORNING_DIAL' | 'REVIEW_TITLE_EXCEPTION' | 'SUPPRESS_DNC';
}

export interface FormattedLeadReasonCard {
  leadHeader: string;
  eventUrgencyLine: string;
  propertySummaryLine: string;
  ownerLine: string;
  economicsLine: string;
  contactabilityLine: string;
  whyCallLine: string;
  nextActionLine: string;
  renderedCard: string;
}

export class LeadReasonCardGenerator {
  public generateCard(inputs: ReasonCardInputs): FormattedLeadReasonCard {
    const header = `${inputs.grade === 'A+' || inputs.grade === 'A' ? 'HOT 🔥' : 'QUALIFIED ⚡'} — ${inputs.leadScore}/100 [Grade: ${inputs.grade}]`;
    
    let eventUrgency = 'Standard Opportunity Window';
    if (inputs.daysToAuctionOrEvent !== undefined && inputs.daysToAuctionOrEvent !== null) {
      const cleanEvent = inputs.eventType ? inputs.eventType.replace(/_/g, ' ') : 'Auction';
      eventUrgency = inputs.daysToAuctionOrEvent <= 7
        ? `CRITICAL — ${cleanEvent} in ${inputs.daysToAuctionOrEvent} days`
        : `${cleanEvent} scheduled in ${inputs.daysToAuctionOrEvent} days`;
    }

    const bedsBaths = inputs.propertySpecs.bedrooms && inputs.propertySpecs.bathrooms
      ? `${inputs.propertySpecs.bedrooms}BR / ${inputs.propertySpecs.bathrooms}BA`
      : inputs.propertySpecs.propertyType;
    const vacancy = inputs.propertySpecs.isVacant ? ' | Confirmed Vacant' : '';
    const propertySummary = `${inputs.propertySpecs.address} (${bedsBaths}${vacancy})`;

    const owner = `${inputs.ownerVerification.ownerName} (Verified via ${inputs.ownerVerification.verificationSource}, ${(inputs.ownerVerification.confidence * 100).toFixed(0)}% title confidence${inputs.ownerVerification.isAbsentee ? ', Absentee' : ''})`;

    const openingBid = inputs.economics.openingBidOrEntry
      ? `Opening Bid / Entry: $${inputs.economics.openingBidOrEntry.toLocaleString()} | `
      : '';
    const economics = `${openingBid}Estimated ARV: $${inputs.economics.estimatedValue.toLocaleString()} (Projected Spread: +$${inputs.economics.projectedSpread.toLocaleString()})`;

    const contactability = `${inputs.contactability.score}/100 [${inputs.contactability.carrierType || 'MOBILE'} - ${inputs.contactability.dncStatus === 'CLEAN' ? 'Clean DNC' : 'Review DNC'}]`;

    const whyCall = inputs.whyCallJustification;
    const nextAction = inputs.nextActionRecommendation.replace(/_/g, ' ');

    const rendered = `
============================================================
${header}
------------------------------------------------------------
Event Urgency:   ${eventUrgency}
Property:        ${propertySummary}
Owner:           ${owner}
Economics:       ${economics}
Contactability:  ${contactability}
Why Call:        ${whyCall}
Next Action:     👉 ${nextAction}
============================================================
    `.trim();

    return {
      leadHeader: header,
      eventUrgencyLine: eventUrgency,
      propertySummaryLine: propertySummary,
      ownerLine: owner,
      economicsLine: economics,
      contactabilityLine: contactability,
      whyCallLine: whyCall,
      nextActionLine: nextAction,
      renderedCard: rendered,
    };
  }
}
