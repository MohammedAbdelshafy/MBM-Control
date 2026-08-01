"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { clipsApi, publishApi, type Clip } from "@/lib/api";
import { toast } from "sonner";
import { CheckCircle2, XCircle, Download, RefreshCw, Send, Sparkles, Flame } from "lucide-react";
import { clsx } from "clsx";

const STATUS_COLORS: Record<string, string> = {
  generating: "badge-blue",
  editing: "badge-blue",
  qc_pending: "badge-yellow",
  qc_pass: "badge-green",
  qc_fail: "badge-red",
  awaiting_approval: "badge-yellow",
  approved: "badge-green",
  rejected_human: "badge-red",
  submitted: "badge-blue",
  accepted: "badge-green",
  rejected_platform: "badge-red",
};

const CLIP_STATUS_FILTERS = [
  "all", "awaiting_approval", "qc_pass", "qc_fail", "submitted", "accepted", "rejected_platform",
];

// Statuses the backend will accept for each action (mirrors clips.py _APPROVABLE / _REJECTABLE)
const APPROVABLE = new Set(["awaiting_approval", "qc_pass", "qc_fail"]);
const REJECTABLE = new Set(["awaiting_approval", "qc_pass", "qc_fail", "approved"]);

export default function ClipsPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [rejectTarget, setRejectTarget] = useState<Clip | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const qc = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["clips", statusFilter, page],
    queryFn: () =>
      clipsApi.list({ status: statusFilter === "all" ? undefined : statusFilter, page }),
    refetchInterval: 10000,
  });

  const enhanceViral = useMutation({
    mutationFn: (id: string) => clipsApi.enhanceViral(id),
    onSuccess: () => {
      toast.success("Viral video comparison & tag enhancement completed!");
      qc.invalidateQueries({ queryKey: ["clips"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const approve = useMutation({
    mutationFn: (id: string) => clipsApi.approve(id),
    onSuccess: () => { toast.success("Clip approved — queued for delivery"); qc.invalidateQueries({ queryKey: ["clips"] }); },
    onError: (e: Error) => toast.error(e.message),
  });

  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      clipsApi.reject(id, reason),
    onSuccess: () => {
      toast.success("Clip rejected");
      setRejectTarget(null);
      setRejectReason("");
      qc.invalidateQueries({ queryKey: ["clips"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const download = useMutation({
    mutationFn: async (id: string) => {
      const { url } = await clipsApi.getDownloadUrl(id);
      window.open(url, "_blank");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Clips</h1>
          <p className="text-sm text-gray-500 mt-1">{data?.total ?? "..."} clips total</p>
        </div>
        <button onClick={() => refetch()} className="btn-ghost flex items-center gap-2">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-1 mb-6 overflow-x-auto pb-1">
        {CLIP_STATUS_FILTERS.map((s) => (
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
            {s === "all" ? "All" : s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-48 text-gray-500">Loading...</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {data?.items.map((clip) => (
            <div key={clip.id} className="card flex flex-col gap-3">
              {/* Video preview placeholder */}
              <div className="aspect-[9/16] bg-gray-800 rounded-lg flex items-center justify-center relative overflow-hidden">
                <span className="text-gray-600 text-xs">
                  {clip.width && clip.height ? `${clip.width}×${clip.height}` : "Video"}
                </span>
                <div className="absolute top-2 right-2 flex flex-col gap-1 items-end">
                  <span className={STATUS_COLORS[clip.status] ?? "badge-gray"}>
                    {clip.status.replace(/_/g, " ")}
                  </span>
                  {clip.viral_benchmark?.tier && (
                    <span className="inline-flex items-center gap-1 bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] px-2 py-0.5 rounded-full font-semibold">
                      <Flame className="w-3 h-3 text-amber-400 fill-amber-400" />
                      {clip.viral_benchmark.tier} ({clip.viral_benchmark.overall_viral_score}%)
                    </span>
                  )}
                </div>
              </div>

              {/* Score bar */}
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      "h-full rounded-full",
                      clip.overall_score >= 0.8
                        ? "bg-green-500"
                        : clip.overall_score >= 0.6
                        ? "bg-yellow-500"
                        : "bg-red-500"
                    )}
                    style={{ width: `${clip.overall_score * 100}%` }}
                  />
                </div>
                <span className="text-xs text-gray-400">
                  {(clip.overall_score * 100).toFixed(0)}%
                </span>
              </div>

              {/* Meta */}
              <div className="text-xs text-gray-500 space-y-1">
                {clip.duration_seconds && (
                  <p>Duration: {clip.duration_seconds.toFixed(1)}s</p>
                )}
                {clip.hook_text && (
                  <p className="text-gray-400 italic">"{clip.hook_text}"</p>
                )}
                {clip.enhanced_tags && clip.enhanced_tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {clip.enhanced_tags.slice(0, 4).map((tag, idx) => (
                      <span key={idx} className="bg-gray-800 text-gray-300 text-[10px] px-1.5 py-0.5 rounded border border-gray-700">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                {clip.qc_notes && <p className="text-red-400">{clip.qc_notes.slice(0, 60)}</p>}
              </div>

              {/* Actions */}
              <div className="flex flex-wrap gap-1 pt-1">
                <button
                  type="button"
                  onClick={() => enhanceViral.mutate(clip.id)}
                  disabled={enhanceViral.isPending}
                  className="flex-1 flex items-center justify-center gap-1 btn-ghost text-amber-400 hover:text-amber-300 text-xs py-1.5"
                  title="Compare with viral video benchmarks & enhance tags"
                >
                  <Sparkles className="w-3 h-3 text-amber-400" />
                  {enhanceViral.isPending ? "Enhancing..." : "Enhance Viral"}
                </button>
                {(APPROVABLE.has(clip.status) || clip.status === "approved") && (
                  <button
                    type="button"
                    onClick={() => publishApi.publishClip(clip.id, ["all"]).then(() => { toast.success("Published to all platforms"); qc.invalidateQueries({ queryKey: ["clips"] }); }).catch(e => toast.error(e.message))}
                    className="flex-1 flex items-center justify-center gap-1 btn-ghost text-purple-400 hover:text-purple-300 text-xs py-1.5"
                  >
                    <Send className="w-3 h-3" />
                    Publish All
                  </button>
                )}
                {APPROVABLE.has(clip.status) && (
                  <button
                    type="button"
                    onClick={() => approve.mutate(clip.id)}
                    className="flex-1 flex items-center justify-center gap-1 btn-ghost text-green-400 hover:text-green-300 text-xs py-1.5"
                  >
                    <CheckCircle2 className="w-3 h-3" />
                    Approve
                  </button>
                )}
                {REJECTABLE.has(clip.status) && (
                  <button
                    type="button"
                    onClick={() => { setRejectTarget(clip); setRejectReason(""); }}
                    className="flex-1 flex items-center justify-center gap-1 btn-ghost text-red-400 hover:text-red-300 text-xs py-1.5"
                  >
                    <XCircle className="w-3 h-3" />
                    Reject
                  </button>
                )}
                <button
                  type="button"
                  title="Download clip"
                  onClick={() => download.mutate(clip.id)}
                  className="btn-ghost px-2 text-gray-400"
                >
                  <Download className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
          {!data?.items.length && (
            <div className="col-span-full text-center text-gray-500 py-12">
              No clips found for this filter
            </div>
          )}
        </div>
      )}

      {/* Reject reason modal */}
      {rejectTarget && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setRejectTarget(null)}
        >
          <div className="card w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-100 mb-1">Reject clip</h2>
            <p className="text-xs text-gray-500 mb-4">
              {rejectTarget.hook_text ? `"${rejectTarget.hook_text}"` : `Clip ${rejectTarget.id.slice(0, 8)}`}
            </p>
            <label className="text-xs text-gray-400 mb-1 block">Reason (optional)</label>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              autoFocus
              rows={3}
              placeholder="e.g. Hook is weak, audio clipping at 0:04…"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-brand-500 resize-none"
            />
            <div className="flex gap-2 mt-4 justify-end">
              <button type="button" onClick={() => setRejectTarget(null)} className="btn-ghost">
                Cancel
              </button>
              <button
                type="button"
                onClick={() =>
                  reject.mutate({
                    id: rejectTarget.id,
                    reason: rejectReason.trim() || "Rejected by operator",
                  })
                }
                disabled={reject.isPending}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                Reject clip
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
