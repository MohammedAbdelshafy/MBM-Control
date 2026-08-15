import Fastify from 'fastify';
import cors from '@fastify/cors';
import jwt from '@fastify/jwt';
import rateLimit from '@fastify/rate-limit';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';
import dotenv from 'dotenv';

import authPlugin from './auth';
import propertyRoutes from './routes/properties';
import leadRoutes from './routes/leads';
import clientRoutes from './routes/clients';
import importRoutes from './routes/imports';
import exportRoutes from './routes/exports';
import dashboardRoutes from './routes/dashboard';
import adminRoutes from './routes/admin';
import outreachRoutes from './routes/outreach';
import { prisma } from './db';

dotenv.config();

const PORT = parseInt(process.env.PORT ?? '4000', 10);
const HOST = process.env.HOST ?? '0.0.0.0';
const JWT_SECRET: string = process.env.JWT_SECRET ?? '';
const NODE_ENV = process.env.NODE_ENV ?? 'development';

if (!JWT_SECRET) {
  console.error('FATAL: JWT_SECRET environment variable is required');
  process.exit(1);
}

/**
 * Creates and configures the Fastify server instance.
 * Registers all plugins, routes, middleware, and Swagger docs.
 */
export async function buildServer() {
  const server = Fastify({
    logger: {
      level: NODE_ENV === 'production' ? 'info' : 'debug',
      transport: NODE_ENV === 'development' ? { target: 'pino-pretty' } : undefined,
    },
  });

  // ── Plugins ──────────────────────────────────────────────────────────────────

  await server.register(cors, {
    origin: true,
    credentials: true,
  });

  await server.register(jwt, {
    secret: JWT_SECRET,
    sign: { expiresIn: '24h' },
  });

  await server.register(rateLimit, {
    max: 100,
    timeWindow: '1 minute',
  });

  await server.register(swagger, {
    openapi: {
      info: {
        title: 'MBM Lead Engine v3 API',
        description: 'REST API for property intelligence and lead generation platform',
        version: '3.0.0',
      },
      servers: [
        { url: `http://localhost:${PORT}`, description: 'Development' },
      ],
      components: {
        securitySchemes: {
          bearerAuth: {
            type: 'http',
            scheme: 'bearer',
            bearerFormat: 'JWT',
          },
        },
      },
    },
  });

  await server.register(swaggerUi, {
    routePrefix: '/docs',
  });

  // ── Auth middleware ──────────────────────────────────────────────────────────
  await server.register(authPlugin);

  // ── Routes ───────────────────────────────────────────────────────────────────
  await server.register(propertyRoutes);
  await server.register(leadRoutes);
  await server.register(clientRoutes);
  await server.register(importRoutes);
  await server.register(exportRoutes);
  await server.register(dashboardRoutes);
  await server.register(adminRoutes);
  await server.register(outreachRoutes);

  // ── Health check ─────────────────────────────────────────────────────────────
  server.get('/health', {
    schema: {
      summary: 'Health check',
      tags: ['System'],
      response: { 200: { type: 'object' } },
    },
  }, async () => {
    const dbStart = Date.now();
    await prisma.$queryRaw`SELECT 1`;
    const dbLatency = Date.now() - dbStart;

    return {
      status: 'ok',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      environment: NODE_ENV,
      db: {
        connected: true,
        latency: dbLatency,
      },
    };
  });

  // ── Swagger docs redirect ──────────────────────────────────────────────────
  server.get('/', async (_req, reply) => {
    reply.redirect('/docs');
  });

  return server;
}

/**
 * Starts the server and handles graceful shutdown on SIGINT / SIGTERM.
 */
export async function startServer() {
  const server = await buildServer();

  const shutdown = async (signal: string) => {
    server.log.info(`Received ${signal} — shutting down gracefully`);
    await server.close();
    await prisma.$disconnect();
    process.exit(0);
  };

  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));

  try {
    await server.listen({ port: PORT, host: HOST });
    server.log.info(`Server listening on ${HOST}:${PORT}`);
    server.log.info(`Swagger docs at http://localhost:${PORT}/docs`);
  } catch (err) {
    server.log.error(err);
    await prisma.$disconnect();
    process.exit(1);
  }
}

// ── Start if executed directly ────────────────────────────────────────────────
if (require.main === module) {
  startServer();
}
