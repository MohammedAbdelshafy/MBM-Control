/**
 * Configurable Lead Scoring — JARVIS Worker 1
 *
 * Lead-scoring weights are NOT hardcoded. They resolve from a
 * `ScoringConfig` registry (per county / source / niche / global) with
 * the built-in DEFAULT_WEIGHTS as the fallback, so operators can tune
 * scoring per market without code changes.
 *
 * Pure logic + injectable repository (Prisma/Supabase in production,
 * in-memory in tests).
 */

import type { PrismaClient } from '@prisma/client';
import { DEFAULT_WEIGHTS, type ScoringWeights } from '../scoring/weights';
import type { ScoringConfigDraft } from './types';

export type ScoringScope = 'global' | 'county' | 'state' | 'source' | 'niche';

export interface ScoringConfigRow {
  id: string;
  name: string;
  scope: string;
  scopeValue: string | null;
  weights: Record<string, number>;
  enabled: boolean;
}

export interface ScoringConfigRepository {
  /** Most specific enabled config first. */
  findBest(scope: ScoringScope, scopeValue: string): Promise<ScoringConfigRow | null>;
  save(config: ScoringConfigDraft): Promise<ScoringConfigRow>;
}

export class PrismaScoringConfigRepository implements ScoringConfigRepository {
  constructor(private readonly db: PrismaClient) {}

  async findBest(scope: ScoringScope, scopeValue: string): Promise<ScoringConfigRow | null> {
    const row = await this.db.scoringConfig.findFirst({
      where: { scope, scopeValue: { equals: scopeValue, mode: 'insensitive' }, enabled: true },
      orderBy: { updatedAt: 'desc' },
    });
    return row ? this.mapRow(row) : null;
  }

  async save(config: ScoringConfigDraft): Promise<ScoringConfigRow> {
    const row = await this.db.scoringConfig.upsert({
      where: { name: config.name },
      create: {
        name: config.name,
        scope: config.scope,
        scopeValue: config.scopeValue ?? null,
        weights: config.weights as never,
        enabled: config.enabled,
      },
      update: {
        scope: config.scope,
        scopeValue: config.scopeValue ?? null,
        weights: config.weights as never,
        enabled: config.enabled,
      },
    });
    return this.mapRow(row);
  }

  private mapRow(row: {
    id: string;
    name: string;
    scope: string;
    scopeValue: string | null;
    weights: unknown;
    enabled: boolean;
  }): ScoringConfigRow {
    return {
      id: row.id,
      name: row.name,
      scope: row.scope,
      scopeValue: row.scopeValue,
      weights: (row.weights ?? {}) as Record<string, number>,
      enabled: row.enabled,
    };
  }
}

export class InMemoryScoringConfigRepository implements ScoringConfigRepository {
  private rows: ScoringConfigRow[] = [];

  async findBest(scope: ScoringScope, scopeValue: string): Promise<ScoringConfigRow | null> {
    const needle = scopeValue.toUpperCase();
    const match = this.rows
      .filter(
        (r) => r.enabled && r.scope === scope && (r.scopeValue ?? '').toUpperCase() === needle,
      )
      .sort((a, b) => b.id.localeCompare(a.id))[0];
    return match ?? null;
  }

  async save(config: ScoringConfigDraft): Promise<ScoringConfigRow> {
    const row: ScoringConfigRow = {
      id: config.name,
      name: config.name,
      scope: config.scope,
      scopeValue: config.scopeValue ?? null,
      weights: config.weights,
      enabled: config.enabled,
    };
    this.rows = this.rows.filter((r) => r.name !== config.name);
    this.rows.push(row);
    return row;
  }

  getAll(): ScoringConfigRow[] {
    return [...this.rows];
  }
}

/**
 * Resolves effective scoring weights for a context.
 *
 * Priority: niche > source > county > state > global > DEFAULT_WEIGHTS.
 */
export class ScoringConfigResolver {
  constructor(private readonly repository: ScoringConfigRepository | null) {}

  public async resolveWeights(context?: {
    county?: string | null;
    state?: string | null;
    source?: string | null;
    niche?: string | null;
  }): Promise<ScoringWeights> {
    const merged: ScoringWeights = { ...DEFAULT_WEIGHTS };

    const layers: Array<{ scope: ScoringScope; value: string | null }> = [
      { scope: 'global', value: null },
      { scope: 'state', value: context?.state ?? null },
      { scope: 'county', value: context?.county ?? null },
      { scope: 'source', value: context?.source ?? null },
      { scope: 'niche', value: context?.niche ?? null },
    ];

    for (const layer of layers) {
      if (!layer.value) continue;
      const row = this.repository
        ? await this.repository.findBest(layer.scope, layer.value)
        : null;
      if (row) {
        const weights = sanitizeWeights(row.weights);
        Object.assign(merged, weights);
      }
    }

    return merged;
  }
}

export function sanitizeWeights(
  raw: Record<string, unknown>,
): Partial<ScoringWeights> {
  const validKeys = Object.keys(DEFAULT_WEIGHTS) as (keyof ScoringWeights)[];
  const result: Partial<ScoringWeights> = {};
  for (const key of validKeys) {
    const val = Number(raw[key]);
    if (Number.isFinite(val)) result[key] = Math.max(0, Math.min(1, val));
  }
  return result;
}

export { DEFAULT_WEIGHTS };
export type { ScoringWeights };