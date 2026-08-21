import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { z } from 'zod';

const QualifyBodySchema = z.object({
  leads: z.array(z.record(z.unknown())).min(1).max(1_000),
  includeLeads: z.boolean().default(false),
});

type QualifyBody = z.infer<typeof QualifyBodySchema>;

async function runQualification(body: QualifyBody): Promise<unknown> {
  const currentDirectory = process.cwd();
  const inferredWorkspaceRoot = existsSync(join(currentDirectory, 'MBM', 'LeadEngine', 'qualification_runner.py'))
    ? currentDirectory
    : resolve(currentDirectory, '..', '..');
  const workspaceRoot = process.env.LEAD_ENGINE_WORKSPACE_ROOT ?? inferredWorkspaceRoot;
  const python = process.env.PYTHON_BIN ?? 'python';
  const args = ['-m', 'MBM.LeadEngine.qualification_runner'];
  if (body.includeLeads) args.push('--include-leads');

  const child = spawn(python, args, {
    cwd: workspaceRoot,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  const stdout: Buffer[] = [];
  const stderr: Buffer[] = [];
  child.stdout.on('data', (chunk: Buffer) => stdout.push(chunk));
  child.stderr.on('data', (chunk: Buffer) => stderr.push(chunk));

  const finished = new Promise<number>((resolveExit, reject) => {
    child.once('error', reject);
    child.once('close', resolveExit);
  });
  child.stdin.end(JSON.stringify({ leads: body.leads }));

  const exitCode = await finished;
  const output = Buffer.concat(stdout).toString('utf8');
  if (exitCode !== 0) {
    throw new Error(Buffer.concat(stderr).toString('utf8').trim() || output || 'Qualification runner failed');
  }
  return JSON.parse(output);
}

/**
 * POST /api/qualify — authenticated, read-only qualification of supplied leads.
 * The Python gate is the canonical policy source; this route does not write queues.
 */
export default async function qualifyRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.post<{ Body: QualifyBody }>(
    '/api/qualify',
    {
      preHandler: [fastify.authenticate],
      schema: {
        summary: 'Qualify supplied lead records without mutating queues',
        tags: ['Qualification'],
        security: [{ bearerAuth: [] }],
        body: {
          type: 'object',
          required: ['leads'],
          properties: {
            leads: { type: 'array', minItems: 1, maxItems: 1000, items: { type: 'object', additionalProperties: true } },
            includeLeads: { type: 'boolean', default: false },
          },
        },
        response: {
          200: { type: 'object', additionalProperties: true },
          400: { type: 'object', additionalProperties: true },
          502: { type: 'object', additionalProperties: true },
        },
      },
    },
    async (request: FastifyRequest<{ Body: QualifyBody }>, reply: FastifyReply) => {
      const body = QualifyBodySchema.parse(request.body);
      try {
        return reply.send(await runQualification(body));
      } catch (error) {
        request.log.error(error, 'lead qualification runner failed');
        return reply.status(502).send({
          status: 'failure',
          errors: ['Qualification service is unavailable.'],
          next_action: 'Check PYTHON_BIN and LEAD_ENGINE_WORKSPACE_ROOT, then retry.',
        });
      }
    },
  );
}
