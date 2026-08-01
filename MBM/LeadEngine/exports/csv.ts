import * as fs from 'node:fs';
import * as path from 'node:path';
import type { LeadExportRow, ExportResult } from './types';

const CSV_HEADERS: (keyof LeadExportRow)[] = [
  'parcelId', 'address', 'city', 'state', 'zip', 'county',
  'propertyType', 'yearBuilt', 'lotSize', 'buildingSize', 'estimatedValue',
  'ownerName', 'ownerType', 'mailingAddress', 'isAbsentee',
  'niche', 'score', 'grade', 'confidence', 'signals', 'summary',
  'source', 'generatedAt', 'exportTimestamp',
];

function escapeCSV(value: unknown): string {
  if (value === null || value === undefined) return '';
  const str = String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function formatRow(row: LeadExportRow): string {
  return CSV_HEADERS.map((key) => escapeCSV(row[key])).join(',');
}

export async function generateCSV(
  leads: LeadExportRow[],
  filePath: string,
): Promise<ExportResult> {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  return new Promise<ExportResult>((resolve, reject) => {
    let recordCount = 0;
    let errored = false;

    const ws = fs.createWriteStream(filePath, { encoding: 'utf-8' });

    ws.on('error', (err) => {
      errored = true;
      reject(err);
    });

    ws.on('finish', () => {
      try {
        const stats = fs.statSync(filePath);
        resolve({
          filePath,
          fileName: path.basename(filePath),
          fileSize: stats.size,
          mimeType: 'text/csv; charset=utf-8',
          totalRecords: recordCount,
          generatedAt: new Date(),
        });
      } catch (err) {
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    });

    ws.write('\ufeff');

    ws.write(CSV_HEADERS.join(',') + '\n');

    const batchSize = 500;
    let idx = 0;

    const writeBatch = () => {
      try {
        const end = Math.min(idx + batchSize, leads.length);
        for (; idx < end; idx++) {
          ws.write(formatRow(leads[idx]) + '\n');
          recordCount++;
        }
        if (idx < leads.length) {
          setImmediate(writeBatch);
        } else {
          ws.end();
        }
      } catch (err) {
        if (!errored) {
          errored = true;
          ws.destroy();
          reject(err instanceof Error ? err : new Error(String(err)));
        }
      }
    };

    writeBatch();
  });
}
