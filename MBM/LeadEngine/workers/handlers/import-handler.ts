import { Worker } from 'bullmq';
import pino from 'pino';
import { getDb } from '../db';
import ExcelJS from 'exceljs';
import {
  normalizeAddress,
  normalizeParcelId,
  computeDedupeKeys,
} from '../../src/property-intel';

const logger = pino({ name: 'import-handler' });

interface ImportPayload {
  importId: string;
  sourceId: string;
  filename?: string;
  csvData?: string;
  fileBuffer?: number[];
}

interface RawRow {
  parcelId?: string;
  addressLine1?: string;
  addressLine2?: string;
  city?: string;
  state?: string;
  zip?: string;
  county?: string;
  ownerName?: string;
  ownerType?: string;
  mailingAddress?: string;
  [key: string]: unknown;
}

const CHUNK_SIZE = 100;

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
}

function parseCSV(csv: string): RawRow[] {
  const lines = csv.split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];

  const headers = parseCSVLine(lines[0]);
  const rows: RawRow[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    const row: RawRow = {};
    for (let j = 0; j < headers.length; j++) {
      const val = values[j] ?? '';
      row[headers[j]] = val;
    }
    rows.push(row);
  }

  return rows;
}

function mapRowToDB(row: RawRow): RawRow {
  const map: Record<string, string> = {
    'parcel id': 'parcelId',
    'parcel_id': 'parcelId',
    'parcelid': 'parcelId',
    'apn': 'parcelId',
    'parcel number': 'parcelId',
    'address': 'addressLine1',
    'address1': 'addressLine1',
    'address line 1': 'addressLine1',
    'address_line1': 'addressLine1',
    'address line1': 'addressLine1',
    'address 2': 'addressLine2',
    'address2': 'addressLine2',
    'address line 2': 'addressLine2',
    'address_line2': 'addressLine2',
    'owner': 'ownerName',
    'owner name': 'ownerName',
    'owner_name': 'ownerName',
    'ownername': 'ownerName',
    'owner type': 'ownerType',
    'owner_type': 'ownerType',
    'ownertype': 'ownerType',
    'mailing address': 'mailingAddress',
    'mailing_address': 'mailingAddress',
    'mailingaddress': 'mailingAddress',
  };

  const mapped: RawRow = {};
  for (const [key, value] of Object.entries(row)) {
    const normalizedKey = key.toLowerCase().trim();
    const targetKey = map[normalizedKey] ?? normalizedKey;
    mapped[targetKey] = value;
  }
  return mapped;
}

export async function handleImport(job: {
  id: string;
  data: unknown;
}): Promise<Record<string, unknown>> {
  const payload = job.data as ImportPayload;
  const { importId, sourceId, csvData, fileBuffer } = payload;
  const db = getDb();

  logger.info({ importId, sourceId }, 'Starting import job');

  await db.import.update({
    where: { id: importId },
    data: { status: 'PROCESSING', startedAt: new Date() },
  });

  try {
    let rows: RawRow[] = [];

    if (csvData) {
      rows = parseCSV(csvData);
    } else if (fileBuffer && fileBuffer.length > 0) {
      const buffer = Buffer.from(fileBuffer);
      const workbook = new ExcelJS.Workbook();
      await workbook.xlsx.load(buffer as unknown as Parameters<typeof workbook.xlsx.load>[0]);
      const worksheet = workbook.worksheets[0];
      if (!worksheet) throw new Error('No worksheet found in XLSX file');

      const headers: string[] = [];
      const headerRow = worksheet.getRow(1);
      for (let col = 1; col <= headerRow.cellCount; col++) {
        headers.push(String(headerRow.getCell(col).value ?? ''));
      }

      for (let rowNum = 2; rowNum <= worksheet.rowCount; rowNum++) {
        const row = worksheet.getRow(rowNum);
        const rawRow: RawRow = {};
        for (let col = 1; col <= headers.length; col++) {
          rawRow[headers[col - 1]] = String(row.getCell(col).value ?? '');
        }
        rows.push(rawRow);
      }
    }

    if (rows.length === 0) {
      throw new Error('No data found in import file');
    }

    const mapped = rows.map(mapRowToDB);

    await db.import.update({
      where: { id: importId },
      data: { totalRows: mapped.length },
    });

    let processed = 0;
    let errorRows = 0;
    const allErrors: string[] = [];

    for (let i = 0; i < mapped.length; i += CHUNK_SIZE) {
      const chunk = mapped.slice(i, i + CHUNK_SIZE);

      try {
        await processChunk(db, sourceId, chunk);
        processed += chunk.length;
      } catch (chunkErr) {
        const msg = `Chunk at offset ${i}: ${(chunkErr as Error).message}`;
        logger.error({ err: chunkErr, importId, offset: i }, 'Chunk processing failed');
        allErrors.push(msg);
        errorRows += chunk.length;
      }

      await db.import.update({
        where: { id: importId },
        data: {
          processedRows: processed,
          errorRows,
          errors: allErrors.length > 0 ? JSON.parse(JSON.stringify(allErrors)) : undefined,
        },
      });

      logger.info(
        { importId, processed, total: mapped.length, errorRows },
        'Import progress',
      );
    }

    const finalStatus = errorRows > 0 && processed > 0 ? 'PARTIAL' : errorRows > 0 ? 'FAILED' : 'COMPLETED';

    await db.import.update({
      where: { id: importId },
      data: {
        status: finalStatus,
        completedAt: new Date(),
        processedRows: processed,
        errorRows,
        errors: allErrors.length > 0 ? JSON.parse(JSON.stringify(allErrors)) : undefined,
      },
    });

    logger.info(
      { importId, finalStatus, processed, total: mapped.length, errorRows },
      'Import completed',
    );

    return {
      importId,
      status: finalStatus,
      totalRows: mapped.length,
      processedRows: processed,
      errorRows,
      errors: allErrors,
    };
  } catch (err) {
    await db.import.update({
      where: { id: importId },
      data: { status: 'FAILED', completedAt: new Date(), errors: [(err as Error).message] },
    });
    throw err;
  }
}

