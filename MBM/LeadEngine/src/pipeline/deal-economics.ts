/**
 * Deal Economics Engine — MBM Lead Quality v3 (P1)
 * Computes realistic opportunity economics, equity spreads, and Maximum Allowable Offer (MAO).
 * Never fabricates missing figures; exposes knowns, assumptions, unknowns, and confidence bounds.
 */

export interface DealEconomicsInputs {
  estimatedValue: number; // ARV / assessed market value
  knownMortgageBalance?: number | null;
  taxLiensAmount?: number | null;
  municipalFinesAmount?: number | null;
  openingBidOrTargetPrice?: number | null;
  sqft?: number | null;
  propertyCondition?: 'DISTRESSED' | 'FAIR' | 'GOOD' | 'EXCELLENT';
  rehabEstimatePerSqft?: number; // default $35/sqft for standard cosmetic, $65 for distressed
}

export interface DealEconomicsResult {
  estimatedValue: number;
  totalKnownObligations: number;
  netEstimatedEquity: number;
  equityPercentage: number;
  estimatedRehabCost: number;
  estimatedClosingAndHoldingCosts: number;
  maximumAllowableOffer70Rule: number;
  projectedGrossSpread: number;
  projectedNetOpportunity: number;
  economicsScore: number; // 0 - 100
  confidenceScore: number;
  knownValues: Record<string, number>;
  assumptions: Record<string, string | number>;
  unknowns: string[];
  isEconomicallyViable: boolean;
}

export class DealEconomicsEngine {
  public calculateEconomics(inputs: DealEconomicsInputs): DealEconomicsResult {
    const knownValues: Record<string, number> = {};
    const assumptions: Record<string, string | number> = {};
    const unknowns: string[] = [];

    // 1. Estimated Value
    const estimatedValue = inputs.estimatedValue;
    knownValues.estimatedValue = estimatedValue;

    // 2. Obligations
    let totalObligations = 0;
    if (inputs.knownMortgageBalance !== undefined && inputs.knownMortgageBalance !== null) {
      totalObligations += inputs.knownMortgageBalance;
      knownValues.knownMortgageBalance = inputs.knownMortgageBalance;
    } else {
      unknowns.push('MORTGAGE_BALANCE_UNRECORDED');
    }

    if (inputs.taxLiensAmount) {
      totalObligations += inputs.taxLiensAmount;
      knownValues.taxLiensAmount = inputs.taxLiensAmount;
    }
    if (inputs.municipalFinesAmount) {
      totalObligations += inputs.municipalFinesAmount;
      knownValues.municipalFinesAmount = inputs.municipalFinesAmount;
    }

    const netEstimatedEquity = Math.max(0, estimatedValue - totalObligations);
    const equityPercentage = estimatedValue > 0 ? Math.round((netEstimatedEquity / estimatedValue) * 100) : 0;

    // 3. Rehab & Transaction Costs
    const sqft = inputs.sqft || 1800;
    if (!inputs.sqft) unknowns.push('EXACT_SQFT_ASSUMED_1800');

    let costPerSqft = inputs.rehabEstimatePerSqft || (inputs.propertyCondition === 'DISTRESSED' ? 55 : 30);
    assumptions.rehabCostPerSqft = `$${costPerSqft}/sqft`;
    const estimatedRehabCost = sqft * costPerSqft;

    // 10% closing, holding, and disposition cost assumption
    const estimatedClosingAndHoldingCosts = Math.round(estimatedValue * 0.10);
    assumptions.closingAndHoldingAllowance = '10% of Estimated Market Value';

    // Standard 70% Rule MAO: (ARV * 0.70) - Rehab - Obligations
    const targetAcquisition = inputs.openingBidOrTargetPrice ?? Math.round(estimatedValue * 0.55);
    if (!inputs.openingBidOrTargetPrice) {
      assumptions.acquisitionBasis = 'Assumed 55% of ARV wholesale entry';
    } else {
      knownValues.openingBidOrTargetPrice = inputs.openingBidOrTargetPrice;
    }

    const maximumAllowableOffer70Rule = Math.max(
      0,
      Math.round(estimatedValue * 0.70 - estimatedRehabCost - (inputs.taxLiensAmount || 0))
    );

    const projectedGrossSpread = Math.max(0, estimatedValue - targetAcquisition);
    const projectedNetOpportunity = Math.max(
      0,
      estimatedValue - targetAcquisition - estimatedRehabCost - estimatedClosingAndHoldingCosts
    );

    // Confidence calculation based on ratio of knowns vs unknowns
    let confidence = 0.90;
    if (unknowns.includes('MORTGAGE_BALANCE_UNRECORDED')) confidence -= 0.15;
    if (unknowns.includes('EXACT_SQFT_ASSUMED_1800')) confidence -= 0.10;

    // Score from 0 - 100
    let score = 0;
    if (equityPercentage >= 70) score += 40;
    else if (equityPercentage >= 50) score += 30;
    else if (equityPercentage >= 30) score += 15;

    if (projectedNetOpportunity >= 100000) score += 40;
    else if (projectedNetOpportunity >= 50000) score += 30;
    else if (projectedNetOpportunity >= 25000) score += 20;

    if (estimatedValue >= 300000) score += 20;
    else score += 10;

    const economicsScore = Math.min(100, Math.round(score * confidence));

    return {
      estimatedValue,
      totalKnownObligations: totalObligations,
      netEstimatedEquity,
      equityPercentage,
      estimatedRehabCost,
      estimatedClosingAndHoldingCosts,
      maximumAllowableOffer70Rule,
      projectedGrossSpread,
      projectedNetOpportunity,
      economicsScore,
      confidenceScore: Math.round(confidence * 100) / 100,
      knownValues,
      assumptions,
      unknowns,
      isEconomicallyViable: projectedNetOpportunity >= 25000 && equityPercentage >= 35,
    };
  }
}
