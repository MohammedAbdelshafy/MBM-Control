import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';
import { prisma } from '../db';
import { Prisma, LeadGrade } from '@prisma/client';

// ─── Schemas ────────────────────────────────────────────────────────────────────

const ListQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(200).default(50),
  status: z.string().optional(),
  grade: z.string().optional(),
  niche: z.string().optional(),
  score_min: z.coerce.number().int().min(0).max(100).optional(),
  score_max: z.coerce.number().int().min(0).max(100).optional(),
  county: z.string().optional(),
});

const ParamsSchema = z.object({ id: z.string().uuid() });

const ClaimBodySchema = z.object({
  clientId: z.string().uuid(),
  assignedTo: z.string().optional(),
});

const RecalculateBodySchema = z.object({
  leadIds: z.array(z.string().uuid()).optional(),
  niche: z.string().optional(),
  county: z.string().optional(),
});

const ExportQuerySchema = z.object({
  format: z.enum(['csv', 'excel', 'json']).default('csv'),
  status: z.string().optional(),
  grade: z.string().optional(),
  niche: z.string().optional(),
  county: z.string().optional(),
});

// ─── Types ──────────────────────────────────────────────────────────────────────

type ListQuery = z.infer<typeof ListQuerySchema>;
type Params = z.infer<typeof ParamsSchema>;
type ClaimBody = z.infer<typeof ClaimBodySchema>;
type RecalculateBody = z.infer<typeof RecalculateBodySchema>;
type ExportQuery = z.infer<typeof ExportQuerySchema>;

// ─── Plugin ─────────────────────────────────────────────────────────────────────

/**
 * Lead routes.
 *
 * GET    /api/leads              — paginated list with filters
 * GET    /api/leads/:id          — single lead with scoring + property details
 * POST   /api/leads/:id/claim    — claim a lead for a client
 * POST   /api/leads/recalculate  — trigger score recalculation
 * GET    /api/leads/export       — export leads in CSV / Excel / JSON
 */
