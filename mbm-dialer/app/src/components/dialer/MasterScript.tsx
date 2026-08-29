import { useState, type ReactNode } from "react";

export type DialerLead = {
  id: string;
  vertical: string;
  company: string;
  contact: string;
  phone: string;
  callable?: boolean;
  phone_verified?: boolean;
  email?: string;
  address?: string;
  city?: string;
  state?: string;
  sales_lane?: string;
  source?: string;
  source_reference?: string;
  verification_status?: string;
  verification_method?: string;
  provenance?: Record<string, any>;
  first_seen_at?: string;
  discovered_at?: string;
  imported_at?: string;
  created_at?: string;
  callability_score?: number;
  verified_at?: string;
  new_today?: boolean;
  freshness_label?: string;
  freshness_stage?: string;
  freshness_score?: number;
  priority_score?: number;
  priority_rank?: number;
  queue_rank?: number;
  call_priority?: number;
  priority_reason?: string;
  qualification_score?: number;
  category_rank?: number;

  queue_bucket?: string;
  partition?: string;
  callability_status?: string;
  callability?: number;
  intent_score?: number;
  stage?: string;
  why_them?: string;
  why_now?: string;
  business_pain?: string;
  ai_fit?: string;
  primary_offer?: string;
  secondary_offer?: string;
  consultancy_angle?: string;
  expected_value_usd?: number;
  recommended_next_action?: string;
  details?: Record<string, any>;
  motivation_tier?: string;
  motivation_score?: number;
  motivation_signals?: string[];
  owner_status?: string;
  domain?: string;
  website?: string;
  category?: string;
  recommended_offer?: string;
  setup_price?: number;
  maintenance_price?: number;
  maintenance_upsell?: boolean;
  next_action?: string;
  intent_topics?: Record<string, number>;
  offer?: {
    name?: string;
    sku?: string;
    category?: string;
    setup_price_usd?: number;
    maintenance_price_usd?: number;
    maintenance_upsell?: boolean;
    neteller_checkout_link?: string;
  };
  scripts?: {
    pack?: string;
    checkout?: {
      setup_price?: number;
      maintenance_price?: number;
      neteller_link?: string;
      sku?: string;
    };
    scripts?: Record<string, string>;
  };
  sales_strategy?: {
    pain_point?: string;
    ai_fit?: string;
    offer?: {
      name?: string;
      tier?: string;
      estimated_deal_value_usd?: number;
      setup_fee_usd?: number;
      monthly_fee_usd?: number;
      secondary_offer?: string;
      consultancy_angle?: string;
      neteller_checkout_link?: string;
    };
    script?: {
      opening?: string;
      pain_question?: string;
      ai_pitch?: string;
      cta?: string;
    };
    objection_path?: {
      primary_objection?: string;
      suggested_counter?: string;
    };
    next_best_action?: string;
  };
  Call_Script?: string;
  script_id?: string;
  segment?: string;
};

const SPAN = `text-[10px] font-sans font-bold uppercase tracking-widest border-b border-slate-800 pb-1`;

function SectionHeader({ children, color = "text-cyan-500" }: { children: ReactNode; color?: string }) {
  return <div className={`${SPAN} ${color} mb-2.5 flex items-center justify-between`}>{children}</div>;
}

