/**
 * MBM Lead Engine v3 — API Layer
 *
 * Barrel re-export for all public API modules.
 */

export { buildServer, startServer } from './server';
export { prisma } from './db';
export { default as authPlugin } from './auth';
export type { JwtPayload } from './auth';

export { default as propertyRoutes } from './routes/properties';
export { default as leadRoutes } from './routes/leads';
export { default as clientRoutes } from './routes/clients';
export { default as importRoutes } from './routes/imports';
export { default as exportRoutes } from './routes/exports';
export { default as dashboardRoutes } from './routes/dashboard';
export { default as adminRoutes } from './routes/admin';
export { default as outreachRoutes } from './routes/outreach';
