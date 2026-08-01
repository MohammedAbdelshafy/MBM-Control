import * as fs from 'node:fs';
import * as path from 'node:path';
import ExcelJS from 'exceljs';
import type { LeadExportRow, ExportResult } from './types';

const EXCEL_HEADERS: { header: string; key: keyof LeadExportRow; width: number }[] = [
  { header: 'Parcel ID', key: 'parcelId', width: 18 },
  { header: 'Address', key: 'address', width: 35 },
  { header: 'City', key: 'city', width: 18 },
  { header: 'State', key: 'state', width: 8 },
  { header: 'ZIP', key: 'zip', width: 10 },
  { header: 'County', key: 'county', width: 18 },
  { header: 'Property Type', key: 'propertyType', width: 16 },
  { header: 'Year Built', key: 'yearBuilt', width: 12 },
  { header: 'Lot Size', key: 'lotSize', width: 12 },
  { header: 'Building Size', key: 'buildingSize', width: 14 },
  { header: 'Est. Value', key: 'estimatedValue', width: 14 },
  { header: 'Owner Name', key: 'ownerName', width: 28 },
  { header: 'Owner Type', key: 'ownerType', width: 14 },
  { header: 'Mailing Address', key: 'mailingAddress', width: 35 },
  { header: 'Absentee', key: 'isAbsentee', width: 10 },
  { header: 'Niche', key: 'niche', width: 18 },
  { header: 'Score', key: 'score', width: 8 },
  { header: 'Grade', key: 'grade', width: 8 },
  { header: 'Confidence', key: 'confidence', width: 12 },
  { header: 'Signals', key: 'signals', width: 30 },
  { header: 'Summary', key: 'summary', width: 40 },
  { header: 'Source', key: 'source', width: 14 },
  { header: 'Generated At', key: 'generatedAt', width: 20 },
  { header: 'Export Timestamp', key: 'exportTimestamp', width: 20 },
];

const GRADE_COLORS: Record<string, string> = {
  'A+': 'FF00B050',
  'A': 'FF92D050',
  'B': 'FFFFC000',
  'C': 'FFFF6600',
  'Reject': 'FFC00000',
};

function getGradeCellColor(grade: string): string {
  return GRADE_COLORS[grade] ?? 'FFD9D9D9';
}

export async function generateExcel(
  leads: LeadExportRow[],
  filePath: string,
): Promise<ExportResult> {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'MBM Lead Engine';
  workbook.created = new Date();

  const ws = workbook.addWorksheet('Leads', {
    views: [{ state: 'frozen', ySplit: 1 }],
  });

  const headerRow = ws.addRow(EXCEL_HEADERS.map((h) => h.header));

  headerRow.eachCell((cell) => {
    cell.font = { bold: true, color: { argb: 'FFFFFFFF' }, size: 11, name: 'Calibri' };
    cell.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF2F5496' },
    };
    cell.alignment = { horizontal: 'center', vertical: 'middle' };
    cell.border = {
      top: { style: 'thin' },
      left: { style: 'thin' },
      bottom: { style: 'thin' },
      right: { style: 'thin' },
    };
  });

  for (const lead of leads) {
    const rowValues = EXCEL_HEADERS.map((col) => {
      const val = lead[col.key];
      return val ?? '';
    });
    const row = ws.addRow(rowValues);

    const grade = lead.grade;
    const gradeColor = getGradeCellColor(grade);

    const gradeColIndex = EXCEL_HEADERS.findIndex((h) => h.key === 'grade') + 1;
    const scoreColIndex = EXCEL_HEADERS.findIndex((h) => h.key === 'score') + 1;

    row.eachCell((cell, colNumber) => {
      cell.font = { size: 10, name: 'Calibri' };
      cell.alignment = { vertical: 'middle' };
      cell.border = {
        top: { style: 'thin', color: { argb: 'FFD9D9D9' } },
        left: { style: 'thin', color: { argb: 'FFD9D9D9' } },
        bottom: { style: 'thin', color: { argb: 'FFD9D9D9' } },
        right: { style: 'thin', color: { argb: 'FFD9D9D9' } },
      };

      if (colNumber === gradeColIndex) {
        cell.fill = {
          type: 'pattern',
          pattern: 'solid',
          fgColor: { argb: gradeColor },
        };
        cell.font = { bold: true, size: 10, name: 'Calibri', color: { argb: 'FF000000' } };
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
      }

      if (colNumber === scoreColIndex) {
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
      }
    });
  }

  for (const col of EXCEL_HEADERS) {
    const colIndex = EXCEL_HEADERS.indexOf(col) + 1;
    ws.getColumn(colIndex).width = col.width;
  }

  const lastCol = String.fromCharCode(64 + EXCEL_HEADERS.length);
  ws.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: leads.length + 1, column: EXCEL_HEADERS.length },
  };

  await workbook.xlsx.writeFile(filePath);

  const stats = fs.statSync(filePath);

  return {
    filePath,
    fileName: path.basename(filePath),
    fileSize: stats.size,
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    totalRecords: leads.length,
    generatedAt: new Date(),
  };
}
