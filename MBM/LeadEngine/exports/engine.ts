import * as path from 'node:path';
import * as fs from 'node:fs';
import type { ExportOptions, ExportResult, LeadExportRow } from './types';
import { generateCSV } from './csv';
import { generateExcel } from './excel';
import { generatePDF } from './pdf';
import { generateJSON } from './json-export';
import { generateCRMImport } from './crm-import';

const EXPORT_DIR = process.env.MBM_EXPORT_DIR ?? path.join(process.cwd(), 'exports', 'output');

const FORMAT_MIME_TYPES: Record<ExportOptions['format'], string> = {
  csv: 'text/csv; charset=utf-8',
  excel: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  pdf: 'application/pdf',
  json: 'application/json',
  crm_import: 'text/csv; charset=utf-8',
};

function detectCounty(leads: LeadExportRow[]): string {
  if (leads.length === 0) return 'all';
  const county = leads[0]?.county?.trim().toLowerCase().replace(/\s+/g, '-');
  return county || 'all';
}

function generateTimestamp(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  const h = String(now.getHours()).padStart(2, '0');
  const min = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');
  return `${y}${m}${d}-${h}${min}${s}`;
}

function generateFileName(county: string, format: ExportOptions['format']): string {
  const extMap: Record<ExportOptions['format'], string> = {
    csv: '.csv',
    excel: '.xlsx',
    pdf: '.pdf',
    json: '.json',
    crm_import: '.csv',
  };

  const ext = extMap[format];
  const timestamp = generateTimestamp();

  return `mbm-leads-${county}-${timestamp}${ext}`;
}

function validateExportOptions(options: ExportOptions): void {
  const validFormats: ExportOptions['format'][] = ['csv', 'excel', 'pdf', 'json', 'crm_import'];
  if (!validFormats.includes(options.format)) {
    throw new Error(`Unsupported export format: ${options.format}. Supported: ${validFormats.join(', ')}`);
  }
}

export async function generateExport(
  leads: LeadExportRow[],
  options: ExportOptions,
): Promise<ExportResult> {
  validateExportOptions(options);

  if (leads.length === 0) {
    throw new Error('Cannot generate export: lead dataset is empty');
  }

  if (!fs.existsSync(EXPORT_DIR)) {
    fs.mkdirSync(EXPORT_DIR, { recursive: true });
  }

  const county = detectCounty(leads);
  const fileName = generateFileName(county, options.format);
  const filePath = path.join(EXPORT_DIR, fileName);

  let result: ExportResult;

  switch (options.format) {
    case 'csv':
      result = await generateCSV(leads, filePath);
      break;
    case 'excel':
      result = await generateExcel(leads, filePath);
      break;
    case 'pdf':
      result = await generatePDF(leads, filePath, options.headerText, options.brandLogo);
      break;
    case 'json':
      result = await generateJSON(leads, filePath);
      break;
    case 'crm_import':
      result = await generateCRMImport(leads, filePath);
      break;
    default: {
      const exhaustive: never = options.format;
      throw new Error(`Unhandled export format: ${exhaustive}`);
    }
  }

  return result;
}
