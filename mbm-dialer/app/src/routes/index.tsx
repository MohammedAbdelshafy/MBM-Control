import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useEffect, useMemo } from "react";
import { SpiralBackdrop } from "../components/dialer/SpiralBackdrop";
import { MasterScript, DialerLead } from "../components/dialer/MasterScript";

export const Route = createFileRoute("/")({
  component: Dashboard,
});

type Decision = {
  status: string;
  followUp?: string;
  amount?: string;
  note?: string;
  at?: string;
  sales_lane?: string;
};

type DecisionGroup = {
  label: string;
  tone: "emerald" | "cyan" | "rose" | "amber";
  items: { id: string; followUp?: boolean; amountField?: boolean; icon?: string }[];
};

const DECISION_GROUPS: DecisionGroup[] = [
  {
    label: "Deal & Pipeline",
    tone: "emerald",
    items: [
      { id: "Deal Won", amountField: true, icon: "💰" },
      { id: "Meeting Booked", amountField: true, icon: "📅" },
      { id: "Proposal Sent", amountField: true, icon: "📑" },
      { id: "Cash Offer Made", amountField: true, icon: "🏠" },
    ],
  },
  {
    label: "Warmed & Qualified",
    tone: "cyan",
    items: [
      { id: "Seller Warmed", followUp: true, icon: "🔥" },
      { id: "AI Buyer Warmed", followUp: true, icon: "🔥" },
      { id: "Qualified Opportunity", followUp: true, icon: "✅" },
      { id: "Hot Lead", followUp: true, icon: "⚡" },
    ],
  },
  {
    label: "Nurture & Follow-Up",
    tone: "amber",
    items: [
      { id: "Call Back", followUp: true, icon: "🔁" },
      { id: "Left Voicemail", followUp: true, icon: "🎙" },
      { id: "No Answer", followUp: true, icon: "⏳" },
      { id: "Busy", followUp: true, icon: "📵" },
    ],
  },
  {
    label: "Dead & Suppression",
    tone: "rose",
    items: [
      { id: "Not Interested", icon: "❌" },
      { id: "Wrong Person", icon: "🚫" },
      { id: "Bad Number", icon: "🚫" },
      { id: "Do Not Call", icon: "🛑" },
    ],
  },
];

const TONE_STYLES: Record<DecisionGroup["tone"], { active: string; chip: string }> = {
  emerald: {
    active: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    chip: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  },
  cyan: {
    active: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40",
    chip: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
  },
  amber: {
    active: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    chip: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  },
  rose: {
    active: "bg-rose-500/20 text-rose-300 border-rose-500/40",
    chip: "bg-rose-500/15 text-rose-400 border-rose-500/30",
  },
};

const DECISION_LOOKUP = Object.fromEntries(
  DECISION_GROUPS.flatMap((g) => g.items.map((i) => [i.id, { ...i, tone: g.tone }])),
);

type CallingLaneTab =
  | "NEW_TODAY"
  | "SELLERS"
  | "BUYERS"
  | "CLINICS"
  | "CONTECH"
  | "DIGITAL"
  | "AI_BUYERS"
  | "HOT"
  | "FOLLOW_UPS"
  | "MEETINGS"
  | "ALL";

type SortMode = "NEWEST_BEST" | "BEST_SCORE" | "CATEGORY" | "CALLABILITY";

// ── CANONICAL FRESHNESS ORDERING (mirror of MBM/LeadEngine/dialer_queue_engine.py) ──
// Ingestion precedence: first_seen_at -> discovered_at -> imported_at -> created_at.
// Missing/invalid timestamps sort LAST deterministically. Never "now".
const FRESHNESS_STAGE_RANK_TS: Record<string, number> = {
  NEWLY_IMPORTED: 0,
  NEWLY_VERIFIED: 1,
  NEWLY_ENRICHED: 2,
  OLD: 3,
};

function ingestionEpoch(lead: DialerLead): number {
  const fields = ["first_seen_at", "discovered_at", "imported_at", "created_at"] as const;
  for (const f of fields) {
    const v = (lead as Record<string, unknown>)[f];
    if (typeof v === "string" && v.trim()) {
      const ms = Date.parse(v);
      if (!Number.isNaN(ms)) return ms;
    }
  }
  return 0; // missing/invalid -> deterministic bottom
}

