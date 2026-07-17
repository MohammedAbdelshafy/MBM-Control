"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { campaignsApi, type Campaign } from "@/lib/api";
import { toast } from "sonner";
import { RefreshCw, Play, Pause, RotateCcw, Trash2, ChevronRight } from "lucide-react";
import { clsx } from "clsx";
import Link from "next/link";

const STATUS_COLORS: Record<string, string> = {
  discovered: "badge-blue",
  analyzing: "badge-yellow",
  ready: "badge-green",
  processing: "badge-yellow",
  qc: "badge-yellow",
  awaiting_approval: "badge-yellow",
  delivering: "badge-blue",
  completed: "badge-green",
  failed: "badge-red",
  paused: "badge-gray",
  expired: "badge-gray",
};

const STATUS_FILTERS = [
  "all", "discovered", "ready", "processing", "awaiting_approval",
  "delivering", "completed", "failed", "paused",
];

export default function CampaignsPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [deleteTarget, setDeleteTarget] = useState<Campaign | null>(null);
  const qc = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["campaigns", statusFilter, page],
    queryFn: () =>
      campaignsApi.list({
        status: statusFilter === "all" ? undefined : statusFilter,
        page,
        per_page: 20,
      }),
    refetchInterval: 15000,
  });

  const pause = useMutation({
    mutationFn: (id: string) => campaignsApi.pause(id),
    onSuccess: () => { toast.success("Campaign paused"); qc.invalidateQueries({ queryKey: ["campaigns"] }); },
    onError: (e: Error) => toast.error(e.message),
  });

  const resume = useMutation({
    mutationFn: (id: string) => campaignsApi.resume(id),
    onSuccess: () => { toast.success("Campaign resumed"); qc.invalidateQueries({ queryKey: ["campaigns"] }); },
    onError: (e: Error) => toast.error(e.message),
  });

  const reprocess = useMutation({
    mutationFn: (id: string) => campaignsApi.reprocess(id),
    onSuccess: () => { toast.success("Reprocessing started"); qc.invalidateQueries({ queryKey: ["campaigns"] }); },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: (id: string) => campaignsApi.delete(id),
    onSuccess: () => {
      toast.success("Campaign removed");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Campaigns</h1>
          <p className="text-sm text-gray-500 mt-1">
            {data?.total ?? "..."} campaigns total
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="btn-ghost flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-1 mb-6 overflow-x-auto pb-1">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => { setStatusFilter(s); setPage(1); }}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-xs font-medium capitalize whitespace-nowrap transition-colors",
              statusFilter === s
                ? "bg-brand-500 text-white"
                : "bg-gray-800 text-gray-400 hover:text-gray-100"
            )}
          >
            {s === "all" ? "All" : s.replace("_", " ")}
          </button>
        ))}
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center h-48 text-gray-500">Loading...</div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left px-6 py-3 text-gray-400 font-medium">Campaign</th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Status</th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Score</th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Payout Rate</th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Clips</th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Earnings</th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Due</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {data?.items.map((c) => (
                <tr key={c.id} className="hover:bg-gray-800/50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="font-medium text-gray-100 truncate max-w-xs">
                      {c.title}
                    </div>
                    <div className="flex items-center gap-1.5 mt-1">
                      {c.brand_name && (
                        <span className="text-xs text-gray-500">{c.brand_name}</span>
                      )}
                      {c.brand_name && c.platform_name && <span className="text-gray-700 text-xs">•</span>}
                      {c.platform_name && (
                        <span className="text-xs text-brand-400 font-semibold">{c.platform_name}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <span className={STATUS_COLORS[c.status] ?? "badge-gray"}>
                      {c.status.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-brand-500 rounded-full"
                          style={{ width: `${(c.opportunity_score || 0) * 100}%` }}
                        />
                      </div>
                      <span className="text-gray-400 text-xs">
                        {((c.opportunity_score || 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-gray-300">
                    {c.payment ? (
                      <span>${c.payment} <span className="text-gray-500 text-xs">/ clip</span></span>
                    ) : c.payout_per_1k_views ? (
                      <span>${c.payout_per_1k_views} <span className="text-gray-500 text-xs">/ 1k views</span></span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-4 text-gray-400">
                    <span className="text-green-400">{c.clips_accepted}</span>
                    <span className="text-gray-600">/</span>
                    <span>{c.clips_submitted}</span>
                    <span className="text-gray-600">/</span>
                    <span>{c.clips_generated}</span>
                  </td>
                  <td className="px-4 py-4 text-green-400 font-medium">
                    ${(c.actual_earnings || 0).toFixed(2)}
                  </td>
                  <td className="px-4 py-4 text-gray-400 text-xs">
                    {c.due_at ? new Date(c.due_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-1">
                      {c.status === "processing" || c.status === "ready" ? (
                        <button
                          onClick={() => pause.mutate(c.id)}
                          className="btn-ghost p-1.5"
                          title="Pause"
                        >
                          <Pause className="w-3.5 h-3.5" />
                        </button>
                      ) : c.status === "paused" ? (
                        <button
                          onClick={() => resume.mutate(c.id)}
                          className="btn-ghost p-1.5"
                          title="Resume"
                        >
                          <Play className="w-3.5 h-3.5" />
                        </button>
                      ) : null}
                      <button
                        onClick={() => reprocess.mutate(c.id)}
                        className="btn-ghost p-1.5"
                        title="Reprocess"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setDeleteTarget(c)}
                        className="btn-ghost p-1.5 text-red-400 hover:text-red-300"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      <Link
                        href={`/campaigns/${c.id}`}
                        className="btn-ghost p-1.5"
                        title="View"
                      >
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
              {!data?.items.length && (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center text-gray-500">
                    No campaigns found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {data && data.total > 20 && (
        <div className="flex items-center justify-between mt-4 text-sm text-gray-400">
          <span>
            Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, data.total)} of {data.total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-ghost disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * 20 >= data.total}
              className="btn-ghost disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {deleteTarget && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setDeleteTarget(null)}
        >
          <div className="card w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-100 mb-2">Delete campaign?</h2>
            <p className="text-sm text-gray-400 mb-5">
              This deactivates{" "}
              <span className="text-gray-200">{deleteTarget.title}</span> and stops
              all processing. This cannot be undone from the dashboard.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteTarget(null)} className="btn-ghost">
                Cancel
              </button>
              <button
                onClick={() => remove.mutate(deleteTarget.id)}
                disabled={remove.isPending}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
