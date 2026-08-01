import * as fs from 'node:fs';
import * as path from 'node:path';
import * as readline from 'node:readline';
import {
  BasePlugin,
  PluginConfig,
  PluginManifest,
  PluginResult,
  PropertyRecord,
  OwnershipType,
  ViolationRecord,
} from './framework';

interface ColumnMap {
  parcelId?: string;
  addressLine1?: string;
  city?: string;
  state?: string;
  zip?: string;
  county?: string;
  ownerName?: string;
  ownerType?: string;
  mailingAddress?: string;
  yearBuilt?: string;
  propertyType?: string;
  lotSize?: string;
  buildingSize?: string;
  estimatedValue?: string;
  lastSaleDate?: string;
  lastSalePrice?: string;
  assessedValue?: string;
  taxAmount?: string;
  taxYear?: string;
  taxDelinquent?: string;
  [key: string]: string | undefined;
}

const COMMON_COLUMN_ALIASES: Record<string, string[]> = {
  parcelId: [
    'parcel id', 'parcel_id', 'parcelnumber', 'parcel number', 'parcel#',
    'apn', 'pin', 'property id', 'property_id', 'propertyid', 'parcel',
    'tax parcel', 'taxparcel', 'account number', 'account#',
  ],
  addressLine1: [
    'address', 'property address', 'site address', 'situs address',
    'location', 'property address 1', 'propertyaddress', 'site',
    'street address', 'street', 'property street',
  ],
  city: [
    'city', 'property city', 'situs city', 'municipality', 'town',
    'property city', 'property_city',
  ],
  state: [
    'state', 'property state', 'situs state', 'st', 'province',
  ],
  zip: [
    'zip', 'zip code', 'zipcode', 'postal code', 'postalcode',
    'post code', 'property zip', 'property_zip', 'zip5',
  ],
  county: [
    'county', 'property county', 'county name', 'countyname',
    'property_county',
  ],
  ownerName: [
    'owner', 'owner name', 'property owner', 'grantee', 'taxpayer',
    'owner_name', 'ownername', 'propertyowner', 'mailing name',
    'current owner', 'currentowner', 'owner 1',
  ],
  ownerType: [
    'owner type', 'ownership type', 'owner_type', 'entity type',
    'entitytype', 'ownership',
  ],
  mailingAddress: [
    'mailing address', 'mail address', 'owner address', 'mail_address',
    'mailingaddress', 'owneraddress', 'owner mailing address',
  ],
  yearBuilt: [
    'year built', 'year_built', 'yr built', 'construction year',
    'yearbuilt', 'yrbuilt', 'built year', 'build year',
  ],
  propertyType: [
    'property type', 'property_type', 'type', 'use code', 'land use',
    'propertytype', 'landuse', 'land_use', 'zoning', 'property class',
  ],
  lotSize: [
    'lot size', 'lot_size', 'lot area', 'acreage', 'sqft lot',
    'lotsize', 'lotarea', 'lot sqft', 'lotsqft', 'lot_sqft',
    'land sqft', 'land area',
  ],
  buildingSize: [
    'building size', 'building sqft', 'sqft', 'square feet',
    'gross area', 'living area', 'buildingsize', 'buildingsqft',
    'total sqft', 'totalsqft', 'square footage', 'heated sqft',
    'gross sqft', 'living sqft',
  ],
  estimatedValue: [
    'estimated value', 'market value', 'estimated market value',
    'total value', 'estimatedvalue', 'marketvalue', 'estimatedvalue',
    'appraised value', 'appraisedvalue', 'total value',
    'totalvalue', 'fair market value',
  ],
  lastSaleDate: [
    'last sale date', 'sale date', 'last sold', 'recording date',
    'lastsaledate', 'saledate', 'lastsold', 'sale date 1',
    'prior sale date', 'sale date 1',
  ],
  lastSalePrice: [
    'last sale price', 'sale price', 'sold price', 'sales amount',
    'consideration', 'lastsaleprice', 'saleprice', 'soldprice',
    'prior sale price', 'sale price 1',
  ],
  assessedValue: [
    'assessed value', 'tax assessed value', 'assessment', 'assessed',
    'assessedvalue', 'taxassessedvalue', 'tax assessed',
    'assessed land value', 'assessed improvement value',
  ],
  taxAmount: [
    'tax amount', 'taxes', 'property tax', 'annual taxes',
    'taxamount', 'propertytax', 'total tax', 'total tax amount',
  ],
  taxYear: [
    'tax year', 'tax_year', 'taxyear',
  ],
  taxDelinquent: [
    'tax delinquent', 'delinquent', 'tax status', 'taxdelinquent',
    'delinquent amount', 'delinquent status',
  ],
};

