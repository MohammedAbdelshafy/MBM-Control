import { describe, it, expect } from 'vitest';
import { BusinessOwnerMachine, type BusinessProspectInput } from '../src/pipeline/business-owner-machine';

describe('AI Business Owner Machine (P2 B2B Revenue Lane)', () => {
  it('evaluates a ConTech business prospect and outputs high-ticket solution & CRM payload', () => {
    const machine = new BusinessOwnerMachine();

    const prospect: BusinessProspectInput = {
      companyName: 'BuildCraft Commercial Contracting',
      websiteUrl: 'https://buildcraftcontracting.com',
      industry: 'Construction / ConTech',
      estimatedEmployeeCount: 35,
      annualRevenueEstimate: 4500000,
      decisionMaker: {
        name: 'David Sterling',
        title: 'Founder & CEO',
        linkedinUrl: 'https://linkedin.com/in/david-sterling-contech',
        verifiedBusinessEmail: 'dsterling@buildcraftcontracting.com',
        businessPhone: '2147894512',
        verificationSource: 'LINKEDIN_PROFESSIONAL',
      },
      digitalAudit: {
        hasOutdatedWebsite: true,
        lacksMobileOptimization: true,
        noAutomatedBookingOrLeadCapture: true,
        manualWorkflowSignals: ['Manual PDF bid takeoffs', 'Paper change orders', 'No automated follow-up'],
      },
    };

    const output = machine.evaluateBusinessProspect(prospect);

    expect(output.companyName).toBe('BuildCraft Commercial Contracting');
    expect(output.decisionMakerName).toBe('David Sterling');
    expect(output.serviceFit).toBe('CONTECH_WORKFLOW_AUTOMATION');
    expect(output.abilityToPayScore).toBeGreaterThanOrEqual(80);
    expect(output.automationOpportunityScore).toBeGreaterThanOrEqual(80);
    expect(output.salesPriorityScore).toBeGreaterThanOrEqual(80);
    expect(output.recommendedRetainerSku).toBe('CONTECH-ENTERPRISE-7500');
    expect(output.netellerCheckoutUrl).toContain('amount=4997.00');
    expect(output.crmPayload.dealStage).toBe('PROSPECT_QUALIFIED');
    expect(output.crmPayload.primaryContactPhone).toBe('2147894512');
  });

  it('evaluates a healthcare clinic prospect and assigns autonomous voice & booking agent', () => {
    const machine = new BusinessOwnerMachine();

    const clinicProspect: BusinessProspectInput = {
      companyName: 'Metroplex Pain & Spine Center',
      industry: 'Healthcare / Clinics',
      estimatedEmployeeCount: 15,
      annualRevenueEstimate: 2200000,
      decisionMaker: {
        name: 'Dr. Robert Chen',
        title: 'Managing Partner',
        verifiedBusinessEmail: 'rchen@metroplexpain.com',
        businessPhone: '3059871234',
        verificationSource: 'CMS_NPI',
      },
      digitalAudit: {
        hasOutdatedWebsite: false,
        lacksMobileOptimization: false,
        noAutomatedBookingOrLeadCapture: true,
        manualWorkflowSignals: ['Voicemails unanswered over weekends'],
      },
    };

    const output = machine.evaluateBusinessProspect(clinicProspect);

    expect(output.serviceFit).toBe('AI_AGENTS_AND_VOICE');
    expect(output.proposedSolution).toContain('AI Voice & Booking Dispatcher');
    expect(output.salesPriorityScore).toBeGreaterThanOrEqual(60);
    expect(output.recommendedRetainerSku).toBe('AI-AGENCY-RETAINER-4997');
  });
});
