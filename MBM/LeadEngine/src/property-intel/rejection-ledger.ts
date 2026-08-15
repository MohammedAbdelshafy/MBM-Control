/**
 * Rejection Ledger — JARVIS Worker 1
 *
 * The guarantee: *previously rejected garbage cannot automatically
 * return to the prime dialer queue.*
 *
 * Every gate rejection is recorded against three deterministic keys:
 *   - the phone,
 *   - the property identity (parcel/APN or canonical address key),
 *   - the combined phone+property identity.
 *
 * Permanent rejections are consulted BEFORE a new lead is evaluated.
 * A number or property that was already rejected is blocked again on
 * the very next run — even if the source re-delivers the same row, or
 * a producer re-imports it with fresh cosmetic fields.
 */

import crypto from 'node:crypto';
import type { PrismaClient } from '@prisma/client';
import { normalizeDispositionPhone } from './disposition';

export interface RejectionRecord {
  id: string;
  rejectionKey: string;
  dimension: 'PHONE' | 'PROPERTY' | 'COMBINED';
  phone: string;
  parcelId: string | null;
  addressKey: string | null;
  reasons: string[];
  permanent: boolean;
  source: string;
  recordedAt: Date;
}

export interface RejectionInput {
  phone: string;
  parcelId?: string | null;
  addressKey?: string | null;
  reasons: string[];
  permanent?: boolean;
  source?: string;
}

export interface RejectionLedgerRepository {
  record(r: RejectionRecord): Promise<void>;
  findPermanentByKey(key: string): Promise<RejectionRecord[]>;
}

function sha256(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

/** Deterministic rejection keys for a lead identity. */
export function rejectionKeysFor(input: {
  phone: string;
  parcelId?: string | null;
  addressKey?: string | null;
}): Array<{ key: string; dimension: RejectionRecord['dimension'] }> {
  const phone = normalizeDispositionPhone(input.phone);
  const keys: Array<{ key: string; dimension: RejectionRecord['dimension'] }> = [];
  if (phone) keys.push({ key: sha256(`phone:${phone}`), dimension: 'PHONE' });
  const propertyIdentity = input.parcelId ?? input.addressKey;
  if (propertyIdentity) {
    keys.push({
      key: sha256(`property:${String(propertyIdentity).trim().toUpperCase()}`),
      dimension: 'PROPERTY',
    });
  }
  keys.push({
    key: sha256(`combined:${phone}|${String(propertyIdentity ?? '').trim().toUpperCase()}`),
    dimension: 'COMBINED',
  });
  return keys;
}

export class PrismaRejectionLedgerRepository implements RejectionLedgerRepository {
  constructor(private readonly db: PrismaClient) {}

  async record(r: RejectionRecord): Promise<void> {
    await this.db.rejectionLedgerRecord.upsert({
      where: {
        rejectionKey_dimension: {
          rejectionKey: r.rejectionKey,
          dimension: r.dimension,
        },
      },
      create: {
        rejectionKey: r.rejectionKey,
        dimension: r.dimension,
        phone: r.phone,
        parcelId: r.parcelId,
        addressKey: r.addressKey,
        reasons: r.reasons as never,
        permanent: r.permanent,
        source: r.source,
        recordedAt: r.recordedAt,
      },
      update: {
        permanent: r.permanent,
        reasons: r.reasons as never,
        source: r.source,
        recordedAt: r.recordedAt,
      },
    });
  }

  async findPermanentByKey(key: string): Promise<RejectionRecord[]> {
    const rows = await this.db.rejectionLedgerRecord.findMany({
      where: { rejectionKey: key, permanent: true },
    });
    return rows.map((row) => ({
      id: row.id,
      rejectionKey: row.rejectionKey,
      dimension: row.dimension as RejectionRecord['dimension'],
      phone: row.phone ?? '',
      parcelId: row.parcelId,
      addressKey: row.addressKey,
      reasons: Array.isArray(row.reasons)
        ? (row.reasons as string[])
        : [String(row.reasons ?? '')],
      permanent: row.permanent,
      source: row.source,
      recordedAt: row.recordedAt,
    }));
  }
}

export class InMemoryRejectionLedgerRepository implements RejectionLedgerRepository {
  private rows: RejectionRecord[] = [];

  async record(r: RejectionRecord): Promise<void> {
    this.rows.push(r);
  }

  async findPermanentByKey(key: string): Promise<RejectionRecord[]> {
    return this.rows.filter((r) => r.permanent && r.rejectionKey === key);
  }

  getAll(): RejectionRecord[] {
    return [...this.rows];
  }
}

export class RejectionLedger {
  private readonly local: Map<string, RejectionRecord> = new Map();

  constructor(private readonly repository?: RejectionLedgerRepository | null) {}

  /**
   * Record a rejection for a lead identity. Returns the primary
   * combined rejection key.
   */
  public async recordRejection(input: RejectionInput): Promise<string> {
    const keys = rejectionKeysFor(input);
    const permanent = input.permanent ?? true;
    for (const { key, dimension } of keys) {
      const record: RejectionRecord = {
        id: crypto.randomUUID(),
        rejectionKey: key,
        dimension,
        phone: normalizeDispositionPhone(input.phone),
        parcelId: input.parcelId ?? null,
        addressKey: input.addressKey ?? null,
        reasons: input.reasons,
        permanent,
        source: input.source ?? 'predial_gate',
        recordedAt: new Date(),
      };
      this.local.set(key, record);
      if (this.repository) await this.repository.record(record);
    }
    return keys[keys.length - 1].key;
  }

  /**
   * Permanent rejection codes currently blocking this identity.
   * Empty array means the identity is clean.
   */
  public async rejectionCodesFor(input: {
    phone: string;
    parcelId?: string | null;
    addressKey?: string | null;
  }): Promise<string[]> {
    const keys = rejectionKeysFor(input);
    const reasons = new Set<string>();
    for (const { key } of keys) {
      const local = this.local.get(key);
      if (local?.permanent) local.reasons.forEach((r) => reasons.add(r));
      if (this.repository) {
        const rows = await this.repository.findPermanentByKey(key);
        for (const row of rows) row.reasons.forEach((r) => reasons.add(r));
      }
    }
    return Array.from(reasons);
  }

  public isBlocked(input: {
    phone: string;
    parcelId?: string | null;
    addressKey?: string | null;
  }): Promise<boolean> {
    return this.rejectionCodesFor(input).then((codes) => codes.length > 0);
  }
}