const FIELD_ALIAS_INDEX = new Map<string, { field: string; score: number }[]>();
for (const [field, aliases] of Object.entries(COMMON_COLUMN_ALIASES)) {
  for (const alias of aliases) {
    const normalized = alias.toLowerCase().replace(/[\s_-]+/g, ' ');
    if (!FIELD_ALIAS_INDEX.has(normalized)) {
      FIELD_ALIAS_INDEX.set(normalized, []);
    }
    FIELD_ALIAS_INDEX.get(normalized)!.push({ field, score: alias.length === normalized.length ? 2 : 1 });
  }
}

function buildColumnMap(headers: string[], explicitMap?: Record<string, string>): ColumnMap {
  const map: ColumnMap = {};

  const normalizedHeaders = headers.map((h) => ({
    original: h,
    normalized: h.toLowerCase().replace(/[\s_-]+/g, ' ').replace(/[^a-z0-9 ]/g, '').trim(),
    exact: h.toLowerCase().trim(),
  }));

  for (const h of normalizedHeaders) {
    if (explicitMap && explicitMap[h.original]) {
      const target = explicitMap[h.original];
      map[target] = h.original;
      continue;
    }

    const matches = FIELD_ALIAS_INDEX.get(h.normalized) ?? FIELD_ALIAS_INDEX.get(h.exact) ?? [];
    if (matches.length > 0) {
      const best = matches.reduce((a, b) => (a.score > b.score ? a : b));
      if (!map[best.field]) {
        map[best.field] = h.original;
      }
    }
  }

  return map;
}

function parseValue(raw: string | undefined | null): string | undefined {
  if (raw === undefined || raw === null) return undefined;
  const trimmed = raw.toString().trim();
  return trimmed.length === 0 ? undefined : trimmed;
}

function parseNumeric(raw: string | undefined | null): number | undefined {
  const val = parseValue(raw);
  if (!val) return undefined;
  const cleaned = val.replace(/[$,]/g, '');
  const num = Number(cleaned);
  return Number.isFinite(num) ? num : undefined;
}

function parseBoolean(raw: string | undefined | null): boolean | undefined {
  const val = parseValue(raw);
  if (!val) return undefined;
  const lower = val.toLowerCase();
  if (['yes', 'true', '1', 'y', 'delinquent'].includes(lower)) return true;
  if (['no', 'false', '0', 'n', 'current', 'paid'].includes(lower)) return false;
  return undefined;
}

function parseDate(raw: string | undefined | null): Date | undefined {
  const val = parseValue(raw);
  if (!val) return undefined;
  const d = new Date(val);
  return Number.isFinite(d.getTime()) ? d : undefined;
}

function mapOwnershipType(raw: string | undefined | null): OwnershipType | undefined {
  const val = parseValue(raw);
  if (!val) return undefined;
  const lower = val.toLowerCase();
  if (/individual|person|sole/.test(lower)) return 'individual';
  if (/corp|inc|corporation/.test(lower)) return 'corporate';
  if (/llc|limited liability/.test(lower)) return 'llc';
  if (/partnership|llp/.test(lower)) return 'partnership';
  if (/trust|trustee/.test(lower)) return 'trust';
  if (/gov|government|county|city|state|federal/.test(lower)) return 'government';
  if (/non.?profit|nonprofit|charity|church/.test(lower)) return 'nonprofit';
  return 'other';
}

