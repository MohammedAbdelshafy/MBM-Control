import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';
import { prisma } from '../db';
import * as fs from 'node:fs';
import * as path from 'node:path';

// ─── Schemas ────────────────────────────────────────────────────────────────────

const ListQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(200).default(50),
});

const CreateExportSchema = z.object({
  format: z.enum(['csv', 'excel', 'pdf', 'json', 'crm_import']),
  filters: z.record(z.unknown()).optional(),
  clientId: z.string().uuid().optional(),
});

const ParamsSchema = z.object({ id: z.string().uuid() });

// ─── Types ──────────────────────────────────────────────────────────────────────

type ListQuery = z.infer<typeof ListQuerySchema>;
type CreateExport = z.infer<typeof CreateExportSchema>;
type Params = z.infer<typeof ParamsSchema>;

// ─── Plugin ─────────────────────────────────────────────────────────────────────

/**
 * Export management routes.
 *
 * GET    /api/exports           — list exports
 * POST   /api/exports           — create an export
 * GET    /api/exports/:id/download — download export file
 * DELETE /api/exports/:id       — delete an export record
 */
export default async function exportRoutes(fastify: FastifyInstance): Promise<void> {
  // ── List ────────────────────────────────────────────────────────────────────
  fastify.get<{ Querystring: ListQuery }>(
    '/api/exports',
    {
      schema: {
        summary: 'List exports',
        tags: ['Exports'],
        querystring: {
          type: 'object',
          properties: {
            page: { type: 'integer', default: 1 },
            limit: { type: 'integer', default: 50 },
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
      const { page, limit } = ListQuerySchema.parse(request.query);

      const [data, total] = await Promise.all([
        prisma.export.findMany({
          skip: (page - 1) * limit,
          take: limit,
          orderBy: { createdAt: 'desc' },
        }),
        prisma.export.count(),
      ]);

      return reply.send({ data, total, page, limit });
    },
  );

  // ── Create ──────────────────────────────────────────────────────────────────
  fastify.post<{ Body: CreateExport }>(
    '/api/exports',
    {
      schema: {
        summary: 'Create a new export',
        tags: ['Exports'],
        body: {
          type: 'object',
          required: ['format'],
          properties: {
            format: { type: 'string', enum: ['csv', 'excel', 'pdf', 'json', 'crm_import'] },
            filters: { type: 'object' },
            clientId: { type: 'string', format: 'uuid' },
          },
        },
        response: { 201: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Body: CreateExport }>, reply: FastifyReply) => {
      const data = CreateExportSchema.parse(request.body);

      // TODO: Delegate to ExportService that:
      //   1. Queries leads matching the filters
      //   2. Generates the file in the requested format (ExcelJS for xlsx, PDFKit for pdf)
      //   3. Writes to storage (local or S3)
      //   4. Creates Export record with filePath and totalLeads

      const exp = await prisma.export.create({
        data: {
          format: data.format as Prisma.EnumExportFormatFilter['equals'],
          filters: data.filters ?? {},
          totalLeads: 0,
          clientId: data.clientId ?? null,
        },
      });

      return reply.status(201).send(exp);
    },
  );

  // ── Download ────────────────────────────────────────────────────────────────
  fastify.get<{ Params: Params }>(
    '/api/exports/:id/download',
    {
      schema: {
        summary: 'Download an export file',
        tags: ['Exports'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: {}, 404: { type: 'object' }, 400: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);

      const exp = await prisma.export.findUnique({ where: { id } });
      if (!exp) {
        return reply.status(404).send({ error: 'Not found', message: 'Export not found' });
      }

      if (!exp.filePath) {
        return reply.status(400).send({ error: 'No file', message: 'Export file has not been generated yet' });
      }

      const filePath = path.resolve(exp.filePath);
      if (!fs.existsSync(filePath)) {
        return reply.status(400).send({ error: 'File missing', message: 'Export file not found on storage' });
      }

      const filename = path.basename(filePath);
      const stream = fs.createReadStream(filePath);

      reply.header('Content-Disposition', `attachment; filename="${filename}"`);
      reply.type('application/octet-stream');

      await reply.send(stream);

      // Update downloaded timestamp
      await prisma.export.update({
        where: { id },
        data: { downloadedAt: new Date() },
      });
    },
  );

  // ── Delete ──────────────────────────────────────────────────────────────────
  fastify.delete<{ Params: Params }>(
    '/api/exports/:id',
    {
      schema: {
        summary: 'Delete an export record',
        tags: ['Exports'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);

      const exp = await prisma.export.findUnique({ where: { id } });
      if (!exp) {
        return reply.status(404).send({ error: 'Not found', message: 'Export not found' });
      }

      // Remove file from storage if it exists
      if (exp.filePath) {
        try {
          fs.unlinkSync(path.resolve(exp.filePath));
        } catch {
          // file may already be deleted — ignore
        }
      }

      await prisma.export.delete({ where: { id } });
      return reply.send({ message: 'Export deleted' });
    },
  );
}
