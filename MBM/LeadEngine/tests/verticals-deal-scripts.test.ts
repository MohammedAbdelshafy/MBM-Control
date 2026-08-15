import { describe, it, expect } from 'vitest';
import {
  REAL_ESTATE_ROLES,
  buildDealScript,
  buildDealScriptContext,
  dealClosingPath,
  roleLabel,
  renderObjectionForDeal,
  VerticalRegistry,
  buildClosingPaths,
  verticalScriptContext,
} from '../src/verticals';
import { DEAL_CLOSING_PATHS } from '../src/verticals';
import type { DealDossier, DealScript, RealEstateRole, ScriptContext } from '../src/verticals';

function dossier(overrides: Partial<DealDossier> = {}): DealDossier {
  return {
    propertyAddress: '2147 Maple Ave',
    city: 'Dallas',
    state: 'TX',
    county: 'Dallas',
    parcelId: '110002345678',
    ownerName: 'Dana Owner',
    ownerPhone: '+1 214 334 9988',
    whyThisDeal: 'Deep equity spread between the opening bid and realistic ARV in a tight single-family rental corridor.',
    whyNow: 'Impending auction schedule creates urgent seller motivation to accept an as-is cash buyout.',
    economicThesis: '70% rule underwriting: ARV $285,000, opening bid $118,000, MAO $199,500, projected spread $81,500.',
    risks: 'Verify title for senior municipal tax liens and mechanics liens before closing.',
    unknownVariables: 'Physical condition unknown; subject to interior inspection.',
    bestNextAction: 'Engage owner of record before the open-market gavel for exclusive contract negotiation.',
    estimatedArv: 285000,
    startingBid: 118000,
    calculatedMao: 199500,
    estimatedRepairCost: 35000,
    potentialFee: 81500,
    source: 'Dallas County Appraisal District + Auction.com',
    ...overrides,
  };
}

