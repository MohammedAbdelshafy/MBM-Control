import { describe, it, expect } from 'vitest';
import {
  ScoringConfigResolver,
  InMemoryScoringConfigRepository,
  sanitizeWeights,
  DEFAULT_WEIGHTS,
} from '../src/property-intel';

describe('Configurable Lead Scoring', () => {
  it('resolves DEFAULT_WEIGHTS when no config exists', async () => {
    const resolver = new ScoringConfigResolver(new InMemoryScoringConfigRepository());
    const weights = await resolver.resolveWeights({ county: 'Dallas', state: 'TX' });
    expect(weights).toEqual(DEFAULT_WEIGHTS);
  });

  it('applies a county-scoped config over the defaults', async () => {
    const repo = new InMemoryScoringConfigRepository();
    await repo.save({
      name: 'dallas-county',
      scope: 'county',
      scopeValue: 'DALLAS',
      weights: { taxDelinquency: 0.5, absenteeSignal: 0.3 },
      enabled: true,
    });

    const resolver = new ScoringConfigResolver(repo);
    const weights = await resolver.resolveWeights({ county: 'Dallas', state: 'TX' });
    expect(weights.taxDelinquency).toBe(0.5);
    expect(weights.absenteeSignal).toBe(0.3);
    // Unspecified keys retain defaults.
    expect(weights.ownershipConfidence).toBe(DEFAULT_WEIGHTS.ownershipConfidence);
  });

  it('more specific scopes override broader ones (niche > source > county)', async () => {
    const repo = new InMemoryScoringConfigRepository();
    await repo.save({ name: 'tx-state', scope: 'state', scopeValue: 'TX', weights: { equityProxy: 0.2 }, enabled: true });
    await repo.save({ name: 'dallas-county', scope: 'county', scopeValue: 'DALLAS', weights: { equityProxy: 0.4 }, enabled: true });
    await repo.save({ name: 'npi-source', scope: 'source', scopeValue: 'CMS_NPI', weights: { equityProxy: 0.6 }, enabled: true });
    await repo.save({ name: 'vacant-niche', scope: 'niche', scopeValue: 'VACANT', weights: { equityProxy: 0.8 }, enabled: true });

    const resolver = new ScoringConfigResolver(repo);
    const weights = await resolver.resolveWeights({
      county: 'Dallas',
      state: 'TX',
      source: 'CMS_NPI',
      niche: 'VACANT',
    });

    expect(weights.equityProxy).toBe(0.8);
  });

  it('ignores disabled configs', async () => {
    const repo = new InMemoryScoringConfigRepository();
    await repo.save({ name: 'disabled', scope: 'county', scopeValue: 'DALLAS', weights: { vacancyIndicators: 1 }, enabled: false });

    const resolver = new ScoringConfigResolver(repo);
    const weights = await resolver.resolveWeights({ county: 'Dallas' });
    expect(weights.vacancyIndicators).toBe(DEFAULT_WEIGHTS.vacancyIndicators);
  });

  it('sanitizes out-of-range weights', () => {
    const sanitized = sanitizeWeights({ ownershipConfidence: 5, taxDelinquency: -1, vacancyIndicators: 'nope' });
    expect(sanitized.ownershipConfidence).toBe(1);
    expect(sanitized.taxDelinquency).toBe(0);
    expect(sanitized.vacancyIndicators).toBeUndefined();
  });

  it('works without a repository (defaults only)', async () => {
    const resolver = new ScoringConfigResolver(null);
    const weights = await resolver.resolveWeights({ county: 'Dallas' });
    expect(weights).toEqual(DEFAULT_WEIGHTS);
  });
});