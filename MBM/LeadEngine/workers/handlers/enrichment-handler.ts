import pino from 'pino';
import { getDb } from '../db';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);
const logger = pino({ name: 'enrichment-handler' });

interface EnrichmentPayload {
  leadIds: string[];
}

interface SkipTraceResult {
  phone: string | null;
  email: string | null;
  source: string;
  confidence: string;
}

export async function handleEnrichment(job: {
  id: string;
  data: unknown;
}): Promise<Record<string, unknown>> {
  const payload = job.data as EnrichmentPayload;
  const { leadIds } = payload;
  const db = getDb();

  if (!leadIds || leadIds.length === 0) {
    logger.warn({ jobId: job.id }, 'No lead IDs provided for enrichment');
    return { enriched: 0, errors: 0 };
  }

  logger.info({ jobId: job.id, batchSize: leadIds.length }, 'Starting enrichment batch');

  let enriched = 0;
  let errors = 0;

  for (const leadId of leadIds) {
    try {
      const lead = await db.lead.findUnique({
        where: { id: leadId },
        include: {
          property: {
            include: {
              owners: true,
            },
          },
        },
      });

      if (!lead) {
        logger.warn({ leadId }, 'Lead not found, skipping');
        errors++;
        continue;
      }

      // Skip if already has both phone and email
      if (lead.phone && lead.email) {
        enriched++;
        continue;
      }

      const { property } = lead;
      const primaryOwner = property.owners[0];
      const ownerName = primaryOwner?.name || lead.contactName || '';
      const address = property.addressLine1
        ? `${property.addressLine1}, ${property.city}, ${property.state} ${property.zip}`
        : '';

      // Call Python free skip tracer
      const result = await runSkipTrace(ownerName, address, property.city);

      // Update lead with enriched data
      const updateData: Record<string, unknown> = {};
      if (result.phone && !lead.phone) {
        updateData.phone = result.phone;
      }
      if (result.email && !lead.email) {
        updateData.email = result.email;
        updateData.emailVerified = true;
      }
      if (result.source) {
        updateData.skipTraceSource = result.source;
      }
      if (result.confidence) {
        updateData.skipTraceConfidence = result.confidence;
      }

      if (Object.keys(updateData).length > 0) {
        updateData.contactVerified = true;
        updateData.contactVerifiedAt = new Date();

        await db.lead.update({
          where: { id: leadId },
          data: updateData,
        });

        enriched++;
        logger.info(
          { leadId, phone: result.phone, email: result.email, source: result.source },
          'Lead enriched'
        );
      }
    } catch (err) {
      logger.error({ err, leadId }, 'Error enriching lead');
      errors++;
    }
  }

  logger.info(
    { jobId: job.id, batchSize: leadIds.length, enriched, errors },
    'Enrichment batch completed'
  );

  return { enriched, errors, total: leadIds.length };
}

async function runSkipTrace(
  name: string,
  address: string,
  city: string
): Promise<SkipTraceResult> {
  const defaultResult: SkipTraceResult = {
    phone: null,
    email: null,
    source: 'none',
    confidence: 'low',
  };

  if (!name && !address) {
    return defaultResult;
  }

  try {
    // Build Python command
    const args = [
      '--name', `"${name.replace(/"/g, '\\"')}"`,
      '--address', `"${address.replace(/"/g, '\\"')}"`,
      '--city', `"${city.replace(/"/g, '\\"')}"`,
    ].join(' ');

    const scriptPath = `${process.cwd()}/../MBM/LeadEngine/free_skip_tracer.py`;
    const command = `python "${scriptPath}" ${args}`;

    const { stdout, stderr } = await execAsync(command, {
      timeout: 30000,
      env: { ...process.env },
    });

    if (stderr) {
      logger.warn({ stderr }, 'Skip tracer stderr output');
    }

    // Parse JSON output
    const output = stdout.trim();
    const jsonStart = output.lastIndexOf('{');
    const jsonEnd = output.lastIndexOf('}') + 1;

    if (jsonStart >= 0 && jsonEnd > jsonStart) {
      const jsonStr = output.substring(jsonStart, jsonEnd);
      const result = JSON.parse(jsonStr);

      return {
        phone: result.phone || null,
        email: result.email || null,
        source: result.source || 'free_skip_tracer',
        confidence: result.confidence || 'low',
      };
    }
  } catch (err) {
    logger.error({ err, name, address }, 'Skip trace execution failed');
  }

  return defaultResult;
}