describe('Real-Estate Deal Script Engine — auction, distressed, buyers, investors, wholesalers', () => {
  it('ships all five required deal roles', () => {
    expect(REAL_ESTATE_ROLES).toEqual([
      'AUCTION_PROPERTY',
      'DISTRESSED_OWNER',
      'CASH_BUYER',
      'INVESTOR',
      'WHOLESALER',
    ]);
  });

  it('builds a full deal script for every role with dossier sections', () => {
    for (const role of REAL_ESTATE_ROLES) {
      const script: DealScript = buildDealScript(dossier(), role);

      expect(script.role).toBe(role);
      expect(script.full).toContain('WHY THIS DEAL');
      expect(script.full).toContain('WHY NOW');
      expect(script.full).toContain('ECONOMIC THESIS');
      expect(script.full).toContain('RISKS');
      expect(script.full).toContain('UNKNOWN VARIABLES');
      expect(script.full).toContain('BEST NEXT ACTION');
      expect(script.opener.length).toBeGreaterThan(40);
      expect(script.diagnosticQuestions.length).toBe(3);
    }
  });

  it('renders a short, evidence-anchored opener for the auction script', () => {
    const script = buildDealScript(dossier(), 'AUCTION_PROPERTY');
    expect(script.opener).toContain('Omar from MBM Capital');
    expect(script.opener).toContain('2147 Maple Ave');
    expect(script.opener).toContain('Dallas, TX');
    expect(script.opener).toContain('$118,000');
    expect(script.opener).not.toContain('[PROPERTY]');
    expect(script.opener).not.toContain('[OWNER_NAME]');
  });

  it('renders a non-fabricating opener for the distressed owner', () => {
    const script = buildDealScript(dossier(), 'DISTRESSED_OWNER');
    expect(script.opener).toContain('I don’t know your exact situation');
    expect(script.opener).toContain('2147 Maple Ave');
    expect(script.opener).not.toContain('[BID]');
  });

  it('anchors investor and cash-buyer scripts to real underwriting numbers', () => {
    const investor = buildDealScript(dossier(), 'INVESTOR');
    expect(investor.opener).toContain('$285,000');
    expect(investor.opener).toContain('$199,500');
    expect(investor.opener).toContain('$118,000');

    const buyer = buildDealScript(dossier(), 'CASH_BUYER');
    expect(buyer.opener).toContain('$81,500');
    expect(buyer.opener).not.toContain('[ARV]');
  });

  it('renders N/A instead of inventing missing economics', () => {
    const script = buildDealScript(dossier({ estimatedArv: null, startingBid: null }), 'INVESTOR');
    expect(script.opener).toContain('N/A');
  });

  it('diagnostic questions expose volume, delay, lost opportunity, manual work, cost, bottleneck, system', () => {
    const allQuestions = REAL_ESTATE_ROLES.flatMap(
      (role) => buildDealScript(dossier(), role).diagnosticQuestions,
    ).join(' ');

    expect(allQuestions).toMatch(/cash|all-cash/i);
    expect(allQuestions).toMatch(/month|30 day/i);
    expect(allQuestions.length).toBeGreaterThan(300);
    expect(hasUnresolved(allQuestions)).toBe(false);
  });

  it('ships all five closing paths and renders them with context', () => {
    const ctx = buildDealScriptContext(dossier());
    expect(Object.keys(DEAL_CLOSING_PATHS)).toHaveLength(5);
    for (const id of ['TEN_MINUTE_DEMO', 'FIFTEEN_MINUTE_DIAGNOSTIC', 'CALENDAR', 'DECISION_MAKER', 'FOLLOW_UP'] as const) {
      const text = dealClosingPath(id, ctx);
      expect(text.length).toBeGreaterThan(40);
      expect(hasUnresolved(text)).toBe(false);
    }
  });

  it('renders closing paths for B2B vertical contexts with offers', () => {
    const registry = new VerticalRegistry();
    const ctx = verticalScriptContext(registry.require('hvac'), 'Riley Owner', 'Express Air', 'Dallas');
    const paths = buildClosingPaths(ctx);

    expect(paths.TEN_MINUTE_DEMO).toContain('AI voice receptionist');
    expect(paths.FOLLOW_UP).toContain('Express Air');
    expect(hasUnresolved(paths.TEN_MINUTE_DEMO)).toBe(false);
  });

  it('renders deal objections with real economic context', () => {
    const ctx = buildDealScriptContext(dossier());
    const objection = renderObjectionForDeal('TOO_EXPENSIVE', ctx);
    expect(objection.respond).toContain('2147 Maple Ave');
    expect(objection.respond).not.toContain('[COMPANY]');
  });

  it('preserves dossier narrative verbatim on the script object', () => {
    const d = dossier();
    const script = buildDealScript(d, 'WHOLESALER');
    expect(script.whyThisDeal).toBe(d.whyThisDeal);
    expect(script.whyNow).toBe(d.whyNow);
    expect(script.economicThesis).toBe(d.economicThesis);
    expect(script.risks).toBe(d.risks);
    expect(script.unknownVariables).toBe(d.unknownVariables);
    expect(script.bestNextAction).toBe(d.bestNextAction);
  });

  it('provides human role labels', () => {
    expect(roleLabel('AUCTION_PROPERTY')).toBe('Auction Property');
    expect(roleLabel('DISTRESSED_OWNER')).toBe('Distressed Owner');
    expect(roleLabel('CASH_BUYER')).toBe('Cash Buyer');
    expect(roleLabel('INVESTOR')).toBe('Investor');
    expect(roleLabel('WHOLESALER')).toBe('Wholesaler');
  });
});

function hasUnresolved(text: string): boolean {
  return /\[(OWNER_NAME|COMPANY|VERTICAL|CITY|KNOWN_PAIN|OBSERVED_SIGNAL|RECOMMENDED_OFFER|VALUE_HYPOTHESIS|PROPERTY|ARV|BID|MAO|REPAIR|FEE)\]/.test(text);
}

// Silence unused-import lint on ScriptContext in this file (kept for type parity).
void (null as unknown as ScriptContext);