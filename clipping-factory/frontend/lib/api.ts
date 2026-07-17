/**
 * Typed API client for the Clipping Factory backend.
 * All fetch calls go through this module — never call fetch() directly in components.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_PREFIX = `${BASE_URL}/api/v1`;

// Credentials injected from env / session
const getAuth = (): string => {
  const user = process.env.NEXT_PUBLIC_ADMIN_USER || "admin";
  const pass = process.env.NEXT_PUBLIC_ADMIN_PASS || "";
  return `Basic ${btoa(`${user}:${pass}`)}`;
};

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: getAuth(),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ──────────────────────────────────────────────
// Campaigns
// ──────────────────────────────────────────────

export type CampaignStatus =
  | "discovered" | "analyzing" | "ready" | "processing"
  | "qc" | "awaiting_approval" | "delivering"
  | "completed" | "failed" | "paused" | "expired";

export type ClipStatus =
  | "generating" | "editing" | "qc_pending"
  | "qc_pass" | "qc_fail" | "awaiting_approval"
  | "approved" | "rejected_human" | "submitted"
  | "accepted" | "rejected_platform";

export interface DashboardSummary {
  campaigns: {
    total: number;
    active: number;
    completed: number;
    failed: number;
  };
  clips: {
    total: number;
    submitted: number;
    accepted: number;
    acceptance_rate: number;
  };
  revenue: {
    total_usd: number;
  };
  jobs: {
    running: number;
    failed: number;
  };
  ts: string;
}

export interface RevenuePoint {
  date: string;
  revenue: number;
  clips_generated: number;
  clips_accepted: number;
  acceptance_rate: number;
}

export interface AuditLogEntry {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  old_value: string | null;
  new_value: string | null;
  ts: string;
}

export interface Campaign {
  id: string;
  title: string;
  brand_name: string | null;
  status: CampaignStatus;
  opportunity_score: number;
  payment: number | null;
  payout_per_1k_views: number | null;
  platform_name: string;
  clips_generated: number;
  clips_submitted: number;
  clips_accepted: number;
  actual_earnings: number;
  due_at: string | null;
  created_at: string;
}

export interface CampaignDetail {
  id: string;
  title: string;
  brand_name: string | null;
  status: CampaignStatus;
  requirements: Record<string, unknown>;
  source_url: string | null;
  source_type: string | null;
  opportunity_score: number;
  payment_per_accepted_clip: number | null;
  clips_generated: number;
  clips_submitted: number;
  clips_accepted: number;
  clips_rejected: number;
  actual_earnings: number;
  intelligence_notes: string | null;
  error_message: string | null;
  due_at: string | null;
  created_at: string;
  updated_at: string;
}

export const campaignsApi = {
  list: (params?: { status?: string; page?: number; per_page?: number }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString();
    return apiFetch<{ items: Campaign[]; total: number }>(`/campaigns${q ? `?${q}` : ""}`);
  },
  get: (id: string) => apiFetch<CampaignDetail>(`/campaigns/${id}`),
  pause: (id: string) => apiFetch(`/campaigns/${id}/pause`, { method: "POST" }),
  resume: (id: string) => apiFetch(`/campaigns/${id}/resume`, { method: "POST" }),
  reprocess: (id: string) => apiFetch(`/campaigns/${id}/reprocess`, { method: "POST" }),
  delete: (id: string) => apiFetch(`/campaigns/${id}`, { method: "DELETE" }),
};

// ──────────────────────────────────────────────
// Clips
// ──────────────────────────────────────────────

export interface Clip {
  id: string;
  campaign_id: string;
  status: ClipStatus;
  overall_score: number;
  scores: Record<string, number>;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  hook_text: string | null;
  qc_notes: string | null;
  rejection_reason: string | null;
  edits_applied: string[];
  version: number;
  created_at: string;
}

export const clipsApi = {
  list: (params?: { campaign_id?: string; status?: string; page?: number }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString();
    return apiFetch<{ items: Clip[]; total: number }>(`/clips${q ? `?${q}` : ""}`);
  },
  getDownloadUrl: (id: string) => apiFetch<{ url: string }>(`/clips/${id}/download-url`),
  approve: (id: string) => apiFetch(`/clips/${id}/approve`, { method: "POST" }),
  reject: (id: string, reason?: string) =>
    apiFetch(`/clips/${id}/reject?reason=${encodeURIComponent(reason || "")}`, { method: "POST" }),
};

// ──────────────────────────────────────────────
// Pages
// ──────────────────────────────────────────────

export interface Page {
  id: string;
  name: string;
  email: string;
  is_active: boolean;
  is_paused: boolean;
  campaigns_completed: number;
  total_earnings_usd: number;
  acceptance_rate: number;
  notes: string | null;
  created_at: string;
}

export const pagesApi = {
  list: () => apiFetch<Page[]>("/pages"),
  create: (data: { name: string; email: string; settings?: Record<string, unknown> }) =>
    apiFetch<{ id: string }>("/pages", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Page>) =>
    apiFetch(`/pages/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: string) => apiFetch(`/pages/${id}`, { method: "DELETE" }),
  scan: (id: string) => apiFetch(`/pages/${id}/scan`, { method: "POST" }),
};

// ──────────────────────────────────────────────
// Health
// ──────────────────────────────────────────────

export interface HealthStatus {
  status: "healthy" | "degraded" | "critical" | "unknown";
  services: Record<string, unknown>;
  cpu_percent: number | null;
  memory_percent: number | null;
  disk_percent: number | null;
  alerts: Array<{ level: string; service: string; message: string }>;
  ts: string;
}

export interface Job {
  id: string;
  task: string;
  status: string;
  progress: number | null;
  progress_message: string | null;
  attempt: number;
  error: string | null;
  created_at: string;
}

export const healthApi = {
  get: () => apiFetch<HealthStatus>("/health/"),
  queueDepths: () => apiFetch<Record<string, number>>("/health/queue-depths"),
  jobs: () => apiFetch<Job[]>("/health/jobs"),
  trigger: () => apiFetch<{ task_id: string }>("/health/trigger", { method: "POST" }),
};

// ──────────────────────────────────────────────
// Analytics
// ──────────────────────────────────────────────

export const analyticsApi = {
  summary: () => apiFetch<DashboardSummary>("/analytics/summary"),
  revenue: (days = 30) =>
    apiFetch<RevenuePoint[]>(`/analytics/revenue?days=${days}`),
  auditLog: (params?: { entity_type?: string; entity_id?: string; page?: number }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString();
    return apiFetch<AuditLogEntry[]>(`/analytics/audit-log${q ? `?${q}` : ""}`);
  },
};

// ──────────────────────────────────────────────
// Commands
// ──────────────────────────────────────────────

export const commandsApi = {
  execute: (text: string) =>
    apiFetch<{ success: boolean; message: string; data?: unknown }>("/commands", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  history: () => apiFetch<unknown[]>("/commands/history"),
};

// ──────────────────────────────────────────────
// Publishing
// ──────────────────────────────────────────────

export interface PublishResult {
  clip_id: string;
  platforms: string[];
  results: Record<string, unknown>;
  published: string[];
}

export const publishApi = {
  publishClip: (clipId: string, platforms?: string[]) =>
    apiFetch<PublishResult>("/publish/clip", {
      method: "POST",
      body: JSON.stringify({ clip_id: clipId, platforms: platforms || ["all"] }),
    }),
  listPlatforms: () =>
    apiFetch<{ platforms: string[]; all_shortcut: boolean; description: string }>("/publish/platforms"),
};
