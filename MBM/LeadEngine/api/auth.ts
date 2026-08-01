import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import fp from 'fastify-plugin';

export interface JwtPayload {
  sub: string;
  role: 'admin' | 'client';
  clientId?: string;
}

declare module 'fastify' {
  interface FastifyInstance {
    authenticate: (request: FastifyRequest, reply: FastifyReply) => Promise<void>;
    requireRole: (...roles: string[]) => (request: FastifyRequest, reply: FastifyReply) => Promise<void>;
  }

  interface FastifyRequest {
    user: JwtPayload;
  }
}

/**
 * Registers JWT verification, role-based access, and a rate-limit helper.
 *
 * Adds `authenticate` and `requireRole` decorators to the Fastify instance.
 */
export default fp(async function authPlugin(fastify: FastifyInstance): Promise<void> {
  if (!fastify.jwt) {
    throw new Error('@fastify/jwt must be registered before authPlugin');
  }

  /**
   * Verifies the Bearer token and attaches `request.user`.
   */
  fastify.decorate('authenticate', async function authenticate(request: FastifyRequest, reply: FastifyReply): Promise<void> {
    try {
      await request.jwtVerify();
    } catch {
      reply.status(401).send({ error: 'Unauthorized', message: 'Invalid or expired token' });
    }
  });

  /**
   * Returns a preHandler that checks the user's role against the allowed list.
   */
  fastify.decorate('requireRole', (...roles: string[]) => {
    return async function roleGuard(request: FastifyRequest, reply: FastifyReply): Promise<void> {
      if (!request.user) {
        reply.status(401).send({ error: 'Unauthorized', message: 'Authentication required' });
        return;
      }
      if (!roles.includes(request.user.role)) {
        reply.status(403).send({ error: 'Forbidden', message: `Requires one of: ${roles.join(', ')}` });
        return;
      }
    };
  });
});

export { fp };
