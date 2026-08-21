# Shared Platform Map — Reusable Foundation

Grounded 2026-08-19 against actual files in this workspace. Rule: **one canonical implementation per module**; duplicates are listed under DUPLICATES for consolidation, never re-created.

Legend: ✅ CANONICAL (reuse this) · 🔁 DUPLICATE (consolidate) · ⚠️ PARTIAL (exists, needs completion) · ❌ MISSING (build once, shared)

---

## AUTH
| Status | Implementation | Where |
|---|---|---|
| ✅ | JWT auth plugin (admin/client roles, `requireRole`, rate-limit helper) | `MBM/LeadEngine/api/auth.ts` |
| ✅ | Frontend login/register/reset + ProtectedRoute + RoleRoute | `src/pages/{Login,Register,ForgotPassword,ResetPassword}.jsx`, `src/components/{ProtectedRoute,RoleRoute,AuthLayout}.jsx` |
| ⚠️ | Supabase auth also present (for Bawab app) | `src/api/supabaseClient.js` — keep for Bawab; do NOT use as platform auth |

## TENANTS
| Status | Implementation | Where |
|---|---|---|
| ✅ | `Client` model + `clientId` FK on `Lead`, `Export`, `Subscription`; tier enum STARTER_100/GROWTH_500/SCALE_1000/COUNTY/STATE/ENTERPRISE | `MBM/LeadEngine/prisma/schema.prisma`, `api/routes/clients.ts` |
| ⚠️ | `clientId` NOT enforced as a scope filter on `GET /api/leads` yet (claim assigns, list is global) | `api/routes/leads.ts` — must scope list/export by `request.user.clientId` |

## USERS / ROLES
| Status | Implementation | Where |
|---|---|---|
| ✅ | JWT role `admin` | `client` + clientId claims | `MBM/LeadEngine/api/auth.ts` |
| ✅ | User management page + sales members | `src/pages/UserManagement.jsx`, `src/pages/SalesMembers.jsx` |

## BILLING
| Status | Implementation | Where |
|---|---|---|
| ✅ | Neteller checkout links (canonical rail) | `MBM/Scripts/neteller_config.py`, `server/neteller.js`, `src/lib/neteller.js` |
| ✅ | Whop storefront (separate hosted channel) | `MBM/Whop/whop_monetize.py` |
| ✅ | Client subscription model + credits | `prisma` `Client`/`Subscription`, `api/routes/clients.ts` |
| ⚠️ | No webhook-to-credits grant loop (paid → creditsRemaining++); wire Neteller/Whop → credits | `api/routes/admin.ts` |

## CRM
| Status | Implementation | Where |
|---|---|---|
| ✅ | Client/orders/pipeline endpoints | `server/index.js` (`/api/orders`, `/api/sales/*`), `supabase/migrations` |
| ⚠️ | No unified customer record across products | Product factory needs one `Customer`/`Organization` root |

## LEADS
| Status | Implementation | Where |
|---|---|---|
| ✅ | Canonical dialer DB + single-writer | `mbm-dialer/app/public/leads_database.json`, `MBM/GLM/single_writer_lock.py`, `server/dialer/dialerDbGateway.js`, `MBM/LeadEngine/dialer_gateway.py` |
| ✅ | Queue engine + freshness ordering | `MBM/LeadEngine/dialer_queue_engine.py`, `server/dialer/freshnessOrder.js` |
| ✅ | API list/claim/recalculate/export | `MBM/LeadEngine/api/routes/leads.ts` |
| 🔁 | Multiple queue JSON files (cold_calling_queue.json, multi_touch_queue.json, ulio_voice_queue.json, real_estate_calling_queue.json) | `MBM/LeadEngine/*.json` — consolidate into canonical DB per product tenant |

## CONTACTS / COMPANIES
| Status | Implementation | Where |
|---|---|---|
| ✅ | Owner resolution + provenance | `MBM/LeadEngine/owner_identity.py`, `lead_provenance.py` |
| ✅ | DCAD / county ownership | `MBM/LeadEngine/dcad_owner_lookup.py`, `property_intel/ownership_verifier.py` |
| ✅ | NPI business registry | `MBM/LeadEngine/npi_verified_callsheet.py` |

## DOCUMENTS
| Status | Implementation | Where |
|---|---|---|
| ✅ | BOQ/estimator item parser | `Construction/construction_estimator_engine.py` |
| ⚠️ | No PDF/drawing extraction layer yet | Build once as shared `document_ingest` service |

## AGENTS
| Status | Implementation | Where |
|---|---|---|
| ✅ | Agent registry (16 roles, 3 model tiers) | `MBM/GLM/agent_registry.py` |
| ✅ | Orchestrator + mission router + ledger | `MBM/GLM/orchestrator.py`, `mission_router.py`, `mission_ledger.py` |
| ⚠️ | Agent factory exists (self-generating agents) | `MBM/LeadEngine/agent_factory.py` — validate before reuse |

