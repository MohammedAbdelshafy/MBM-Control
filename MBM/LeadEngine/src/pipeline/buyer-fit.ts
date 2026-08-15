/**
 * Buyer Fit Engine — MBM Lead Quality v3 (P2)
 * Connects SELLER → PROPERTY → BUYER intelligence.
 * Optimizes deal flow for immediate liquidity and buyer matchability.
 */

export interface BuyerProfile {
  id: string;
  buyerName: string;
  buyerType: 'INSTITUTIONAL_FUND' | 'HEDGE_FUND' | 'FIX_AND_FLIP' | 'BUY_AND_HOLD' | 'DEVELOPER' | 'FAMILY_OFFICE';
  targetGeographies: string[]; // Counties / States e.g. ["Miami-Dade", "Dallas", "FL", "TX"]
  targetPropertyTypes: string[]; // ["SINGLE_FAMILY", "MULTI_FAMILY", "COMMERCIAL"]
  priceMin: number;
  priceMax: number;
  minimumProjectedSpread: number; // e.g. $40,000
  activeCapitalAvailable: number;
  contactEmail?: string;
  contactPhone?: string;
  netellerWalletVerified?: boolean;
}

export interface BuyerMatchResult {
  buyerFitScore: number; // 0 - 100
  matchedBuyersCount: number;
  topMatchedBuyers: Array<{
    buyerName: string;
    buyerType: string;
    matchConfidence: number;
    matchReason: string;
  }>;
  liquiditySpeedTier: 'INSTANT_LIQUIDITY_UNDER_48H' | 'HIGH_LIQUIDITY_7_DAYS' | 'MODERATE_30_DAYS' | 'LOW_SPECIALIZED_BUYER';
}

export class BuyerFitEngine {
  private buyers: BuyerProfile[] = [];

  constructor(initialBuyers?: BuyerProfile[]) {
    if (initialBuyers) {
      this.buyers = initialBuyers;
    } else {
      // Default institutional & private buyer network
      this.buyers = [
        {
          id: 'buyer-inst-01',
          buyerName: 'Blackrock SFR Fund VII',
          buyerType: 'INSTITUTIONAL_FUND',
          targetGeographies: ['Dallas', 'Tarrant', 'Collin', 'TX', 'FL'],
          targetPropertyTypes: ['SINGLE_FAMILY', 'TOWNHOUSE'],
          priceMin: 200000,
          priceMax: 650000,
          minimumProjectedSpread: 35000,
          activeCapitalAvailable: 50000000,
          netellerWalletVerified: true,
        },
        {
          id: 'buyer-rehab-02',
          buyerName: 'Evergreen Real Estate Capital',
          buyerType: 'FIX_AND_FLIP',
          targetGeographies: ['Miami-Dade', 'Broward', 'Palm Beach', 'FL'],
          targetPropertyTypes: ['SINGLE_FAMILY', 'MULTI_FAMILY', 'CONDO'],
          priceMin: 150000,
          priceMax: 1200000,
          minimumProjectedSpread: 45000,
          activeCapitalAvailable: 15000000,
          netellerWalletVerified: true,
        },
        {
          id: 'buyer-comm-03',
          buyerName: 'Contech Asset Partners',
          buyerType: 'FAMILY_OFFICE',
          targetGeographies: ['National', 'FL', 'TX', 'NY', 'CA', 'IL'],
          targetPropertyTypes: ['COMMERCIAL', 'INDUSTRIAL', 'LAND'],
          priceMin: 500000,
          priceMax: 10000000,
          minimumProjectedSpread: 100000,
          activeCapitalAvailable: 100000000,
          netellerWalletVerified: true,
        },
      ];
    }
  }

  public evaluateBuyerFit(property: {
    county: string;
    state: string;
    propertyType: string;
    estimatedValue: number;
    projectedSpread: number;
  }): BuyerMatchResult {
    const matched: BuyerMatchResult['topMatchedBuyers'] = [];

    for (const buyer of this.buyers) {
      const geoMatch =
        buyer.targetGeographies.includes(property.county) ||
        buyer.targetGeographies.includes(property.state) ||
        buyer.targetGeographies.includes('National');

      const typeMatch = buyer.targetPropertyTypes.includes(property.propertyType);
      const priceMatch = property.estimatedValue >= buyer.priceMin && property.estimatedValue <= buyer.priceMax;
      const spreadMatch = property.projectedSpread >= buyer.minimumProjectedSpread;

      if (geoMatch && typeMatch && priceMatch) {
        let confidence = 0.70;
        if (spreadMatch) confidence += 0.20;
        if (buyer.netellerWalletVerified) confidence += 0.10;

        matched.push({
          buyerName: buyer.buyerName,
          buyerType: buyer.buyerType,
          matchConfidence: Math.min(1.0, confidence),
          matchReason: `Matches ${buyer.buyerType} criteria for ${property.county}, ${property.state} within $${buyer.priceMin.toLocaleString()} - $${buyer.priceMax.toLocaleString()} target band.`,
        });
      }
    }

    let score = 0;
    if (matched.length >= 3) score = 95;
    else if (matched.length === 2) score = 85;
    else if (matched.length === 1) score = 70;
    else score = 25;

    let speed: BuyerMatchResult['liquiditySpeedTier'] = 'LOW_SPECIALIZED_BUYER';
    if (score >= 85) speed = 'INSTANT_LIQUIDITY_UNDER_48H';
    else if (score >= 70) speed = 'HIGH_LIQUIDITY_7_DAYS';
    else if (score >= 50) speed = 'MODERATE_30_DAYS';

    return {
      buyerFitScore: score,
      matchedBuyersCount: matched.length,
      topMatchedBuyers: matched,
      liquiditySpeedTier: speed,
    };
  }
}
