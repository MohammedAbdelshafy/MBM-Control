/**
 * Master Opportunity Intelligence Engine & Lead Competition Ranking (MBM Lead Quality v3)
 * Replaces simple sorting with multi-dimensional competition ranking:
 * OVERALL PRIORITY = Opportunity + Motivation + Callability + Freshness + Economics + BuyerFit + Portfolio
 */

import crypto from 'node:crypto';
import type { PropertyIdentity, OwnershipRecord, ContactEvidence } from './types';
import { FreshnessEngine, type PropertyEvent } from './freshness-engine';
import { MotivationEngine, type MotivationSignalType } from './motivation-engine';
import { PortfolioEngine } from './portfolio-engine';
import { DealEconomicsEngine } from './deal-economics';
import { NegativeLearningEngine, type CallDisposition } from './negative-learning';
import { CorroborationEngine, type SourceClaim } from './corroboration-engine';
import { BuyerFitEngine } from './buyer-fit';
import { LeadReasonCardGenerator, type FormattedLeadReasonCard } from './reason-card';
import { PreDialGateEngine } from './predial-gate';
import { CallabilityEngine } from './callability-engine';

export interface OpportunityRankingWeights {
  opportunityWeight: number; // default 0.20
  motivationWeight: number; // default 0.20
  callabilityWeight: number; // default 0.20
  freshnessWeight: number; // default 0.15
  economicsWeight: number; // default 0.10
  buyerFitWeight: number; // default 0.10
  portfolioWeight: number; // default 0.05
}

export interface ComprehensiveLeadInput {
  leadId?: string;
  property: PropertyIdentity;
  ownership: OwnershipRecord;
  contact: ContactEvidence;
  events: PropertyEvent[];
  motivationSignals: Array<{
    type: MotivationSignalType;
    source: string;
    sourceReference?: string;
    date: string;
    confidence: number;
  }>;
  sourceClaims?: SourceClaim[];
  economicsInputs?: {
    knownMortgageBalance?: number;
    taxLiensAmount?: number;
    openingBidOrTargetPrice?: number;
    sqft?: number;
    propertyCondition?: 'DISTRESSED' | 'FAIR' | 'GOOD' | 'EXCELLENT';
  };
  portfolioEntityKey?: string;
}

export interface RankedOpportunityOutput {
  leadId: string;
  overallPriorityScore: number; // 0 - 100
  opportunityScore: number;
  motivationScore: number;
  callabilityScore: number;
  freshnessScore: number;
  economicsScore: number;
  buyerFitScore: number;
  portfolioScoreBoost: number;
  isCallablePrimeQueue: boolean;
  reasonCard: FormattedLeadReasonCard;
  dispositionState: {
    isSuppressed: boolean;
    isSold: boolean;
  };
  provenanceCheck: {
    corroborationConfidence: number;
    independentSourcesCount: number;
  };
  netellerCheckoutUrl: string;
}

export class OpportunityIntelligenceOrchestrator {
  private freshnessEngine: FreshnessEngine;
  private motivationEngine: MotivationEngine;
  private portfolioEngine: PortfolioEngine;
  private economicsEngine: DealEconomicsEngine;
  private negativeLearningEngine: NegativeLearningEngine;
  private corroborationEngine: CorroborationEngine;
  private buyerFitEngine: BuyerFitEngine;
  private reasonCardGenerator: LeadReasonCardGenerator;
  private gateEngine: PreDialGateEngine;
  private callabilityEngine: CallabilityEngine;

  private weights: OpportunityRankingWeights = {
    opportunityWeight: 0.20,
    motivationWeight: 0.20,
    callabilityWeight: 0.20,
    freshnessWeight: 0.15,
    economicsWeight: 0.10,
    buyerFitWeight: 0.10,
    portfolioWeight: 0.05,
  };

  constructor(customWeights?: Partial<OpportunityRankingWeights>) {
    this.freshnessEngine = new FreshnessEngine();
    this.motivationEngine = new MotivationEngine();
    this.portfolioEngine = new PortfolioEngine();
    this.economicsEngine = new DealEconomicsEngine();
    this.negativeLearningEngine = new NegativeLearningEngine();
    this.corroborationEngine = new CorroborationEngine();
    this.buyerFitEngine = new BuyerFitEngine();
    this.reasonCardGenerator = new LeadReasonCardGenerator();
    this.gateEngine = new PreDialGateEngine();
    this.callabilityEngine = new CallabilityEngine();

    if (customWeights) {
      this.weights = { ...this.weights, ...customWeights };
    }
  }

