import fs from 'fs/promises';
import path from 'path';
import pino from 'pino';
import { getDb } from '../db';

const logger = pino({ name: 'cleanup-handler' });

interface CleanupSummary {
  staleJobsRemoved: number;
  exportsArchived: number;
  tempFilesCleaned: number;
  errors: string[];
}

const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;
const NINETY_DAYS_MS = 90 * 24 * 60 * 60 * 1000;

export async function handleCleanup(): Promise<CleanupSummary> {
  const db = getDb();
  const summary: CleanupSummary = {
    staleJobsRemoved: 0,
    exportsArchived: 0,
    tempFilesCleaned: 0,
    errors: [],
  };

  logger.info('Starting cleanup job');

  try {
    const staleCutoff = new Date(Date.now() - THIRTY_DAYS_MS);

    const staleJobs = await db.job.deleteMany({
      where: {
        createdAt: { lt: staleCutoff },
        status: { in: ['COMPLETED', 'FAILED', 'CANCELLED'] },
      },
    });

    summary.staleJobsRemoved = staleJobs.count;
    logger.info({ removed: staleJobs.count }, 'Stale job records removed');
  } catch (err) {
    const msg = `Stale job cleanup failed: ${(err as Error).message}`;
    logger.error({ err }, msg);
    summary.errors.push(msg);
  }

  try {
    const archiveCutoff = new Date(Date.now() - NINETY_DAYS_MS);

    const oldExports = await db.export.findMany({
      where: { createdAt: { lt: archiveCutoff } },
      select: { id: true, filePath: true },
    });

    for (const exp of oldExports) {
      if (exp.filePath) {
        try {
          await fs.unlink(exp.filePath);
          summary.tempFilesCleaned++;
        } catch {
          // file may already be gone
        }
      }
    }

    summary.exportsArchived = oldExports.length;
    logger.info({ archived: oldExports.length }, 'Old export records identified');
  } catch (err) {
    const msg = `Export archive failed: ${(err as Error).message}`;
    logger.error({ err }, msg);
    summary.errors.push(msg);
  }

  try {
    const tempDir = process.env.STORAGE_PATH || './data/exports';
    const tempCutoff = Date.now() - 24 * 60 * 60 * 1000;

    try {
      const files = await fs.readdir(tempDir);
      for (const file of files) {
        try {
          const filePath = path.join(tempDir, file);
          const stat = await fs.stat(filePath);
          if (stat.isFile() && stat.mtimeMs < tempCutoff) {
            await fs.unlink(filePath);
            summary.tempFilesCleaned++;
          }
        } catch {
          // skip individual file errors
        }
      }
    } catch {
      // directory may not exist
    }

    logger.info({ cleaned: summary.tempFilesCleaned }, 'Temp files cleaned');
  } catch (err) {
    const msg = `Temp file cleanup failed: ${(err as Error).message}`;
    logger.error({ err }, msg);
    summary.errors.push(msg);
  }

  logger.info(
    {
      staleJobsRemoved: summary.staleJobsRemoved,
      exportsArchived: summary.exportsArchived,
      tempFilesCleaned: summary.tempFilesCleaned,
      errors: summary.errors.length,
    },
    'Cleanup completed',
  );

  return summary;
}
