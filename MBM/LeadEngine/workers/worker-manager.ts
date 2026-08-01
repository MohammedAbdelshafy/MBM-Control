import { Worker, type WorkerOptions } from 'bullmq';
import pino from 'pino';
import { QueueManager } from './queue';
import { handleImport } from './handlers/import-handler';
import { handleScoring } from './handlers/scoring-handler';
import { handleExport } from './handlers/export-handler';
import { handleCleanup } from './handlers/cleanup-handler';
import { handleEnrichment } from './handlers/enrichment-handler';

const logger = pino({ name: 'worker-manager' });

type JobHandler = (job: { id: string; data: unknown }) => Promise<unknown>;

const HANDLER_MAP: Record<string, JobHandler> = {
  import: handleImport,
  scoring: handleScoring,
  export: handleExport,
  cleanup: handleCleanup,
  enrichment: handleEnrichment,
  outreach: async (job) => {
    logger.info({ jobId: job.id, data: job.data }, 'Outreach job stub');
    return { processed: true, note: 'outreach handler not yet implemented' };
  },
};

const activeWorkers: Worker[] = [];

export function startWorkers(): void {
  const connection = QueueManager.getConnection();
  const queueNames = ['import', 'scoring', 'export', 'cleanup', 'enrichment', 'outreach'];

  for (const name of queueNames) {
    const handler = HANDLER_MAP[name];
    if (!handler) {
      logger.warn({ queue: name }, 'No handler registered, skipping worker');
      continue;
    }

    const options: WorkerOptions = {
      connection,
      concurrency: name === 'scoring' ? 4 : name === 'import' ? 2 : 1,
      lockDuration: 60_000,
      stalledInterval: 30_000,
      maxStalledCount: 3,
    };

    const worker = new Worker(name, async (job) => {
      const start = Date.now();
      logger.info({ jobId: job.id, queue: name }, 'Job started');
      try {
        const result = await handler({ id: job.id!, data: job.data });
        const duration = Date.now() - start;
        logger.info({ jobId: job.id, queue: name, duration }, 'Job completed');
        return result;
      } catch (err) {
        const duration = Date.now() - start;
        logger.error({ err, jobId: job.id, queue: name, duration }, 'Job failed');
        throw err;
      }
    }, options);

    worker.on('failed', (job, err) => {
      logger.error(
        { err, jobId: job?.id, queue: name, attempts: job?.attemptsMade },
        'Worker job failed',
      );
    });

    worker.on('completed', (job) => {
      logger.info({ jobId: job.id, queue: name }, 'Worker job completed');
    });

    activeWorkers.push(worker);
    logger.info({ queue: name, concurrency: options.concurrency }, 'Worker started');
  }
}

export async function stopWorkers(): Promise<void> {
  logger.info({ count: activeWorkers.length }, 'Shutting down workers');

  await Promise.all(
    activeWorkers.map(async (worker) => {
      try {
        await worker.close(true);
        logger.info({ queue: worker.name }, 'Worker closed');
      } catch (err) {
        logger.error({ err, queue: worker.name }, 'Error closing worker');
      }
    }),
  );

  activeWorkers.length = 0;
  logger.info('All workers stopped');
}

process.on('SIGTERM', async () => {
  logger.info('Received SIGTERM, shutting down gracefully');
  await stopWorkers();
  await QueueManager.closeAll();
  process.exit(0);
});

process.on('SIGINT', async () => {
  logger.info('Received SIGINT, shutting down gracefully');
  await stopWorkers();
  await QueueManager.closeAll();
  process.exit(0);
});
