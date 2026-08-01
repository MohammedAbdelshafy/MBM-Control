const SECONDS_IN_DAY = 86_400_000;
const DAYS_IN_YEAR = 365;

interface OwnerRecord {
  mailingAddress?: string | null;
  propertyAddress?: string | null;
  mailingCity?: string | null;
  propertyCity?: string | null;
}

interface PropertyRecord {
  estimatedValue?: number | null;
  lastSalePrice?: number | null;
  assessedValue?: number | null;
}

interface ViolationRecord {
  type?: string | null;
  filedAt?: string | Date | null;
}

interface TaxRecord {
  status?: string | null;
  yearsDelinquent?: number | null;
  lastPaymentDate?: string | Date | null;
}

interface UtilityRecord {
  isActive?: boolean | null;
  lastPayment?: string | Date | null;
}

const COMMERCIAL_TYPES = new Set([
  'commercial',
  'industrial',
  'multi-family',
  'mixed-use',
  'retail',
  'office',
  'warehouse',
]);

function normalizeString(val: unknown): string {
  if (typeof val === 'string') return val.trim().toLowerCase();
  return '';
}

function normalizeAddress(addr: unknown): string {
  return normalizeString(addr).replace(/[^a-z0-9]/g, '');
}

/**
 * Determines absentee signal based on variance between mailing and property address.
 * Returns 1.0 if addresses differ entirely, 0.5 if same city but different address,
 * 0.0 if addresses match, 0 if input is insufficient.
 */
export function detectAbsentee(owner: OwnerRecord | null | undefined): number {
  if (!owner) return 0;

  const mailing = normalizeAddress(owner.mailingAddress);
  const property = normalizeAddress(owner.propertyAddress);

  if (!mailing || !property) return 0;

  if (mailing === property) return 0;

  const mailingCity = normalizeString(owner.mailingCity);
  const propertyCity = normalizeString(owner.propertyCity);

  if (mailingCity && propertyCity && mailingCity === propertyCity) {
    return 0.5;
  }

  return 1.0;
}

/**
 * Estimates vacancy likelihood from utility records, violations, and tax delinquency.
 * Each contributing factor is evidence-weighted; absence of data returns 0.
 */
export function detectVacancy(
  property: PropertyRecord | null | undefined,
  violations: ViolationRecord[] | null | undefined,
  utilityRecords: UtilityRecord[] | null | undefined,
): number {
  let score = 0;
  let evidenceCount = 0;

  if (Array.isArray(violations) && violations.length > 0) {
    const now = Date.now();
    const recentViolations = violations.filter((v) => {
      if (!v.filedAt) return false;
      const ts = new Date(v.filedAt).getTime();
      return !isNaN(ts) && now - ts < 180 * SECONDS_IN_DAY;
    });
    if (recentViolations.length >= 3) {
      score += 0.5;
    } else if (recentViolations.length > 0) {
      score += 0.3;
    }
    evidenceCount++;
  }

  if (Array.isArray(utilityRecords)) {
    const inactive = utilityRecords.some(
      (u) => u.isActive === false,
    );
    const stalePayment = utilityRecords.some((u) => {
      if (!u.lastPayment) return false;
      const ts = new Date(u.lastPayment).getTime();
      return !isNaN(ts) && Date.now() - ts > 90 * SECONDS_IN_DAY;
    });

    if (inactive || stalePayment) {
      score += 0.4;
    }
    evidenceCount++;
  }

  return evidenceCount > 0 ? Math.min(1, score) : 0;
}

/**
 * Calculates violation severity on a weighted scale:
 * structural = 1.0, safety = 0.8, maintenance = 0.5, cosmetic = 0.2.
 * Returns the mean severity across all violations, or 0 if none.
 */
export function detectViolationSeverity(
  violations: ViolationRecord[] | null | undefined,
): number {
  if (!Array.isArray(violations) || violations.length === 0) return 0;

  let totalSeverity = 0;
  let count = 0;

  for (const v of violations) {
    const type = normalizeString(v.type);
    let severity = 0;

    if (/struct(ural)?/.test(type) || /foundation/.test(type) || /roof/.test(type)) {
      severity = 1.0;
    } else if (/safety/.test(type) || /fire/.test(type) || /electrical/.test(type) || /hazard/.test(type)) {
      severity = 0.8;
    } else if (/maintenance/.test(type) || /exterior/.test(type) || /plumbing/.test(type) || /hvac/.test(type)) {
      severity = 0.5;
    } else if (/cosmetic/.test(type) || /paint/.test(type) || /landscaping/.test(type)) {
      severity = 0.2;
    }

    totalSeverity += severity;
    count++;
  }

  return count > 0 ? totalSeverity / count : 0;
}

