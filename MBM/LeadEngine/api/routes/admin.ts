import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';
import { prisma } from '../db';

// ─── Schemas ────────────────────────────────────────────────────────────────────

const AuditLogQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(200).default(50),
  action: z.string().optional(),
  entityType: z.string().optional(),
});

const JobsQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(200).default(50),
  status: z.string().optional(),
  type: z.string().optional(),
});

const PipelineParamsSchema = z.object({ id: z.string().uuid() });

// ─── Types ──────────────────────────────────────────────────────────────────────

type AuditLogQuery = z.infer<typeof AuditLogQuerySchema>;
type JobsQuery = z.infer<typeof JobsQuerySchema>;
type PipelineParams = z.infer<typeof PipelineParamsSchema>;

// ─── Plugin ─────────────────────────────────────────────────────────────────────

/**
 * Admin-only routes.
 *
 * GET  /api/admin/workers         — list registered workers
 * GET  /api/admin/audit-logs      — paginated audit log
 * GET  /api/admin/jobs            — list background jobs
 * POST /api/admin/pipelines/:id/run — trigger pipeline run
 */
export default async function adminRoutes(fastify: FastifyInstance): Promise<void> {
  // ── Workers ─────────────────────────────────────────────────────────────────
  fastify.get(
    '/api/admin/workers',
    {
      schema: {
        summary: 'List registered workers and their status',
        tags: ['Admin'],
        response: { 200: { type: 'array' } },
      },
    },
    async (_request: FastifyRequest, reply: FastifyReply) => {
      const workers = await prisma.worker.findMany({
        orderBy: { lastHeartbeat: 'desc' },
      });

      return reply.send(workers);
    },
  );

  // ── Audit logs ──────────────────────────────────────────────────────────────
  fastify.get<{ Querystring: AuditLogQuery }>(
    '/api/admin/audit-logs',
    {
      schema: {
        summary: 'Paginated audit log',
        tags: ['Admin'],
        querystring: {
          type: 'object',
          properties: {
            page: { type: 'integer', default: 1 },
            limit: { type: 'integer', default: 50 },
            action: { type: 'string' },
            entityType: { type: 'string' },
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
    async (request: FastifyRequest<{ Querystring: AuditLogQuery }>, reply: FastifyReply) => {
      const { page, limit, action, entityType } = AuditLogQuerySchema.parse(request.query);

      const where: Record<string, unknown> = {};
      if (action) where.action = action;
      if (entityType) where.entityType = entityType;

      const [data, total] = await Promise.all([
        prisma.auditLog.findMany({
          where,
          skip: (page - 1) * limit,
          take: limit,
          orderBy: { createdAt: 'desc' },
        }),
        prisma.auditLog.count({ where }),
      ]);

      return reply.send({ data, total, page, limit });
    },
  );

  // ── Jobs ────────────────────────────────────────────────────────────────────
  fastify.get<{ Querystring: JobsQuery }>(
    '/api/admin/jobs',
    {
      schema: {
        summary: 'List background jobs',
        tags: ['Admin'],
        querystring: {
          type: 'object',
          properties: {
            page: { type: 'integer', default: 1 },
            limit: { type: 'integer', default: 50 },
            status: { type: 'string' },
            type: { type: 'string' },
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
    async (request: FastifyRequest<{ Querystring: JobsQuery }>, reply: FastifyReply) => {
      const { page, limit, status, type } = JobsQuerySchema.parse(request.query);

      const where: Record<string, unknown> = {};
      if (status) where.status = status;
      if (type) where.type = type;

      const [data, total] = await Promise.all([
        prisma.job.findMany({
          where,
          skip: (page - 1) * limit,
          take: limit,
          orderBy: { createdAt: 'desc' },
          include: { tasks: true },
        }),
        prisma.job.count({ where }),
      ]);

      return reply.send({ data, total, page, limit });
    },
  );

  // ── Run pipeline ────────────────────────────────────────────────────────────
  fastify.post<{ Params: PipelineParams }>(
    '/api/admin/pipelines/:id/run',
    {
      schema: {
        summary: 'Trigger a pipeline run',
        tags: ['Admin'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: PipelineParams }>, reply: FastifyReply) => {
      const { id } = PipelineParamsSchema.parse(request.params);

      const pipeline = await prisma.pipeline.findUnique({ where: { id } });
      if (!pipeline) {
        return reply.status(404).send({ error: 'Not found', message: 'Pipeline not found' });
      }

      if (!pipeline.isActive) {
        return reply.status(400).send({ error: 'Inactive', message: 'Pipeline is not active' });
      }

      // TODO: Delegate to PipelineRunner that:
      //   1. Iterates through pipeline.steps
      //   2. Creates a Job record
      //   3. Enqueues each step as a BullMQ task
      //   4. Monitors progress via job/task status updates

      const job = await prisma.job.create({
        data: {
          type: `pipeline:${pipeline.name}`,
          status: 'QUEUED',
          payload: { pipelineId: id, steps: pipeline.steps },
        },
      });

      return reply.send({
        message: `Pipeline '${pipeline.name}' triggered`,
        jobId: job.id,
      });
    },
  );
}
