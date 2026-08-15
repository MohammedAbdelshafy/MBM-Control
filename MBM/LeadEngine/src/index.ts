/**
 * MBM Lead Engine v3 — Entry Point
 *
 * Boots the Fastify API server and, in the same process, the BullMQ worker
 * fleet + repeatable schedulers. Graceful shutdown on SIGINT/SIGTERM.
 */

import dotenv from 'dotenv';

dotenv.config();

import { buildServer } from '../api/server';
import { prisma } from '../api/db';
import { startWorkers, stopWorkers } from '../workers/worker-manager';
import { setupSchedulers, teardownSchedulers } from '../workers/scheduler';
import { QueueManager } from '../workers/queue';

const PORT = parseInt(process.env.PORT ?? '4000', 10);
const HOST = process.env.HOST ?? '0.0.0.0';
const ENABLE_WORKERS = process.env.ENABLE_WORKERS !== 'false';

async function main(): Promise<void> {
  const server = await buildServer();

  if (ENABLE_WORKERS) {
    startWorkers();
    await setupSchedulers();
  } else {
    console.log('[lead-engine] workers disabled (ENABLE_WORKERS=false)');
  }

  const shutdown = async (signal: string): Promise<void> => {
    console.log(`[lead-engine] received ${signal} — shutting down`);
    await server.close();
    if (ENABLE_WORKERS) {
      await stopWorkers();
      await teardownSchedulers();
      await QueueManager.closeAll();
    }
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

main().catch((err) => {
  console.error('[lead-engine] FATAL startup error:', err);
  process.exit(1);
});