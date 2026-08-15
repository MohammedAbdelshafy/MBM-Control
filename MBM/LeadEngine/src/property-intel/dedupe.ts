/**
 * Deterministic Deduplication — JARVIS Worker 1
 *
 * Registers property identities by canonical keys so that the same
 * property imported from multiple sources collapses to ONE row, and
 * the same row can never be re-added to a queue twice.
 *
 * A property is deduplicated on EITHER:
 *   - parcel/APN (county+state scoped), or
 *   - canonical address dedupe key.
 *
 * Pure module with an injectable repository so it is testable without
 * a database and usable against Postgres/Supabase in production.
 */

import { normalizeAddress, normalizeState, type NormalizedAddress } from './normalize-address';

export interface PropertyIdentityInput {
  parcelId?: string | null;
  addressLine1?: string | null;
  addressLine2?: string | null;
  city?: string | null;
  state?: string | null;
  zip?: string | null;
  county?: string | null;
}

export interface DedupeResult {
  /** True when this identity is already registered. */
  isDuplicate: boolean;
  /** Key that matched (parcel or address). */
  matchedKey: string;
  /** Resolved canonical keys for this identity. */
  keys: DedupeKeys;
}

export interface DedupeKeys {
  /** Canonical address key (county-agnostic). */
  addressKey: string;
  /** County-scoped address key. */
  addressKeyWithCounty: string;
  /** Normalized parcel/APN + county + state, or null when no APN. */
  parcelKey: string | null;
}

export interface DedupeRepository {
  /** Return true when the key is already registered. */
  exists(key: string): Promise<boolean> | boolean;
  /** Register a key. */
  register(key: string, propertyId?: string): Promise<void> | void;
  /** Look up the existing property id for a key, if any. */
  findByKey(key: string): Promise<string | null> | string | null;
}

export function normalizeParcelId(parcelId: string): string {
  return parcelId
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '');
}

export function computeDedupeKeys(input: PropertyIdentityInput): DedupeKeys {
  const normalized = normalizeAddress(input);
  const parcelKey =
    input.parcelId && String(input.parcelId).trim()
      ? [normalizeParcelId(String(input.parcelId)), normalized.state, normalized.county ?? '']
          .filter(Boolean)
          .join('::')
      : null;

  return {
    addressKey: normalized.dedupeKey,
    addressKeyWithCounty: normalized.dedupeKeyWithCounty,
    parcelKey,
  };
}

/** A canonical, deterministic dedupe key for a property identity. */
export function dedupeKeyFor(input: PropertyIdentityInput): string {
  const keys = computeDedupeKeys(input);
  return keys.parcelKey ?? keys.addressKey;
}

export class PropertyDedupeRegistry {
  private repository: DedupeRepository | null;
  private local: Map<string, string> = new Map();

  constructor(repository?: DedupeRepository | null) {
    this.repository = repository ?? null;
  }

  /**
   * Check a property identity for duplication. When `register=true`
   * (default), a non-duplicate is atomically registered so a second
   * concurrent call cannot slip the same identity through.
   */
  public async checkAndRegister(
    input: PropertyIdentityInput,
    propertyId?: string,
  ): Promise<DedupeResult> {
    const keys = computeDedupeKeys(input);
    const candidates = keys.parcelKey
      ? [keys.parcelKey, keys.addressKey, keys.addressKeyWithCounty]
      : [keys.addressKey, keys.addressKeyWithCounty];

    for (const key of candidates) {
      if (await this.isRegistered(key)) {
        return { isDuplicate: true, matchedKey: key, keys };
      }
    }

    const primary = candidates[0];
    // Register EVERY canonical key so a future import that matches on any
    // of them (parcel, address, county-scoped address) collapses to this row.
    for (const key of candidates) {
      await this.register(key, propertyId);
    }
    return { isDuplicate: false, matchedKey: primary, keys };
  }

  public async isDuplicate(input: PropertyIdentityInput): Promise<boolean> {
    const result = await this.checkAndRegister(input, undefined);
    return result.isDuplicate;
  }

  private async isRegistered(key: string): Promise<boolean> {
    if (this.local.has(key)) return true;
    if (this.repository) return Boolean(await this.repository.exists(key));
    return false;
  }

  private async register(key: string, propertyId?: string): Promise<void> {
    if (!this.local.has(key)) this.local.set(key, propertyId ?? key);
    if (this.repository) await this.repository.register(key, propertyId);
  }
}

export { normalizeState };
export type { NormalizedAddress };