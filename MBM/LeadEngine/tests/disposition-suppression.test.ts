import { describe, it, expect } from 'vitest';
import {
  DispositionRegistry,
  InMemoryDispositionRepository,
  NEGATIVE_DISPOSITION_CODES,
  normalizeDispositionPhone,
  isNegativeDisposition,
} from '../src/property-intel';

describe('Negative Disposition Suppression', () => {
  it('exposes all seven canonical negative disposition codes', () => {
    expect(NEGATIVE_DISPOSITION_CODES.sort()).toEqual(
      ['BAD_NUMBER', 'WRONG_PERSON', 'NON_OWNER', 'DUPLICATE', 'DNC', 'SOLD', 'NOT_INTERESTED'].sort(),
    );
  });

  it('treats every negative disposition as permanent by default', () => {
    for (const code of NEGATIVE_DISPOSITION_CODES) {
      expect(isNegativeDisposition(code)).toBe(true);
    }
  });

  it('returns permanent suppression codes for a phone', async () => {
    const repo = new InMemoryDispositionRepository();
    const registry = new DispositionRegistry(repo);

    await registry.record({ phone: '+13057684905', type: 'DNC', source: 'dialer' });
    await registry.record({ phone: '3057684905', type: 'SOLD', source: 'dialer' });

    const codes = await registry.suppressionCodesFor('3057684905');
    expect(codes).toContain('DNC');
    expect(codes).toContain('SOLD');
  });

  it('distinguishes non-permanent (expiring) dispositions', async () => {
    const registry = new DispositionRegistry(new InMemoryDispositionRepository());

    await registry.record({ phone: '3057684905', type: 'OTHER', permanent: false });
    const codes = await registry.suppressionCodesFor('3057684905');
    expect(codes).not.toContain('OTHER');
  });

  it('maps permanent dispositions to gate seeds (bad numbers + suppression)', async () => {
    const repo = new InMemoryDispositionRepository();
    const registry = new DispositionRegistry(repo);

    await registry.record({ phone: '+12145551234', type: 'BAD_NUMBER' });
    await registry.record({ phone: '2145551234', type: 'NOT_INTERESTED' });

    const records = await repo.findActiveByPhone('2145551234');
    const seeds = registry.toGateSeeds(records);

    expect(seeds.badNumbers).toContain('2145551234');
    expect(seeds.suppressionList).toContain('2145551234');
  });

  it('normalizes phone variants to a single identity', () => {
    expect(normalizeDispositionPhone('+13057684905')).toBe('3057684905');
    expect(normalizeDispositionPhone('(305) 768-4905')).toBe('3057684905');
  });

  it('blocks a phone that was recorded by a different process', async () => {
    const repo = new InMemoryDispositionRepository();
    await repo.record({ phone: '2125550175', type: 'BAD_NUMBER', source: 'twilio_bridge' });

    const registry = new DispositionRegistry(repo);
    const codes = await registry.suppressionCodesFor('2125550175');
    expect(codes).toContain('BAD_NUMBER');
  });
});