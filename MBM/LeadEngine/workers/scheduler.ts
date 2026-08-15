import { type JobsOptions } from 'bullmq';
import pino from 'pino';
import { QueueManager } from './queue';

const logger = pino({ name: 'scheduler' });

const REPEATABLE_JOBS: {
  queueName: string;
  jobName: string;
  data?: Record<string, unknown>;
  opts: JobsOptions & { pattern?: string; every?: number };
}[] = [
  {
    queueName: 'scoring',
    jobName: 're-score-active-leads',
    data: { type: 'batch-rescore' },
    opts: { pattern: '0 0 * * *', jobId: 're-score-active-leads' },
  },
  {
    queueName: 'cleanup',
    jobName: 'cleanup-maintenance',
    opts: { pattern: '0 */12 * * *', jobId: 'cleanup-maintenance' },
  },
  {
    queueName: 'import',
    jobName: 'check-stale-imports',
    data: { type: 'stale-check' },
    opts: { every: 30 * 60 * 1000, jobId: 'check-stale-imports' },
  },
  {
    queueName: 'export',
    jobName: 'generate-weekly-report',
    data: { type: 'weekly-report' },
    opts: { pattern: '0 6 * * 1', jobId: 'generate-weekly-report' },
  },
];

export async function setupSchedulers(): Promise<void> {
  const connection = QueueManager.getConnection();

  // BullMQ v5: repeatable jobs are registered directly on the Queue — no
  // separate QueueScheduler instance exists in v5 (removed API).

  for (const { queueName, jobName, data, opts } of REPEATABLE_JOBS) {
    try {
      const queue = QueueManager.getQueue(queueName);

      const exists = await queue.getJob(opts.jobId as string);
      if (exists) {
        logger.info({ queueName, jobName }, 'Repeatable job already registered, skipping');
        continue;
      }

      await queue.add(jobName, data ?? {}, {
        ...opts,
        removeOnComplete: { age: 7 * 24 * 3600 },
        removeOnFail: { age: 14 * 24 * 3600 },
      });

      logger.info({ queueName, jobName, pattern: opts.pattern ?? opts.every }, 'Repeatable job registered');
    } catch (err) {
      logger.error({ err, queueName, jobName }, 'Failed to register repeatable job');
    }
  }

  logger.info('All schedulers initialized');
}

export async function teardownSchedulers(): Promise<void> {
  logger.info('Tearing down schedulers');

  for (const { queueName, opts } of REPEATABLE_JOBS) {
    try {
      const queue = QueueManager.getQueue(queueName);
      await queue.removeRepeatableByKey(opts.jobId as string);
      logger.info({ queueName, jobId: opts.jobId }, 'Repeatable job removed');
    } catch (err) {
      logger.error({ err, queueName, jobId: opts.jobId }, 'Failed to remove repeatable job');
    }
  }
}
