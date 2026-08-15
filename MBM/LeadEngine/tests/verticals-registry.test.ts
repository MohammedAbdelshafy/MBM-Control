import { describe, it, expect } from 'vitest';
import {
  VerticalRegistry,
  validateVertical,
  DEFAULT_VERTICAL_CATALOG,
  CATEGORY_LABELS,
  DEFAULT_SCORE_WEIGHTS,
} from '../src/verticals';
import type { VerticalDefinition } from '../src/verticals';

const ALL_CATEGORIES = ['HOME_SERVICES', 'HEALTH_WELLNESS', 'PROFESSIONAL_SERVICES', 'LOCAL_SERVICES', 'B2B_INDUSTRIAL'];

describe('Vertical Registry — configurable marketplace', () => {
  it('ships the five initial categories with the full catalog', () => {
    const registry = new VerticalRegistry();
    const categories = registry.categories();
    expect(categories.sort()).toEqual([...ALL_CATEGORIES].sort());
    for (const cat of ALL_CATEGORIES) {
      expect(registry.byCategory(cat as never).length).toBeGreaterThan(0);
    }
    expect(CATEGORY_LABELS.HOME_SERVICES).toBe('Home Services');
  });

  it('covers every requested initial vertical', () => {
    const registry = new VerticalRegistry();
    const ids = registry.ids();
    const expected = [
      'hvac', 'plumbing', 'electrical', 'roofing', 'solar', 'landscaping',
      'pest_control', 'cleaning', 'restoration', 'garage_door', 'pool_services',
      'painting', 'flooring', 'remodeling', 'general_contractors',
      'yoga', 'pilates', 'gyms', 'personal_training', 'med_spas',
      'chiropractors', 'physical_therapy', 'dental', 'aesthetic_clinics',
      'massage', 'wellness', 'nutrition',
      'law_firms', 'accounting', 'tax', 'insurance', 'mortgage',
      'real_estate_brokerages', 'property_management', 'architecture',
      'engineering', 'construction',
      'restaurants', 'catering', 'auto_repair', 'auto_dealers', 'detailing',
      'salons', 'barbers', 'beauty_studios', 'pet_grooming', 'veterinary',
      'moving', 'storage',
      'manufacturing', 'distributors', 'logistics', 'staffing',
      'commercial_contractors', 'industrial_suppliers', 'security',
      'equipment_rental', 'wholesale',
    ];
    for (const id of expected) {
      expect(ids).toContain(id);
    }
  });

  it('registers a brand-new vertical from config with no engine changes', () => {
    const registry = new VerticalRegistry();
    const newVertical: VerticalDefinition = {
      id: 'marinas',
      name: 'Marina & Boat Storage',
      category: 'LOCAL_SERVICES',
      icp: 'Marinas with slip rentals and boat storage inventory.',
      decisionMakerProfile: 'Owner or Dockmaster.',
      painSignals: [{ id: 'missed_calls', label: 'After-hours slip inquiry calls missed', weight: 0.5 }],
      buyingSignals: [{ id: 'foot_traffic', label: 'High slip demand / waitlists', weight: 1 }],
      aiOpportunitySignals: [{ id: 'ai_reception_local', label: 'AI receptionist for slip inquiries', weight: 1 }],
      websiteOpportunitySignals: [{ id: 'outdated_site_local', label: 'Outdated website', weight: 1 }],
      automationOpportunitySignals: [{ id: 'manual_orders', label: 'Manual reservation handling', weight: 1 }],
      appSoftwareOpportunitySignals: [{ id: 'ordering_app', label: 'Slip reservation app', weight: 1 }],
      recommendedOffers: ['AI voice receptionist', 'reservation automation'],
      estimatedDealSize: { min: 2997, max: 8000, currency: 'USD', unit: 'monthly retainer' },
      outreachAngle: 'Slip inquiries are answered by voicemail today — an AI agent books reservations 24/7.',
    };

    expect(() => registry.register(newVertical)).not.toThrow();
    expect(registry.get('marinas')?.name).toBe('Marina & Boat Storage');
    expect(registry.byCategory('LOCAL_SERVICES').some((v) => v.id === 'marinas')).toBe(true);
  });

  it('overrides and removes verticals', () => {
    const registry = new VerticalRegistry();
    const before = registry.get('hvac')!.name;
    registry.register({ ...registry.require('hvac'), name: 'HVAC Masters' });
    expect(registry.get('hvac')!.name).toBe('HVAC Masters');
    registry.remove('hvac');
    expect(registry.get('hvac')).toBeUndefined();
    expect(before).toBeTruthy();
  });

  it('rejects malformed vertical definitions', () => {
    const bad = { ...DEFAULT_VERTICAL_CATALOG[0], id: 'x', painSignals: [] };
    const errors = validateVertical(bad as VerticalDefinition);
    expect(errors.some((e) => e.includes('painSignals'))).toBe(true);

    const missingSize = { ...DEFAULT_VERTICAL_CATALOG[0], id: 'y', estimatedDealSize: { min: 5000, max: 1000, currency: 'USD', unit: 'x' } };
    expect(validateVertical(missingSize as VerticalDefinition).some((e) => e.includes('cannot exceed'))).toBe(true);

    const registry = new VerticalRegistry();
    expect(() => registry.register(bad as VerticalDefinition)).toThrow(/Invalid vertical/);
  });

  it('normalizes weights and exposes defaults', () => {
    const registry = new VerticalRegistry();
    const weights = registry.weightsFor('hvac');
    const total = Object.values(weights).reduce((a, b) => a + b, 0);
    expect(Math.abs(total - 1)).toBeLessThan(0.001);
    expect(DEFAULT_SCORE_WEIGHTS.pain).toBeGreaterThan(0);
  });

  it('requires an existing vertical and throws otherwise', () => {
    const registry = new VerticalRegistry();
    expect(() => registry.require('does_not_exist')).toThrow(/Unknown vertical/);
  });
});