function parseRow(headers: string[], values: string[], columnMap: ColumnMap, rowIndex: number): { record?: PropertyRecord; error?: string } {
  const row = Object.fromEntries(headers.map((h, i) => [h, values[i] ?? '']));

  const getVal = (field: string): string | undefined => {
    const header = columnMap[field];
    return header ? parseValue(row[header]) : undefined;
  };

  const getNum = (field: string): number | undefined => {
    const header = columnMap[field];
    return header ? parseNumeric(row[header]) : undefined;
  };

  const parcelId = getVal('parcelId');
  const address = getVal('addressLine1');
  const city = getVal('city');
  const state = getVal('state');
  const zip = getVal('zip');
  const county = getVal('county');

  if (!parcelId && !address) {
    return { error: `Row ${rowIndex}: Missing required field — must have at least 'parcelId' or 'addressLine1'` };
  }

  try {
    const record: PropertyRecord = {
      parcelId: parcelId ?? `auto-${rowIndex}`,
      addressLine1: address ?? 'UNKNOWN',
      city: city ?? 'UNKNOWN',
      state: state ?? 'UNKNOWN',
      zip: zip ?? '00000',
      county: county ?? 'UNKNOWN',
      ownerName: getVal('ownerName'),
      ownerType: mapOwnershipType(getVal('ownerType')),
      mailingAddress: getVal('mailingAddress'),
      yearBuilt: getNum('yearBuilt'),
      propertyType: getVal('propertyType'),
      lotSize: getNum('lotSize'),
      buildingSize: getNum('buildingSize'),
      estimatedValue: getNum('estimatedValue'),
      lastSaleDate: parseDate(getVal('lastSaleDate')),
      lastSalePrice: getNum('lastSalePrice'),
      assessedValue: getNum('assessedValue'),
      taxAmount: getNum('taxAmount'),
      taxYear: getNum('taxYear'),
      taxDelinquent: parseBoolean(getVal('taxDelinquent')),
    };

    const nonNullFields = Object.values(record).filter((v) => v !== undefined && v !== null).length;
    if (nonNullFields < 3) {
      return { error: `Row ${rowIndex}: Insufficient data — only ${nonNullFields} fields populated` };
    }

    return { record };
  } catch (err) {
    return { error: `Row ${rowIndex}: ${err instanceof Error ? err.message : String(err)}` };
  }
}

function parseCSVLine(line: string): string[] {
  const fields: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      if (inQuotes && i + 1 < line.length && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      fields.push(current);
      current = '';
    } else {
      current += char;
    }
  }

  fields.push(current);
  return fields;
}

async function* streamCSVRows(
  filePath: string,
  chunkSize: number,
): AsyncGenerator<string[][], void, unknown> {
  const rl = readline.createInterface({
    input: fs.createReadStream(filePath, { encoding: 'utf-8' }),
    crlfDelay: Infinity,
  });

  let headers: string[] | undefined;
  let buffer: string[][] = [];

  for await (const rawLine of rl) {
    let line = rawLine;
    if (!headers && line.charCodeAt(0) === 0xfeff) {
      line = line.slice(1);
    }

    if (line.trim().length === 0) continue;

    const parsed = parseCSVLine(line);

    if (!headers) {
      headers = parsed.map((h) => h.trim());
      continue;
    }

    buffer.push(parsed);

    if (buffer.length >= chunkSize) {
      yield buffer;
      buffer = [];
    }
  }

  if (buffer.length > 0) {
    yield buffer;
  }
}

