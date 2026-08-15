import pino from 'pino';
import type { Prisma } from '@prisma/client';
import { getDb } from '../db';
import {
  calculateLeadScore,
  gradeFromScore,
  calculateSignalConfidence,
  detectAbsentee,
  detectVacancy,
  detectViolationSeverity,
  detectTaxDelinquency,
  detectEquityProxy,
  detectRecordFreshness,
  detectCommercialOpportunity,
  detectDataCompleteness,
} from '../../src/scoring';
import type { ScoringSignals } from '../../src/scoring/types';
import { CallabilityEngine } from '../../src/pipeline/callability-engine';
import type { ContactEvidence, OwnershipRecord, PropertyIdentity } from '../../src/pipeline/types';
import {
  PrismaScoringConfigRepository,
  ScoringConfigResolver,
} from '../../src/property-intel/scoring-config';

const logger = pino({ name: 'scoring-handler' });

interface ScoringPayload {
  leadIds: string[];
}

export async function handleScoring(job: {
  id: string;
  data: unknown;
}): Promise<Record<string, unknown>> {
  const payload = job.data as ScoringPayload;
  const { leadIds } = payload;
  const db = getDb();
  const resolver = new ScoringConfigResolver(new PrismaScoringConfigRepository(db));
  const callabilityEngine = new CallabilityEngine();

  if (!leadIds || leadIds.length === 0) {
    logger.warn({ jobId: job.id }, 'No lead IDs provided for scoring');
    return { scored: 0, errors: 0 };
  }

  logger.info({ jobId: job.id, batchSize: leadIds.length }, 'Starting scoring batch');

  let scored = 0;
  let errors = 0;

  for (const leadId of leadIds) {
    try {
      const lead = await db.lead.findUnique({
        where: { id: leadId },
        include: {
          property: {
            include: {
              owners: true,
              violations: true,
              taxRecords: true,
            },
          },
        },
      });

      if (!lead) {
        logger.warn({ leadId }, 'Lead not found, skipping');
        errors++;
        continue;
      }

      const { property } = lead;
      const primaryOwner = property.owners[0] ?? null;

      const ownerRecord = primaryOwner
        ? {
            mailingAddress: primaryOwner.mailingAddress,
            propertyAddress: property.addressLine1,
            mailingCity: null,
            propertyCity: property.city,
          }
        : null;

      const signalInputs = {
        owner: ownerRecord,
        property: property as Record<string, unknown>,
        violations: property.violations.map((v) => ({
          type: v.severity,
          filedAt: v.filedDate,
        })),
        taxRecords: property.taxRecords.map((t) => ({
          status: t.paid ? 'paid' : 'delinquent',
          yearsDelinquent: t.delinquencyAmount && t.delinquencyAmount > 0 ? 1 : 0,
          lastPaymentDate: t.paidDate,
        })),
        utilityRecords: [] as { isActive: boolean; lastPayment: Date | null }[],
      };

      const signals: ScoringSignals = {
        ownershipConfidence: primaryOwner ? Math.min(1, primaryOwner.confidenceScore) : 0,
        recordFreshness: detectRecordFreshness(lead.generatedAt),
        absenteeSignal: detectAbsentee(signalInputs.owner),
        vacancyIndicators: detectVacancy(property, signalInputs.violations, signalInputs.utilityRecords),
        violationSeverity: detectViolationSeverity(signalInputs.violations),
        taxDelinquency: detectTaxDelinquency(signalInputs.taxRecords),
        equityProxy: detectEquityProxy(property),
        commercialOpportunity: detectCommercialOpportunity(property.propertyType),
        dataCompleteness: detectDataCompleteness(property as Record<string, unknown>),
        duplicatePenalty: 0,
      };

      // Configurable weights — per county/state/niche config wins over defaults.
      const weights = await resolver.resolveWeights({
        county: property.county,
        state: property.state,
        niche: lead.niche,
      });

      const result = calculateLeadScore(leadId, signals, weights);
      const confidence = calculateSignalConfidence(signals);
      const grade = result.grade;

      // Separate CALLABILITY score (dialability), independent of lead score.
      const callability = computeCallabilityScore(lead, primaryOwner, result.overallScore, callabilityEngine);

      await db.$transaction([
        db.lead.update({
          where: { id: leadId },
          data: {
            score: result.overallScore,
            grade: mapGrade(grade),
            confidence,
            callabilityScore: callability.totalScore,
            signals: result.breakdown as unknown as Prisma.InputJsonValue,
          },
        }),
        db.leadScore.upsert({
          where: { leadId },
          create: {
            leadId,
            overallScore: result.overallScore,
            callabilityScore: callability.totalScore,
            callabilityBreakdown: callability as unknown as Prisma.InputJsonValue,
            ownershipConfidence: signals.ownershipConfidence,
            recordFreshness: signals.recordFreshness,
            absenteeSignal: signals.absenteeSignal,
            vacancyIndicators: signals.vacancyIndicators,
            violationSeverity: signals.violationSeverity,
            taxDelinquency: signals.taxDelinquency,
            equityProxy: signals.equityProxy,
            commercialOpportunity: signals.commercialOpportunity,
            dataCompleteness: signals.dataCompleteness,
            duplicatePenalty: signals.duplicatePenalty,
          },
          update: {
            overallScore: result.overallScore,
            callabilityScore: callability.totalScore,
            callabilityBreakdown: callability as unknown as Prisma.InputJsonValue,
            ownershipConfidence: signals.ownershipConfidence,
            recordFreshness: signals.recordFreshness,
            absenteeSignal: signals.absenteeSignal,
            vacancyIndicators: signals.vacancyIndicators,
            violationSeverity: signals.violationSeverity,
            taxDelinquency: signals.taxDelinquency,
            equityProxy: signals.equityProxy,
            commercialOpportunity: signals.commercialOpportunity,
            dataCompleteness: signals.dataCompleteness,
            duplicatePenalty: signals.duplicatePenalty,
          },
        }),
      ]);

      scored++;
    } catch (err) {
      logger.error({ err, leadId }, 'Error scoring lead');
      errors++;
    }
  }

  logger.info(
    { jobId: job.id, batchSize: leadIds.length, scored, errors },
    'Scoring batch completed',
  );

  return { scored, errors, total: leadIds.length };
}