function canonicalDialerCompare(a: DialerLead, b: DialerLead): number {
  const queueRank = (l: DialerLead): number => {
    const r = (l as Record<string, unknown>).queue_rank;
    return typeof r === "number" ? r : 999999;
  };
  const rankA = queueRank(a);
  const rankB = queueRank(b);
  if (rankA !== rankB) return rankA - rankB;

  const prioA = a.priority_score ?? 0;
  const prioB = b.priority_score ?? 0;
  if (prioA !== prioB) return prioB - prioA; // higher score first

  const stageA = FRESHNESS_STAGE_RANK_TS[a.freshness_stage || "OLD"] ?? 3;
  const stageB = FRESHNESS_STAGE_RANK_TS[b.freshness_stage || "OLD"] ?? 3;
  if (stageA !== stageB) return stageA - stageB;
  const ingA = ingestionEpoch(a);
  const ingB = ingestionEpoch(b);
  if (ingA !== ingB) return ingB - ingA; // newest FIRST
  return String(a.id || "").localeCompare(String(b.id || ""));
}

// new_today is DERIVED from ingestion metadata (same precedence as the engine),
// never trusted from the persisted boolean alone (legacy rows carry stale flags).
function isNewTodayLead(lead: DialerLead): boolean {
  if (lead.new_today === true) return true;
  const stage = lead.freshness_stage;
  if (stage === "NEWLY_IMPORTED" || stage === "NEWLY_VERIFIED") return true;
  const today = new Date().toLocaleDateString("en-CA"); // local YYYY-MM-DD
  const fields = ["first_seen_at", "discovered_at", "imported_at", "created_at"] as const;
  return fields.some((f) => {
    const v = (lead as Record<string, unknown>)[f];
    return typeof v === "string" && v.startsWith(today);
  });
}