async function processXLSX(
  filePath: string,
  columnMap: ColumnMap,
  chunkSize: number,
): Promise<{ properties: PropertyRecord[]; errors: string[] }> {
  const ExcelJS = await importExcelJS();
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(filePath);

  const worksheet = workbook.worksheets[0];
  if (!worksheet) {
    return { properties: [], errors: ['No worksheets found in workbook'] };
  }

  const properties: PropertyRecord[] = [];
  const errors: string[] = [];
  let rowIndex = 0;
  let headers: string[] = [];
  const buffer: string[][] = [];

  worksheet.eachRow({ includeEmpty: true }, (row: import('exceljs').Row) => {
    const values = (row.values as (import('exceljs').CellValue | undefined)[]).slice(1).map((v) => v?.toString() ?? '');
    rowIndex++;

    if (rowIndex === 1) {
      headers = values.map((h) => h.trim());
      return;
    }

    buffer.push(values);

    if (buffer.length >= chunkSize) {
      for (const rowValues of buffer) {
        const result = parseRow(headers, rowValues, columnMap, rowIndex - buffer.length + buffer.indexOf(rowValues));
        if (result.record) {
          properties.push(result.record);
        }
        if (result.error) {
          errors.push(result.error);
        }
      }
      buffer.length = 0;
    }
  });

  for (const rowValues of buffer) {
    const result = parseRow(headers, rowValues, columnMap, rowIndex - buffer.length + buffer.indexOf(rowValues) + 1);
    if (result.record) {
      properties.push(result.record);
    }
    if (result.error) {
      errors.push(result.error);
    }
  }

  return { properties, errors };
}

async function importExcelJS(): Promise<typeof import('exceljs')> {
  try {
    return await import('exceljs');
  } catch {
    throw new Error(
      'exceljs is required for XLSX support. Install it with: npm install exceljs',
    );
  }
}

type ChunkHandler = (chunk: PropertyRecord[]) => Promise<void> | void;

export class CsvImportPlugin extends BasePlugin {
  manifest: PluginManifest = {
    id: 'csv-import',
    name: 'CSV Import',
    version: '1.0.0',
    description: 'Import property records from CSV and XLSX files with automatic column mapping',
    author: 'MBM Lead Engine',
    supportedCounties: ['*'],
    type: 'csv',
  };

  private defaultConfig = {
    chunkSize: 500,
    maxRows: 50000,
    columnMap: undefined as Record<string, string> | undefined,
    onChunk: undefined as ChunkHandler | undefined,
  };

  constructor(config: PluginConfig) {
    super(config);
  }

  async import(onChunk?: ChunkHandler): Promise<PluginResult> {
    const startTime = Date.now();
    const filePath = this.config.config?.filePath as string | undefined;
    const chunkSize = (this.config.config?.chunkSize as number) ?? this.defaultConfig.chunkSize;
    const maxRows = (this.config.config?.maxRows as number) ?? this.defaultConfig.maxRows;
    const explicitMap = (this.config.config?.columnMap as Record<string, string>) ?? this.defaultConfig.columnMap;
    const chunkHandler = onChunk ?? (this.config.config?.onChunk as ChunkHandler | undefined);

    if (!filePath) {
      return {
        properties: [],
        errors: ['config.filePath is required'],
        totalProcessed: 0,
        totalErrors: 1,
        duration: Date.now() - startTime,
      };
    }

    if (!fs.existsSync(filePath)) {
      return {
        properties: [],
        errors: [`File not found: ${filePath}`],
        totalProcessed: 0,
        totalErrors: 1,
        duration: Date.now() - startTime,
      };
    }

    const ext = path.extname(filePath).toLowerCase();

    if (ext === '.xlsx' || ext === '.xls') {
      return this.importXLSX(filePath, chunkSize, maxRows, explicitMap, chunkHandler, startTime);
    }

    return this.importCSV(filePath, chunkSize, maxRows, explicitMap, chunkHandler, startTime);
  }

