/**
 * Multi-Signal Motivation Engine — MBM Lead Quality v3 (P1)
 * Combines independent distress signals into a transparent, composite motivation score.
 * Never allows a single uncorroborated signal to dictate lead priority.
 */

export type MotivationSignalType =
  | 'FORECLOSURE_AUCTION'
  | 'VACANCY'
  | 'TAX_DELINQUENCY'
  | 'ABSENTEE_OWNERSHIP'
  | 'LONG_TENURE'
  | 'EXPIRED_FAILED_LISTING'
  | 'PRICE_REDUCTIONS'
  | 'MUNICIPAL_CODE_VIOLATION'
  | 'ESTATE_PROBATE';

export interface MotivationSignalItem {
  signalType: MotivationSignalType;
  source: string;
  sourceReference?: string | null;
  detectedDate: string;
  confidence: number; // 0 - 1.0
  severityWeight: number; // 0 - 100
  scoreContribution: number; // points contributed to total
  description: string;
}

export interface MotivationScoreResult {
  totalMotivationScore: number; // 0 - 100
  signalCount: number;
  signals: MotivationSignalItem[];
  motivationTier: 'TIER_1_EXTREME_URGENCY' | 'TIER_2_HIGH_MOTIVATION' | 'TIER_3_MODERATE' | 'TIER_4_LOW_OR_PASSIVE';
  primaryMotivationDriver: string;
  explanation: string;
}

export class MotivationEngine {
  private static readonly MAX_WEIGHTS: Record<MotivationSignalType, number> = {
    FORECLOSURE_AUCTION: 35,
    ESTATE_PROBATE: 25,
    TAX_DELINQUENCY: 20,
    VACANCY: 20,
    EXPIRED_FAILED_LISTING: 18,
    PRICE_REDUCTIONS: 15,
    MUNICIPAL_CODE_VIOLATION: 15,
    ABSENTEE_OWNERSHIP: 12,
    LONG_TENURE: 10,
  };

  public calculateMotivation(signals: Array<{
    type: MotivationSignalType;
    source: string;
    sourceReference?: string;
    date: string;
    confidence: number;
    description?: string;
  }>): MotivationScoreResult {
    if (!signals || signals.length === 0) {
      return {
        totalMotivationScore: 0,
        signalCount: 0,
        signals: [],
        motivationTier: 'TIER_4_LOW_OR_PASSIVE',
        primaryMotivationDriver: 'None detected',
        explanation: 'No independent distress signals recorded.',
      };
    }

    const processedSignals: MotivationSignalItem[] = [];
    let rawSum = 0;
    let highestContribution = 0;
    let topDriver = 'General Market Ingestion';

    for (const item of signals) {
      const maxWeight = MotivationEngine.MAX_WEIGHTS[item.type] || 10;
      const contribution = Math.round(maxWeight * Math.min(1.0, Math.max(0, item.confidence)));
      
      const processed: MotivationSignalItem = {
        signalType: item.type,
        source: item.source,
        sourceReference: item.sourceReference,
        detectedDate: item.date,
        confidence: item.confidence,
        severityWeight: maxWeight,
        scoreContribution: contribution,
        description: item.description || `Confirmed ${item.type.replace(/_/g, ' ').toLowerCase()} via ${item.source}`,
      };

      processedSignals.push(processed);
      rawSum += contribution;

      if (contribution > highestContribution) {
        highestContribution = contribution;
        topDriver = item.type.replace(/_/g, ' ');
      }
    }

    // Corroboration multiplier: 2+ signals boost score, 3+ boost further
    let synergyMultiplier = 1.0;
    if (processedSignals.length >= 3) synergyMultiplier = 1.20;
    else if (processedSignals.length === 2) synergyMultiplier = 1.10;

    const totalMotivationScore = Math.min(100, Math.round(rawSum * synergyMultiplier));

    let tier: MotivationScoreResult['motivationTier'] = 'TIER_4_LOW_OR_PASSIVE';
    if (totalMotivationScore >= 80) tier = 'TIER_1_EXTREME_URGENCY';
    else if (totalMotivationScore >= 60) tier = 'TIER_2_HIGH_MOTIVATION';
    else if (totalMotivationScore >= 35) tier = 'TIER_3_MODERATE';

    const explanation = `Score ${totalMotivationScore}/100 derived from ${processedSignals.length} verified signal(s): ${processedSignals
      .map((s) => `${s.signalType.replace(/_/g, ' ')} (+${s.scoreContribution}pts, source: ${s.source})`)
      .join('; ')}.`;

    return {
      totalMotivationScore,
      signalCount: processedSignals.length,
      signals: processedSignals,
      motivationTier: tier,
      primaryMotivationDriver: topDriver,
      explanation,
    };
  }
}
