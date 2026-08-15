/**
 * Negative Disposition Suppression — JARVIS Worker 1
 *
 * Permanent suppression of leads/numbers that were rejected in the
 * field or at the gate:
 *
 *   BAD_NUMBER, WRONG_PERSON, NON_OWNER, DUPLICATE, DNC, SOLD,
 *   NOT_INTERESTED
 *
 * A negative disposition is PERMANENT by default and can never be
 * auto-cleared — previously rejected garbage must not flow back into
 * the prime dialer queue.
 *
 * Pure logic + injectable repository (Prisma/Supabase in production,
 * in-memory in tests).
 */

import crypto from 'node:crypto';
import type { PrismaClient } from '@prisma/client';
import type {
  DispositionDraft,
  DispositionType,
  NegativeDisposition,
} from './types';
import { NEGATIVE_DISPOSITIONS, PERMANENT_DISPOSITIONS } from './types';

export interface DispositionRecord {
  id: string;
  leadId: string | null;
  propertyId: string | null;
  phone: string;
  type: DispositionType;
  reason: string | null;
  permanent: boolean;
  source: string;
  recordedBy: string | null;
  recordedAt: Date;
  expiresAt: Date | null;
}

export interface DispositionRepository {
  record(d: DispositionDraft): Promise<{ id: string }>;
  findActiveByPhone(phone: string): Promise<DispositionRecord[]>;
  findActiveByProperty(propertyId: string): Promise<DispositionRecord[]>;
}

/** Strip to 10-digit (drop leading US country code) for canonical keys. */
export function normalizeDispositionPhone(phone: string): string {
  const digits = phone.replace(/\D/g, '');
  if (digits.length === 11 && digits.startsWith('1')) return digits.slice(1);
  return digits;
}

export function isNegativeDisposition(type: DispositionType): type is NegativeDisposition {
  return PERMANENT_DISPOSITIONS.has(type as NegativeDisposition);
}

export class PrismaDispositionRepository implements DispositionRepository {
  constructor(private readonly db: PrismaClient) {}

  async record(d: DispositionDraft): Promise<{ id: string }> {
    const created = await this.db.disposition.create({
      data: {
        leadId: d.leadId ?? null,
        propertyId: d.propertyId ?? null,
        phone: normalizeDispositionPhone(d.phone),
        type: toPrismaDisposition(d.type),
        reason: d.reason ?? null,
        permanent: d.permanent ?? isNegativeDisposition(d.type),
        source: d.source ?? 'dialer',
        recordedBy: d.recordedBy ?? null,
        expiresAt: d.expiresAt ?? null,
      },
      select: { id: true },
    });
    return created;
  }

  async findActiveByPhone(phone: string): Promise<DispositionRecord[]> {
    const now = new Date();
    const rows = await this.db.disposition.findMany({
      where: {
        phone: normalizeDispositionPhone(phone),
        OR: [{ expiresAt: null }, { expiresAt: { gt: now } }],
      },
      orderBy: { recordedAt: 'desc' },
    });
    return rows.map(toDispositionRecord);
  }

  async findActiveByProperty(propertyId: string): Promise<DispositionRecord[]> {
    const now = new Date();
    const rows = await this.db.disposition.findMany({
      where: {
        propertyId,
        OR: [{ expiresAt: null }, { expiresAt: { gt: now } }],
      },
      orderBy: { recordedAt: 'desc' },
    });
    return rows.map(toDispositionRecord);
  }
}

function toPrismaDisposition(type: DispositionType): 'BAD_NUMBER' | 'WRONG_PERSON' | 'NON_OWNER' | 'DUPLICATE' | 'DNC' | 'SOLD' | 'NOT_INTERESTED' | 'OTHER' {
  return type;
}

function toDispositionRecord(row: {
  id: string;
  leadId: string | null;
  propertyId: string | null;
  phone: string;
  type: DispositionType;
  reason: string | null;
  permanent: boolean;
  source: string | null;
  recordedBy: string | null;
  recordedAt: Date;
  expiresAt: Date | null;
}): DispositionRecord {
  return {
    id: row.id,
    leadId: row.leadId,
    propertyId: row.propertyId,
    phone: row.phone,
    type: row.type,
    reason: row.reason,
    permanent: row.permanent,
    source: row.source ?? 'MANUAL',
    recordedBy: row.recordedBy,
    recordedAt: row.recordedAt,
    expiresAt: row.expiresAt,
  };
}

export class InMemoryDispositionRepository implements DispositionRepository {
  private rows: DispositionRecord[] = [];

