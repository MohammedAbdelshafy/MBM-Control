import { Queue, type QueueOptions, type JobsOptions } from 'bullmq';
import IORedis from 'ioredis';
import pino from 'pino';

const logger = pino({ name: 'queue-manager' });

export interface QueueConfig {
  concurrency: number;
  retryAttempts: number;
  retryDelayMs: number;
}

const DEFAULT_QUEUE_CONFIGS: Record<string, QueueConfig> = {
  import: { concurrency: 2, retryAttempts: 3, retryDelayMs: 5_000 },
  scoring: { concurrency: 4, retryAttempts: 2, retryDelayMs: 10_000 },
  export: { concurrency: 1, retryAttempts: 3, retryDelayMs: 15_000 },
  enrichment: { concurrency: 3, retryAttempts: 2, retryDelayMs: 10_000 },
  outreach: { concurrency: 2, retryAttempts: 3, retryDelayMs: 30_000 },
  cleanup: { concurrency: 1, retryAttempts: 1, retryDelayMs: 5_000 },
};

class QueueManagerImpl {
  private connection: IORedis;
  private queues: Map<string, Queue> = new Map();

  constructor() {
    const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
    this.connection = new IORedis(redisUrl, {
      maxRetriesPerRequest: null,
      enableReadyCheck: false,
      retryStrategy: (times: number) => Math.min(times * 100, 5_000),
    });

    this.connection.on('connect', () => logger.info('Redis connected'));
    this.connection.on('error', (err) => logger.error({ err }, 'Redis error'));
  }

  getQueue(name: string): Queue {
    const existing = this.queues.get(name);
    if (existing) return existing;

    const config = DEFAULT_QUEUE_CONFIGS[name] ?? {
      concurrency: 1,
      retryAttempts: 3,
      retryDelayMs: 10_000,
    };

    const defaultJobOptions: JobsOptions = {
      attempts: config.retryAttempts,
      backoff: {
        type: 'exponential',
        delay: config.retryDelayMs,
      },
      removeOnComplete: { age: 7 * 24 * 3600, count: 500 },
      removeOnFail: { age: 14 * 24 * 3600, count: 200 },
    };

    const options: QueueOptions = {
      connection: this.connection,
      defaultJobOptions,
    };

    const queue = new Queue(name, options);
    this.queues.set(name, queue);
    logger.info({ queue: name }, 'Queue created');

    return queue;
  }

  async closeAll(): Promise<void> {
    const entries = Array.from(this.queues.entries());
    await Promise.all(
      entries.map(async ([name, queue]) => {
        try {
          await queue.close();
          logger.info({ queue: name }, 'Queue closed');
        } catch (err) {
          logger.error({ err, queue: name }, 'Error closing queue');
        }
      }),
    );
    this.queues.clear();
    await this.connection.quit();
  }

  getConnection(): IORedis {
    return this.connection;
  }
}

export const QueueManager = new QueueManagerImpl();
export const getQueue = QueueManager.getQueue.bind(QueueManager);