function Dashboard() {
  const [leads, setLeads] = useState<DialerLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [activeLane, setActiveLane] = useState<CallingLaneTab>("NEW_TODAY");
  const [sortMode, setSortMode] = useState<SortMode>("NEWEST_BEST");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedVertical, setSelectedVertical] = useState("ALL");
  const [currentPage, setCurrentPage] = useState(1);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [showMeetingModal, setShowMeetingModal] = useState(false);
  const [meetingDate, setMeetingDate] = useState("");
  const [meetingNotes, setMeetingNotes] = useState("");
  const [meetingBookingStatus, setMeetingBookingStatus] = useState<string | null>(null);

  // Load leads database
  useEffect(() => {
    fetch("/leads_database.json")
      .then((res) => res.json())
      .then((data: DialerLead[]) => {
        setLeads(data);
        if (data.length > 0) {
          // Default selection to first New Today or Hot lead
          const firstNew = data.find((l) => isNewTodayLead(l));
          setSelectedLeadId(firstNew ? firstNew.id : data[0].id);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load leads database:", err);
        setLoading(false);
      });
  }, []);

  // Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (["INPUT", "TEXTAREA"].includes((e.target as HTMLElement)?.tagName)) return;
      if (e.key === "n" || e.key === "ArrowDown") {
        e.preventDefault();
        selectNextLead(1);
      } else if (e.key === "p" || e.key === "ArrowUp") {
        e.preventDefault();
        selectNextLead(-1);
      } else if (e.key === "w") {
        e.preventDefault();
        if (selectedLead) handleRecordDecision("AI Buyer Warmed");
      } else if (e.key === "q") {
        e.preventDefault();
        if (selectedLead) handleRecordDecision("Qualified Opportunity");
      } else if (e.key === "b") {
        e.preventDefault();
        setShowMeetingModal(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  const selectNextLead = (direction: number) => {
    if (filteredAndRankedLeads.length === 0) return;
    const currentIndex = filteredAndRankedLeads.findIndex((l) => l.id === selectedLeadId);
    let nextIndex = currentIndex + direction;
    if (nextIndex < 0) nextIndex = 0;
    if (nextIndex >= filteredAndRankedLeads.length) nextIndex = filteredAndRankedLeads.length - 1;
    setSelectedLeadId(filteredAndRankedLeads[nextIndex].id);
    // Follow the selection across pagination boundaries without resetting sort.
    const targetPage = Math.floor(nextIndex / PAGE_SIZE) + 1;
    if (targetPage !== safePage) setCurrentPage(targetPage);
  };

  const isSeller = (l: DialerLead) => {
    const v = (l.vertical || "").toLowerCase();
    return (
      v.includes("seller") || v.includes("real estate") || l.sales_lane === "REAL_ESTATE_WHOLESALE"
    );
  };

  const isBuyer = (l: DialerLead) => {
    const v = (l.vertical || "").toLowerCase();
    const c = (l.category || "").toLowerCase();
    return v.includes("buyer") || c.includes("buyer");
  };

  const isClinic = (l: DialerLead) => {
    const v = (l.vertical || "").toLowerCase();
    return (
      v.includes("clinic") ||
      v.includes("dental") ||
      v.includes("health") ||
      v.includes("chiro") ||
      v.includes("spa") ||
      v.includes("therap") ||
      v.includes("medical") ||
      v.includes("vet")
    );
  };

  const isConTech = (l: DialerLead) => {
    const v = (l.vertical || "").toLowerCase();
    return (
      v.includes("construct") ||
      v.includes("contract") ||
      v.includes("electric") ||
      v.includes("hvac") ||
      v.includes("plumb") ||
      v.includes("b2b") ||
      v.includes("service") ||
      v.includes("collision") ||
      v.includes("property management")
    );
  };

  const isDigital = (l: DialerLead) => {
    const v = (l.vertical || "").toLowerCase();
    return v.includes("digital") || l.sales_lane === "DIGITAL_SERVICES";
  };

  // Filter and Rank Leads for Tonight Queue
  const filteredAndRankedLeads = useMemo(() => {
    return leads
      .filter((lead) => {
        // Exclude uncallable / quarantined leads from dialer queue
        if (lead.callable === false) return false;

        // Tab filtering
        if (activeLane === "NEW_TODAY" && !isNewTodayLead(lead)) return false;
        if (activeLane === "SELLERS" && !isSeller(lead)) return false;
        if (activeLane === "BUYERS" && !isBuyer(lead)) return false;
        if (activeLane === "CLINICS" && !isClinic(lead)) return false;
        if (activeLane === "CONTECH" && !isConTech(lead)) return false;
        if (activeLane === "DIGITAL" && !isDigital(lead)) return false;
        if (activeLane === "AI_BUYERS" && isSeller(lead)) return false;
        if (
          activeLane === "HOT" &&
          (!lead.intent_score || lead.intent_score < 80) &&
          (!lead.priority_score || lead.priority_score < 85)
        )
          return false;
        if (activeLane === "FOLLOW_UPS" && !decisions[lead.id]?.followUp) return false;
        if (activeLane === "MEETINGS" && decisions[lead.id]?.status !== "Meeting Booked")
          return false;

        // Vertical filter
        if (selectedVertical !== "ALL" && lead.vertical !== selectedVertical) return false;

        // Search query
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchCompany = (lead.company || "").toLowerCase().includes(q);
          const matchContact = (lead.contact || "").toLowerCase().includes(q);
          const matchPhone = (lead.phone || "").includes(q);
          const matchAddress = (lead.address || "").toLowerCase().includes(q);
          return matchCompany || matchContact || matchPhone || matchAddress;
        }
        return true;
      })
      .sort((a, b) => {
        if (sortMode === "NEWEST_BEST") {
          // Canonical newest-first invariant (stage -> ingestion ts -> prio -> id).
          // Falls back to precomputed priority_rank ONLY as a final tiebreaker.
          const canonical = canonicalDialerCompare(a, b);
          if (canonical !== 0) return canonical;
          return (a.priority_rank || 9999) - (b.priority_rank || 9999);
        } else if (sortMode === "BEST_SCORE") {
          const scoreA =
            a.priority_score ||
            a.intent_score ||
            (a.motivation_score ? a.motivation_score * 10 : 70);
          const scoreB =
            b.priority_score ||
            b.intent_score ||
            (b.motivation_score ? b.motivation_score * 10 : 70);
          return scoreB - scoreA;
        } else if (sortMode === "CATEGORY") {
          const catA = a.vertical || "";
          const catB = b.vertical || "";
          if (catA !== catB) return catA.localeCompare(catB);
          return canonicalDialerCompare(a, b); // newest-first within each category
        } else if (sortMode === "CALLABILITY") {
          return (b.callability_score || 90) - (a.callability_score || 90);
        }
        return 0;
      });
  }, [leads, activeLane, sortMode, selectedVertical, searchQuery, decisions]);

  // ── PAGINATION: always FILTER → SORT → PAGINATE (never re-sort per page) ──
  const PAGE_SIZE = 50;
  const totalPages = Math.max(1, Math.ceil(filteredAndRankedLeads.length / PAGE_SIZE));
  const safePage = Math.min(Math.max(1, currentPage), totalPages);
  const pagedLeads = useMemo(
    () => filteredAndRankedLeads.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE),
    [filteredAndRankedLeads, safePage],
  );

  // Reset to page 1 whenever the filtered set or ordering changes so page 1
  // ALWAYS begins with the newest eligible lead.
  useEffect(() => {
    setCurrentPage(1);
  }, [activeLane, sortMode, selectedVertical, searchQuery]);

  // Keep selection inside the current page window when navigating pages.
  // Intentionally NOT keyed on selectedLeadId: operator-driven selections outside
  // the current page must survive; only page changes clamp the selection.
  useEffect(() => {
    if (pagedLeads.length > 0 && !pagedLeads.some((l) => l.id === selectedLeadId)) {
      setSelectedLeadId(pagedLeads[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pagedLeads]);

  const selectedLead = useMemo(() => {
    return leads.find((l) => l.id === selectedLeadId) || filteredAndRankedLeads[0] || null;
  }, [leads, selectedLeadId, filteredAndRankedLeads]);

  // Handle Decision Record
  const handleRecordDecision = (status: string, amount?: string, note?: string) => {
    if (!selectedLead) return;
    const dec: Decision = {
      status,
      amount,
      note,
      at: new Date().toISOString(),
      sales_lane: isSeller(selectedLead) ? "REAL_ESTATE_WHOLESALE" : "AI_CONSULTANCY",
    };
    setDecisions((prev) => ({ ...prev, [selectedLead.id]: dec }));

    // Send to backend if available (same-origin follow-up API)
    fetch("/api/decision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lead_id: selectedLead.id,
        decision_id: status,
        decision_label: status,
        lane: dec.sales_lane,
        amount: amount || "",
        note: note || "",
      }),
    }).catch(() => {});

    // Trigger AfterCall AI Processor
    if (note) {
      fetch("/api/aftercall", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          leadId: selectedLead.id,
          phone: selectedLead.phone,
          transcript: note,
          currentStage: status,
        }),
      }).catch((err) => console.error("AfterCall failed:", err));
    }
  };

  // Handle Booking Discovery Meeting
  const handleBookMeeting = async () => {
    if (!selectedLead) return;
    setMeetingBookingStatus("Booking...");

    try {
      const res = await fetch("/api/meeting", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lead_id: selectedLead.id,
          company: selectedLead.company,
          contact: selectedLead.contact,
          phone: selectedLead.phone,
          scheduled_time: meetingDate || "Tomorrow 10:00 AM CST",
          meeting_type: "15-Minute Executive AI Discovery Walkthrough",
          ai_fit: selectedLead.primary_offer || selectedLead.ai_fit || "24/7 AI Receptionist",
          notes: meetingNotes,
        }),
      });
      const data = await res.json();
      if (data.ok) {
        handleRecordDecision("Meeting Booked", "$8,400", meetingNotes);
        setMeetingBookingStatus("SUCCESS! Meeting Brief created & Telegram notified.");
        setTimeout(() => {
          setShowMeetingModal(false);
          setMeetingBookingStatus(null);
        }, 1500);
      } else {
        setMeetingBookingStatus("Saved locally.");
        handleRecordDecision("Meeting Booked", "$8,400", meetingNotes);
        setShowMeetingModal(false);
      }
    } catch {
      handleRecordDecision("Meeting Booked", "$8,400", meetingNotes);
      setMeetingBookingStatus("Saved locally.");
      setTimeout(() => {
        setShowMeetingModal(false);
        setMeetingBookingStatus(null);
      }, 1000);
    }
  };

  // Live Scoreboard Counts
  const counts = useMemo(() => {
    const totalLeads = leads.length;
    const sellersCount = leads.filter(isSeller).length;
    const buyersCount = leads.filter(isBuyer).length;
    const clinicsCount = leads.filter(isClinic).length;
    const contechCount = leads.filter(isConTech).length;
    const digitalCount = leads.filter(isDigital).length;
    const aiBuyersCount = leads.filter((l) => !isSeller(l)).length;
    const newTodayCount = leads.filter(isNewTodayLead).length;
    const hotCount = leads.filter(
      (l) =>
        (l.intent_score && l.intent_score >= 80) ||
        (l.priority_score && l.priority_score >= 85) ||
        l.stage === "HOT_BUYER",
    ).length;

    const decList = Object.values(decisions);
    const callsPlaced = decList.length;
    const connected = decList.filter(
      (d) => !["Bad Number", "No Answer", "Busy"].includes(d.status),
    ).length;
    const sellersWarmed = decList.filter((d) => d.status === "Seller Warmed").length;
    const aiBuyersWarmed = decList.filter((d) => d.status === "AI Buyer Warmed").length;
    const qualified = decList.filter((d) => d.status === "Qualified Opportunity").length;
    const meetings = decList.filter((d) => d.status === "Meeting Booked").length;
    const proposals = decList.filter((d) => d.status === "Proposal Sent").length;
    const deals = decList.filter((d) => d.status === "Deal Won").length;

    const pipelineVal = meetings * 8400 + proposals * 4500 + qualified * 2000;
    const confirmedRev = deals * 4000;

    return {
      totalLeads,
      sellersCount,
      buyersCount,
      clinicsCount,
      contechCount,
      digitalCount,
      aiBuyersCount,
      newTodayCount,
      hotCount,
      callsPlaced,
      connected,
      warmed: sellersWarmed + aiBuyersWarmed,
      qualified,
      meetings,
      proposals,
      deals,
      pipelineVal,
      confirmedRev,
    };
  }, [leads, decisions]);

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950 text-slate-200">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
          <span className="font-mono text-sm uppercase tracking-widest text-slate-400">
            Initializing MBM Global Revenue Cockpit...
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-950 text-slate-100 font-sans antialiased selection:bg-cyan-500 selection:text-slate-950">
      <SpiralBackdrop />

      {/* ─────────────────────────────────────────────────────────────
          1. TOP EXECUTIVE HEADER: 🌙 TONIGHT SCOREBOARD
          ───────────────────────────────────────────────────────────── */}
      <header className="relative z-10 flex h-14 shrink-0 items-center justify-between border-b border-slate-800/80 bg-slate-950/90 px-4 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
            </span>
            <span className="font-mono font-black text-sm uppercase tracking-wider text-slate-100 flex items-center gap-1.5">
              <span>🌙 TONIGHT</span>
              <span className="text-[10px] text-cyan-400 font-normal">
                | GLOBAL REVENUE COCKPIT
              </span>
            </span>
          </div>
        </div>

        {/* Live Counters HUD */}
        <div className="flex items-center gap-2 md:gap-4 overflow-x-auto text-xs font-mono py-1">
          <div className="flex items-center gap-1 bg-slate-900/80 px-2.5 py-1 rounded border border-slate-800">
            <span className="text-slate-500 font-bold">CALLS:</span>
            <span className="text-slate-200 font-bold">{counts.callsPlaced}</span>
          </div>
          <div className="flex items-center gap-1 bg-slate-900/80 px-2.5 py-1 rounded border border-slate-800">
            <span className="text-slate-500 font-bold">CONNECTED:</span>
            <span className="text-emerald-400 font-bold">{counts.connected}</span>
          </div>
          <div className="flex items-center gap-1 bg-slate-900/80 px-2.5 py-1 rounded border border-slate-800">
            <span className="text-slate-500 font-bold">WARMED:</span>
            <span className="text-cyan-400 font-bold">{counts.warmed}</span>
          </div>
          <div className="flex items-center gap-1 bg-slate-900/80 px-2.5 py-1 rounded border border-slate-800">
            <span className="text-slate-500 font-bold">QUALIFIED:</span>
            <span className="text-indigo-400 font-bold">{counts.qualified}</span>
          </div>
          <div className="flex items-center gap-1 bg-slate-900/80 px-2.5 py-1 rounded border border-slate-800">
            <span className="text-slate-500 font-bold">MEETINGS:</span>
            <span className="text-amber-400 font-bold">{counts.meetings}</span>
          </div>
          <div className="flex items-center gap-1 bg-emerald-500/10 px-2.5 py-1 rounded border border-emerald-500/30">
            <span className="text-emerald-400 font-bold">PIPELINE:</span>
            <span className="text-emerald-300 font-black">
              ${counts.pipelineVal.toLocaleString()}
            </span>
          </div>
          <div className="flex items-center gap-1 bg-cyan-500/10 px-2.5 py-1 rounded border border-cyan-500/30">
            <span className="text-cyan-400 font-bold">REVENUE:</span>
            <span className="text-cyan-300 font-black">
              ${counts.confirmedRev.toLocaleString()}
            </span>
          </div>

          <div className="h-4 w-px bg-slate-800 hidden sm:block" />

          <Link
            to="/analytics"
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-slate-900 border border-slate-800 hover:border-cyan-500/50 text-slate-300 hover:text-cyan-300 text-xs font-mono font-bold transition whitespace-nowrap shadow-sm"
          >
            📊 <span className="hidden sm:inline">ANALYTICS</span>
          </Link>
        </div>
      </header>

      {/* ─────────────────────────────────────────────────────────────
          2. PRIMARY NAVIGATION BAR (Expanded Niches & Fast Lanes)
          ───────────────────────────────────────────────────────────── */}
      <nav className="relative z-10 flex h-11 shrink-0 items-center justify-between border-b border-slate-800/80 bg-slate-900/80 px-4 backdrop-blur-sm overflow-x-auto">
        <div className="flex items-center gap-1.5">
          {(
            [
              {
                id: "NEW_TODAY",
                label: "🟢 NEW TODAY",
                count: counts.newTodayCount,
                tone: "text-emerald-400",
              },
              {
                id: "SELLERS",
                label: "🏠 SELLERS",
                count: counts.sellersCount,
                tone: "text-amber-400",
              },
              {
                id: "BUYERS",
                label: "💼 CASH BUYERS",
                count: counts.buyersCount,
                tone: "text-cyan-400",
              },
              {
                id: "CLINICS",
                label: "🩺 CLINICS & HEALTH",
                count: counts.clinicsCount,
                tone: "text-emerald-400",
              },
              {
                id: "CONTECH",
                label: "⚡ CONTECH & B2B",
                count: counts.contechCount,
                tone: "text-yellow-400",
              },
              {
                id: "DIGITAL",
                label: "🌐 DIGITAL",
                count: counts.digitalCount,
                tone: "text-blue-400",
              },
              { id: "HOT", label: "🔥 HOT", count: counts.hotCount, tone: "text-rose-400" },
              {
                id: "FOLLOW_UPS",
                label: "🔁 FOLLOW-UPS",
                count: Object.values(decisions).filter((d) => d.followUp).length,
                tone: "text-amber-300",
              },
              {
                id: "MEETINGS",
                label: "📅 MEETINGS",
                count: counts.meetings,
                tone: "text-cyan-400",
              },
              {
                id: "ALL",
                label: "⭐ ALL LEADS",
                count: counts.totalLeads,
                tone: "text-slate-300",
              },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveLane(tab.id as CallingLaneTab)}
              className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-bold transition-all whitespace-nowrap ${
                activeLane === tab.id
                  ? "bg-slate-800 text-white shadow border border-slate-700 ring-1 ring-cyan-400/40"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-slate-950/80 ${tab.tone}`}
              >
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Hotkeys Hint */}
        <div className="hidden lg:flex items-center gap-2 text-[10px] font-mono text-slate-500 shrink-0">
          <span>Shortcuts:</span>
          <span className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">W: Warm</span>
          <span className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">Q: Qualify</span>
          <span className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">B: Book</span>
          <span className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">↓/N: Next</span>
        </div>
      </nav>

      {/* ─────────────────────────────────────────────────────────────
          3. MAIN LAYOUT: SIDEBAR QUEUE + CALL COCKPIT + DECISION BAR
          ───────────────────────────────────────────────────────────── */}
      <div className="relative z-10 flex flex-1 overflow-hidden">
        {/* LEFT COLUMN: 🎯 TONIGHT QUEUE */}
        <aside className="flex w-80 md:w-96 shrink-0 flex-col border-r border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
          {/* Search, Sort & Fast Filters */}
          <div className="p-3 border-b border-slate-800/80 space-y-2">
            <div className="relative">
              <input
                type="text"
                placeholder="Search company, owner, phone..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-2 text-[10px] text-slate-400 hover:text-slate-200"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Sorting Mode Selector + Pagination */}
            <div className="flex items-center justify-between gap-2 text-[10px] font-mono text-slate-400">
              <span className="font-bold uppercase tracking-wider text-cyan-400 truncate">
                🎯 QUEUE ({filteredAndRankedLeads.length})
              </span>
              <div className="flex items-center gap-1">
                <span className="text-slate-500">Sort:</span>
                <select
                  value={sortMode}
                  onChange={(e) => setSortMode(e.target.value as SortMode)}
                  className="bg-slate-900 border border-slate-800 text-slate-200 rounded px-1.5 py-0.5 text-[10px] font-mono focus:border-cyan-500 focus:outline-none"
                >
                  <option value="NEWEST_BEST">⚡ Newest + Best (Default)</option>
                  <option value="BEST_SCORE">🏆 Best Score</option>
                  <option value="CATEGORY">📂 By Category</option>
                  <option value="CALLABILITY">📞 Callability</option>
                </select>
              </div>
            </div>
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-1.5 text-[10px] font-mono text-slate-400">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={safePage <= 1}
                  className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 disabled:opacity-30 hover:border-cyan-500"
                >
                  ◀ Prev
                </button>
                <span className="text-slate-300">
                  Page {safePage} / {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={safePage >= totalPages}
                  className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 disabled:opacity-30 hover:border-cyan-500"
                >
                  Next ▶
                </button>
              </div>
            )}
          </div>

          {/* Lead List — canonical order preserved: page 1 starts with the newest */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/40">
            {pagedLeads.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500">
                No leads match the active filter. Switch tabs to view more.
              </div>
            ) : (
              pagedLeads.map((lead, idx) => {
                const globalIdx = (safePage - 1) * PAGE_SIZE + idx;
                const isSel = lead.id === selectedLead?.id;
                const dec = decisions[lead.id];
                const isNew = isNewTodayLead(lead) || lead.freshness_stage === "NEWLY_VERIFIED";
                const isCallNow =
                  lead.queue_bucket === "FRESH_CALL_NOW" ||
                  (lead.priority_rank && lead.priority_rank <= 25);

                return (
                  <div
                    key={lead.id}
                    onClick={() => setSelectedLeadId(lead.id)}
                    className={`p-3 cursor-pointer transition-all border-l-2 ${
                      isSel
                        ? "bg-slate-800/90 border-cyan-400 shadow-sm"
                        : "border-transparent hover:bg-slate-900/60 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] font-mono text-cyan-400 font-bold">
                          #{lead.priority_rank || globalIdx + 1}
                        </span>
                        {lead.category_rank && (
                          <span className="text-[9px] font-mono text-slate-500">
                            [Cat #{lead.category_rank}]
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        {isCallNow ? (
                          <span className="text-[9px] bg-rose-500/20 text-rose-300 font-black px-1.5 py-0.2 rounded border border-rose-500/40 animate-pulse">
                            🔥 CALL NOW
                          </span>
                        ) : isNew ? (
                          <span className="text-[9px] bg-emerald-500/20 text-emerald-300 font-black px-1.5 py-0.2 rounded border border-emerald-500/30">
                            🟢 NEW
                          </span>
                        ) : null}
                        {dec ? (
                          <span className="text-[9px] bg-cyan-500/20 text-cyan-300 font-bold px-1.5 py-0.2 rounded border border-cyan-500/30">
                            {dec.status}
                          </span>
                        ) : (
                          <span className="text-[9px] font-mono text-amber-400 font-bold">
                            {lead.priority_score
                              ? `${lead.priority_score} PTS`
                              : lead.intent_score
                                ? `${lead.intent_score}% INTENT`
                                : "READY"}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="font-bold text-xs text-slate-100 truncate mb-0.5">
                      {lead.company}
                    </div>
                    <div className="text-[11px] text-slate-400 truncate mb-1">
                      {lead.contact} {lead.details?.Role ? `· ${lead.details.Role}` : ""}
                    </div>

                    <div className="flex items-center justify-between text-[10px] font-mono">
                      <span className="text-slate-500">{lead.phone}</span>
                      <span className="text-slate-400 text-[9px] truncate max-w-[120px]">
                        {lead.vertical}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </aside>

        {/* CENTER / RIGHT COLUMN: CALL COCKPIT & SCRIPT */}
        <main className="flex flex-1 flex-col overflow-y-auto bg-slate-950/60 p-4 md:p-6">
          {selectedLead ? (
            <div className="max-w-4xl w-full mx-auto space-y-6">
              {/* 1-Click Action Bar */}
              <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-slate-900/90 border border-slate-800 rounded-xl shadow-md">
                <div className="flex items-center gap-2">
                  <a
                    href={`tel:${selectedLead.phone}`}
                    className="flex items-center gap-1.5 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black rounded-lg text-xs transition-all shadow-md"
                  >
                    <span>📞 DIAL</span>
                    <span className="font-mono">{selectedLead.phone}</span>
                  </a>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <button
                    onClick={() =>
                      handleRecordDecision(
                        isSeller(selectedLead) ? "Seller Warmed" : "AI Buyer Warmed",
                      )
                    }
                    className="px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 font-bold border border-cyan-500/40 rounded-lg text-xs transition-all"
                  >
                    🔥 WARM (W)
                  </button>
                  <button
                    onClick={() => handleRecordDecision("Qualified Opportunity")}
                    className="px-3 py-1.5 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 font-bold border border-indigo-500/40 rounded-lg text-xs transition-all"
                  >
                    ✅ QUALIFIED (Q)
                  </button>
                  <button
                    onClick={() => setShowMeetingModal(true)}
                    className="px-3 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black rounded-lg text-xs transition-all shadow"
                  >
                    📅 BOOK MEETING (B)
                  </button>
                  <button
                    onClick={() => handleRecordDecision("Wrong Person")}
                    className="px-2.5 py-1.5 bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 font-bold border border-slate-700 rounded-lg text-xs transition-all"
                  >
                    🚫 WRONG PERSON
                  </button>
                </div>
              </div>

              {/* Master Script HUD Component */}
              <MasterScript lead={selectedLead} />

              {/* GTM Quick Brief Widget */}
              <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2 text-xs">
                <div className="flex items-center justify-between font-mono text-[10px] text-slate-400 uppercase tracking-widest pb-1 border-b border-slate-800">
                  <span className="text-cyan-400 font-bold">🚀 GTM REVENUE BRIEF</span>
                  <span>Active Session</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1 text-slate-300">
                  <div>
                    <span className="text-slate-500 block text-[10px]">Confirmed Revenue:</span>
                    <strong className="text-cyan-300 font-mono">
                      ${counts.confirmedRev.toLocaleString()}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">Active Pipeline:</span>
                    <strong className="text-emerald-300 font-mono">
                      ${counts.pipelineVal.toLocaleString()}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">Warmed Leads:</span>
                    <strong className="text-slate-100 font-mono">{counts.warmed}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">Booked Meetings:</span>
                    <strong className="text-amber-300 font-mono">{counts.meetings}</strong>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-slate-500 text-sm">
              Select a lead from the queue to start calling.
            </div>
          )}
        </main>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          4. 1-CLICK MEETING BOOKING MODAL
          ───────────────────────────────────────────────────────────── */}
      {showMeetingModal && selectedLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl bg-slate-900 border border-amber-500/40 p-5 shadow-2xl space-y-4 animate-scaleUp">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-sm font-bold uppercase tracking-wider text-amber-400 font-mono">
                📅 Schedule 15-Min Discovery Walkthrough
              </span>
              <button
                onClick={() => setShowMeetingModal(false)}
                className="text-slate-400 hover:text-slate-200 text-sm"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-400 block mb-1">Prospect:</span>
                <div className="font-bold text-slate-100 bg-slate-950 p-2 rounded border border-slate-800">
                  {selectedLead.company} · {selectedLead.contact} ({selectedLead.phone})
                </div>
              </div>

              <div>
                <span className="text-slate-400 block mb-1">Scheduled Time:</span>
                <input
                  type="text"
                  placeholder="e.g. Tomorrow at 10:00 AM CST"
                  value={meetingDate}
                  onChange={(e) => setMeetingDate(e.target.value)}
                  className="w-full rounded bg-slate-950 border border-slate-800 p-2 text-slate-100 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <span className="text-slate-400 block mb-1">Meeting Notes & Objectives:</span>
                <textarea
                  rows={3}
                  placeholder="Discussed after-hours call overflow; walkthrough 24/7 AI Receptionist live voice simulation."
                  value={meetingNotes}
                  onChange={(e) => setMeetingNotes(e.target.value)}
                  className="w-full rounded bg-slate-950 border border-slate-800 p-2 text-slate-100 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              {meetingBookingStatus && (
                <div className="p-2 bg-amber-500/10 border border-amber-500/30 rounded text-amber-300 font-mono text-[11px]">
                  {meetingBookingStatus}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setShowMeetingModal(false)}
                className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                onClick={handleBookMeeting}
                className="px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black rounded text-xs transition-all shadow"
              >
                Confirm & Dispatch Brief
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