  private async importCSV(
    filePath: string,
    chunkSize: number,
    maxRows: number,
    explicitMap: Record<string, string> | undefined,
    chunkHandler: ChunkHandler | undefined,
    startTime: number,
  ): Promise<PluginResult> {
    const allProperties: PropertyRecord[] = [];
    const errors: string[] = [];
    let totalProcessed = 0;
    let headers: string[] = [];
    let columnMap: ColumnMap = {};

    const rowStream = streamCSVRows(filePath, chunkSize);
    const first = await rowStream.next();

    if (first.done || first.value.length === 0) {
      return {
        properties: [],
        errors: ['CSV file is empty or missing headers'],
        totalProcessed: 0,
        totalErrors: 1,
        duration: Date.now() - startTime,
      };
    }

    headers = first.value[0];
    columnMap = buildColumnMap(headers, explicitMap);
    const dataRows = first.value.slice(1);

    for (const values of dataRows) {
      totalProcessed++;
      const result = parseRow(headers, values, columnMap, totalProcessed);
      if (result.record) {
        result.record.county = this.config.county || result.record.county;
        allProperties.push(result.record);
      }
      if (result.error) {
        errors.push(result.error);
      }
      if (totalProcessed >= maxRows) break;
    }

    if (chunkHandler && allProperties.length > 0) {
      await chunkHandler(allProperties);
    }

    for await (const rows of rowStream) {
      if (totalProcessed >= maxRows) break;

      const chunkProperties: PropertyRecord[] = [];

      for (const values of rows) {
        totalProcessed++;
        const result = parseRow(headers, values, columnMap, totalProcessed);
        if (result.record) {
          result.record.county = this.config.county || result.record.county;
          chunkProperties.push(result.record);
        }
        if (result.error) {
          errors.push(result.error);
        }
        if (totalProcessed >= maxRows) break;
      }

      if (chunkHandler && chunkProperties.length > 0) {
        await chunkHandler(chunkProperties);
      }

      allProperties.push(...chunkProperties);
    }

    return {
      properties: allProperties,
      errors,
      totalProcessed,
      totalErrors: errors.length,
      duration: Date.now() - startTime,
    };
  }

  private async importXLSX(
    filePath: string,
    chunkSize: number,
    maxRows: number,
    explicitMap: Record<string, string> | undefined,
    chunkHandler: ChunkHandler | undefined,
    startTime: number,
  ): Promise<PluginResult> {
    try {
      const { properties, errors } = await processXLSX(filePath, buildColumnMap([], explicitMap), chunkSize);

      const limitedProperties = properties.slice(0, maxRows);
      const totalProcessed = properties.length;

      if (chunkHandler && limitedProperties.length > 0) {
        const chunks: PropertyRecord[][] = [];
        for (let i = 0; i < limitedProperties.length; i += chunkSize) {
          chunks.push(limitedProperties.slice(i, i + chunkSize));
        }
        for (const chunk of chunks) {
          await chunkHandler(chunk);
        }
      }

      for (const p of limitedProperties) {
        p.county = this.config.county || p.county;
      }

      return {
        properties: limitedProperties,
        errors,
        totalProcessed,
        totalErrors: errors.length,
        duration: Date.now() - startTime,
      };
    } catch (err) {
      return {
        properties: [],
        errors: [`XLSX parse error: ${err instanceof Error ? err.message : String(err)}`],
        totalProcessed: 0,
        totalErrors: 1,
        duration: Date.now() - startTime,
      };
    }
  }

  async testConnection(): Promise<boolean> {
    const filePath = this.config.config?.filePath as string | undefined;
    if (!filePath) return false;
    return fs.existsSync(filePath);
  }

  async estimateCount(_filters?: Record<string, unknown>): Promise<number> {
    const filePath = this.config.config?.filePath as string | undefined;
    if (!filePath || !fs.existsSync(filePath)) return 0;

    const ext = path.extname(filePath).toLowerCase();
    if (ext === '.xlsx' || ext === '.xls') {
      try {
        const ExcelJS = await importExcelJS();
        const workbook = new ExcelJS.Workbook();
        await workbook.xlsx.readFile(filePath);
        const ws = workbook.worksheets[0];
        return ws ? ws.rowCount - 1 : 0;
      } catch {
        return 0;
      }
    }

    let count = 0;
    const rl = readline.createInterface({
      input: fs.createReadStream(filePath, { encoding: 'utf-8' }),
      crlfDelay: Infinity,
    });

    for await (const _ of rl) {
      count++;
    }

    return Math.max(0, count - 1);
  }
}
