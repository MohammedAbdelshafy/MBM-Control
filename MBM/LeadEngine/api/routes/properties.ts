import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';
import { prisma } from '../db';
import { Prisma } from '@prisma/client';

// ─── Schemas ────────────────────────────────────────────────────────────────────

const ListQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(200).default(50),
  county: z.string().optional(),
  city: z.string().optional(),
  zip: z.string().optional(),
  property_type: z.string().optional(),
  search: z.string().optional(),
});

const CreatePropertySchema = z.object({
  parcelId: z.string().min(1),
  addressLine1: z.string().min(1),
  addressLine2: z.string().optional(),
  city: z.string().min(1),
  state: z.string().length(2),
  zip: z.string().min(5).max(10),
  county: z.string().min(1),
  lat: z.number().optional(),
  lng: z.number().optional(),
  propertyType: z.enum(['SINGLE_FAMILY', 'MULTI_FAMILY', 'COMMERCIAL', 'INDUSTRIAL', 'LAND', 'CONDO', 'TOWNHOUSE', 'OTHER']),
  yearBuilt: z.number().int().optional(),
  lotSizeSqft: z.number().optional(),
  buildingSqft: z.number().optional(),
  bedrooms: z.number().int().optional(),
  bathrooms: z.number().optional(),
  estimatedValue: z.number().optional(),
  lastSaleDate: z.string().datetime().optional(),
  lastSalePrice: z.number().optional(),
  assessedValue: z.number().optional(),
  marketValue: z.number().optional(),
  legalDescription: z.string().optional(),
});

const UpdatePropertySchema = CreatePropertySchema.partial().omit({ parcelId: true });

const ParamsSchema = z.object({ id: z.string().uuid() });

// ─── Types ──────────────────────────────────────────────────────────────────────

type ListQuery = z.infer<typeof ListQuerySchema>;
type CreateProperty = z.infer<typeof CreatePropertySchema>;
type UpdateProperty = z.infer<typeof UpdatePropertySchema>;
type Params = z.infer<typeof ParamsSchema>;

// ─── Plugin ─────────────────────────────────────────────────────────────────────

/**
 * Property CRUD routes.
 *
 * GET    /api/properties       — paginated list with filters
 * GET    /api/properties/:id   — single property (includes owners, violations, tax records)
 * POST   /api/properties       — create
 * PUT    /api/properties/:id   — update
 * DELETE /api/properties/:id   — soft delete
 */
export default async function propertyRoutes(fastify: FastifyInstance): Promise<void> {
  // ── List ────────────────────────────────────────────────────────────────────
  fastify.get<{ Querystring: ListQuery }>(
    '/api/properties',
    {
      schema: {
        summary: 'List properties',
        tags: ['Properties'],
        querystring: {
          type: 'object',
          properties: {
            page: { type: 'integer', default: 1 },
            limit: { type: 'integer', default: 50 },
            county: { type: 'string' },
            city: { type: 'string' },
            zip: { type: 'string' },
            property_type: { type: 'string' },
            search: { type: 'string' },
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
      const { page, limit, county, city, zip, property_type, search } = ListQuerySchema.parse(request.query);

      const where: Prisma.PropertyWhereInput = {};

      if (county) where.county = { contains: county, mode: 'insensitive' };
      if (city) where.city = { contains: city, mode: 'insensitive' };
      if (zip) where.zip = zip;
      if (property_type) where.propertyType = property_type as Prisma.EnumPropertyTypeFilter['equals'];
      if (search) {
        where.OR = [
          { addressLine1: { contains: search, mode: 'insensitive' } },
          { parcelId: { contains: search, mode: 'insensitive' } },
        ];
      }

      const [data, total] = await Promise.all([
        prisma.property.findMany({
          where,
          skip: (page - 1) * limit,
          take: limit,
          orderBy: { createdAt: 'desc' },
        }),
        prisma.property.count({ where }),
      ]);

      return reply.send({ data, total, page, limit });
    },
  );

  // ── Get by ID ──────────────────────────────────────────────────────────────
  fastify.get<{ Params: Params }>(
    '/api/properties/:id',
    {
      schema: {
        summary: 'Get property by ID',
        tags: ['Properties'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);

      const property = await prisma.property.findUnique({
        where: { id },
        include: {
          owners: true,
          violations: true,
          taxRecords: true,
        },
      });

      if (!property) {
        return reply.status(404).send({ error: 'Not found', message: 'Property not found' });
      }

      return reply.send(property);
    },
  );

  // ── Create ──────────────────────────────────────────────────────────────────
  fastify.post<{ Body: CreateProperty }>(
    '/api/properties',
    {
      schema: {
        summary: 'Create a property',
        tags: ['Properties'],
        body: {
          type: 'object',
          required: ['parcelId', 'addressLine1', 'city', 'state', 'zip', 'county', 'propertyType'],
        },
        response: { 201: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Body: CreateProperty }>, reply: FastifyReply) => {
      const data = CreatePropertySchema.parse(request.body);

      const existing = await prisma.property.findUnique({ where: { parcelId: data.parcelId } });
      if (existing) {
        return reply.status(409).send({ error: 'Conflict', message: `Property with parcelId '${data.parcelId}' already exists` });
      }

      const property = await prisma.property.create({ data });
      return reply.status(201).send(property);
    },
  );

  // ── Update ──────────────────────────────────────────────────────────────────
  fastify.put<{ Params: Params; Body: UpdateProperty }>(
    '/api/properties/:id',
    {
      schema: {
        summary: 'Update a property',
        tags: ['Properties'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params; Body: UpdateProperty }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);
      const data = UpdatePropertySchema.parse(request.body);

      const existing = await prisma.property.findUnique({ where: { id } });
      if (!existing) {
        return reply.status(404).send({ error: 'Not found', message: 'Property not found' });
      }

      const property = await prisma.property.update({ where: { id }, data });
      return reply.send(property);
    },
  );

  // ── Delete (soft) ───────────────────────────────────────────────────────────
  fastify.delete<{ Params: Params }>(
    '/api/properties/:id',
    {
      schema: {
        summary: 'Soft-delete a property',
        tags: ['Properties'],
        params: { type: 'object', properties: { id: { type: 'string', format: 'uuid' } } },
        response: { 200: { type: 'object' }, 404: { type: 'object' } },
      },
    },
    async (request: FastifyRequest<{ Params: Params }>, reply: FastifyReply) => {
      const { id } = ParamsSchema.parse(request.params);

      const existing = await prisma.property.findUnique({ where: { id } });
      if (!existing) {
        return reply.status(404).send({ error: 'Not found', message: 'Property not found' });
      }

      // TODO: Add `status` field to Property model for soft delete support
      // Until then, use a convention: store status in a separate model or metadata
      // await prisma.property.update({ where: { id }, data: { status: 'deleted' } });

      return reply.send({ message: 'Soft-delete not yet implemented — add a `status` field to the Property model' });
    },
  );
}
