import { describe, it, expect } from 'vitest';
import {
  RejectionLedger,
  InMemoryRejectionLedgerRepository,
  rejectionKeysFor,
} from '../src/property-intel';

describe('Rejection Ledger — previously rejected garbage cannot return', () => {
  it('keys rejections deterministically by phone, property, and combined identity', () => {
    const keys = rejectionKeysFor({
      phone: '+12145551234',
      parcelId: 'TX-DAL-101',
      addressKey: 'abc123',
    });
    expect(keys).toHaveLength(3);
    const dimensions = keys.map((k) => k.dimension);
    expect(dimensions).toContain('PHONE');
    expect(dimensions).toContain('PROPERTY');
    expect(dimensions).toContain('COMBINED');

    const again = rejectionKeysFor({
      phone: '2145551234',
      parcelId: 'tx-dal-101',
      addressKey: 'abc123',
    });
    expect(again.map((k) => k.key).sort()).toEqual(keys.map((k) => k.key).sort());
  });

  it('returns the recorded rejection codes for a previously rejected identity', async () => {
    const repo = new InMemoryRejectionLedgerRepository();
    const ledger = new RejectionLedger(repo);

    await ledger.recordRejection({
      phone: '2145551234',
      parcelId: 'TX-DAL-101',
      addressKey: 'abc123',
      reasons: ['PHONE_QUALITY_FAILED', 'INVALID_OWNER'],
    });

    const codes = await ledger.rejectionCodesFor({
      phone: '+12145551234',
      parcelId: 'tx-dal-101',
      addressKey: 'abc123',
    });

    expect(codes).toContain('PHONE_QUALITY_FAILED');
    expect(codes).toContain('INVALID_OWNER');
    expect(await ledger.isBlocked({ phone: '2145551234', parcelId: 'TX-DAL-101' })).toBe(true);
  });

  it('returns empty codes for a clean identity', async () => {
    const ledger = new RejectionLedger(new InMemoryRejectionLedgerRepository());
    const codes = await ledger.rejectionCodesFor({ phone: '2125550175' });
    expect(codes).toHaveLength(0);
    expect(await ledger.isBlocked({ phone: '2125550175' })).toBe(false);
  });

  it('blocks the phone across different properties (shared suppression)', async () => {
    const repo = new InMemoryRejectionLedgerRepository();
    const ledger = new RejectionLedger(repo);

    await ledger.recordRejection({ phone: '2145551234', parcelId: 'TX-DAL-101', reasons: ['BAD_NUMBER_HISTORY'] });

    // Same phone, different property → still blocked.
    const codes = await ledger.rejectionCodesFor({ phone: '2145551234', parcelId: 'NY-MAN-222' });
    expect(codes).toContain('BAD_NUMBER_HISTORY');
  });

  it('persists rejections through the repository so a fresh ledger instance still blocks', async () => {
    const repo = new InMemoryRejectionLedgerRepository();
    const first = new RejectionLedger(repo);
    await first.recordRejection({
      phone: '3057684905',
      addressKey: 'def456',
      reasons: ['INVALID_CONTACT_SOURCE'],
    });

    // New process instance, same repository.
    const second = new RejectionLedger(repo);
    const codes = await second.rejectionCodesFor({ phone: '+13057684905', addressKey: 'def456' });
    expect(codes).toContain('INVALID_CONTACT_SOURCE');
  });
});