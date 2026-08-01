import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';
import { prisma } from '../db';

// ─── Schemas ────────────────────────────────────────────────────────────────────

const CreateClientSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
  company: z.string().optional(),
  tier: z.enum(['STARTER_100', 'GROWTH_500', 'SCALE_1000', 'COUNTY', 'STATE', 'ENTERPRISE']),
  creditsRemaining: z.number().int().min(0).default(0),
});

const UpdateClientSchema = z.object({
  name: z.string().min(1).optional(),
  company: z.string().optional(),
  tier: z.enum(['STARTER_100', 'GROWTH_500', 'SCALE_1000', 'COUNTY', 'STATE', 'ENTERPRISE']).optional(),
  isActive: z.boolean().optional(),
});

const ParamsSchema = z.object({ id: z.string().uuid() });

const AddCreditsBodySchema = z.object({
  amount: z.number().int().positive(),
});

// ─── Types ──────────────────────────────────────────────────────────────────────

type CreateClient = z.infer<typeof CreateClientSchema>;
type UpdateClient = z.infer<typeof UpdateClientSchema>;
type Params = z.infer<typeof ParamsSchema>;
type AddCreditsBody = z.infer<typeof AddCreditsBodySchema>;

// ─── Plugin ─────────────────────────────────────────────────────────────────────

/**
 * Client management routes.
 *
 * GET    /api/clients              — list clients
 * POST   /api/clients              — create client
 * GET    /api/clients/:id          — client details with subscription info
 * PUT    /api/clients/:id          — update client
 * GET    /api/clients/:id/downloads — list export downloads for client
 * POST   /api/clients/:id/credits  — add credits to client
 */
export default async function clientRoutes(fastify: FastifyInstance): Promise<void> {
  // ── List ────────────────────────────────────────────────────────────────────
  fastify.get(
    '/api/clients',
    {
      schema: {
        summary: 'List clients',
        tags: ['Clients'],
        response: { 200: { type: 'array' } },
      },
    },
    async (_request: FastifyRequest, reply: FastifyReply) => {
      const clients = await prisma.client.findMany({
        orderBy: { createdAt: 'desc' },
        include: { subscriptions: true },
      });
      return reply.send(clients);
    },
  );

  // ── Create ──────────────────────────────────────────────────────────────────
  fastify.post<{ Body: CreateClient }>(
    '/api/clients',
    {
      schema: {
        summary: 'Create a client',
        tags: ['Clients'],
        body: {
          type: 'object',
          required: ['name', 'email', 'tier'],
          properties: {
            name: { type: 'string' },
            email: { type: 'string', format: 'email' },
            company: { type: 'string' },
            tier: { type: 'string' },
            creditsRemaining: { type: 'integer', default: 0 },
          },
        },
        response: { 201: { type: 'object' }, 409: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Body: CreateClient }>, reply: FastifyReply) => {
      const data = CreateClientSchema.parse(request.body);

      const existing = await prisma.client.findUnique({ where: { email: data.email } });
      if (existing) {
        return reply.status(409).send({ error: 'Conflict', message: `Client with email '${data.email}' already exists` });
      }

      const client = await prisma.client.create({
        data: {
          ...data,
          totalPurchased: 0,
        },
      });

      return reply.status(201).send(client);
    },
  );

  // ── Get by ID ──────────────────────────────────────────────────────────────
  fastify.get<{ Params: Params }>(
    '/api/clients/:id',
    {
      schema: {
        summary: 'Get client by ID',
        tags: ['Clients'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);

      const client = await prisma.client.findUnique({
        where: { id },
        include: { subscriptions: true },
      });

      if (!client) {
        return reply.status(404).send({ error: 'Not found', message: 'Client not found' });
      }

      // TODO: Add credits usage, recent downloads, lead counts to the response
      return reply.send(client);
    },
  );

  // ── Update ──────────────────────────────────────────────────────────────────
  fastify.put<{ Params: Params; Body: UpdateClient }>(
    '/api/clients/:id',
    {
      schema: {
        summary: 'Update a client',
        tags: ['Clients'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params; Body: UpdateClient }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);
      const data = UpdateClientSchema.parse(request.body);

      const existing = await prisma.client.findUnique({ where: { id } });
      if (!existing) {
        return reply.status(404).send({ error: 'Not found', message: 'Client not found' });
      }

      const client = await prisma.client.update({ where: { id }, data });
      return reply.send(client);
    },
  );

  // ── Downloads ───────────────────────────────────────────────────────────────
  fastify.get<{ Params: Params }>(
    '/api/clients/:id/downloads',
    {
      schema: {
        summary: 'List export downloads for a client',
        tags: ['Clients'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'array' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);

      const client = await prisma.client.findUnique({ where: { id } });
      if (!client) {
        return reply.status(404).send({ error: 'Not found', message: 'Client not found' });
      }

      const exports = await prisma.export.findMany({
        where: { clientId: id },
        orderBy: { createdAt: 'desc' },
      });

      return reply.send(exports);
    },
  );

  // ── Add Credits ─────────────────────────────────────────────────────────────
  fastify.post<{ Params: Params; Body: AddCreditsBody }>(
    '/api/clients/:id/credits',
    {
      schema: {
        summary: 'Add credits to client',
        tags: ['Clients'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        body: {
          type: 'object',
          required: ['amount'],
          properties: { amount: { type: 'integer', minimum: 1 } },
        },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params; Body: AddCreditsBody }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);
      const { amount } = AddCreditsBodySchema.parse(request.body);

      const client = await prisma.client.findUnique({ where: { id } });
      if (!client) {
        return reply.status(404).send({ error: 'Not found', message: 'Client not found' });
      }

      const updated = await prisma.client.update({
        where: { id },
        data: {
          creditsRemaining: { increment: amount },
          totalPurchased: { increment: amount },
        },
      });

      return reply.send(updated);
    },
  );
}
