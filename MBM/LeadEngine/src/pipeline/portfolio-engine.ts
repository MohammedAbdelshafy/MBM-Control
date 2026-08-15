/**
 * Portfolio Intelligence Engine — MBM Lead Quality v3 (P1)
 * Maps multi-property owner/entity relationships and boosts repeatable deal opportunities.
 * Never infers ownership merely from loose name or address similarity.
 */

export interface LinkedPropertySummary {
  propertyId: string;
  parcelId: string;
  address: string;
  estimatedValue: number;
  distressEventsCount: number;
  verificationSource: string;
}

export interface PortfolioRecord {
  ownerEntityId: string;
  canonicalName: string;
  entityType: 'INDIVIDUAL' | 'LLC' | 'CORPORATION' | 'TRUST' | 'PARTNERSHIP';
  linkedProperties: LinkedPropertySummary[];
  totalPortfolioValue: number;
  totalPropertiesCount: number;
  provenanceSource: string; // e.g. "FL_DOS_SUNBIZ_CORPORATE_FILING + DADE_COUNTY_TAX_ROLL"
  hasRepeatableDealPotential: boolean;
  portfolioScoreBoost: number; // 0 - 25 points
}

export class PortfolioEngine {
  private portfolioStore: Map<string, PortfolioRecord> = new Map();

  public registerVerifiedPropertyToEntity(
    entityKey: string,
    entityName: string,
    entityType: PortfolioRecord['entityType'],
    property: LinkedPropertySummary,
    verificationProof: {
      deedBookPage?: string;
      secretaryOfStateDocId?: string;
      assessorTaxAccount?: string;
    }
  ): PortfolioRecord {
    // Verification Gate: Require authoritative proof
    const hasProof = !!(
      verificationProof.deedBookPage ||
      verificationProof.secretaryOfStateDocId ||
      verificationProof.assessorTaxAccount
    );

    if (!hasProof) {
      throw new Error(
        `Portfolio linkage rejected for "${entityName}": Missing authoritative title or corporate filing proof.`
      );
    }

    const key = entityKey.trim().toLowerCase();
    let portfolio = this.portfolioStore.get(key);

    if (!portfolio) {
      portfolio = {
        ownerEntityId: entityKey,
        canonicalName: entityName,
        entityType,
        linkedProperties: [],
        totalPortfolioValue: 0,
        totalPropertiesCount: 0,
        provenanceSource: verificationProof.secretaryOfStateDocId
          ? `SOS_DOC_${verificationProof.secretaryOfStateDocId}`
          : `TAX_ACC_${verificationProof.assessorTaxAccount || verificationProof.deedBookPage}`,
        hasRepeatableDealPotential: false,
        portfolioScoreBoost: 0,
      };
      this.portfolioStore.set(key, portfolio);
    }

    // Avoid duplicate property entry
    const existingIndex = portfolio.linkedProperties.findIndex((p) => p.parcelId === property.parcelId);
    if (existingIndex === -1) {
      portfolio.linkedProperties.push(property);
      portfolio.totalPropertiesCount = portfolio.linkedProperties.length;
      portfolio.totalPortfolioValue = portfolio.linkedProperties.reduce((sum, p) => sum + (p.estimatedValue || 0), 0);
    }

    // Calculate portfolio score boost (scaled with validated properties)
    if (portfolio.totalPropertiesCount >= 5) {
      portfolio.portfolioScoreBoost = 25;
      portfolio.hasRepeatableDealPotential = true;
    } else if (portfolio.totalPropertiesCount >= 3) {
      portfolio.portfolioScoreBoost = 18;
      portfolio.hasRepeatableDealPotential = true;
    } else if (portfolio.totalPropertiesCount === 2) {
      portfolio.portfolioScoreBoost = 10;
      portfolio.hasRepeatableDealPotential = true;
    } else {
      portfolio.portfolioScoreBoost = 0;
      portfolio.hasRepeatableDealPotential = false;
    }

    return portfolio;
  }

  public getPortfolioForEntity(entityKey: string): PortfolioRecord | null {
    return this.portfolioStore.get(entityKey.trim().toLowerCase()) || null;
  }
}
