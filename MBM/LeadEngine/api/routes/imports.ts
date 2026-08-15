import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';
import type { Prisma, SourceType } from '@prisma/client';
import { prisma } from '../db';
import { registry } from '../../plugins/registry';

// ─── Schemas ────────────────────────────────────────────────────────────────────

const ListQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(200).default(50),
  status: z.string().optional(),
});

const CreateImportSchema = z.object({
  sourceType: z.enum(['county_assessor', 'property_appraiser', 'gis', 'tax_assessor', 'open_records', 'municipal_code_enforcement', 'court_records', 'business_registry', 'auction_data', 'user_import', 'api_connector']) as unknown as z.ZodType<SourceType, z.ZodTypeDef, string>,
  config: z.record(z.unknown()).default({}),
  filename: z.string().optional(),
});

const ParamsSchema = z.object({ id: z.string().uuid() });

const RunPluginBodySchema = z.object({
  config: z.record(z.unknown()).default({}),
});

// ─── Types ──────────────────────────────────────────────────────────────────────

type ListQuery = z.infer<typeof ListQuerySchema>;
type CreateImport = z.infer<typeof CreateImportSchema>;
type Params = z.infer<typeof ParamsSchema>;
type RunPluginBody = z.infer<typeof RunPluginBodySchema>;

// ─── Plugin ─────────────────────────────────────────────────────────────────────

/**
 * Import and plugin routes.
 *
 * GET    /api/imports           — list imports
 * POST   /api/imports           — start a new import
 * GET    /api/imports/:id       — import progress and results
 * POST   /api/imports/:id/cancel — cancel running import
 * GET    /api/plugins           — list registered plugins
 * POST   /api/plugins/:id/run   — run a plugin
 */
export default async function importRoutes(fastify: FastifyInstance): Promise<void> {
  // ── List imports ────────────────────────────────────────────────────────────
  fastify.get<{ Querystring: ListQuery }>(
    '/api/imports',
    {
      schema: {
        summary: 'List imports',
        tags: ['Imports'],
        querystring: {
          type: 'object',
          properties: {
            page: { type: 'integer', default: 1 },
            limit: { type: 'integer', default: 50 },
            status: { type: 'string' },
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
      const { page, limit, status } = ListQuerySchema.parse(request.query);

      const where: Record<string, unknown> = {};
      if (status) where.status = status;

      const [data, total] = await Promise.all([
        prisma.import.findMany({
          where,
          skip: (page - 1) * limit,
          take: limit,
          orderBy: { createdAt: 'desc' },
          include: { source: true },
        }),
        prisma.import.count({ where }),
      ]);

      return reply.send({ data, total, page, limit });
    },
  );

  // ── Create import ──────────────────────────────────────────────────────────
  fastify.post<{ Body: CreateImport }>(
    '/api/imports',
    {
      schema: {
        summary: 'Start a new import',
        tags: ['Imports'],
        body: {
          type: 'object',
          required: ['sourceType'],
          properties: {
            sourceType: { type: 'string' },
            config: { type: 'object' },
            filename: { type: 'string' },
          },
        },
        response: { 201: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Body: CreateImport }>, reply: FastifyReply) => {
      const { sourceType, config, filename } = CreateImportSchema.parse(request.body);

      // TODO: Handle file upload (multipart) — currently accepts a filename for config
      //       Support CSV file upload via Busboy or @fastify/multipart

      // Find or create a source
      let source = await prisma.source.findFirst({
        where: { type: sourceType, enabled: true },
      });

      if (!source) {
        source = await prisma.source.create({
          data: {
            type: sourceType,
            name: sourceType,
            county: String(config.county ?? 'UNKNOWN'),
            state: String(config.state ?? 'UNKNOWN'),
            config: config as Prisma.InputJsonValue,
          },
        });
      }

      const imp = await prisma.import.create({
        data: {
          sourceId: source.id,
          filename: filename ?? null,
          status: 'PENDING',
          totalRows: 0,
          processedRows: 0,
          errorRows: 0,
        },
      });

      // TODO: Enqueue import processing job (BullMQ)
      //       The worker should call the appropriate plugin and update import progress

      return reply.status(201).send(imp);
    },
  );

  // ── Get import by ID ───────────────────────────────────────────────────────
  fastify.get<{ Params: Params }>(
    '/api/imports/:id',
    {
      schema: {
        summary: 'Get import progress and results',
        tags: ['Imports'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);

      const imp = await prisma.import.findUnique({
        where: { id },
        include: { source: true },
      });

      if (!imp) {
        return reply.status(404).send({ error: 'Not found', message: 'Import not found' });
      }

      return reply.send(imp);
    },
  );

  // ── Cancel import ──────────────────────────────────────────────────────────
  fastify.post<{ Params: Params }>(
    '/api/imports/:id/cancel',
    {
      schema: {
        summary: 'Cancel a running import',
        tags: ['Imports'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);

      const imp = await prisma.import.findUnique({ where: { id } });
      if (!imp) {
        return reply.status(404).send({ error: 'Not found', message: 'Import not found' });
      }

      if (imp.status !== 'PROCESSING' && imp.status !== 'PENDING') {
        return reply.status(409).send({ error: 'Conflict', message: `Import is in '${imp.status}' state — cannot cancel` });
      }

      const updated = await prisma.import.update({
        where: { id },
        data: { status: 'FAILED' },
      });

      // TODO: Cancel the associated BullMQ job

      return reply.send(updated);
    },
  );

  // ── List plugins ────────────────────────────────────────────────────────────
  fastify.get(
    '/api/plugins',
    {
      schema: {
        summary: 'List registered plugins',
        tags: ['Plugins'],
        response: { 200: { type: 'array' } },
      },
    },
    async (_request: FastifyRequest, reply: FastifyReply) => {
      const plugins = registry.list();
      return reply.send(plugins);
    },
  );

  // ── Run plugin ──────────────────────────────────────────────────────────────
  fastify.post<{ Params: { id: string }; Body: RunPluginBody }>(
    '/api/plugins/:id/run',
    {
      schema: {
        summary: 'Run a plugin',
        tags: ['Plugins'],
        params: { type: 'object', properties: { id: { type: 'string' } } },
        body: {
          type: 'object',
          properties: { config: { type: 'object' } },
        },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: { id: string }; Body: RunPluginBody }>, reply: FastifyReply) => {
      const { id } = request.params;
      const { config } = RunPluginBodySchema.parse(request.body);

      const plugin = registry.get(id);
      if (!plugin) {
        return reply.status(404).send({ error: 'Not found', message: `Plugin '${id}' not registered` });
      }

      // TODO: Run plugin asynchronously (BullMQ job) and track via Import model
      //       For now, we run synchronously for small datasets
      plugin.configure(config);

      const errors = plugin.validate();
      if (errors.length > 0) {
        return reply.status(400).send({ error: 'Validation failed', details: errors });
      }

      // TODO: offload to worker for non-trivial runs
      const result = await plugin.import();

      return reply.send(result);
    },
  );
}
