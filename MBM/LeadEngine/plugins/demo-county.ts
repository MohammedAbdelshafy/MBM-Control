import {
  BasePlugin,
  PluginConfig,
  PluginManifest,
  PluginResult,
  PropertyRecord,
  ViolationRecord,
} from './framework';

const DEMO_STREETS = [
  '123 Main St', '456 Oak Ave', '789 Elm Dr', '321 Pine Ln', '654 Maple Ct',
  '987 Cedar Blvd', '111 Birch Way', '222 Walnut Rd', '333 Cherry Cir', '444 Spruce Ter',
  '555 Ash Pl', '666 Hickory Ln', '777 Sycamore Ave', '888 Poplar Dr', '999 Willow Ct',
  '100 Magnolia Way', '200 Dogwood Blvd', '300 Juniper Rd', '400 Linden Cir', '500 Alder Ter',
  '600 Beech Ln', '700 Cypress Ave', '800 Hemlock Dr', '900 Laurel Ct', '150 Myrtle Way',
];

const DEMO_CITIES = ['Springfield', 'Riverside', 'Fairview', 'Maplewood', 'Brookside'];
const DEMO_OWNERS = [
  'James & Mary Thompson', 'Robert Hernandez', 'Patricia Mitchell',
  'John & Susan Davis', 'Michael Anderson', 'Jennifer Williams',
  'David & Linda Garcia', 'Richard Martinez', 'Barbara Robinson',
  'Thomas & Karen Clark', 'Charles Lewis', 'Nancy Walker', 'Joseph Hall',
  'Daniel & Betty Allen', 'Donald Young', 'Margaret King', 'Kenneth Wright',
  'Steven & Lisa Hill', 'Edward Scott', 'Carol Adams', 'Brian Baker',
  'George & Donna Nelson', 'Ronald Carter', 'Dorothy Mitchell', 'Frank Perez',
];

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

function generateDemoProperty(index: number): PropertyRecord {
  const rand = seededRandom(index + 1);
  const rand2 = seededRandom(index + 999);

  const priceBase = 150000 + rand() * 600000;
  const yearBuilt = Math.floor(1950 + rand2() * 73);
  const lotSqft = Math.floor(5000 + rand() * 45000);
  const buildingSqft = Math.floor(800 + rand2() * 3200);

  const violationCount = Math.floor(rand() * 3);
  const violations: ViolationRecord[] = [];
  const violationCodes = ['V-1001', 'V-2003', 'V-3012', 'V-4015', 'V-5020'];
  const violationDesc = [
    'Overgrown vegetation',
    'Broken window',
    'Unsecured structure',
    'Accumulated debris',
    'Fence in disrepair',
  ];
  const severities = ['low', 'medium', 'high'];

  for (let i = 0; i < violationCount; i++) {
    const vi = Math.floor(rand() * violationCodes.length);
    violations.push({
      code: violationCodes[vi],
      description: violationDesc[vi],
      severity: severities[Math.floor(rand() * severities.length)],
      filedDate: `2024-${String(Math.floor(1 + rand() * 12)).padStart(2, '0')}-${String(Math.floor(1 + rand() * 28)).padStart(2, '0')}`,
      status: rand() > 0.5 ? 'open' : 'closed',
    });
  }

  const ownerName = DEMO_OWNERS[index % DEMO_OWNERS.length];
  const city = DEMO_CITIES[index % DEMO_CITIES.length];

  return {
    parcelId: `DEMO-${String(index + 1).padStart(6, '0')}`,
    addressLine1: DEMO_STREETS[index % DEMO_STREETS.length],
    city,
    state: 'TX',
    zip: ['75001', '75201', '76101', '77001', '78201'][index % 5],
    county: 'DEMO',
    ownerName,
    ownerType: rand() > 0.65 ? 'corporate' : 'individual',
    mailingAddress: `${DEMO_STREETS[(index + 3) % DEMO_STREETS.length]}, ${city}, TX ${['75001', '75201', '76101', '77001', '78201'][(index + 2) % 5]}`,
    yearBuilt,
    propertyType: ['Single Family', 'Multi Family', 'Commercial', 'Vacant Land', 'Duplex'][index % 5],
    lotSize: lotSqft,
    buildingSize: buildingSqft,
    estimatedValue: Math.round(priceBase),
    lastSaleDate: new Date(2020 + Math.floor(rand2() * 5), Math.floor(rand() * 12), Math.floor(1 + rand() * 28)),
    lastSalePrice: Math.round(priceBase * 0.65),
    assessedValue: Math.round(priceBase * 0.85),
    taxAmount: Math.round(priceBase * 0.02),
    taxYear: 2024,
    taxDelinquent: rand() < 0.15,
    violations: violations.length > 0 ? violations : undefined,
  };
}

export class DemoCountyPlugin extends BasePlugin {
  manifest: PluginManifest = {
    id: 'demo-county',
    name: 'Demo County',
    version: '1.0.0',
    description: 'Demo plugin that generates sample property records for testing',
    author: 'MBM Lead Engine',
    supportedCounties: ['DEMO'],
    type: 'demo',
  };

  private configDefaults = {
    recordCount: 25,
  };

  constructor(config: PluginConfig) {
    super(config);
  }

  async import(): Promise<PluginResult> {
    const startTime = Date.now();
    const recordCount = (this.config.config?.recordCount as number) ?? this.configDefaults.recordCount;
    const count = Math.min(Math.max(1, recordCount), 1000);

    const properties: PropertyRecord[] = [];
    const errors: string[] = [];

    for (let i = 0; i < count; i++) {
      try {
        properties.push(generateDemoProperty(i));
      } catch (err) {
        errors.push(`Row ${i + 1}: ${err instanceof Error ? err.message : String(err)}`);
      }
    }

    return {
      properties,
      errors,
      totalProcessed: count,
      totalErrors: errors.length,
      duration: Date.now() - startTime,
    };
  }

  async testConnection(): Promise<boolean> {
    return true;
  }

  async estimateCount(_filters?: Record<string, unknown>): Promise<number> {
    return this.configDefaults.recordCount;
  }
}
