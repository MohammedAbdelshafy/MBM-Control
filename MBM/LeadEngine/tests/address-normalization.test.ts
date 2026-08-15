import { describe, it, expect } from 'vitest';
import {
  normalizeAddress,
  normalizeState,
  normalizeZip,
  normalizeParcelId,
  canonicalFragmentKey,
} from '../src/property-intel';

describe('Address Normalization — deterministic identity', () => {
  it('collapses equivalent street spellings to the same dedupe key', () => {
    const a = normalizeAddress({
      line1: '123 Main Street',
      city: 'Dallas',
      state: 'TX',
      zip: '75201',
      county: 'Dallas',
    });
    const b = normalizeAddress({
      line1: '123 MAIN ST.',
      city: ' dallas ',
      state: 'Texas',
      zip: '75201',
      county: 'Dallas County',
    });

    expect(a.dedupeKey).toBe(b.dedupeKey);
    expect(a.line1).toBe('123 MAIN ST');
    expect(a.city).toBe('DALLAS');
    expect(a.state).toBe('TX');
  });

  it('normalizes directionals and unit designators deterministically', () => {
    const a = normalizeAddress({
      line1: '1 North Oak Lane Apt 12',
      city: 'Austin',
      state: 'TX',
      zip: '78701',
    });
    const b = normalizeAddress({
      line1: '1 N Oak Ln #12',
      city: 'Austin',
      state: 'TX',
      zip: '78701',
    });

    expect(a.dedupeKey).toBe(b.dedupeKey);
    expect(a.line1).toContain('N OAK LN UNIT 12');
  });

  it('distinguishes different properties on the same street', () => {
    const a = normalizeAddress({ line1: '100 Oak St', city: 'Dallas', state: 'TX', zip: '75201' });
    const b = normalizeAddress({ line1: '200 Oak St', city: 'Dallas', state: 'TX', zip: '75201' });
    expect(a.dedupeKey).not.toBe(b.dedupeKey);
  });

  it('does not conflate different cities or states', () => {
    const a = normalizeAddress({ line1: '100 Oak St', city: 'Dallas', state: 'TX', zip: '75201' });
    const b = normalizeAddress({ line1: '100 Oak St', city: 'Fort Worth', state: 'TX', zip: '76102' });
    expect(a.dedupeKey).not.toBe(b.dedupeKey);
  });

  it('normalizes zip to ZIP+4 and handles leading zeros', () => {
    expect(normalizeZip('33139-1234')).toBe('33139-1234');
    expect(normalizeZip('07501')).toBe('07501');
    expect(normalizeZip('')).toBe('00000');
  });

  it('normalizes full state names and case variants', () => {
    expect(normalizeState('california')).toBe('CA');
    expect(normalizeState('CA')).toBe('CA');
    expect(normalizeState('New York')).toBe('NY');
  });

  it('produces a stable canonical fragment key for partial identities', () => {
    const k1 = canonicalFragmentKey(['+12145551234', '045-882-019-A']);
    const k2 = canonicalFragmentKey(['2145551234', '045-882-019-A']);
    expect(k1).toBe(k2);
  });

  it('normalizes parcel ids deterministically', () => {
    expect(normalizeParcelId('045-882-019-A')).toBe('045882019A');
    expect(normalizeParcelId('045 882 019 a')).toBe('045882019A');
  });
});