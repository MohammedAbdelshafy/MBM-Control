export type SourceType = 'county' | 'csv' | 'api' | 'demo';

export type OwnershipType =
  | 'individual'
  | 'corporate'
  | 'llc'
  | 'partnership'
  | 'trust'
  | 'government'
  | 'nonprofit'
  | 'other';

export interface PluginConfig {
  id: string;
  name: string;
  county: string;
  state: string;
  type: SourceType;
  enabled: boolean;
  config: Record<string, unknown>;
}

export interface PluginManifest {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  supportedCounties: string[];
  type: SourceType;
}

export interface PluginResult {
  properties: PropertyRecord[];
  errors: string[];
  totalProcessed: number;
  totalErrors: number;
  duration: number;
}

export interface PropertyRecord {
  parcelId: string;
  addressLine1: string;
  city: string;
  state: string;
  zip: string;
  county: string;
  ownerName?: string;
  ownerType?: OwnershipType;
  mailingAddress?: string;
  yearBuilt?: number;
  propertyType?: string;
  lotSize?: number;
  buildingSize?: number;
  estimatedValue?: number;
  lastSaleDate?: Date;
  lastSalePrice?: number;
  assessedValue?: number;
  taxAmount?: number;
  taxYear?: number;
  taxDelinquent?: boolean;
  violations?: ViolationRecord[];
}

export interface ViolationRecord {
  code: string;
  description: string;
  severity: string;
  filedDate: string;
  status: string;
}

export abstract class BasePlugin {
  abstract manifest: PluginManifest;

  constructor(protected config: PluginConfig) {}

  validate(): string[] {
    const errors: string[] = [];
    if (!this.config.id) errors.push('Plugin id is required');
    if (!this.config.name) errors.push('Plugin name is required');
    return errors;
  }

  abstract import(): Promise<PluginResult>;

  abstract testConnection(): Promise<boolean>;

  abstract estimateCount(filters?: Record<string, unknown>): Promise<number>;
}

export class PluginRegistry {
  private plugins: Map<string, BasePlugin> = new Map();

  register(plugin: BasePlugin): void {
    const id = plugin.manifest.id;
    if (this.plugins.has(id)) {
      throw new Error(`Plugin ${id} already registered`);
    }
    this.plugins.set(id, plugin);
  }

  get(id: string): BasePlugin | undefined {
    return this.plugins.get(id);
  }

  list(): PluginManifest[] {
    return Array.from(this.plugins.values()).map((p) => p.manifest);
  }

  findByCounty(county: string, state?: string): BasePlugin[] {
    return Array.from(this.plugins.values()).filter((p) =>
      p.manifest.supportedCounties.some(
        (c) => c.toLowerCase() === county.toLowerCase(),
      ),
    );
  }

  remove(id: string): boolean {
    return this.plugins.delete(id);
  }

  clear(): void {
    this.plugins.clear();
  }
}