  async record(d: DispositionDraft): Promise<{ id: string }> {
    const id = crypto.randomUUID();
    this.rows.push({
      id,
      leadId: d.leadId ?? null,
      propertyId: d.propertyId ?? null,
      phone: normalizeDispositionPhone(d.phone),
      type: d.type,
      reason: d.reason ?? null,
      permanent: d.permanent ?? isNegativeDisposition(d.type),
      source: d.source ?? 'dialer',
      recordedBy: d.recordedBy ?? null,
      recordedAt: new Date(),
      expiresAt: d.expiresAt ?? null,
    });
    return { id };
  }

  async findActiveByPhone(phone: string): Promise<DispositionRecord[]> {
    const norm = normalizeDispositionPhone(phone);
    const now = new Date();
    return this.rows.filter(
      (r) =>
        r.phone === norm &&
        (r.expiresAt === null || r.expiresAt > now),
    );
  }

  async findActiveByProperty(propertyId: string): Promise<DispositionRecord[]> {
    const now = new Date();
    return this.rows.filter(
      (r) =>
        r.propertyId === propertyId &&
        (r.expiresAt === null || r.expiresAt > now),
    );
  }

  getAll(): DispositionRecord[] {
    return [...this.rows];
  }
}

export class DispositionRegistry {
  private readonly local: Map<string, DispositionRecord> = new Map();

  constructor(private readonly repository?: DispositionRepository | null) {}

  /**
   * Record a disposition. Negative dispositions default to `permanent`.
   * The record is written to the local registry AND the repository so
   * the very next gate evaluation in this process is suppressed.
   */
  public async record(d: DispositionDraft): Promise<void> {
    const phone = normalizeDispositionPhone(d.phone);
    const record: DispositionRecord = {
      id: crypto.randomUUID(),
      leadId: d.leadId ?? null,
      propertyId: d.propertyId ?? null,
      phone,
      type: d.type,
      reason: d.reason ?? null,
      permanent: d.permanent ?? isNegativeDisposition(d.type),
      source: d.source ?? 'dialer',
      recordedBy: d.recordedBy ?? null,
      recordedAt: new Date(),
      expiresAt: d.expiresAt ?? null,
    };
    this.local.set(`${phone}::${record.type}::${record.propertyId ?? ''}`, record);
    if (this.repository) await this.repository.record(d);
  }

  /** Active negative dispositions for a phone (optionally property-scoped). */
  public async dispositionsFor(
    phone: string,
    propertyId?: string,
  ): Promise<DispositionRecord[]> {
    const phoneRecords =
      (this.repository ? await this.repository.findActiveByPhone(phone) : []) ?? [];
    const localRecords = Array.from(this.local.values()).filter(
      (r) => r.phone === normalizeDispositionPhone(phone),
    );
    const merged = new Map<string, DispositionRecord>();
    for (const r of [...localRecords, ...phoneRecords]) {
      const key = `${r.phone}::${r.type}::${r.propertyId ?? ''}`;
      if (!merged.has(key) || r.recordedAt >= merged.get(key)!.recordedAt) {
        merged.set(key, r);
      }
    }
    const active = Array.from(merged.values()).filter(
      (r) => r.expiresAt === null || r.expiresAt > new Date(),
    );
    if (!propertyId) return active;
    return active.filter((r) => r.propertyId === null || r.propertyId === propertyId);
  }

  /** Permanent suppression codes for the phone/property, if any. */
  public async suppressionCodesFor(
    phone: string,
    propertyId?: string,
  ): Promise<NegativeDisposition[]> {
    const rows = await this.dispositionsFor(phone, propertyId);
    const codes = rows.filter((r) => r.permanent).map((r) => r.type);
    return Array.from(new Set(codes)) as NegativeDisposition[];
  }

  public isNegative(type: DispositionType): boolean {
    return isNegativeDisposition(type);
  }

  /** Translate permanent dispositions into gate seed lists. */
  public toGateSeeds(
    records: DispositionRecord[],
  ): { suppressionList: string[]; badNumbers: string[] } {
    const suppressionList: string[] = [];
    const badNumbers: string[] = [];
    for (const r of records) {
      if (!r.permanent) continue;
      const phone = normalizeDispositionPhone(r.phone);
      if (r.type === 'BAD_NUMBER' || r.type === 'WRONG_PERSON' || r.type === 'NON_OWNER') {
        badNumbers.push(phone);
      }
      if (
        r.type === 'DNC' ||
        r.type === 'SOLD' ||
        r.type === 'NOT_INTERESTED' ||
        r.type === 'WRONG_PERSON' ||
        r.type === 'NON_OWNER' ||
        r.type === 'DUPLICATE'
      ) {
        suppressionList.push(phone);
      }
    }
    return { suppressionList, badNumbers };
  }
}

export const NEGATIVE_DISPOSITION_CODES: readonly NegativeDisposition[] =
  NEGATIVE_DISPOSITIONS;