export function MasterScript({ lead }: { lead: DialerLead }) {
  const isSeller =
    lead.vertical === "Real Estate Sellers" ||
    lead.vertical === "Texas Real Estate" ||
    lead.vertical === "Master Catch-All" ||
    lead.sales_lane === "REAL_ESTATE_WHOLESALE" ||
    lead.vertical.toLowerCase().includes("real estate");

  const isDigital =
    lead.sales_lane === "DIGITAL_SERVICES" ||
    lead.vertical === "Digital Services" ||
    lead.vertical.toLowerCase().includes("digital services");

  // State for interactive toggles
  const [sellerOpeningMode, setSellerOpeningMode] = useState<"general" | "absentee" | "vacant" | "rental">("general");
  const [activeObjectionCategory, setActiveObjectionCategory] = useState<string | null>(null);
  const [activeIdentityStatus, setActiveIdentityStatus] = useState<string>(
    lead.owner_status === "VERIFIED_OWNER" ? "OWNER_CONFIRMED" : "UNCONFIRMED"
  );
  const [copiedQuestion, setCopiedQuestion] = useState<string | null>(null);
  const [showConsultancyPanel, setShowConsultancyPanel] = useState(true);
  const [showFullScript, setShowFullScript] = useState(true);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedQuestion(id);
    setTimeout(() => setCopiedQuestion(null), 2000);
  };

  const propertyAddress =
    lead.details?.Property_Address ||
    lead.details?.Address ||
    lead.address ||
    lead.company ||
    "the property";

  const ownerDatabase =
    lead.details?.owner_status ||
    (lead.details?.first_name ? `${lead.details?.first_name} ${lead.details?.last_name || ""}`.trim() : lead.contact) ||
    "Verified County Record";

  const motivationSignal =
    (lead.motivation_signals && lead.motivation_signals.length > 0)
      ? lead.motivation_signals.join(", ").replace(/_/g, " ")
      : lead.details?.distress_reason ||
        lead.details?.Tax_Delinquent ||
        (isSeller ? "High-Equity Property / Absentee Owner" : "After-Hours Call Bottleneck");

  const dealValueEst =
    lead.sales_strategy?.offer?.estimated_deal_value_usd ||
    lead.expected_value_usd ||
    (isSeller ? 5000 : 8400);

  const netellerCheckoutUrl =
    lead.sales_strategy?.offer?.neteller_checkout_link ||
    (isSeller
      ? "https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount=5000.00&currency=USD&item=Wholesale+Assignment+Deposit"
      : "https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount=1997.00&currency=USD&item=AI+Assistant+Monthly+Retainer");

  // Vertical-specific "WHAT WE CAN BUILD" matrix — operational systems only, no generic AI receptionist pitch
  const getVerticalSolutions = () => {
    const v = (lead.vertical || "").toLowerCase();
    if (v.includes("dental")) {
      return {
        niche: "Dental & Orthodontics",
        solutions: [
          { name: "Automated Recall & Rebooking Workflow", desc: "Surfaces 6-month overdue hygiene and rebooks via intake → scheduling → recall → follow-up", price: "$1,997/mo" },
          { name: "Unscheduled Treatment Follow-Up", desc: "Follows up on presented crowns/implants to recover treatment scheduling", price: "$1,997/mo" },
          { name: "Referral & Scheduling Analytics", desc: "Tracks referral → scheduling → case acceptance with weekly reporting", price: "$1,497/mo" },
        ]
      };
    } else if (v.includes("hvac") || v.includes("mechanical")) {
      return {
        niche: "HVAC & Mechanical Contractors",
        solutions: [
          { name: "Estimate Recovery & Follow-Up Workflow", desc: "Recovers unreturned estimates with structured follow-up and payment workflow", price: "$2,500/mo" },
          { name: "Booking & Dispatch Workflow", desc: "Co-ordinates booking → dispatch → scheduling with route and capacity tracking", price: "$1,997/mo" },
          { name: "Maintenance Renewal & Retention Workflow", desc: "Books furnace/AC tune-ups and tracks renewal reporting", price: "$1,497/mo" },
        ]
      };
    } else if (v.includes("construction") || v.includes("civil")) {
      return {
        niche: "Civil & Commercial Construction",
        solutions: [
          { name: "CAD / DXF to BOQ Estimator", desc: "Automated takeoff extracting concrete, earthwork, and steel quantities", price: "$2,497/mo" },
          { name: "Subcontractor Bid Nurture Bot", desc: "Tracks proposal deadlines and collects sub bids autonomously", price: "$1,997/mo" },
          { name: "Daily Field Log & RFI Synthesizer", desc: "Transcribes voice field updates into Procore daily reports", price: "$1,497/mo" },
        ]
      };
    } else if (v.includes("law") || v.includes("legal")) {
      return {
        niche: "Law Firms & Legal Practice",
        solutions: [
          { name: "24/7 AI Intake & Retainer Closer", desc: "Qualifies PI / family law claimants in <2 minutes and sends DocuSign", price: "$2,997/mo" },
          { name: "Conflict Check & Calendar Agent", desc: "Screens conflicts and books attorney consultation slots in Clio", price: "$1,997/mo" },
        ]
      };
    } else {
      return {
        niche: "Clinic & Healthcare Operations",
        solutions: [
          { name: "Patient Recall & Rebooking System", desc: "Rebooks overdue recall via intake → scheduling → recall → analytics", price: "$1,997/mo" },
          { name: "Referral & Intake Workflow", desc: "Tracks referral → intake → scheduling with follow-up reporting", price: "$1,497/mo" },
          { name: "Patient Follow-Up & Payment Workflow", desc: "Manages treatment follow-up, payment workflow and retention reporting", price: "$1,997/mo" },
        ]
      };
    }
  };

  const verticalSolutions = getVerticalSolutions();

  // Detect provider conflict and missing property evidence for banner surfacing
  const hasConflict = (() => {
    const norm = (p: string) => p.replace(/\D/g, "").replace(/^1/, "");
    const phones = [lead.phone, (lead as any).verified_phone, (lead as any).skip_trace_phone_alt].filter(Boolean).map((p) => norm(String(p)));
    const distinct = new Set(phones.filter(Boolean));
    return distinct.size > 1;
  })();
  const missingProperty = isSeller && !(lead as any).property_evidence && !lead.address && !(lead.details as any)?.Property_Address;
  const hasPropertyMissing = isSeller && ((lead as any).property_evidence === "MISSING" || missingProperty);
  const offMarketUnknown = isSeller && (lead as any).off_market_status === "UNKNOWN";

  return (
    <div className="space-y-6 text-sm font-sans">
      {/* CONFLICT / PROPERTY WARNING BANNERS — surfaced from business_systems_engine CONFLICT logic */}
      {hasConflict && (
        <div className="p-3 bg-rose-950/40 border border-rose-500/40 rounded-xl text-xs">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-rose-400 font-mono font-bold uppercase tracking-widest">⚠️ CONFLICT — Providers Disagree</span>
            <span className="text-[10px] font-mono text-rose-300 border border-rose-500/30 px-1.5 py-0.5 rounded">DO NOT PRESENT AS VERIFIED FACT</span>
          </div>
          <div className="text-rose-200">Independent sources report different phones for this lead. Resolve before dialing. BusinessSystemsEngine marks this as <span className="font-mono font-bold">CONFLICT</span>.</div>
        </div>
      )}
      {hasPropertyMissing && (
        <div className="p-3 bg-amber-950/30 border border-amber-500/30 rounded-xl text-xs">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-amber-400 font-mono font-bold uppercase tracking-widest">🏚 PROPERTY EVIDENCE MISSING</span>
            <span className="text-[10px] font-mono text-amber-300 border border-amber-500/30 px-1.5 py-0.5 rounded">UNKNOWN · NOT OFF_MARKET_CONFIRMED</span>
          </div>
          <div className="text-amber-200">No APN/address/property evidence on file. Listing status is <span className="font-mono">UNKNOWN</span> — never inferred as off-market. Seller queue requires PROPERTY+OWNER+PHONE evidence chain.</div>
        </div>
      )}
      {offMarketUnknown && !hasPropertyMissing && (
        <div className="p-2 bg-slate-800/50 border border-slate-700 rounded-lg text-[11px] font-mono text-slate-400">Listing status: <span className="text-amber-300">UNKNOWN</span> — not verified as off-market. No distress claim without signal evidence.</div>
      )}
      {/* ─────────────────────────────────────────────────────────────
          1. DUAL-ENGINE INTELLIGENCE CARD (SELLER vs AI BUSINESS BUYER)
          ───────────────────────────────────────────────────────────── */}
      {isSeller ? (
        <div className="p-4 bg-gradient-to-br from-amber-950/40 via-slate-900/60 to-slate-950/80 border border-amber-500/30 rounded-xl shadow-lg">
          <SectionHeader color="text-amber-400">
            <span className="flex items-center gap-2">
              <span>🏠 REAL ESTATE SELLER CARD</span>
              {lead.new_today && (
                <span className="bg-emerald-500 text-slate-950 font-black text-[9px] px-2 py-0.5 rounded-full tracking-wider animate-pulse">
                  🟢 NEW TODAY
                </span>
              )}
              {lead.priority_rank && (
                <span className="bg-slate-800 text-cyan-300 font-mono text-[9px] px-2 py-0.5 rounded border border-cyan-500/30">
                  Global #{lead.priority_rank}
                </span>
              )}
              {lead.category_rank && (
                <span className="bg-slate-800 text-amber-300 font-mono text-[9px] px-2 py-0.5 rounded border border-amber-500/30">
                  Niche #{lead.category_rank}
                </span>
              )}
            </span>
            <div className="flex items-center gap-1.5 font-mono">
              <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/40">
                Prio {lead.priority_score || 90}/100
              </span>
              <span className="text-[9px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded border border-amber-500/40">
                SELLER_MODE
              </span>
            </div>
          </SectionHeader>

          <div className="grid grid-cols-2 gap-2 text-xs mb-3">
            <div>
              <span className="text-slate-500 uppercase text-[10px] font-bold block">Owner DB</span>
              <span className="text-slate-200 font-semibold truncate block">{ownerDatabase}</span>
            </div>
            <div>
              <span className="text-slate-500 uppercase text-[10px] font-bold block">Verified Phone</span>
              <a href={`tel:${lead.phone}`} className="text-emerald-400 font-mono font-bold hover:underline block">
                {lead.phone}
              </a>
            </div>
            <div className="col-span-2">
              <span className="text-slate-500 uppercase text-[10px] font-bold block">Property Address</span>
              <span className="text-slate-200 font-medium truncate block">{propertyAddress}</span>
            </div>
          </div>

          {/* Live Caller Identity Verification */}
          <div className="mt-3 pt-3 border-t border-amber-500/20">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1.5">
              Live Caller Identity:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {(
                [
                  { id: "OWNER_CONFIRMED", label: "✅ Owner Confirmed", tone: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" },
                  { id: "AUTHORIZED_DM", label: "👔 Auth Decision Maker", tone: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40" },
                  { id: "UNCONFIRMED", label: "⏳ Unconfirmed", tone: "bg-slate-800 text-slate-400 border-slate-700" },
                  { id: "WRONG_PERSON", label: "🚫 Wrong Person", tone: "bg-rose-500/20 text-rose-300 border-rose-500/40" },
                  { id: "TENANT", label: "🔑 Tenant", tone: "bg-purple-500/20 text-purple-300 border-purple-500/40" },
                ] as const
              ).map((idOpt) => (
                <button
                  key={idOpt.id}
                  onClick={() => setActiveIdentityStatus(idOpt.id)}
                  className={`text-[10px] px-2 py-1 rounded border font-semibold transition-all ${
                    activeIdentityStatus === idOpt.id ? `${idOpt.tone} ring-1 ring-amber-400/50` : "bg-slate-900/60 text-slate-500 border-slate-800"
                  }`}
                >
                  {idOpt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-amber-500/20 space-y-1.5 text-xs">
            <div className="flex items-start gap-1.5">
              <strong className="text-amber-300 shrink-0">Why This Seller:</strong>
              <span className="text-slate-300">High-equity single-family asset with verified owner record in county index.</span>
            </div>
            <div className="flex items-start gap-1.5">
              <strong className="text-amber-300 shrink-0">Motivation:</strong>
              <span className="text-slate-300 uppercase tracking-wide text-[11px] font-semibold">{motivationSignal}</span>
            </div>
            <div className="flex items-start gap-1.5">
              <strong className="text-amber-300 shrink-0">Next Move:</strong>
              <span className="text-cyan-300 font-medium">Verify live ownership → Establish occupancy & condition → Discover timeline.</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-4 bg-gradient-to-br from-indigo-950/40 via-slate-900/60 to-slate-950/80 border border-indigo-500/30 rounded-xl shadow-lg">
          <SectionHeader color="text-indigo-400">
            <span className="flex items-center gap-2">
              <span>🤖 AI BUSINESS BUYER CARD</span>
              {lead.priority_reason && (
                <span className="bg-emerald-500/20 text-emerald-300 font-mono text-[9px] px-2 py-0.5 rounded border border-emerald-500/40 font-bold">
                  🎯 {lead.priority_reason}
                </span>
              )}
              {typeof lead.queue_rank === "number" && (
                <span className="bg-cyan-500/20 text-cyan-300 font-mono text-[9px] px-2 py-0.5 rounded border border-cyan-500/40 font-bold">
                  Queue #{lead.queue_rank}
                </span>
              )}
              {lead.new_today && (
                <span className="bg-emerald-500 text-slate-950 font-black text-[9px] px-2 py-0.5 rounded-full tracking-wider animate-pulse">
                  🟢 NEW TODAY
                </span>
              )}
              {lead.priority_rank && !lead.queue_rank && (
                <span className="bg-slate-800 text-cyan-300 font-mono text-[9px] px-2 py-0.5 rounded border border-cyan-500/30">
                  Global #{lead.priority_rank}
                </span>
              )}
              {lead.category_rank && (
                <span className="bg-slate-800 text-amber-300 font-mono text-[9px] px-2 py-0.5 rounded border border-amber-500/30">
                  Niche #{lead.category_rank}
                </span>
              )}
            </span>
            <div className="flex items-center gap-1.5 font-mono">
              <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/40 font-bold">
                Prio {lead.priority_score || 90}
              </span>
              <span className="text-[9px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded border border-indigo-500/40">
                AI_MODE
              </span>
            </div>

          </SectionHeader>

          <div className="grid grid-cols-2 gap-2 text-xs mb-3">
            <div>
              <span className="text-slate-500 uppercase text-[10px] font-bold block">Company</span>
              <span className="text-slate-200 font-semibold truncate block">{lead.company}</span>
            </div>
            <div>
              <span className="text-slate-500 uppercase text-[10px] font-bold block">Buyer / Role</span>
              <span className="text-slate-200 font-semibold truncate block">{lead.contact}</span>
            </div>
            <div>
              <span className="text-slate-500 uppercase text-[10px] font-bold block">Phone</span>
              <a href={`tel:${lead.phone}`} className="text-emerald-400 font-mono font-bold hover:underline block">
                {lead.phone}
              </a>
            </div>
            <div>
              <span className="text-slate-500 uppercase text-[10px] font-bold block">Expected Value</span>
              <span className="text-cyan-300 font-mono font-bold block">${dealValueEst.toLocaleString()}</span>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-indigo-500/20 space-y-1.5 text-xs">
            <div className="flex items-start gap-1.5">
              <strong className="text-indigo-300 shrink-0">Business Pain:</strong>
              <span className="text-slate-300">
                {lead.business_pain ||
                  lead.sales_strategy?.pain_point ||
                  lead.details?.Pain_Point ||
                  lead.details?.pain ||
                  "Overwhelmed front desk losing after-hours callers and delayed follow-ups."}
              </span>
            </div>
            <div className="flex items-start gap-1.5">
              <strong className="text-indigo-300 shrink-0">Recommended System:</strong>
              <span className="text-emerald-300 font-semibold">
                {lead.primary_offer ||
                  lead.ai_fit ||
                  lead.sales_strategy?.offer?.name ||
                  lead.details?.ai_fit ||
                  "Recall & Rebooking + Intake & Scheduling Workflow"}
              </span>
            </div>
            <div className="flex items-start gap-1.5">
              <strong className="text-indigo-300 shrink-0">Consultancy Angle:</strong>
              <span className="text-slate-300">
                {lead.consultancy_angle ||
                  lead.sales_strategy?.offer?.consultancy_angle ||
                  "AI Revenue Operations & Autonomous Phone/CRM Intake"}
              </span>
            </div>
            <div className="flex items-start gap-1.5">
              <strong className="text-indigo-300 shrink-0">Next Move:</strong>
              <span className="text-cyan-300 font-medium">
                {lead.recommended_next_action ||
                  lead.sales_strategy?.next_best_action ||
                  "Diagnose front-desk bottleneck → Book 15-min interactive walkthrough"}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          2. AI CONSULTANCY PANEL ("WHAT WE CAN BUILD")
          ───────────────────────────────────────────────────────────── */}
      {!isSeller && (
        <div className="p-4 bg-slate-900/90 border border-purple-500/30 rounded-xl shadow-md">
          <div className="flex items-center justify-between mb-2.5 pb-1 border-b border-purple-500/20">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-purple-300 font-mono">
                ⚡ WHAT WE CAN BUILD ({verticalSolutions.niche})
              </span>
            </div>
            <button
              onClick={() => setShowConsultancyPanel(!showConsultancyPanel)}
              className="text-[10px] text-purple-400 hover:text-purple-300 font-mono"
            >
              {showConsultancyPanel ? "Collapse" : "Expand"}
            </button>
          </div>

          {showConsultancyPanel && (
            <div className="space-y-2.5 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {verticalSolutions.solutions.map((sol, idx) => (
                  <div key={idx} className="p-2.5 bg-slate-800/80 border border-slate-700 rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold text-slate-100 text-[11px]">{sol.name}</span>
                      <span className="text-[10px] font-mono text-emerald-400 font-bold">{sol.price}</span>
                    </div>
                    <p className="text-[10px] text-slate-300 leading-normal">{sol.desc}</p>
                  </div>
                ))}
              </div>

              {/* 1-Click Neteller Checkout Bar */}
              <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg flex items-center justify-between text-xs">
                <span className="text-slate-300">
                  Ready to close? Deposit rail: <strong className="text-emerald-400 font-mono">Neteller (ID 4599228811)</strong>
                </span>
                <a
                  href={netellerCheckoutUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3 py-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black rounded text-[11px] transition-all shadow-sm flex items-center gap-1"
                >
                  <span>💰 1-Click Checkout</span>
                </a>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          2.5 TAILORED VERBATIM SCRIPT & SCRIPT ID PLAYBOOK
          ───────────────────────────────────────────────────────────── */}
      {lead.Call_Script && (
        <div className="p-4 bg-slate-900/90 border border-cyan-500/30 rounded-xl shadow-md">
          <div className="flex items-center justify-between mb-2.5 pb-1 border-b border-cyan-500/20">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-cyan-300 font-mono flex items-center gap-1.5">
                <span>📋 TAILORED VERBATIM SCRIPT</span>
                {lead.script_id && (
                  <span className="text-[9px] bg-cyan-950 text-cyan-400 border border-cyan-700/50 px-1.5 py-0.5 rounded font-mono">
                    {lead.script_id}
                  </span>
                )}
                {lead.segment && (
                  <span className="text-[9px] bg-indigo-950 text-indigo-400 border border-indigo-700/50 px-1.5 py-0.5 rounded font-mono">
                    {lead.segment}
                  </span>
                )}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => copyToClipboard(lead.Call_Script!, "full_script")}
                className="text-[10px] font-mono px-2 py-0.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 rounded border border-cyan-500/40"
              >
                {copiedQuestion === "full_script" ? "COPIED!" : "COPY SCRIPT"}
              </button>
              <button
                onClick={() => setShowFullScript(!showFullScript)}
                className="text-[10px] text-cyan-400 hover:text-cyan-300 font-mono"
              >
                {showFullScript ? "Collapse" : "Expand"}
              </button>
            </div>
          </div>
          {showFullScript && (
            <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-lg text-slate-200 text-xs font-sans whitespace-pre-line leading-relaxed">
              {lead.Call_Script}
            </div>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          3. SCRIPT PLAYBOOK & DYNAMIC DISCOVERY LADDER
          ───────────────────────────────────────────────────────────── */}
      {isSeller ? (
        <div className="space-y-4">
          <SectionHeader color="text-amber-400">
            <span>🎙 SELLER CALL PLAYBOOK</span>
            <span className="text-[9px] text-slate-400 font-normal">Dynamic Flow</span>
          </SectionHeader>

          {/* Opening Variants Selector */}
          <div>
            <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1.5 flex items-center justify-between">
              <span>Choose Opening:</span>
              <span className="text-amber-400 font-mono text-[9px]">Evidence-Based</span>
            </div>
            <div className="grid grid-cols-4 gap-1 mb-2">
              {(
                [
                  { id: "general", label: "General" },
                  { id: "absentee", label: "Absentee" },
                  { id: "vacant", label: "Vacant" },
                  { id: "rental", label: "Rental" },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setSellerOpeningMode(opt.id)}
                  className={`py-1 text-[11px] font-bold rounded transition-colors ${
                    sellerOpeningMode === opt.id
                      ? "bg-amber-500 text-slate-950 shadow-sm"
                      : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="p-3 bg-slate-900/80 border border-amber-500/30 rounded-lg text-slate-200 leading-relaxed text-xs">
              {sellerOpeningMode === "general" && (
                <p>
                  "Hey {lead.contact}, I'm Mohammed. I know I'm calling out of the blue. I'm reaching out about the property on{" "}
                  <strong className="text-amber-300 font-semibold">{propertyAddress}</strong>. Did I catch the owner?"
                </p>
              )}
              {sellerOpeningMode === "absentee" && (
                <p>
                  "Hey {lead.contact}, I'm calling about the property on{" "}
                  <strong className="text-amber-300 font-semibold">{propertyAddress}</strong>. I believe you're the owner on file — are you still holding that property or would you consider a cash offer?"
                </p>
              )}
              {sellerOpeningMode === "vacant" && (
                <p>
                  "Hey {lead.contact}, quick question about the property on{" "}
                  <strong className="text-amber-300 font-semibold">{propertyAddress}</strong>. Is it currently occupied, or is it sitting vacant right now?"
                </p>
              )}
              {sellerOpeningMode === "rental" && (
                <p>
                  "Hey {lead.contact}, are you planning to keep the property on{" "}
                  <strong className="text-amber-300 font-semibold">{propertyAddress}</strong> as a rental long term, or have you thought about getting out of the landlord headaches?"
                </p>
              )}
            </div>
          </div>

          {/* Dynamic Discovery Ladder */}
          <div>
            <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-2">
              🧠 Seller Discovery Questions (Click to Copy):
            </div>
            <div className="space-y-1.5">
              {[
                { id: "q1", text: "Are you currently living in the property, or is it rented out?" },
                { id: "q2", text: "How long have you owned it, and what's the situation with it right now?" },
                { id: "q3", text: "Are you planning to keep it long term, or have you considered letting it go?" },
                { id: "q4", text: "What kind of timeline are you working with if we could close cash with zero fees?" },
                { id: "q5", text: "Is there anything about the property or maintenance you'd rather not deal with?" },
                { id: "q6", text: "What ballpark number would make selling completely as-is worth considering?" },
              ].map((q) => (
                <button
                  key={q.id}
                  onClick={() => copyToClipboard(q.text, q.id)}
                  className="w-full text-left p-2 rounded bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 hover:border-amber-500/40 text-xs text-slate-300 flex items-center justify-between group transition-all"
                >
                  <span>{q.text}</span>
                  <span className="text-[10px] font-mono text-amber-400 opacity-0 group-hover:opacity-100 transition-opacity">
                    {copiedQuestion === q.id ? "COPIED" : "COPY"}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Cash Offer Pitch */}
          <div className="p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-xl">
            <span className="text-[10px] text-amber-400 font-bold uppercase tracking-wider block mb-1">
              💰 Cash Offer Pitch (As-Is Close):
            </span>
            <p className="text-xs text-slate-200 leading-relaxed mb-2">
              "We buy completely as-is, which means you pay zero commissions, zero closing fees, and don't have to fix or clean a thing. If our underwriting team runs the comps today, could I get you a firm cash number by tomorrow morning?"
            </p>
            <div className="flex items-center justify-between pt-2 border-t border-amber-500/20 text-xs">
              <span className="text-slate-400">Offer Rail:</span>
              <span className="text-amber-300 font-bold font-mono">As-Is Cash Close / 7-Day Neteller Assignment</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <SectionHeader color="text-indigo-400">
            <span>🎙 AI CONSULTANCY PLAYBOOK</span>
            <span className="text-[9px] text-emerald-400 font-mono">Land & Expand</span>
          </SectionHeader>

          {/* Positioning — operational system, not generic AI */}
          <div className="p-3 bg-gradient-to-r from-indigo-950/60 to-purple-950/40 border border-indigo-500/30 rounded-xl">
            <span className="text-[10px] font-bold text-indigo-300 uppercase tracking-wider block mb-1">
              Consultancy Positioning ("What Do You Do?"):
            </span>
            <p className="text-xs text-slate-200 leading-relaxed italic">
              "We build operational workflows for practices — intake, scheduling, recall, rebooking and follow-up — directly into your existing software, so overdue patients get booked and staff time is recovered."
            </p>
          </div>

          {/* Opening Hook — observation → discovery, not pitch */}
          <div className="p-3.5 bg-slate-900/80 border border-indigo-500/30 rounded-xl">
            <span className="text-[10px] text-indigo-400 font-bold uppercase tracking-widest block mb-1">
              🎙 Opening Hook (Pattern Interrupt):
            </span>
            <p className="text-xs text-slate-200 leading-relaxed">
              "Hey {lead.contact}, I know I'm calling out of the blue. I was looking at{" "}
              <strong className="text-white font-semibold">{lead.company}</strong> in your area and wanted to ask how you’re currently handling recall for patients overdue 6+ months — is that mostly manual today?"
            </p>
          </div>

          {/* Discovery Questions */}
          <div>
            <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-2">
              🧠 Diagnostic Discovery Questions — recall / rebooking / intake (Click to Copy):
            </div>
            <div className="space-y-1.5">
              {[
                { id: "ai_q1", text: "How are you currently tracking patients overdue for recall — is there a list, and how often is it worked?" },
                { id: "ai_q2", text: "What happens when a hygiene slot opens last-minute — how is it filled today?" },
                { id: "ai_q3", text: "Where do you feel your front desk loses the most time — intake, scheduling, or follow-up?" },
                { id: "ai_q4", text: "If recall rebooking happened without manual chasing, what would that save per week?" },
                { id: "ai_q5", text: "If you could fix one intake or recall bottleneck tomorrow, which one would it be?" },
              ].map((q) => (
                <button
                  key={q.id}
                  onClick={() => copyToClipboard(q.text, q.id)}
                  className="w-full text-left p-2 rounded bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 hover:border-indigo-500/40 text-xs text-slate-300 flex items-center justify-between group transition-all"
                >
                  <span>{q.text}</span>
                  <span className="text-[10px] font-mono text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity">
                    {copiedQuestion === q.id ? "COPIED" : "COPY"}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          4. 12-CATEGORY OBJECTION MATRIX (5-STEP RESOLUTION)
          ───────────────────────────────────────────────────────────── */}
      <div>
        <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-2 flex items-center justify-between">
          <span>🛡 12 Objection Playbooks:</span>
          <span className="text-cyan-400 font-mono text-[9px]">Acknowledge → Clarify → Isolate → Respond → Check</span>
        </div>
        <div className="grid grid-cols-3 md:grid-cols-4 gap-1 mb-2">
          {(
            [
              "PRICE",
              "TIMING",
              "TRUST",
              "AI_SKEPTICISM",
              "ALREADY_HAVE_SOLUTION",
              "DO_IT_INTERNALLY",
              "NO_NEED",
              "NO_BUDGET",
              "AUTHORITY",
              "SECURITY",
              "INTEGRATION",
              "STAFF",
            ] as const
          ).map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveObjectionCategory(activeObjectionCategory === cat ? null : cat)}
              className={`py-1 px-1.5 text-[9px] font-bold rounded truncate transition-colors uppercase ${
                activeObjectionCategory === cat
                  ? "bg-cyan-500 text-slate-950 font-black shadow-sm"
                  : "bg-slate-800/80 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
              }`}
            >
              {cat.replace(/_/g, " ")}
            </button>
          ))}
        </div>

        {activeObjectionCategory && (
          <div className="p-3.5 bg-slate-900 border border-cyan-500/40 rounded-xl text-xs text-slate-200 leading-relaxed shadow-lg animate-fadeIn">
            <span className="text-[10px] uppercase tracking-widest text-cyan-300 font-bold block mb-1">
              5-Step Response for {activeObjectionCategory.replace(/_/g, " ")}:
            </span>
            <div className="space-y-1 text-[11px]">
              <p><strong className="text-slate-400">1. Acknowledge:</strong> "I completely hear you — that makes total sense."</p>
              <p><strong className="text-slate-400">2. Clarify:</strong> "Is it primarily about the monthly budget, or making sure the setup doesn't disrupt daily operations?"</p>
              <p><strong className="text-slate-400">3. Isolate:</strong> "If we could prove it recovers 3x its cost in the first 30 days, would you be open to a 5-minute walkthrough?"</p>
              <p className="p-2 bg-slate-950/80 border border-cyan-500/20 rounded font-medium text-cyan-100">
                <strong className="text-cyan-400">4. Respond:</strong> "Our retainer is backed by a 30-day performance guarantee — recovering just two missed patient calls covers 100% of the cost."
              </p>
              <p><strong className="text-slate-400">5. Check:</strong> "Does tomorrow morning at 10 AM or 2 PM work better for a quick 10-minute screen share?"</p>
            </div>
          </div>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────
          5. 1-CLICK NETELLER SETTLEMENT & CHECKOUT CARD
          ───────────────────────────────────────────────────────────── */}
      <div className="p-4 bg-gradient-to-r from-emerald-950/40 via-slate-900 to-cyan-950/40 border border-emerald-500/40 rounded-xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-mono font-bold text-xs uppercase tracking-wider">
              💳 Neteller 1-Click Checkout
            </span>
            <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold">
              CANONICAL RAIL
            </span>
          </div>
          <span className="text-[10px] font-mono text-slate-400">
            Account: 4599228811
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs font-mono">
          <div className="p-2.5 rounded bg-slate-950/80 border border-slate-800">
            <div className="text-[10px] text-slate-400 uppercase">Setup & Onboarding</div>
            <div className="text-sm font-bold text-white mt-0.5">
              ${(lead.setup_price || lead.offer?.setup_price_usd || 4500).toLocaleString()} USD
            </div>
          </div>
          <div className="p-2.5 rounded bg-slate-950/80 border border-slate-800">
            <div className="text-[10px] text-slate-400 uppercase">Monthly Maintenance</div>
            <div className="text-sm font-bold text-emerald-400 mt-0.5">
              ${(lead.maintenance_price || lead.offer?.maintenance_price_usd || 1500).toLocaleString()}/mo
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <a
            href={
              lead.offer?.neteller_checkout_link ||
              lead.sales_strategy?.offer?.neteller_checkout_link ||
              `https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount=${lead.setup_price || 4500}&currency=USD&item=${encodeURIComponent(lead.company || "AI-RETAINER")}`
            }
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 py-2 px-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xs font-mono text-center shadow-lg transition-all"
          >
            ⚡ Open Neteller Pay ($
            {(lead.setup_price || lead.offer?.setup_price_usd || 4500).toLocaleString()})
          </a>
          <button
            onClick={() => {
              const link =
                lead.offer?.neteller_checkout_link ||
                lead.sales_strategy?.offer?.neteller_checkout_link ||
                `https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount=${lead.setup_price || 4500}&currency=USD&item=${encodeURIComponent(lead.company || "AI-RETAINER")}`;
              navigator.clipboard.writeText(link);
              setCopiedQuestion("neteller_link");
              setTimeout(() => setCopiedQuestion(null), 2000);
            }}
            className="py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-mono font-bold text-slate-200 transition-all"
          >
            {copiedQuestion === "neteller_link" ? "✓ COPIED" : "COPY LINK"}
          </button>
        </div>
      </div>
    </div>
  );
}
