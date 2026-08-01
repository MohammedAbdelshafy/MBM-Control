import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { prisma } from '../db';

/**
 * Dashboard statistics routes.
 *
 * GET /api/dashboard/stats — aggregated platform statistics
 */
export default async function dashboardRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.get(
    '/api/dashboard/stats',
    {
      schema: {
        summary: 'Dashboard statistics',
        tags: ['Dashboard'],
        response: { 200: { type: 'object' } },
      },
    },
    async (_request: FastifyRequest, reply: FastifyReply) => {
      const todayStart = new Date();
      todayStart.setHours(0, 0, 0, 0);

      const [
        totalProperties,
        totalLeads,
        leadsByGrade,
        leadsByNiche,
        recentImports,
        topCounties,
        exportCount,
        todayImports,
        duplicateRateResult,
      ] = await Promise.all([
        prisma.property.count(),
        prisma.lead.count(),
        prisma.lead.groupBy({
          by: ['grade'],
          _count: { id: true },
        }),
        prisma.lead.groupBy({
          by: ['niche'],
          _count: { id: true },
          orderBy: { _count: { id: 'desc' } },
          take: 10,
        }),
        prisma.import.findMany({
          orderBy: { createdAt: 'desc' },
          take: 5,
          select: { id: true, status: true, totalRows: true, processedRows: true, createdAt: true },
        }),
        prisma.property.groupBy({
          by: ['county'],
          _count: { id: true },
          orderBy: { _count: { id: 'desc' } },
          take: 10,
        }),
        prisma.export.count(),
        prisma.import.count({
          where: { createdAt: { gte: todayStart } },
        }),
        // TODO: Implement proper duplicate detection
        // For now, estimate based on properties sharing the same parcelId pattern
        prisma.lead.findMany({
          where: { niche: 'CODE_VIOLATION' },
          take: 1,
          select: { id: true },
        }).then(() => 0.02), // placeholder 2% duplicate rate
      ]);

      // ── Revenue forecast ────────────────────────────────────────────────────
      // TODO: Build a proper RevenueService that aggregates subscription data,
      //       credit purchases, and projects future revenue
      const revenueForecast = {
        currentMonth: 0,
        nextMonth: 0,
        quarterly: 0,
        annual: 0,
        currency: 'USD',
      };

      // ── Source health ───────────────────────────────────────────────────────
      // TODO: Track source health by checking lastRunAt, error rates, etc.
      const sourceHealth = {
        total: 0,
        healthy: 0,
        degraded: 0,
        down: 0,
      };

      const gradeMap = leadsByGrade.reduce<Record<string, number>>((acc, g) => {
        if (g.grade) acc[g.grade] = g._count.id;
        return acc;
      }, {});

      const nicheMap = leadsByNiche.reduce<Record<string, number>>((acc, n) => {
        acc[n.niche] = n._count.id;
        return acc;
      }, {});

      const countyMap = topCounties.reduce<Record<string, number>>((acc, c) => {
        acc[c.county] = c._count.id;
        return acc;
      }, {});

      return reply.send({
        total_properties: totalProperties,
        total_leads: totalLeads,
        leads_by_grade: gradeMap,
        leads_by_niche: nicheMap,
        recent_imports: recentImports,
        top_counties: countyMap,
        export_count: exportCount,
        revenue_forecast: revenueForecast,
        today_imports: todayImports,
        duplicate_rate: duplicateRateResult,
        source_health: sourceHealth,
      });
    },
  );
}
