/**
 * Vertical Registry — Multi-Vertical AI Sales Engine
 *
 * A configurable marketplace: register, override, or remove verticals at
 * runtime (from JSON config, DB rows, or code) without touching the
 * engine. The default catalog ships with the five initial categories.
 */

import {
  DEFAULT_VERTICAL_CATALOG,
} from './definitions';
import type {
  ScoreDimension,
  ScoreWeights,
  VerticalCategoryId,
  VerticalDefinition,
} from './types';
import { SCORE_DIMENSIONS } from './types';

export const DEFAULT_SCORE_WEIGHTS: ScoreWeights = {
  pain: 0.2,
  buyingSignal: 0.15,
  companySize: 0.12,
  digitalGap: 0.15,
  automationPotential: 0.12,
  revenuePotential: 0.12,
  contactability: 0.09,
  recency: 0.05,
};

const REQUIRED_FIELDS = [
  'id',
  'name',
  'category',
  'icp',
  'decisionMakerProfile',
  'painSignals',
  'buyingSignals',
  'aiOpportunitySignals',
  'websiteOpportunitySignals',
  'automationOpportunitySignals',
  'appSoftwareOpportunitySignals',
  'recommendedOffers',
  'estimatedDealSize',
  'outreachAngle',
] as const;

export class VerticalRegistry {
  private readonly verticals = new Map<string, VerticalDefinition>();
  private readonly categoryOrder: VerticalCategoryId[] = [
    'HOME_SERVICES',
    'HEALTH_WELLNESS',
    'PROFESSIONAL_SERVICES',
    'LOCAL_SERVICES',
    'B2B_INDUSTRIAL',
  ];

  constructor(catalog: VerticalDefinition[] = DEFAULT_VERTICAL_CATALOG) {
    for (const def of catalog) {
      this.register(def);
    }
  }

  /** Register (or override) a vertical. Rejects malformed definitions. */
  public register(def: VerticalDefinition): VerticalDefinition {
    const errors = validateVertical(def);
    if (errors.length > 0) {
      throw new Error(
        `Invalid vertical "${def?.id ?? '<no id>'}": ${errors.join('; ')}`,
      );
    }
    this.verticals.set(def.id, def);
    return def;
  }

  public registerAll(defs: VerticalDefinition[]): number {
    let count = 0;
    for (const def of defs) {
      this.register(def);
      count += 1;
    }
    return count;
  }

  public remove(id: string): boolean {
    return this.verticals.delete(id);
  }

  public get(id: string): VerticalDefinition | undefined {
    return this.verticals.get(id);
  }

  public require(id: string): VerticalDefinition {
    const def = this.verticals.get(id);
    if (!def) throw new Error(`Unknown vertical: ${id}`);
    return def;
  }

  public all(): VerticalDefinition[] {
    return Array.from(this.verticals.values());
  }

  public byCategory(category: VerticalCategoryId): VerticalDefinition[] {
    return this.all().filter((v) => v.category === category);
  }

  public categories(): VerticalCategoryId[] {
    return this.categoryOrder.filter((c) => this.byCategory(c).length > 0);
  }

  public size(): number {
    return this.verticals.size;
  }

  public ids(): string[] {
    return Array.from(this.verticals.keys());
  }

  /** Effective scoring weights for a vertical (defaults + overrides). */
  public weightsFor(id: string): ScoreWeights {
    const def = this.require(id);
    const merged = { ...DEFAULT_SCORE_WEIGHTS };
    if (def.weightOverrides) {
      for (const dim of SCORE_DIMENSIONS) {
        const override = def.weightOverrides[dim];
        if (typeof override === 'number' && Number.isFinite(override)) {
          merged[dim] = Math.max(0, Math.min(1, override));
        }
      }
    }
    const total = SCORE_DIMENSIONS.reduce((acc, d) => acc + merged[d], 0);
    if (total === 0) return merged;
    // Normalize so the weighted sum always lands in [0, 100].
    for (const dim of SCORE_DIMENSIONS) {
      merged[dim] = merged[dim] / total;
    }
    return merged;
  }
}

export function validateVertical(def: VerticalDefinition): string[] {
  const errors: string[] = [];
  if (!def) return ['definition is null'];
  for (const field of REQUIRED_FIELDS) {
    const value = (def as unknown as Record<string, unknown>)[field];
    if (value === undefined || value === null || value === '') {
      errors.push(`missing "${field}"`);
    }
  }
  if (!Array.isArray(def.painSignals) || def.painSignals.length === 0) {
    errors.push('painSignals must be a non-empty array');
  }
  if (!Array.isArray(def.recommendedOffers) || def.recommendedOffers.length === 0) {
    errors.push('recommendedOffers must be a non-empty array');
  }
  const size = def.estimatedDealSize;
  if (!size || typeof size.min !== 'number' || typeof size.max !== 'number') {
    errors.push('estimatedDealSize.min/max must be numbers');
  } else if (size.min > size.max) {
    errors.push('estimatedDealSize.min cannot exceed max');
  }
  return errors;
}

export function scoreDimensionLabel(dim: ScoreDimension): string {
  return {
    pain: 'Pain',
    buyingSignal: 'Buying Signal',
    companySize: 'Company Size',
    digitalGap: 'Digital Gap',
    automationPotential: 'Automation Potential',
    revenuePotential: 'Revenue Potential',
    contactability: 'Contactability',
    recency: 'Recency',
  }[dim];
}