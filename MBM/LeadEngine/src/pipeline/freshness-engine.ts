/**
 * Freshness Engine — MBM Lead Quality v3 (P0)
 * Calculates real-time event freshness with exponential time decay.
 * A 6-day-old high-intent event outranks a 2-year-old generic distress record.
 */

export type EventType =
  | 'AUCTION_SCHEDULED'
  | 'AUCTION_APPROACHING'
  | 'FORECLOSURE_NOTICE'
  | 'VACANCY_DETECTED'
  | 'NEW_FILING'
  | 'PRICE_REDUCTION'
  | 'LISTING_STATUS_CHANGE'
  | 'TAX_DELINQUENCY_NOTICE'
  | 'OWNERSHIP_TRANSFER'
  | 'CODE_VIOLATION_CITED'
  | 'PROBATE_RECORDED';

export interface PropertyEvent {
  id: string;
  propertyId: string;
  eventType: EventType;
  eventDate: string; // ISO date
  retrievedAt: string; // ISO date
  source: string;
  sourceUrl?: string | null;
  sourceReference?: string | null;
  confidence: number; // 0 - 1.0
  isIndependentSource: boolean;
  metadata?: Record<string, unknown>;
}

export interface FreshnessScoreResult {
  rawEventScore: number;
  decayedScore: number; // 0 - 100
  daysElapsed: number;
  halfLifeDays: number;
  decayFactor: number;
  mostRecentEvent: PropertyEvent | null;
  activeEventsCount: number;
  freshnessLabel: 'ULTRA_HOT_CRITICAL' | 'HOT_RECENT' | 'WARM_ACTIVE' | 'COOLING' | 'STALE_DECAYED';
}

export class FreshnessEngine {
  // Half-life decay rates in days by event severity
  private static readonly HALF_LIFE_MAP: Record<EventType, number> = {
    AUCTION_APPROACHING: 7, // 7 days half-life (extremely urgent)
    AUCTION_SCHEDULED: 14,
    FORECLOSURE_NOTICE: 30,
    VACANCY_DETECTED: 21,
    PRICE_REDUCTION: 14,
    NEW_FILING: 30,
    LISTING_STATUS_CHANGE: 21,
    CODE_VIOLATION_CITED: 45,
    TAX_DELINQUENCY_NOTICE: 60,
    PROBATE_RECORDED: 60,
    OWNERSHIP_TRANSFER: 90,
  };

  // Base raw value per event type (0 - 100)
  private static readonly BASE_WEIGHT_MAP: Record<EventType, number> = {
    AUCTION_APPROACHING: 100,
    AUCTION_SCHEDULED: 95,
    FORECLOSURE_NOTICE: 90,
    VACANCY_DETECTED: 85,
    PRICE_REDUCTION: 80,
    NEW_FILING: 75,
    LISTING_STATUS_CHANGE: 70,
    PROBATE_RECORDED: 75,
    CODE_VIOLATION_CITED: 65,
    TAX_DELINQUENCY_NOTICE: 60,
    OWNERSHIP_TRANSFER: 50,
  };

  public calculateFreshness(events: PropertyEvent[], referenceDate: Date = new Date()): FreshnessScoreResult {
    if (!events || events.length === 0) {
      return {
        rawEventScore: 0,
        decayedScore: 0,
        daysElapsed: 999,
        halfLifeDays: 30,
        decayFactor: 0,
        mostRecentEvent: null,
        activeEventsCount: 0,
        freshnessLabel: 'STALE_DECAYED',
      };
    }

    let highestDecayedScore = 0;
    let mostRecentEvent: PropertyEvent | null = null;
    let lowestDaysElapsed = 9999;
    let selectedHalfLife = 30;

    for (const event of events) {
      const eventTime = new Date(event.eventDate).getTime();
      const refTime = referenceDate.getTime();
      const msDiff = Math.max(0, refTime - eventTime);
      const daysElapsed = msDiff / (1000 * 60 * 60 * 24);

      const halfLife = FreshnessEngine.HALF_LIFE_MAP[event.eventType] || 30;
      const baseWeight = FreshnessEngine.BASE_WEIGHT_MAP[event.eventType] || 50;

      // Exponential decay: Score(t) = Base * 2^(-t / HalfLife) * Confidence
      const decayFactor = Math.pow(2, -daysElapsed / halfLife);
      const score = baseWeight * decayFactor * event.confidence;

      if (score > highestDecayedScore) {
        highestDecayedScore = score;
        mostRecentEvent = event;
        lowestDaysElapsed = daysElapsed;
        selectedHalfLife = halfLife;
      }
    }

    const decayedScore = Math.round(Math.min(100, Math.max(0, highestDecayedScore)));

    let freshnessLabel: FreshnessScoreResult['freshnessLabel'] = 'STALE_DECAYED';
    if (decayedScore >= 85) freshnessLabel = 'ULTRA_HOT_CRITICAL';
    else if (decayedScore >= 70) freshnessLabel = 'HOT_RECENT';
    else if (decayedScore >= 50) freshnessLabel = 'WARM_ACTIVE';
    else if (decayedScore >= 25) freshnessLabel = 'COOLING';

    return {
      rawEventScore: mostRecentEvent ? FreshnessEngine.BASE_WEIGHT_MAP[mostRecentEvent.eventType] : 0,
      decayedScore,
      daysElapsed: Math.round(lowestDaysElapsed * 10) / 10,
      halfLifeDays: selectedHalfLife,
      decayFactor: Math.round(Math.pow(2, -lowestDaysElapsed / selectedHalfLife) * 1000) / 1000,
      mostRecentEvent,
      activeEventsCount: events.length,
      freshnessLabel,
    };
  }
}
