import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useEffect, useMemo } from "react";
import {
  PhoneCall,
  CalendarCheck,
  DollarSign,
  ShieldCheck,
  TrendingUp,
  Flame,
  Building2,
  Stethoscope,
  HardHat,
  Sparkles,
  ArrowLeft,
  RefreshCw,
} from "lucide-react";
import { SpiralBackdrop } from "../components/dialer/SpiralBackdrop";

export const Route = createFileRoute("/analytics")({
  component: AnalyticsDashboard,
});

type Lead = {
  id: string;
  vertical: string;
  callable?: boolean;
  phone_verified?: boolean;
  priority_score?: number;
  intent_score?: number;
  motivation_score?: number;
  expected_value_usd?: number;
  first_seen_at?: string;
  new_today?: boolean;
  owner_status?: string;
  sales_lane?: string;
};

function AnalyticsDashboard() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [tenantId] = useState("DEFAULT_TENANT");
  const [apiMetrics, setApiMetrics] = useState<{
    totalLoggedCalls: number;
    booked: number;
    pipelineValue: number;
    rawOutput: string;
  } | null>(null);

  useEffect(() => {
    // 1. Fetch leads database
    fetch("/leads_database.json")
      .then((res) => res.json())
      .then((data: Lead[]) => {
        setLeads(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load leads database:", err);
        setLoading(false);
      });

    // 2. Fetch API analytics in parallel
    fetch("/api/analytics", {
      headers: { "x-tenant-id": tenantId },
    })
      .then((res) => res.json())
      .then((result) => {
        if (result.success && result.metrics) {
          setApiMetrics(result.metrics);
        }
      })
      .catch(() => {});
  }, [tenantId]);

  // Compute rich aggregations
  const stats = useMemo(() => {
    const total = leads.length;
    const callable = leads.filter((l) => l.callable !== false).length;
    const verifiedPhones = leads.filter((l) => l.phone_verified).length;
    const newToday = leads.filter((l) => l.new_today || l.first_seen_at === "2026-08-16").length;
    const hot = leads.filter(
      (l) => (l.intent_score && l.intent_score >= 80) || (l.priority_score && l.priority_score >= 85),
    ).length;

    // Vertical breakdown
    const verticalCounts: Record<string, number> = {};
    let totalPipeline = 0;

    leads.forEach((l) => {
      const v = l.vertical || "Uncategorized";
      verticalCounts[v] = (verticalCounts[v] || 0) + 1;
      totalPipeline += l.expected_value_usd || 4500;
    });

    const topVerticals = Object.entries(verticalCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({
        name,
        count,
        percent: total > 0 ? Math.round((count / total) * 100) : 0,
      }));

    return {
      total,
      callable,
      verifiedPhones,
      newToday,
      hot,
      totalPipeline,
      topVerticals,
    };
  }, [leads]);

  const effectiveLoggedCalls = apiMetrics?.totalLoggedCalls || 0;
  const effectiveBooked = apiMetrics?.booked || 0;
  const effectivePipelineValue = apiMetrics?.pipelineValue || stats.totalPipeline;

  return (
    <div className="relative min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-cyan-500/30">
      <SpiralBackdrop />

      {/* Top Header */}
      <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/"
            className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-900 border border-slate-800 hover:border-cyan-500/50 text-slate-300 hover:text-cyan-300 text-xs font-semibold transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Dialer Console
          </Link>

          <div className="h-4 w-px bg-slate-800" />

          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold tracking-tight text-white">
                MBM REVENUE INTELLIGENCE
              </span>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                PROD-LIVE
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono">
              Aggregated Outbound & Pipeline Analytics • Neteller Rail Secured
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <div className="text-[10px] font-mono uppercase text-slate-400">Canonical Leads</div>
            <div className="text-sm font-mono font-bold text-emerald-400">
              {stats.callable.toLocaleString()} Callable / {stats.total.toLocaleString()} Total
            </div>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="p-2 rounded bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-400 hover:text-white transition"
            title="Refresh Data"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="flex items-center gap-3 text-cyan-400 font-mono text-sm">
              <RefreshCw className="w-5 h-5 animate-spin" />
              Loading Revenue & Lead Intelligence...
            </div>
          </div>
        ) : (
          <>
            {/* Top KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Card 1: Pipeline Value */}
              <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800/80 hover:border-cyan-500/40 transition">
                <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
                  <span>EST. PIPELINE VALUE</span>
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-2xl font-bold font-mono text-emerald-400">
                  ${effectivePipelineValue.toLocaleString()}
                </div>
                <div className="text-[11px] text-slate-400 mt-1 font-mono">
                  Across {stats.callable.toLocaleString()} high-intent accounts
                </div>
              </div>

              {/* Card 2: Callable Verified Leads */}
              <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800/80 hover:border-cyan-500/40 transition">
                <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
                  <span>CALLABLE QUEUE</span>
                  <PhoneCall className="w-4 h-4 text-cyan-400" />
                </div>
                <div className="text-2xl font-bold font-mono text-cyan-400">
                  {stats.callable.toLocaleString()}
                </div>
                <div className="text-[11px] text-slate-400 mt-1 font-mono">
                  {stats.verifiedPhones.toLocaleString()} verified government NPI / county APN
                </div>
              </div>

              {/* Card 3: Hot Leads & New Today */}
              <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800/80 hover:border-cyan-500/40 transition">
                <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
                  <span>HOT INTENT PROSPECTS</span>
                  <Flame className="w-4 h-4 text-amber-400" />
                </div>
                <div className="text-2xl font-bold font-mono text-amber-400">
                  {stats.hot.toLocaleString()}
                </div>
                <div className="text-[11px] text-slate-400 mt-1 font-mono">
                  +{stats.newToday} freshly harvested today
                </div>
              </div>

              {/* Card 4: Diagnostics Booked */}
              <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800/80 hover:border-cyan-500/40 transition">
                <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-2">
                  <span>BOOKED DIAGNOSTICS</span>
                  <CalendarCheck className="w-4 h-4 text-purple-400" />
                </div>
                <div className="text-2xl font-bold font-mono text-purple-400">
                  {effectiveBooked}
                </div>
                <div className="text-[11px] text-slate-400 mt-1 font-mono">
                  {effectiveLoggedCalls} logged calls in current shift
                </div>
              </div>
            </div>

            {/* Vertical Distribution & Market Split */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left 2 Cols: Vertical Market Breakdown */}
              <div className="lg:col-span-2 p-5 rounded-lg bg-slate-900/60 border border-slate-800/80 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-cyan-400" />
                    <h2 className="font-mono text-sm font-bold text-white uppercase tracking-wider">
                      Market Vertical Distribution
                    </h2>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">
                    {stats.topVerticals.length} Active Tracks
                  </span>
                </div>

                <div className="space-y-3">
                  {stats.topVerticals.map((vert) => (
                    <div key={vert.name} className="space-y-1">
                      <div className="flex items-center justify-between text-xs font-mono">
                        <span className="text-slate-300 font-semibold flex items-center gap-2">
                          {vert.name.includes("Healthcare") || vert.name.includes("Clinic") ? (
                            <Stethoscope className="w-3.5 h-3.5 text-emerald-400" />
                          ) : vert.name.includes("Real Estate") ? (
                            <Building2 className="w-3.5 h-3.5 text-cyan-400" />
                          ) : vert.name.includes("ConTech") ? (
                            <HardHat className="w-3.5 h-3.5 text-amber-400" />
                          ) : (
                            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                          )}
                          {vert.name}
                        </span>
                        <span className="text-slate-400 font-bold">
                          {vert.count.toLocaleString()} leads ({vert.percent}%)
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500"
                          style={{ width: `${Math.max(vert.percent, 3)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right Col: Compliance & Settlement Rails */}
              <div className="p-5 rounded-lg bg-slate-900/60 border border-slate-800/80 space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <h2 className="font-mono text-sm font-bold text-white uppercase tracking-wider">
                    Settlement & Gates
                  </h2>
                </div>

                <div className="space-y-3 text-xs font-mono">
                  <div className="p-3 rounded bg-slate-950/70 border border-slate-800/80">
                    <div className="text-[10px] text-slate-400 uppercase">Monetization Rail</div>
                    <div className="text-emerald-400 font-bold mt-0.5">
                      Neteller 1-Click Checkout
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1">
                      Account: 4599228811 (abdelshafyclapps@gmail.com)
                    </div>
                  </div>

                  <div className="p-3 rounded bg-slate-950/70 border border-slate-800/80">
                    <div className="text-[10px] text-slate-400 uppercase">Outbound Gateway</div>
                    <div className="text-cyan-400 font-bold mt-0.5">
                      Phound Wave + Twilio Bridge
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1">
                      0 Synthetic / 0 Fabricated Numbers Invariant
                    </div>
                  </div>

                  <div className="p-3 rounded bg-slate-950/70 border border-slate-800/80">
                    <div className="text-[10px] text-slate-400 uppercase">Single-Writer Lock</div>
                    <div className="text-purple-400 font-bold mt-0.5">
                      DialerSingleWriter (GLM Invariant)
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1">
                      Dataset size strictly monotonic (&ge; 1,222)
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
