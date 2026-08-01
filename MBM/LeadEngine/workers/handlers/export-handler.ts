import path from 'path';
import fs from 'fs/promises';
import pino from 'pino';
import ExcelJS from 'exceljs';
import PDFDocument from 'pdfkit';
import { getDb } from '../db';
import type { Lead, Property, Owner, LeadScore } from '@prisma/client';

const logger = pino({ name: 'export-handler' });

interface ExportPayload {
  exportId: string;
  format: 'CSV' | 'EXCEL' | 'PDF' | 'JSON';
  filters?: Record<string, unknown>;
  clientId?: string;
  generatedBy?: string;
  storageType?: string;
  storagePath?: string;
}

interface LeadExportRow {
  parcelId: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  county: string;
  ownerName: string;
  ownerType: string;
  mailingAddress: string;
  niche: string;
  status: string;
  grade: string;
  score: number;
  confidence: number;
  propertyType: string;
  estimatedValue: number | null;
  yearBuilt: number | null;
  lotSize: number | null;
  buildingSize: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  lastSaleDate: string;
  lastSalePrice: number | null;
  absenteeSignal: number;
  violationSeverity: number;
  taxDelinquency: number;
  [key: string]: unknown;
}

export async function handleExport(job: {
  id: string;
  data: unknown;
}): Promise<Record<string, unknown>> {
  const payload = job.data as ExportPayload;
  const { exportId, format, filters } = payload;
  const db = getDb();

  logger.info({ exportId, format }, 'Starting export job');

  const where: Record<string, unknown> = {};
  if (filters) {
    if (filters.status) where.status = filters.status;
    if (filters.grade) where.grade = filters.grade;
    if (filters.niche) where.niche = filters.niche;
    if (filters.clientId) where.clientId = filters.clientId;
    if (filters.scoreMin) where.score = { gte: filters.scoreMin };
    if (filters.scoreMax) {
      where.score = { ...(where.score as Record<string, unknown> || {}), lte: filters.scoreMax };
    }
  }

  const leads = await db.lead.findMany({
    where: where as Record<string, unknown>,
    include: {
      property: {
        include: {
          owners: true,
        },
      },
      leadScore: true,
    },
    orderBy: { score: 'desc' },
  });

  logger.info({ exportId, leadCount: leads.length }, 'Leads fetched for export');

  const rows: LeadExportRow[] = leads.map((lead) => {
    const p = lead.property;
    const owner = p.owners[0] ?? null;
    const score = lead.leadScore;

    return {
      parcelId: p.parcelId,
      address: `${p.addressLine1}${p.addressLine2 ? ' ' + p.addressLine2 : ''}`,
      city: p.city,
      state: p.state,
      zip: p.zip,
      county: p.county,
      ownerName: owner?.name ?? '',
      ownerType: owner?.ownerType ?? '',
      mailingAddress: owner?.mailingAddress ?? '',
      niche: lead.niche,
      status: lead.status,
      grade: lead.grade ?? '',
      score: lead.score,
      confidence: lead.confidence,
      propertyType: p.propertyType,
      estimatedValue: p.estimatedValue,
      yearBuilt: p.yearBuilt,
      lotSize: p.lotSizeSqft,
      buildingSize: p.buildingSqft,
      bedrooms: p.bedrooms,
      bathrooms: p.bathrooms,
      lastSaleDate: p.lastSaleDate?.toISOString() ?? '',
      lastSalePrice: p.lastSalePrice,
      absenteeSignal: score?.absenteeSignal ?? 0,
      violationSeverity: score?.violationSeverity ?? 0,
      taxDelinquency: score?.taxDelinquency ?? 0,
    };
  });

  const basename = `export_${exportId}_${Date.now()}`;
  const storagePath = payload.storagePath || process.env.STORAGE_PATH || './data/exports';
  await fs.mkdir(storagePath, { recursive: true });

  let filename: string;
  let filePath: string;
  let fileSize: number;

  switch (format) {
    case 'CSV':
      filename = `${basename}.csv`;
      filePath = path.join(storagePath, filename);
      fileSize = await generateCSV(rows, filePath);
      break;
    case 'JSON':
      filename = `${basename}.json`;
      filePath = path.join(storagePath, filename);
      fileSize = await generateJSON(rows, filePath);
      break;
    case 'EXCEL':
      filename = `${basename}.xlsx`;
      filePath = path.join(storagePath, filename);
      fileSize = await generateExcel(rows, filePath);
      break;
    case 'PDF':
      filename = `${basename}.pdf`;
      filePath = path.join(storagePath, filename);
      fileSize = await generatePDF(rows, filePath);
      break;
    default:
      throw new Error(`Unsupported export format: ${format}`);
  }

  await db.export.update({
    where: { id: exportId },
    data: {
      totalLeads: rows.length,
      filePath,
      fileSize,
    },
  });

  logger.info({ exportId, format, filename, fileSize, leadCount: rows.length }, 'Export completed');

  return {
    exportId,
    format,
    filename,
    filePath,
    fileSize,
    totalLeads: rows.length,
  };
}