## MISSIONS / WORKERS / WORKFLOWS
| Status | Implementation | Where |
|---|---|---|
| ✅ | Daily refresh + hourly NPI + code-violation daily + lead pack | `MBM/LeadEngine/daily_refresh.py`, `npi_verified_callsheet.py`, `code_violation/daily.py`, `lead_pack_builder.py` |
| ✅ | CI schedules | `.github/workflows/schedule.yml` |
| ⚠️ | No generic workflow engine; flows are script-bound | Future: thin workflow runner over existing scripts |

## VOICE
| Status | Implementation | Where |
|---|---|---|
| ✅ | Twilio bridge + Phound SMS (canonical outbound) | `server/dialer/phoundSmsProvider.js`, `MBM/LeadEngine/call_bridge_to_phone.py`, `re_call_bridge.py` |
| ✅ | Voice agent studio (ElevenLabs/Retell/Vapi/Synthflow adapters) | `MBM/LeadEngine/voice_agency_studio.py` |
| ✅ | Vapi appointment-setter service | `voice-agent-saas/backend/app/services/vapi_service.py` |
| 🔁 | Multiple dialers (mbm-dialer primary; coldcall cockpit sellable; progressive/power/omega) | `mbm-dialer/app/`, `coldcall/dialer/`, `MBM/LeadEngine/{progressive,power,omega}_dialer*.py` |

## EMAIL
| Status | Implementation | Where |
|---|---|---|
| ✅ | Gmail SMTP + IMAP reply detection + idempotent ledger | `server/emailSender.js`, `server/dialer/../emailSender.js`, `reply_detector.py`, `MBM/LeadEngine/gtm_notification_bus.py` |

## WHATSAPP
| Status | Implementation | Where |
|---|---|---|
| ✅ | Phound SMS rail; WhatsApp direct blaster (Phound-linked) | `MBM/LeadEngine/phound_wave_campaign.py`, `twilio_whatsapp_direct_blaster.py` |

## NOTIFICATIONS
| Status | Implementation | Where |
|---|---|---|
| ✅ | Telegram bus + email adapters | `MBM/LeadEngine/gtm_notification_bus.py`, `send_csv_to_telegram.py` |

## DASHBOARDS / REPORTING
| Status | Implementation | Where |
|---|---|---|
| ✅ | Vite dashboard (pages: Dashboard, AutoDialer, MobileDialer, VoiceAgentsStudio, Reports, Kpis…) | `src/` |
| ✅ | mbm-dialer app (TanStack + Vite + Tailwind) | `mbm-dialer/app/` |
| ✅ | Money & progress reports | `MBM/GLM/delivery_report.py`, `revenue_dashboard.py` |
| 🔁 | Many ad-hoc dashboard generators | `dialer_dashboard_generator.py`, `create_live_call_dashboard.py`, `revenue_dashboard_html.py` — keep ONE product dashboard |

## KNOWLEDGE
| Status | Implementation | Where |
|---|---|---|
| ✅ | Memory/lessons/SOPs/knowledge dirs | `MBM/Knowledge/`, `MBM/Memory/`, `MBM/SOPs/`, `MBM/LessonsLearned/` |
| ⚠️ | No shared vector store | Future: one embeddings store for all products |

## ANALYTICS
| Status | Implementation | Where |
|---|---|---|
| ✅ | KPI/score/audit tooling | `MBM/LeadEngine/lead_quality_scorer.py`, `lead_volume_auditor.py`, `monetization_auditor.py`, `src/pages/Kpis.jsx` |
| ⚠️ | No per-tenant usage analytics | Extend `Client.creditsRemaining` into a usage ledger |

---

## DUPLICATES TO CONSOLIDATE (never re-create)
1. **Dialer engines**: `progressive_dialer.py`, `power_dialer.py`, `omega_telephony_dialer_engine.py`, `coldcall/`, `higgsfield_dailer.py` — primary = `mbm-dialer/app`; coldcall cockpit = sellable standalone; rest archive.
2. **Queue JSON files**: `cold_calling_queue.json`, `multi_touch_queue.json`, `ulio_voice_queue.json`, `us_re_dialer_queue.json`, `real_estate_calling_queue.json` — canonical = `mbm-dialer/app/public/leads_database.json`.
3. **Dashboard generators**: consolidate into one product dashboard.
4. **Script builders**: `dialer_script_engine.py`, `lead_scripts.py`, `cgpt_script_generator.py`, `script_package.py` — canonical = `dialer_script_engine.py`.
5. **Skip tracers**: `free_skip_tracer.py`, `seller_skip_tracer.py`, `npi_skip_enricher.py`, `skip_trace_all.py` — keep per-vertical, share phone validation via `lead_provenance.py`.
6. **Voice adapters**: `voice_agency_studio.py` vs `voice-agent-saas/backend/app/services/vapi_service.py` — canonical for appointment flow = voice-agent-saas; studio stays for revenue platform adapters.

## MISSING SHARED MODULES (build once, used by every product)
1. Tenant-scoped lead list/export middleware (`clientId` enforcement).
2. Billing webhook → credits loop (Neteller/Whop → `Client.creditsRemaining`).
3. Unified Customer/Organization root entity.
4. Shared document ingest (PDF/drawing → structured items).
5. Generic workflow runner (daily tasks as config).
6. Usage/analytics ledger per tenant.