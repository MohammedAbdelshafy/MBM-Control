import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';
import { prisma } from '../db';

// ─── Schemas ────────────────────────────────────────────────────────────────────

const CreateCampaignSchema = z.object({
  name: z.string().min(1),
  leadFilters: z.record(z.unknown()).optional(),
  templateIds: z.array(z.string()).optional(),
  scheduledAt: z.string().datetime().optional(),
});

const CreateTemplateSchema = z.object({
  name: z.string().min(1),
  type: z.string().min(1),
  subject: z.string().optional(),
  body: z.string().min(1),
  variables: z.record(z.unknown()).optional(),
});

const GenerateContentSchema = z.object({
  leadId: z.string().uuid(),
  type: z.enum(['email', 'call_script', 'sms', 'voicemail']),
  tone: z.enum(['professional', 'friendly', 'urgent', 'consultative']).default('professional'),
  variables: z.record(z.unknown()).optional(),
});

// ─── Types ──────────────────────────────────────────────────────────────────────

type CreateCampaign = z.infer<typeof CreateCampaignSchema>;
type CreateTemplate = z.infer<typeof CreateTemplateSchema>;
type GenerateContent = z.infer<typeof GenerateContentSchema>;

// ─── Plugin ─────────────────────────────────────────────────────────────────────

/**
 * Outreach campaign routes.
 *
 * GET  /api/outreach/campaigns   — list campaigns
 * POST /api/outreach/campaigns   — create campaign
 * GET  /api/outreach/templates   — list templates
 * POST /api/outreach/templates   — create template
 * POST /api/outreach/generate    — generate outreach content for a lead
 */
export default async function outreachRoutes(fastify: FastifyInstance): Promise<void> {
  // ── List campaigns ──────────────────────────────────────────────────────────
  fastify.get(
    '/api/outreach/campaigns',
    {
      schema: {
        summary: 'List outreach campaigns',
        tags: ['Outreach'],
        response: { 200: { type: 'array' } },
      },
    },
    async (_request: FastifyRequest, reply: FastifyReply) => {
      const campaigns = await prisma.outreachCampaign.findMany({
        orderBy: { createdAt: 'desc' },
      });
      return reply.send(campaigns);
    },
  );

  // ── Create campaign ─────────────────────────────────────────────────────────
  fastify.post<{ Body: CreateCampaign }>(
    '/api/outreach/campaigns',
    {
      schema: {
        summary: 'Create an outreach campaign',
        tags: ['Outreach'],
        body: {
          type: 'object',
          required: ['name'],
          properties: {
            name: { type: 'string' },
            leadFilters: { type: 'object' },
            templateIds: { type: 'array', items: { type: 'string' } },
            scheduledAt: { type: 'string', format: 'date-time' },
          },
        },
        response: { 201: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Body: CreateCampaign }>, reply: FastifyReply) => {
      const data = CreateCampaignSchema.parse(request.body);

      const campaign = await prisma.outreachCampaign.create({
        data: {
          name: data.name,
          leadFilters: data.leadFilters ?? {},
          templateIds: data.templateIds ?? [],
          scheduledAt: data.scheduledAt ? new Date(data.scheduledAt) : null,
          status: 'draft',
        },
      });

      return reply.status(201).send(campaign);
    },
  );

  // ── List templates ──────────────────────────────────────────────────────────
  fastify.get(
    '/api/outreach/templates',
    {
      schema: {
        summary: 'List outreach templates',
        tags: ['Outreach'],
        response: { 200: { type: 'array' } },
      },
    },
    async (_request: FastifyRequest, reply: FastifyReply) => {
      const templates = await prisma.outreachTemplate.findMany({
        orderBy: { createdAt: 'desc' },
      });
      return reply.send(templates);
    },
  );

  // ── Create template ─────────────────────────────────────────────────────────
  fastify.post<{ Body: CreateTemplate }>(
    '/api/outreach/templates',
    {
      schema: {
        summary: 'Create an outreach template',
        tags: ['Outreach'],
        body: {
          type: 'object',
          required: ['name', 'type', 'body'],
          properties: {
            name: { type: 'string' },
            type: { type: 'string' },
            subject: { type: 'string' },
            body: { type: 'string' },
            variables: { type: 'object' },
          },
        },
        response: { 201: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Body: CreateTemplate }>, reply: FastifyReply) => {
      const data = CreateTemplateSchema.parse(request.body);

      const template = await prisma.outreachTemplate.create({ data });
      return reply.status(201).send(template);
    },
  );

  // ── Generate outreach content ──────────────────────────────────────────────
  fastify.post<{ Body: GenerateContent }>(
    '/api/outreach/generate',
    {
      schema: {
        summary: 'Generate outreach content for a lead',
        tags: ['Outreach'],
        body: {
          type: 'object',
          required: ['leadId', 'type'],
          properties: {
            leadId: { type: 'string', format: 'uuid' },
            type: { type: 'string', enum: ['email', 'call_script', 'sms', 'voicemail'] },
            tone: { type: 'string', enum: ['professional', 'friendly', 'urgent', 'consultative'], default: 'professional' },
            variables: { type: 'object' },
          },
        },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Body: GenerateContent }>, reply: FastifyReply) => {
      const { leadId, type, tone, variables } = GenerateContentSchema.parse(request.body);

      const lead = await prisma.lead.findUnique({
        where: { id: leadId },
        include: {
          property: {
            include: { owners: true, violations: true, taxRecords: true },
          },
          leadScore: true,
        },
      });

      if (!lead) {
        return reply.status(404).send({ error: 'Not found', message: 'Lead not found' });
      }

      // TODO: Implement LLM-based content generation.
      //       This endpoint should:
      //       1. Gather lead + property context
      //       2. Pick the right template
      //       3. Call OpenAI/Anthropic to generate personalized content
      //       4. Return the generated text with metadata

      const owner = lead.property.owners[0];
      const ownerName = owner?.name ?? 'Property Owner';

      const generatedContent: Record<string, string> = {
        email: `Subject: ${ownerName}, regarding your property at ${lead.property.addressLine1}\n\nDear ${ownerName},\n\n...`,
        call_script: `Hi, this is [Name] from [Company]. I'm calling about ${lead.property.addressLine1} in ${lead.property.city}...`,
        sms: `Hi ${ownerName}, I saw your property at ${lead.property.addressLine1} and wanted to discuss options...`,
        voicemail: `Hi ${ownerName}, this is [Name] from [Company]. Please call me back about ${lead.property.addressLine1}...`,
      };

      return reply.send({
        leadId,
        type,
        tone,
        content: generatedContent[type],
        // TODO: Return actual generated content once AI integration is wired
        isPlaceholder: true,
      });
    },
  );
}
