export type ExportFormat = 'csv' | 'excel' | 'pdf' | 'json' | 'crm_import';

export interface ExportOptions {
  format: ExportFormat;
  filters?: Record<string, unknown>;
  columns?: string[];
  includeScore?: boolean;
  includeOwnerDetails?: boolean;
  includePropertyDetails?: boolean;
  clientId?: string;
  brandLogo?: string;
  headerText?: string;
}

export interface ExportResult {
  filePath: string;
  fileName: string;
  fileSize: number;
  mimeType: string;
  totalRecords: number;
  generatedAt: Date;
}

export interface LeadExportRow {
  // Property
  parcelId: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  county: string;
  propertyType: string;
  yearBuilt?: number;
  lotSize?: number;
  buildingSize?: number;
  estimatedValue?: number;

  // Owner
  ownerName: string;
  ownerType: string;
  mailingAddress: string;
  isAbsentee: boolean;

  // Lead
  niche: string;
  score: number;
  grade: string;
  confidence: number;
  signals: string;
  summary: string;

  // Metadata
  source: string;
  generatedAt: string;
  exportTimestamp: string;
}
