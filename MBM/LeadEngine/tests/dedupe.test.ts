import { describe, it, expect } from 'vitest';
import {
  PropertyDedupeRegistry,
  computeDedupeKeys,
  dedupeKeyFor,
  normalizeParcelId,
  type DedupeRepository,
} from '../src/property-intel';

class FakeDedupeRepo implements DedupeRepository {
  keys = new Set<string>();
  map = new Map<string, string>();

  async exists(key: string): Promise<boolean> {
    return this.keys.has(key);
  }

  async register(key: string, propertyId?: string): Promise<void> {
    this.keys.add(key);
    this.map.set(key, propertyId ?? key);
  }

  async findByKey(key: string): Promise<string | null> {
    return this.map.get(key) ?? null;
  }
}

describe('Deterministic Deduplication', () => {
  it('computes identical keys for semantically identical properties', () => {
    const a = computeDedupeKeys({
      parcelId: '045-882-019-A',
      addressLine1: '1420 Ocean Drive',
      city: 'Miami Beach',
      state: 'FL',
      zip: '33139',
      county: 'Miami-Dade',
    });
    const b = computeDedupeKeys({
      parcelId: '045882019A',
      addressLine1: '1420 Ocean Dr',
      city: 'miami beach',
      state: 'FL',
      zip: '33139',
      county: 'Miami-Dade',
    });
    expect(a.parcelKey).toBe(b.parcelKey);
    expect(a.addressKey).toBe(b.addressKey);
  });

  it('dedupeKeyFor prefers parcel when available', () => {
    const withParcel = dedupeKeyFor({
      parcelId: '045-882-019-A',
      addressLine1: '1420 Ocean Dr',
      city: 'Miami Beach',
      state: 'FL',
      zip: '33139',
      county: 'Miami-Dade',
    });
    const withoutParcel = dedupeKeyFor({
      addressLine1: '1420 Ocean Dr',
      city: 'Miami Beach',
      state: 'FL',
      zip: '33139',
      county: 'Miami-Dade',
    });
    expect(withParcel).not.toBe(withoutParcel);
  });

  it('detects the second occurrence of the same property', async () => {
    const repo = new FakeDedupeRepo();
    const registry = new PropertyDedupeRegistry(repo);

    const first = await registry.checkAndRegister({
      parcelId: '045-882-019-A',
      addressLine1: '1420 Ocean Drive',
      city: 'Miami Beach',
      state: 'FL',
      zip: '33139',
      county: 'Miami-Dade',
    });
    expect(first.isDuplicate).toBe(false);

    const second = await registry.checkAndRegister({
      parcelId: '045882019A',
      addressLine1: '1420 Ocean Dr',
      city: 'Miami Beach',
      state: 'FL',
      zip: '33139',
      county: 'Miami-Dade',
    });
    expect(second.isDuplicate).toBe(true);
    expect(second.matchedKey).toBe(first.matchedKey);
  });

  it('dedupes by canonical address when no parcel id exists', async () => {
    const registry = new PropertyDedupeRegistry(null);
    const first = await registry.checkAndRegister({
      addressLine1: '4820 Elm Street',
      city: 'Dallas',
      state: 'TX',
      zip: '75201',
    });
    const second = await registry.checkAndRegister({
      addressLine1: '4820 Elm St.',
      city: 'Dallas',
      state: 'TX',
      zip: '75201',
    });
    expect(first.isDuplicate).toBe(false);
    expect(second.isDuplicate).toBe(true);
  });

  it('normalizes parcel ids consistently', () => {
    expect(normalizeParcelId('ABC-123')).toBe('ABC123');
    expect(normalizeParcelId('abc 123')).toBe('ABC123');
    expect(normalizeParcelId('045.882.019.a')).toBe('045882019A');
  });
});