function computeCallabilityScore(
  lead: {
    phone: string | null;
    email: string | null;
    contactName: string | null;
    skipTraceSource: string | null;
    skipTraceConfidence: number | null;
    generatedAt: Date;
    niche: string;
  },
  primaryOwner: { name: string; ownerType: string; mailingAddress: string; isAbsentee: boolean; confidenceScore: number; verifiedAt: Date | null } | null,
  leadScore: number,
  engine: CallabilityEngine,
) {
  const property = {} as PropertyIdentity;
  const ownership: OwnershipRecord | null = primaryOwner
    ? {
        ownerName: primaryOwner.name,
        ownerType: primaryOwner.ownerType as OwnershipRecord['ownerType'],
        mailingAddress: primaryOwner.mailingAddress,
        isAbsentee: primaryOwner.isAbsentee,
        confidenceScore: primaryOwner.confidenceScore,
        verifiedAt: primaryOwner.verifiedAt?.toISOString() ?? new Date().toISOString(),
      }
    : null;

  const contact: ContactEvidence = {
    contactName: lead.contactName ?? primaryOwner?.name ?? '',
    phone: lead.phone ?? '',
    email: lead.email,
    source: mapContactSource(lead.skipTraceSource),
    dncStatus: 'CLEAN',
    confidenceScore: lead.skipTraceConfidence ?? 0,
    extractedAt: lead.generatedAt.toISOString(),
  };

  return engine.calculateCallability(property, ownership ?? fallbackOwnership(), contact, leadScore);
}

function fallbackOwnership(): OwnershipRecord {
  return {
    ownerName: '',
    ownerType: 'INDIVIDUAL',
    mailingAddress: '',
    isAbsentee: false,
    confidenceScore: 0,
    verifiedAt: new Date().toISOString(),
  };
}

function mapContactSource(
  source: string | null,
): ContactEvidence['source'] {
  const s = (source ?? '').toUpperCase();
  if (s.includes('NPI') || s.includes('CMS')) return 'CMS_NPI';
  if (s.includes('COUNTY') || s.includes('TAX')) return 'COUNTY_TAX';
  if (s.includes('SECRETARY') || s.includes('SOS')) return 'SECRETARY_OF_STATE';
  if (s.includes('RAPIDAPI')) return 'RAPIDAPI';
  if (s.includes('SKIP') || s.includes('TRACE')) return 'SKIP_TRACE';
  return 'SKIP_TRACE';
}

function mapGrade(grade: string): 'A_PLUS' | 'A' | 'B' | 'C' | 'REJECT' {
  switch (grade) {
    case 'A+': return 'A_PLUS';
    case 'A': return 'A';
    case 'B': return 'B';
    case 'C': return 'C';
    default: return 'REJECT';
  }
}