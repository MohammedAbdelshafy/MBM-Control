import { describe, it, expect } from 'vitest';
import { FreshnessEngine, type PropertyEvent } from '../src/pipeline/freshness-engine';
import { MotivationEngine } from '../src/pipeline/motivation-engine';
import { PortfolioEngine } from '../src/pipeline/portfolio-engine';
import { DealEconomicsEngine } from '../src/pipeline/deal-economics';
import { NegativeLearningEngine } from '../src/pipeline/negative-learning';
import { CorroborationEngine, type SourceClaim } from '../src/pipeline/corroboration-engine';
import { BuyerFitEngine } from '../src/pipeline/buyer-fit';
import { OpportunityIntelligenceOrchestrator } from '../src/pipeline/opportunity-orchestrator';

describe('Opportunity Intelligence Engine v3 (P0 - P2)', () => {
  // ── P0: Freshness Engine ──
  it('P0: 6-day-old approaching auction event significantly outranks a 2-year-old stale record', () => {
    const freshnessEngine = new FreshnessEngine();
    const now = new Date();

    const sixDaysAgo = new Date(now.getTime() - 6 * 24 * 60 * 60 * 1000).toISOString();
    const twoYearsAgo = new Date(now.getTime() - 730 * 24 * 60 * 60 * 1000).toISOString();

    const freshAuctionEvent: PropertyEvent = {
      id: 'event-fresh-01',
      propertyId: 'prop-01',
      eventType: 'AUCTION_APPROACHING',
      eventDate: sixDaysAgo,
      retrievedAt: now.toISOString(),
      source: 'AUCTION_DOT_COM_SCRAPER',
      confidence: 0.98,
      isIndependentSource: true,
    };

    const staleRecordEvent: PropertyEvent = {
      id: 'event-stale-02',
      propertyId: 'prop-02',
      eventType: 'CODE_VIOLATION_CITED',
      eventDate: twoYearsAgo,
      retrievedAt: twoYearsAgo,
      source: 'MUNICIPAL_OPEN_DATA',
      confidence: 0.90,
      isIndependentSource: true,
    };

    const freshResult = freshnessEngine.calculateFreshness([freshAuctionEvent], now);
    const staleResult = freshnessEngine.calculateFreshness([staleRecordEvent], now);

    expect(freshResult.decayedScore).toBeGreaterThanOrEqual(50);
    expect(freshResult.freshnessLabel).toBe('WARM_ACTIVE');
    expect(staleResult.decayedScore).toBeLessThan(5);
    expect(staleResult.freshnessLabel).toBe('STALE_DECAYED');
    expect(freshResult.decayedScore).toBeGreaterThan(staleResult.decayedScore * 10);
  });

  // ── P1: Multi-Signal Motivation Engine ──
  it('P1: Multi-signal motivation engine combines independent evidence and applies synergy boosts', () => {
    const motivationEngine = new MotivationEngine();

    const signals = [
      {
        type: 'FORECLOSURE_AUCTION' as const,
        source: 'COUNTY_CLERK_LIS_PENDENS',
        date: new Date().toISOString(),
        confidence: 0.95,
      },
      {
        type: 'VACANCY' as const,
        source: 'USPS_VACANCY_FEED',
        date: new Date().toISOString(),
        confidence: 0.90,
      },
      {
        type: 'TAX_DELINQUENCY' as const,
        source: 'COUNTY_TAX_ASSESSOR',
        date: new Date().toISOString(),
        confidence: 0.92,
      },
    ];

    const result = motivationEngine.calculateMotivation(signals);

    expect(result.totalMotivationScore).toBeGreaterThanOrEqual(80);
    expect(result.motivationTier).toBe('TIER_1_EXTREME_URGENCY');
    expect(result.signalCount).toBe(3);
    expect(result.explanation).toContain('FORECLOSURE AUCTION');
    expect(result.explanation).toContain('VACANCY');
    expect(result.explanation).toContain('TAX DELINQUENCY');
  });

  // ── P1: Portfolio Intelligence ──
  it('P1: Portfolio intelligence identifies multi-property owners and applies repeat-opportunity boost with proof', () => {
    const portfolioEngine = new PortfolioEngine();

    // Register property 1
    portfolioEngine.registerVerifiedPropertyToEntity(
      'entity-apex-01',
      'Apex Sun Holdings LLC',
      'LLC',
      {
        propertyId: 'p1',
        parcelId: 'PARCEL-01',
        address: '100 Biscayne Blvd',
        estimatedValue: 600000,
        distressEventsCount: 1,
        verificationSource: 'FL_DEED_BOOK_9912',
      },
      { deedBookPage: 'DB-9912-401' }
    );

    // Register property 2
    portfolioEngine.registerVerifiedPropertyToEntity(
      'entity-apex-01',
      'Apex Sun Holdings LLC',
      'LLC',
      {
        propertyId: 'p2',
        parcelId: 'PARCEL-02',
        address: '200 Brickell Ave',
        estimatedValue: 850000,
        distressEventsCount: 2,
        verificationSource: 'FL_DEED_BOOK_9918',
      },
      { deedBookPage: 'DB-9918-102' }
    );

    // Register property 3
    const portfolio = portfolioEngine.registerVerifiedPropertyToEntity(
      'entity-apex-01',
      'Apex Sun Holdings LLC',
      'LLC',
      {
        propertyId: 'p3',
        parcelId: 'PARCEL-03',
        address: '300 Ocean Dr',
        estimatedValue: 1200000,
        distressEventsCount: 1,
        verificationSource: 'FL_DEED_BOOK_9924',
      },
      { deedBookPage: 'DB-9924-880' }
    );

    expect(portfolio.totalPropertiesCount).toBe(3);
    expect(portfolio.totalPortfolioValue).toBe(2650000);
    expect(portfolio.hasRepeatableDealPotential).toBe(true);
    expect(portfolio.portfolioScoreBoost).toBe(18);
  });

  it('P1: Portfolio engine rejects unverified linkages missing authoritative title proof', () => {
    const portfolioEngine = new PortfolioEngine();

    expect(() =>
      portfolioEngine.registerVerifiedPropertyToEntity(
        'entity-fake-01',
        'Unverified Group LLC',
        'LLC',
        {
          propertyId: 'p-fake',
          parcelId: 'PARCEL-FAKE',
          address: '400 Fake Way',
          estimatedValue: 500000,
          distressEventsCount: 0,
          verificationSource: 'SCRAPED_PORTAL',
        },
        {} // Missing proof
      )
    ).toThrowError(/Missing authoritative title/);
  });

  // ── P1: Deal Economics ──
  it('P1: Deal economics engine calculates 70% Rule MAO, net equity, and exposes knowns and unknowns', () => {
    const economicsEngine = new DealEconomicsEngine();

    const result = economicsEngine.calculateEconomics({
      estimatedValue: 500000,
      knownMortgageBalance: 150000,
      taxLiensAmount: 12000,
      openingBidOrTargetPrice: 220000,
      sqft: 2000,
      propertyCondition: 'DISTRESSED',
    });

    expect(result.netEstimatedEquity).toBe(338000);
    expect(result.equityPercentage).toBe(68);
    expect(result.maximumAllowableOffer70Rule).toBe(228000);
    expect(result.projectedGrossSpread).toBe(280000);
    expect(result.economicsScore).toBeGreaterThan(50);
    expect(result.isEconomicallyViable).toBe(true);
    expect(result.knownValues.estimatedValue).toBe(500000);
    expect(result.knownValues.knownMortgageBalance).toBe(150000);
  });

  // ── P1: Negative Learning & Feedback ──
  it('P1: Negative learning engine handles call dispositions, enforces DNC, and handles NO_ANSWER retry backoff', () => {
    const negativeEngine = new NegativeLearningEngine();

    // 1. BAD_NUMBER
    const badNum = negativeEngine.recordDisposition({
      id: 'd-01',
      leadId: 'l-01',
      propertyId: 'prop-01',
      phone: '3057684905',
      ownerName: 'John Doe',
      disposition: 'BAD_NUMBER',
      timestamp: new Date().toISOString(),
    });
    expect(badNum.shouldRemoveFromActiveQueue).toBe(true);
    expect(negativeEngine.isPhoneSuppressed('3057684905')).toBe(true);

    // 2. NON_OWNER
    const nonOwner = negativeEngine.recordDisposition({
      id: 'd-02',
      leadId: 'l-02',
      propertyId: 'prop-02',
      phone: '2145551234',
      ownerName: 'Wrong Owner LLC',
      disposition: 'NON_OWNER',
      timestamp: new Date().toISOString(),
    });
    expect(negativeEngine.isOwnerInvalidated('prop-02', 'Wrong Owner LLC')).toBe(true);

    // 3. NO_ANSWER retry logic
    const attempt1 = negativeEngine.recordDisposition({
      id: 'd-03',
      leadId: 'l-03',
      propertyId: 'prop-03',
      phone: '2174928172',
      ownerName: 'Active Seller',
      disposition: 'NO_ANSWER',
      timestamp: new Date().toISOString(),
    });
    expect(attempt1.shouldRemoveFromActiveQueue).toBe(false); // Retained for controlled retry
    expect(attempt1.actionTaken).toContain('Attempt 1/4');
  });

  // ── P1: Multi-Source Corroboration ──
  it('P1: Corroboration engine distinguishes independent sources from syndicated echoes', () => {
    const corroborationEngine = new CorroborationEngine();

    const claimsWithSyndication: SourceClaim[] = [
      {
        sourceName: 'Auction.com',
        sourceDomain: 'auction.com',
        claimType: 'OWNERSHIP',
        claimedValue: 'Elena Rostova',
        retrievedAt: new Date().toISOString(),
        isSyndicatedFeed: false,
      },
      {
        sourceName: 'Miami-Dade Tax Collector',
        sourceDomain: 'miamidade.gov',
        claimType: 'OWNERSHIP',
        claimedValue: 'Elena Rostova',
        retrievedAt: new Date().toISOString(),
        isSyndicatedFeed: false,
      },
      {
        sourceName: 'Realtor.com MLS Echo',
        sourceDomain: 'realtor.com',
        claimType: 'OWNERSHIP',
        claimedValue: 'Elena Rostova',
        retrievedAt: new Date().toISOString(),
        isSyndicatedFeed: true,
      },
      {
        sourceName: 'Redfin MLS Echo',
        sourceDomain: 'redfin.com',
        claimType: 'OWNERSHIP',
        claimedValue: 'Elena Rostova',
        retrievedAt: new Date().toISOString(),
        isSyndicatedFeed: true,
      },
    ];

    const result = corroborationEngine.evaluateCorroboration(claimsWithSyndication);

    // Should count Auction.com + Miami-Dade gov + 1 MLS Root, and ignore duplicate Redfin echo
    expect(result.syndicatedSourcesIgnoredCount).toBe(1);
    expect(result.independentSourcesCount).toBe(3);
    expect(result.isAuthoritativelyCorroborated).toBe(true);
    expect(result.corroborationConfidence).toBeGreaterThanOrEqual(0.90);
  });

  // ── P2: Buyer Fit & Opportunity Orchestration ──
  it('P2: Evaluates end-to-end Opportunity Intelligence with Reason Card & Multi-Dimensional Ranking', () => {
    const orchestrator = new OpportunityIntelligenceOrchestrator();

    const now = new Date();
    const threeDaysAgo = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000).toISOString();

    const output = orchestrator.evaluateOpportunity({
      property: {
        parcelId: 'FL-MIA-09921',
        addressLine1: '8800 Collins Ave',
        city: 'Miami Beach',
        state: 'FL',
        zip: '33154',
        county: 'Miami-Dade',
        propertyType: 'SINGLE_FAMILY',
        estimatedValue: 850000,
      },
      ownership: {
        ownerName: 'Vanguard Realty Partners LLC',
        ownerType: 'LLC',
        mailingAddress: '8800 Collins Ave, Miami Beach, FL 33154',
        isAbsentee: true,
        confidenceScore: 0.95,
        corporateOfficerName: 'Marcus Vance',
        verifiedAt: now.toISOString(),
      },
      contact: {
        contactName: 'Marcus Vance',
        phone: '3057684905',
        email: 'marcus.vance@vanguardrealty.com',
        source: 'CMS_NPI',
        carrierType: 'MOBILE',
        lineStatus: 'ACTIVE',
        dncStatus: 'CLEAN',
        confidenceScore: 0.96,
        extractedAt: now.toISOString(),
      },
      events: [
        {
          id: 'ev-01',
          propertyId: 'FL-MIA-09921',
          eventType: 'AUCTION_APPROACHING',
          eventDate: threeDaysAgo,
          retrievedAt: now.toISOString(),
          source: 'COUNTY_AUCTION_BOARD',
          confidence: 0.98,
          isIndependentSource: true,
        },
      ],
      motivationSignals: [
        {
          type: 'FORECLOSURE_AUCTION',
          source: 'COUNTY_LIS_PENDENS',
          date: threeDaysAgo,
          confidence: 0.96,
        },
        {
          type: 'VACANCY',
          source: 'WATER_UTILITY_SHUTOFF',
          date: threeDaysAgo,
          confidence: 0.90,
        },
      ],
      economicsInputs: {
        knownMortgageBalance: 250000,
        openingBidOrTargetPrice: 420000,
        sqft: 2400,
        propertyCondition: 'DISTRESSED',
      },
    });

    expect(output.overallPriorityScore).toBeGreaterThanOrEqual(70);
    expect(output.isCallablePrimeQueue).toBe(true);
    expect(output.reasonCard.leadHeader).toContain('QUALIFIED');
    expect(output.reasonCard.eventUrgencyLine).toContain('AUCTION APPROACHING in 3 days');
    expect(output.reasonCard.ownerLine).toContain('Vanguard Realty Partners LLC');
    expect(output.reasonCard.whyCallLine).toBeDefined();
    expect(output.netellerCheckoutUrl).toContain('DEAL-FLMIA09921');
  });
});