export default async function leadRoutes(fastify: FastifyInstance): Promise<void> {
  // ── List ────────────────────────────────────────────────────────────────────
  fastify.get<{ Querystring: ListQuery }>(
    '/api/leads',
    {
      preHandler: [fastify.authenticate],
      schema: {
        summary: 'List leads',
        tags: ['Leads'],
        querystring: {
          type: 'object',
          properties: {
            page: { type: 'integer', default: 1 },
            limit: { type: 'integer', default: 50 },
            status: { type: 'string' },
            grade: { type: 'string' },
            niche: { type: 'string' },
            score_min: { type: 'integer' },
            score_max: { type: 'integer' },
            county: { type: 'string' },
          },
        },
        response: {
          200: {
            type: 'object',
            properties: {
              data: { type: 'array' },
              total: { type: 'integer' },
              page: { type: 'integer' },
              limit: { type: 'integer' },
            },
          },
        },
      },
    },
    async (request: FastifyRequest<{ Querystring: ListQuery }>, reply: FastifyReply) => {
      const { page, limit, status, grade, niche, score_min, score_max, county } = ListQuerySchema.parse(request.query);

      const where: Prisma.LeadWhereInput = {};

      if (request.user.role === 'client') {
        if (!request.user.clientId) {
          return reply.status(403).send({ error: 'Forbidden', message: 'Client token is missing a client scope' });
        }
        where.clientId = request.user.clientId;
      }

      if (status) where.status = status as Prisma.EnumLeadStatusFilter['equals'];
      if (grade) where.grade = grade as LeadGrade;
      if (niche) where.niche = niche as Prisma.EnumNicheTypeFilter['equals'];
      if (score_min !== undefined || score_max !== undefined) {
        where.score = {};
        if (score_min !== undefined) where.score.gte = score_min;
        if (score_max !== undefined) where.score.lte = score_max;
      }
      if (county) {
        where.property = { county: { contains: county, mode: 'insensitive' } };
      }

      const [data, total] = await Promise.all([
        prisma.lead.findMany({
          where,
          skip: (page - 1) * limit,
          take: limit,
          orderBy: { score: 'desc' },
          include: {
            property: { select: { id: true, addressLine1: true, city: true, state: true, zip: true, county: true } },
            leadScore: true,
          },
        }),
        prisma.lead.count({ where }),
      ]);

      return reply.send({ data, total, page, limit });
    },
  );

  // ── Get by ID ──────────────────────────────────────────────────────────────
  fastify.get<{ Params: Params }>(
    '/api/leads/:id',
    {
      preHandler: [fastify.authenticate],
      schema: {
        summary: 'Get lead by ID',
        tags: ['Leads'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);

      const where: Prisma.LeadWhereInput = { id };
      if (request.user.role === 'client') {
        if (!request.user.clientId) {
          return reply.status(403).send({ error: 'Forbidden', message: 'Client token is missing a client scope' });
        }
        where.clientId = request.user.clientId;
      }

      const lead = await prisma.lead.findFirst({
        where,
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

      return reply.send(lead);
    },
  );

  // ── Claim ───────────────────────────────────────────────────────────────────
  fastify.post<{ Params: Params; Body: ClaimBody }>(
    '/api/leads/:id/claim',
    {
      preHandler: [fastify.authenticate, fastify.requireRole('admin')],
      schema: {
        summary: 'Claim a lead for a client',
        tags: ['Leads'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        body: {
          type: 'object',
          required: ['clientId'],
          properties: {
            clientId: { type: 'string', format: 'uuid' },
            assignedTo: { type: 'string' },
          },
        },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params; Body: ClaimBody }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);
      const { clientId, assignedTo } = ClaimBodySchema.parse(request.body);

      const lead = await prisma.lead.findUnique({ where: { id } });
      if (!lead) {
        return reply.status(404).send({ error: 'Not found', message: 'Lead not found' });
      }

      if (lead.clientId) {
        return reply.status(409).send({ error: 'Conflict', message: 'Lead is already claimed' });
      }

      const updated = await prisma.lead.update({
        where: { id },
        data: {
          clientId,
          assignedTo,
          status: 'ACTIVE',
          claimedAt: new Date(),
        },
      });

      return reply.send(updated);
    },
  );

  // ── Recalculate scores ─────────────────────────────────────────────────────
  fastify.post<{ Body: RecalculateBody }>(
    '/api/leads/recalculate',
    {
      preHandler: [fastify.authenticate, fastify.requireRole('admin')],
      schema: {
        summary: 'Recalculate lead scores',
        tags: ['Leads'],
        body: {
          type: 'object',
          properties: {
            leadIds: { type: 'array', items: { type: 'string', format: 'uuid' } },
            niche: { type: 'string' },
            county: { type: 'string' },
          },
        },
        response: { 200: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Body: RecalculateBody }>, reply: FastifyReply) => {
      const params = RecalculateBodySchema.parse(request.body);

      // TODO: Delegate to scoring service. This endpoint should:
      //   1. Fetch leads matching the filters (or by leadIds)
      //   2. For each lead, compute signals from property/owner/tax/violation data
      //   3. Call calculateLeadScore() from src/scoring
      //   4. Upsert LeadScore record and update Lead.grade/score/signals
      //   5. Return summary of recalculated leads

      let leadCount = 0;
      if (params.leadIds) {
        leadCount = params.leadIds.length;
      } else {
        const where: Prisma.LeadWhereInput = {};
        if (params.niche) where.niche = params.niche as Prisma.EnumNicheTypeFilter['equals'];
        if (params.county) where.property = { county: { contains: params.county, mode: 'insensitive' } };
        leadCount = await prisma.lead.count({ where });
      }

      return reply.send({
        message: 'Score recalculation queued',
        estimatedLeads: leadCount,
        // TODO: enqueue BullMQ job
        jobId: null,
      });
    },
  );

  // ── Export ──────────────────────────────────────────────────────────────────
  fastify.get<{ Querystring: ExportQuery }>(
    '/api/leads/export',
    {
      preHandler: [fastify.authenticate],
      schema: {
        summary: 'Export leads',
        tags: ['Leads'],
        querystring: {
          type: 'object',
          properties: {
            format: { type: 'string', enum: ['csv', 'excel', 'json'], default: 'csv' },
            status: { type: 'string' },
            grade: { type: 'string' },
            niche: { type: 'string' },
            county: { type: 'string' },
          },
        },
        response: { 200: { type: 'string' } },
      },
    },
    async (request: FastifyRequest<{ Querystring: ExportQuery }>, reply: FastifyReply) => {
      const { format, status, grade, niche, county } = ExportQuerySchema.parse(request.query);

      const where: Prisma.LeadWhereInput = {};
      if (request.user.role === 'client') {
        if (!request.user.clientId) {
          return reply.status(403).send({ error: 'Forbidden', message: 'Client token is missing a client scope' });
        }
        where.clientId = request.user.clientId;
      }
      if (status) where.status = status as Prisma.EnumLeadStatusFilter['equals'];
      if (grade) where.grade = grade as LeadGrade;
      if (niche) where.niche = niche as Prisma.EnumNicheTypeFilter['equals'];
      if (county) where.property = { county: { contains: county, mode: 'insensitive' } };

      const leads = await prisma.lead.findMany({
        where,
        include: {
          property: true,
          leadScore: true,
        },
        orderBy: { score: 'desc' },
      });

      // TODO: Use actual export service (ExcelJS for xlsx, PDFKit for pdf)
      // For now, return JSON that client can format
      if (format === 'json') {
        reply.header('Content-Type', 'application/json');
        reply.header('Content-Disposition', 'attachment; filename="leads-export.json"');
        return reply.send(leads);
      }

      // TODO: Generate CSV or Excel using a dedicated export service
      return reply.send({
        message: `Export in ${format} format`,
        totalLeads: leads.length,
        downloadUrl: null,
        // TODO: return file or enqueue generation
      });
    },
  );
}