function escapeCSV(value: unknown): string {
  const str = String(value ?? '');
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function buildCSVHeader(keys: string[]): string {
  return keys.map(escapeCSV).join(',') + '\n';
}

function buildCSVRow(row: LeadExportRow, keys: string[]): string {
  return keys.map((k) => escapeCSV(row[k])).join(',') + '\n';
}

async function generateCSV(rows: LeadExportRow[], filePath: string): Promise<number> {
  const keys = Object.keys(rows[0] ?? {});
  let csv = buildCSVHeader(keys);
  for (const row of rows) {
    csv += buildCSVRow(row, keys);
  }
  await fs.writeFile(filePath, csv, 'utf-8');
  return Buffer.byteLength(csv, 'utf-8');
}

async function generateJSON(rows: LeadExportRow[], filePath: string): Promise<number> {
  const json = JSON.stringify(rows, null, 2);
  await fs.writeFile(filePath, json, 'utf-8');
  return Buffer.byteLength(json, 'utf-8');
}

async function generateExcel(rows: LeadExportRow[], filePath: string): Promise<number> {
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet('Leads');
  const keys = Object.keys(rows[0] ?? {});

  const headerRow = sheet.addRow(keys);
  headerRow.font = { bold: true };
  headerRow.fill = {
    type: 'pattern',
    pattern: 'solid',
    fgColor: { argb: 'FFE0E0E0' },
  };

  for (const row of rows) {
    sheet.addRow(keys.map((k) => row[k]));
  }

  sheet.columns.forEach((col) => {
    if (col.eachCell) {
      let maxLen = 10;
      col.eachCell?.((cell) => {
        const val = cell.value ? String(cell.value).length : 0;
        if (val > maxLen) maxLen = val;
      });
      col.width = Math.min(maxLen + 3, 50);
    } else {
      col.width = 20;
    }
  });

  const buffer = await workbook.xlsx.writeBuffer();
  await fs.writeFile(filePath, Buffer.from(buffer));
  return Buffer.byteLength(buffer);
}

async function generatePDF(rows: LeadExportRow[], filePath: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const doc = new PDFDocument({ margin: 30, size: 'A4', layout: 'landscape' });
    const chunks: Buffer[] = [];

    doc.on('data', (chunk: Buffer) => chunks.push(chunk));
    doc.on('end', async () => {
      const buffer = Buffer.concat(chunks);
      await fs.writeFile(filePath, buffer);
      resolve(buffer.length);
    });
    doc.on('error', reject);

    doc.fontSize(16).text('Lead Export Report', { align: 'center' });
    doc.moveDown();
    doc.fontSize(9).text(`Generated: ${new Date().toISOString()} | Total Leads: ${rows.length}`, { align: 'center' });
    doc.moveDown();

    const headers = ['Parcel ID', 'Address', 'City', 'State', 'Score', 'Grade', 'Owner', 'Niche', 'Status'];
    const columns = ['parcelId', 'address', 'city', 'state', 'score', 'grade', 'ownerName', 'niche', 'status'] as const;
    const colWidths = [14, 26, 12, 6, 8, 8, 20, 14, 10];
    const pageWidth = 780;
    const rowHeight = 16;

    const drawHeader = (y: number) => {
      doc.fontSize(8).font('Helvetica-Bold');
      let x = 30;
      for (let i = 0; i < headers.length; i++) {
        doc.text(headers[i], x, y, { width: (colWidths[i] / 100) * pageWidth, align: 'left' });
        x += (colWidths[i] / 100) * pageWidth;
      }
    };

    const drawRow = (row: LeadExportRow, y: number) => {
      doc.fontSize(7).font('Helvetica');
      let x = 30;
      for (let i = 0; i < columns.length; i++) {
        const val = String(row[columns[i]] ?? '');
        doc.text(val, x, y, { width: (colWidths[i] / 100) * pageWidth, align: 'left' });
        x += (colWidths[i] / 100) * pageWidth;
      }
    };

    let y = doc.y;
    drawHeader(y);
    y += rowHeight;

    for (let i = 0; i < rows.length; i++) {
      if (y > 560) {
        doc.addPage();
        y = 30;
        drawHeader(y);
        y += rowHeight;
      }
      drawRow(rows[i], y);
      y += rowHeight;
    }

    doc.end();
  });
}