async function processChunk(
  db: ReturnType<typeof getDb>,
  sourceId: string,
  chunk: RawRow[],
): Promise<void> {
  for (const row of chunk) {
    const result = await findOrCreateProperty(db, row);
    if (!result) continue;

    const { propertyId } = result;

    if (row.ownerName) {
      const mailingAddr = String(row.mailingAddress ?? '').trim() || String(row.addressLine1 ?? '').trim();
      const ownerType = normalizeOwnerType(String(row.ownerType ?? ''));

      await db.owner.create({
        data: {
          propertyId,
          name: String(row.ownerName).trim(),
          ownerType,
          mailingAddress: mailingAddr,
        },
      });
    }
  }
}

function normalizeOwnerType(raw: string): 'INDIVIDUAL' | 'LLC' | 'CORPORATION' | 'TRUST' | 'PARTNERSHIP' | 'GOVERNMENT' | 'OTHER' {
  const val = raw.toLowerCase().trim();
  if (/llc|limited liability/i.test(val)) return 'LLC';
  if (/corp|corporation|inc/i.test(val)) return 'CORPORATION';
  if (/trust/i.test(val)) return 'TRUST';
  if (/partnership|llp/i.test(val)) return 'PARTNERSHIP';
  if (/gov|government|county|city|state/i.test(val)) return 'GOVERNMENT';
  if (/individual|sole/i.test(val)) return 'INDIVIDUAL';
  return 'OTHER';
}

/**
 * Deterministic dedupe: normalize the address once, derive the canonical
 * dedupe key, then collapse duplicates on parcel OR canonical address.
 */
async function findOrCreateProperty(
  db: ReturnType<typeof getDb>,
  row: RawRow,
): Promise<{ propertyId: string; existing: boolean } | null> {
  const parcelIdRaw = String(row.parcelId ?? '').trim();
  const address = String(row.addressLine1 ?? '').trim();
  const city = String(row.city ?? '').trim();
  const state = String(row.state ?? '').trim().toUpperCase().slice(0, 2);
  const zip = String(row.zip ?? '').trim().slice(0, 10);
  const county = String(row.county ?? '').trim();

  if (!parcelIdRaw && !address) return null;

  const keys = computeDedupeKeys({
    parcelId: parcelIdRaw || undefined,
    addressLine1: address || undefined,
    city: city || undefined,
    state: state || undefined,
    zip: zip || undefined,
    county: county || undefined,
  });
  const normalized = normalizeAddress({
    line1: address,
    city,
    state,
    zip,
    county,
  });

  const propertyData = {
    parcelId: parcelIdRaw ? normalizeParcelId(parcelIdRaw) : `ADDR-${keys.addressKey.slice(0, 20).toUpperCase()}`,
    addressLine1: address || 'Unknown',
    addressLine2: String(row.addressLine2 ?? '').trim() || undefined,
    normalizedAddress: normalized.full,
    dedupeKey: keys.addressKey,
    city: normalized.city || 'Unknown',
    state: normalized.state,
    zip: normalized.zip,
    county: county || 'Unknown',
    propertyType: 'OTHER' as const,
  };

  // Lookup by parcel id first (strongest key), then canonical address.
  let existingId: string | null = null;
  if (parcelIdRaw) {
    const byParcel = await db.property.findUnique({
      where: { parcelId: normalizeParcelId(parcelIdRaw) },
      select: { id: true },
    });
    existingId = byParcel?.id ?? null;
  }
  if (!existingId) {
    const byDedupe = await db.property.findUnique({
      where: { dedupeKey: keys.addressKey },
      select: { id: true },
    });
    existingId = byDedupe?.id ?? null;
  }

  if (existingId) {
    await db.property.update({ where: { id: existingId }, data: propertyData });
    return { propertyId: existingId, existing: true };
  }

  const created = await db.property.create({ data: propertyData });
  return { propertyId: created.id, existing: false };
}
