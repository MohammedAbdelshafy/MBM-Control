import * as fs from 'node:fs';
import * as path from 'node:path';
import type { LeadExportRow, ExportResult } from './types';

export async function generateJSON(
  leads: LeadExportRow[],
  filePath: string,
): Promise<ExportResult> {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const jsonContent = JSON.stringify(leads, null, 2);

  await fs.promises.writeFile(filePath, jsonContent, { encoding: 'utf-8' });

  const stats = await fs.promises.stat(filePath);

  return {
    filePath,
    fileName: path.basename(filePath),
    fileSize: stats.size,
    mimeType: 'application/json',
    totalRecords: leads.length,
    generatedAt: new Date(),
  };
}