/**
 * Assesses tax delinquency severity.
 * 3+ years delinquent → 1.0, 1-2 years → 0.7, current year only → 0.3, paid → 0.0.
 */
export function detectTaxDelinquency(
  taxRecords: TaxRecord[] | TaxRecord | null | undefined,
): number {
  const records = Array.isArray(taxRecords) ? taxRecords : [taxRecords].filter(Boolean);
  if (records.length === 0) return 0;

  let maxSeverity = 0;

  for (const r of records) {
    if (!r) continue;

    if (r.status && /paid|current/.test(normalizeString(r.status))) {
      continue;
    }

    if (typeof r.yearsDelinquent === 'number') {
      if (r.yearsDelinquent >= 3) {
        maxSeverity = Math.max(maxSeverity, 1.0);
      } else if (r.yearsDelinquent >= 1) {
        maxSeverity = Math.max(maxSeverity, 0.7);
      } else if (r.yearsDelinquent > 0) {
        maxSeverity = Math.max(maxSeverity, 0.3);
      }
    } else {
      maxSeverity = Math.max(maxSeverity, 0.3);
    }
  }

  return maxSeverity;
}

/**
 * Estimates equity proxy from property value data.
 * Returns ratio of (estimated - owed) / estimated, clamped 0-1.
 * Falls back to assessed value if last sale price is unavailable.
 */
export function detectEquityProxy(
  property: PropertyRecord | null | undefined,
): number {
  if (!property) return 0;

  const estimated = property.estimatedValue ?? property.assessedValue ?? 0;
  if (estimated <= 0) return 0;

  const owed = property.lastSalePrice ?? property.assessedValue ?? 0;
  if (owed <= 0) return 0;

  const equity = (estimated - owed) / estimated;
  return Math.max(0, Math.min(1, equity));
}

/**
 * Computes record freshness using a logarithmic decay curve.
 * 1.0 for today, decays to 0.0 at 365+ days.
 */
export function detectRecordFreshness(
  createdAt: string | Date | null | undefined,
): number {
  if (!createdAt) return 0;

  const created = new Date(createdAt);
  if (isNaN(created.getTime())) return 0;

  const ageMs = Date.now() - created.getTime();
  const ageDays = ageMs / SECONDS_IN_DAY;

  if (ageDays <= 0) return 1.0;
  if (ageDays >= DAYS_IN_YEAR) return 0;

  return Math.round((1 - Math.log(ageDays + 1) / Math.log(DAYS_IN_YEAR + 1)) * 1000) / 1000;
}

/**
 * Returns a commercial-opportunity score based on property type.
 * Commercial/industrial → 1.0, multi-family/mixed-use → 0.8,
 * retail/office/warehouse → 0.6, residential → 0.2, unknown → 0.
 */
export function detectCommercialOpportunity(
  propertyType: string | null | undefined,
): number {
  const type = normalizeString(propertyType);
  if (!type) return 0;

  if (/commercial|industrial/.test(type)) return 1.0;
  if (/multi.?family|mixed.?use/.test(type)) return 0.8;
  if (/retail|office|warehouse/.test(type)) return 0.6;
  if (/residential|single.?family|condo|townhouse/.test(type)) return 0.2;

  if (COMMERCIAL_TYPES.has(type)) return 1.0;

  return 0;
}

/**
 * Computes data completeness as the ratio of populated fields
 * to all known fields on the property object.
 */
export function detectDataCompleteness(
  property: Record<string, unknown> | null | undefined,
): number {
  if (!property) return 0;

  const keys = Object.keys(property);
  if (keys.length === 0) return 0;

  const populated = keys.filter((k) => {
    const val = property[k];
    return val !== null && val !== undefined && val !== '' && !(Array.isArray(val) && val.length === 0);
  }).length;

  return populated / keys.length;
}