  public evaluateOpportunity(input: ComprehensiveLeadInput): RankedOpportunityOutput {
    const leadId = input.leadId || crypto.randomUUID();

    // 1. Freshness Evaluation
    const freshness = this.freshnessEngine.calculateFreshness(input.events);

    // 2. Motivation Evaluation
    const motivation = this.motivationEngine.calculateMotivation(input.motivationSignals);

    // 3. Deal Economics Evaluation
    const economics = this.economicsEngine.calculateEconomics({
      estimatedValue: input.property.estimatedValue || 450000,
      ...input.economicsInputs,
    });

    // 4. Buyer Fit Evaluation
    const buyerFit = this.buyerFitEngine.evaluateBuyerFit({
      county: input.property.county,
      state: input.property.state,
      propertyType: input.property.propertyType,
      estimatedValue: input.property.estimatedValue || 450000,
      projectedSpread: economics.projectedGrossSpread,
    });

    // 5. Portfolio Relevance Evaluation
    let portfolioBoost = 0;
    if (input.portfolioEntityKey) {
      const p = this.portfolioEngine.getPortfolioForEntity(input.portfolioEntityKey);
      if (p) portfolioBoost = p.portfolioScoreBoost;
    }

    // 6. Multi-Source Corroboration
    const corroboration = this.corroborationEngine.evaluateCorroboration(input.sourceClaims || []);

    // 7. Base Opportunity Score (0 - 100)
    const baseOpportunityScore = Math.round(
      motivation.totalMotivationScore * 0.40 +
      economics.economicsScore * 0.35 +
      freshness.decayedScore * 0.25
    );

    // 8. Contactability / Callability Scoring (0 - 100)
    const callability = this.callabilityEngine.calculateCallability(
      input.property,
      input.ownership,
      input.contact,
      baseOpportunityScore
    );

    // 9. Negative Learning / Disposition Checks
    const isSuppressed = this.negativeLearningEngine.isPhoneSuppressed(input.contact.phone);
    const isOwnerInvalid = this.negativeLearningEngine.isOwnerInvalidated(input.property.parcelId, input.ownership.ownerName);
    const isSold = this.negativeLearningEngine.isPropertySold(input.property.parcelId);
    const priorityModifier = this.negativeLearningEngine.getLeadPriorityModifier(leadId);

    // 10. Hard Pre-Dial Gate Check
    const gateResult = this.gateEngine.evaluateGate(input.property, input.ownership, input.contact, leadId);
    const isCallablePrime = gateResult.isCallable && !isSuppressed && !isOwnerInvalid && !isSold && callability.totalScore >= 60;

    // 11. Multi-Dimensional Competition Priority Score
    const weightedScore =
      baseOpportunityScore * this.weights.opportunityWeight +
      motivation.totalMotivationScore * this.weights.motivationWeight +
      callability.totalScore * this.weights.callabilityWeight +
      freshness.decayedScore * this.weights.freshnessWeight +
      economics.economicsScore * this.weights.economicsWeight +
      buyerFit.buyerFitScore * this.weights.buyerFitWeight +
      portfolioBoost * this.weights.portfolioWeight +
      priorityModifier;

    const overallPriorityScore = Math.min(100, Math.max(0, Math.round(weightedScore)));

    // 12. Grade assignment
    let grade: 'A+' | 'A' | 'B' | 'C' | 'REJECT' = 'REJECT';
    if (overallPriorityScore >= 88) grade = 'A+';
    else if (overallPriorityScore >= 75) grade = 'A';
    else if (overallPriorityScore >= 60) grade = 'B';
    else if (overallPriorityScore >= 40) grade = 'C';

    // 13. Reason Card Generation
    const reasonCard = this.reasonCardGenerator.generateCard({
      leadScore: overallPriorityScore,
      grade,
      daysToAuctionOrEvent: freshness.mostRecentEvent ? Math.round(freshness.daysElapsed) : null,
      eventType: freshness.mostRecentEvent?.eventType,
      propertySpecs: {
        address: input.property.addressLine1,
        propertyType: input.property.propertyType,
        isVacant: motivation.signals.some((s) => s.signalType === 'VACANCY'),
      },
      ownerVerification: {
        ownerName: input.ownership.ownerName,
        verificationSource: input.ownership.corporateOfficerName ? 'SOS_CORPORATE_OFFICER_REGISTRY' : 'COUNTY_DEED_RECORDS',
        isAbsentee: input.ownership.isAbsentee,
        confidence: input.ownership.confidenceScore,
      },
      economics: {
        openingBidOrEntry: input.economicsInputs?.openingBidOrTargetPrice,
        estimatedValue: economics.estimatedValue,
        projectedSpread: economics.projectedNetOpportunity,
      },
      contactability: {
        score: callability.totalScore,
        phone: input.contact.phone,
        carrierType: input.contact.carrierType,
        dncStatus: input.contact.dncStatus,
      },
      whyCallJustification: `${freshness.freshnessLabel.replace(/_/g, ' ')} with ${motivation.primaryMotivationDriver} (+${motivation.totalMotivationScore}pts), ${(corroboration.corroborationConfidence * 100).toFixed(0)}% verified provenance, and immediate buyer fit score ${buyerFit.buyerFitScore}/100.`,
      nextActionRecommendation: isCallablePrime ? 'CALL_NOW_PRIME_WINDOW' : 'REVIEW_TITLE_EXCEPTION',
    });

    const netellerUrl = `https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount=997.00&currency=USD&item=DEAL-${input.property.parcelId.replace(/[^A-Z0-9]/gi, '')}`;

    return {
      leadId,
      overallPriorityScore,
      opportunityScore: baseOpportunityScore,
      motivationScore: motivation.totalMotivationScore,
      callabilityScore: callability.totalScore,
      freshnessScore: freshness.decayedScore,
      economicsScore: economics.economicsScore,
      buyerFitScore: buyerFit.buyerFitScore,
      portfolioScoreBoost: portfolioBoost,
      isCallablePrimeQueue: isCallablePrime,
      reasonCard,
      dispositionState: {
        isSuppressed,
        isSold,
      },
      provenanceCheck: {
        corroborationConfidence: corroboration.corroborationConfidence,
        independentSourcesCount: corroboration.independentSourcesCount,
      },
      netellerCheckoutUrl: netellerUrl,
    };
  }

  public registerDisposition(
    leadId: string,
    propertyId: string,
    phone: string,
    ownerName: string,
    disposition: CallDisposition
  ) {
    return this.negativeLearningEngine.recordDisposition({
      id: crypto.randomUUID(),
      leadId,
      propertyId,
      phone,
      ownerName,
      disposition,
      timestamp: new Date().toISOString(),
    });
  }

  public getPortfolioEngine(): PortfolioEngine {
    return this.portfolioEngine;
  }
}
