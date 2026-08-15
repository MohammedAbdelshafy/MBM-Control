/**
 * AI Business Owner Machine — MBM Lead Quality v3 (P2)
 * Parallel B2B Revenue Lane targeting owners/founders/CEOs of companies
 * with high operational pain, outdated digital presence, and high ability-to-pay.
 */

import crypto from 'node:crypto';

export interface BusinessProspectInput {
  companyName: string;
  websiteUrl?: string;
  industry: string; // e.g. "Construction / ConTech", "Healthcare / Clinics", "Real Estate Brokerage", "Logistics"
  estimatedEmployeeCount?: number;
  annualRevenueEstimate?: number;
  decisionMaker: {
    name: string;
    title: string; // "Founder", "CEO", "Owner", "Managing Partner", "Operations Director"
    linkedinUrl?: string;
    verifiedBusinessEmail?: string;
    businessPhone?: string;
    verificationSource: 'LINKEDIN_PROFESSIONAL' | 'COMPANY_REGISTRATION' | 'GOOGLE_BUSINESS' | 'CMS_NPI';
  };
  digitalAudit: {
    hasOutdatedWebsite: boolean;
    lacksMobileOptimization: boolean;
    noAutomatedBookingOrLeadCapture: boolean;
    slowResponseTimeHours?: number;
    manualWorkflowSignals: string[];
  };
}

export interface BusinessOpportunityOutput {
  id: string;
  companyName: string;
  decisionMakerName: string;
  decisionMakerTitle: string;
  verifiedIdentitySource: string;
  businessProblem: string;
  proposedSolution: string;
  valueHypothesis: string;
  serviceFit: 'AI_AGENTS_AND_VOICE' | 'CONTECH_WORKFLOW_AUTOMATION' | 'CUSTOM_LEAD_ENGINE' | 'MODERN_APP_AND_WEB';
  abilityToPayScore: number; // 0 - 100
  automationOpportunityScore: number; // 0 - 100
  contactabilityScore: number; // 0 - 100
  salesPriorityScore: number; // 0 - 100
  recommendedRetainerSku: string;
  netellerCheckoutUrl: string;
  crmPayload: {
    dealStage: 'PROSPECT_QUALIFIED';
    customSubject: string;
    valueProposition: string;
    primaryContactPhone: string;
    primaryContactEmail: string;
  };
}

export class BusinessOwnerMachine {
  public evaluateBusinessProspect(input: BusinessProspectInput): BusinessOpportunityOutput {
    const id = crypto.randomUUID();

    // 1. Ability-to-Pay Scoring (0 - 100)
    let abilityToPay = 50;
    const employees = input.estimatedEmployeeCount || 10;
    if (employees >= 50) abilityToPay += 35;
    else if (employees >= 20) abilityToPay += 25;
    else if (employees >= 5) abilityToPay += 15;

    const rev = input.annualRevenueEstimate || 1500000;
    if (rev >= 5000000) abilityToPay += 15;
    else if (rev >= 2000000) abilityToPay += 10;
    const abilityToPayScore = Math.min(100, abilityToPay);

    // 2. Automation Opportunity & Operational Pain (0 - 100)
    let painScore = 30;
    if (input.digitalAudit.hasOutdatedWebsite) painScore += 20;
    if (input.digitalAudit.lacksMobileOptimization) painScore += 15;
    if (input.digitalAudit.noAutomatedBookingOrLeadCapture) painScore += 25;
    if (input.digitalAudit.manualWorkflowSignals.length >= 2) painScore += 15;
    const automationOpportunityScore = Math.min(100, painScore);

    // 3. Contactability Scoring (0 - 100)
    let contactScore = 40;
    if (input.decisionMaker.businessPhone) contactScore += 30;
    if (input.decisionMaker.verifiedBusinessEmail) contactScore += 20;
    if (input.decisionMaker.linkedinUrl) contactScore += 10;
    const contactabilityScore = Math.min(100, contactScore);

    // 4. Determine Best-Fit Solution
    let serviceFit: BusinessOpportunityOutput['serviceFit'] = 'AI_AGENTS_AND_VOICE';
    let solution = 'Autonomous AI Voice & Booking Dispatcher with Instant CRM Bridge';
    let problem = 'Slow lead follow-up and uncaptured after-hours customer calls.';
    let valueHypo = 'Captures 35% more qualified bookings and eliminates manual telephone intake latency.';
    let retainerSku = 'AI-AGENCY-RETAINER-4997';

    if (input.industry.toLowerCase().includes('construction') || input.industry.toLowerCase().includes('contech')) {
      serviceFit = 'CONTECH_WORKFLOW_AUTOMATION';
      solution = 'Automated BOQ Estimator & Drawing-to-Takeoff AI Agent';
      problem = 'Manual bid estimating and slow takeoff turnarounds bottlenecking contractor volume.';
      valueHypo = 'Accelerates bid generation by 80% with zero calculation error margins.';
      retainerSku = 'CONTECH-ENTERPRISE-7500';
    } else if (input.digitalAudit.hasOutdatedWebsite) {
      serviceFit = 'MODERN_APP_AND_WEB';
      solution = 'Next-Gen High-Conversion Terminal & Web Application';
      problem = 'Outdated web presence driving high bounce rates and low inbound trust.';
      valueHypo = 'Increases visitor-to-lead conversion rates by 2.4x with integrated client portal.';
      retainerSku = 'DIGITAL-TRANSFORMATION-5997';
    }

    // 5. Composite Sales Priority Score
    const salesPriorityScore = Math.round(
      abilityToPayScore * 0.35 +
      automationOpportunityScore * 0.35 +
      contactabilityScore * 0.30
    );

    const netellerUrl = `https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount=4997.00&currency=USD&item=${encodeURIComponent(retainerSku)}`;

    return {
      id,
      companyName: input.companyName,
      decisionMakerName: input.decisionMaker.name,
      decisionMakerTitle: input.decisionMaker.title,
      verifiedIdentitySource: input.decisionMaker.verificationSource,
      businessProblem: problem,
      proposedSolution: solution,
      valueHypothesis: valueHypo,
      serviceFit,
      abilityToPayScore,
      automationOpportunityScore,
      contactabilityScore,
      salesPriorityScore,
      recommendedRetainerSku: retainerSku,
      netellerCheckoutUrl: netellerUrl,
      crmPayload: {
        dealStage: 'PROSPECT_QUALIFIED',
        customSubject: `AI Automation Proposal for ${input.companyName} (${input.decisionMaker.name})`,
        valueProposition: valueHypo,
        primaryContactPhone: input.decisionMaker.businessPhone || '',
        primaryContactEmail: input.decisionMaker.verifiedBusinessEmail || '',
      },
    };
  }
}
