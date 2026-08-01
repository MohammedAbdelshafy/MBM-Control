import * as fs from 'node:fs';
import * as path from 'node:path';
import type { LeadExportRow, ExportResult } from './types';

interface CRMFieldMapping {
  header: string;
  value: (row: LeadExportRow) => string | number | boolean | undefined;
}

const CRM_FIELD_MAPPINGS: CRMFieldMapping[] = [
  { header: 'First Name', value: (r) => extractFirstName(r.ownerName) },
  { header: 'Last Name', value: (r) => extractLastName(r.ownerName) },
  { header: 'Company', value: (r) => r.ownerType === 'individual' ? '' : r.ownerName },
  { header: 'Lead Source', value: () => 'MBM Lead Engine' },
  { header: 'Lead Status', value: () => 'New' },
  { header: 'Property Address', value: (r) => r.address },
  { header: 'Property City', value: (r) => r.city },
  { header: 'Property State', value: (r) => r.state },
  { header: 'Property ZIP', value: (r) => r.zip },
  { header: 'Property County', value: (r) => r.county },
  { header: 'Property Type', value: (r) => r.propertyType },
  { header: 'Parcel ID (APN)', value: (r) => r.parcelId },
  { header: 'Year Built', value: (r) => r.yearBuilt },
  { header: 'Lot Size (sqft)', value: (r) => r.lotSize },
  { header: 'Building Size (sqft)', value: (r) => r.buildingSize },
  { header: 'Estimated Value', value: (r) => r.estimatedValue },
  { header: 'Owner Name', value: (r) => r.ownerName },
  { header: 'Owner Type', value: (r) => r.ownerType },
  { header: 'Mailing Address', value: (r) => r.mailingAddress },
  { header: 'Absentee Owner', value: (r) => r.isAbsentee ? 'Yes' : 'No' },
  { header: 'Lead Score', value: (r) => r.score },
  { header: 'Lead Grade', value: (r) => r.grade },
  { header: 'Confidence', value: (r) => r.confidence },
  { header: 'Niche', value: (r) => r.niche },
  { header: 'Signals', value: (r) => r.signals },
  { header: 'Summary', value: (r) => r.summary },
  { header: 'Data Source', value: (r) => r.source },
  { header: 'Date Generated', value: (r) => r.generatedAt },
];

const COLUMN_MAPPING_HEADER = `# MBM Lead Engine CRM Import
# Compatible with: HubSpot, Salesforce, Pipedrive
# Fields mapped for property lead import
# Generated: ${new Date().toISOString()}
# Total records: {{TOTAL_RECORDS}}
# ---`;

function extractFirstName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  if (parts.length <= 1) return fullName;
  return parts[0];
}

function extractLastName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  if (parts.length <= 1) return '';
  return parts.slice(1).join(' ');
}

function escapeCSV(value: unknown): string {
  if (value === null || value === undefined) return '';
  const str = String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export async function generateCRMImport(
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

    ws.write(COLUMN_MAPPING_HEADER.replace('{{TOTAL_RECORDS}}', String(leads.length)) + '\n');

    const headers = CRM_FIELD_MAPPINGS.map((m) => m.header);
    ws.write(headers.join(',') + '\n');

    const batchSize = 500;
    let idx = 0;

    const writeBatch = () => {
      try {
        const end = Math.min(idx + batchSize, leads.length);
        for (; idx < end; idx++) {
          const values = CRM_FIELD_MAPPINGS.map((m) => escapeCSV(m.value(leads[idx])));
          ws.write(values.join(',') + '\n');
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
