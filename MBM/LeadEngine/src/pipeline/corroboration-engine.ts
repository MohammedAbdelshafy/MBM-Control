/**
 * Multi-Source Corroboration Engine — MBM Lead Quality v3 (P1)
 * Validates independent source agreement and filters out syndicated/duplicate feeds.
 * Auction Source + County Tax Record + Secretary of State + NPI yields maximum composite confidence.
 */

export interface SourceClaim {
  sourceName: string;
  sourceDomain: string;
  claimType: 'OWNERSHIP' | 'VALUATION' | 'DISTRESS' | 'CONTACT' | 'PARCEL_APN';
  claimedValue: string;
  retrievedAt: string;
  isSyndicatedFeed: boolean;
  syndicationParent?: string;
}

export interface CorroborationResult {
  independentSourcesCount: number;
  syndicatedSourcesIgnoredCount: number;
  corroborationConfidence: number; // 0 - 1.0
  isAuthoritativelyCorroborated: boolean;
  participatingIndependentSources: string[];
  discrepancies: string[];
}

export class CorroborationEngine {
  // Known syndication networks where child feeds echo the same MLS/listing source
  private static readonly KNOWN_SYNDICATED_PAIRS: Map<string, string> = new Map([
    ['realtor.com', 'MLS_FEED'],
    ['redfin.com', 'MLS_FEED'],
    ['estately.com', 'MLS_FEED'],
    ['movoto.com', 'MLS_FEED'],
    ['zillow.com', 'MLS_FEED'],
    ['trulia.com', 'MLS_FEED'],
  ]);

  public evaluateCorroboration(claims: SourceClaim[]): CorroborationResult {
    if (!claims || claims.length === 0) {
      return {
        independentSourcesCount: 0,
        syndicatedSourcesIgnoredCount: 0,
        corroborationConfidence: 0,
        isAuthoritativelyCorroborated: false,
        participatingIndependentSources: [],
        discrepancies: ['No sources available for corroboration.'],
      };
    }

    const uniqueIndependentDomains = new Set<string>();
    const participatingSources: string[] = [];
    let syndicatedIgnored = 0;
    const valueMap: Map<string, Set<string>> = new Map();

    for (const claim of claims) {
      const cleanDomain = claim.sourceDomain.toLowerCase().trim();
      const isSyndicated =
        claim.isSyndicatedFeed ||
        CorroborationEngine.KNOWN_SYNDICATED_PAIRS.has(cleanDomain);

      if (isSyndicated) {
        const syndicationKey =
          claim.syndicationParent ||
          CorroborationEngine.KNOWN_SYNDICATED_PAIRS.get(cleanDomain) ||
          'SYNDICATED_PORTAL_GROUP';

        if (uniqueIndependentDomains.has(syndicationKey)) {
          syndicatedIgnored += 1;
          continue; // Ignore duplicate syndicated echoes
        } else {
          uniqueIndependentDomains.add(syndicationKey);
          participatingSources.push(`${claim.sourceName} (Syndicated Root)`);
        }
      } else {
        uniqueIndependentDomains.add(cleanDomain);
        participatingSources.push(claim.sourceName);
      }

      // Check consistency across claims of the same type
      const normalizedClaimValue = claim.claimedValue.trim().toLowerCase();
      const existingClaims = valueMap.get(claim.claimType) || new Set();
      existingClaims.add(normalizedClaimValue);
      valueMap.set(claim.claimType, existingClaims);
    }

    const independentCount = uniqueIndependentDomains.size;
    const discrepancies: string[] = [];

    // Check if conflicting values exist for any claim type
    for (const [claimType, values] of valueMap.entries()) {
      if (values.size > 1) {
        discrepancies.push(`Conflicting values found for ${claimType}: [${Array.from(values).join(' vs ')}]`);
      }
    }

    // Bayesian confidence scaling based on independent corroboration
    let confidence = 0.50;
    if (independentCount >= 4) confidence = 0.98;
    else if (independentCount === 3) confidence = 0.92;
    else if (independentCount === 2) confidence = 0.80;
    else if (independentCount === 1) confidence = 0.60;

    // Discrepancy penalty
    if (discrepancies.length > 0) {
      confidence = Math.max(0.30, confidence - 0.25 * discrepancies.length);
    }

    return {
      independentSourcesCount: independentCount,
      syndicatedSourcesIgnoredCount: syndicatedIgnored,
      corroborationConfidence: Math.round(confidence * 100) / 100,
      isAuthoritativelyCorroborated: independentCount >= 2 && discrepancies.length === 0,
      participatingIndependentSources: participatingSources,
      discrepancies,
    };
  }
}
