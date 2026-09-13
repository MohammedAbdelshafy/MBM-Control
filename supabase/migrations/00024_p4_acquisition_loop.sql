-- 00024_p4_acquisition_loop.sql
-- P4 DFY acquisition loop: minimal durable spine.
-- Reuses business_prospects (prospect), outreach_* (send pipeline),
-- client_orders/payments (money). Adds only the three missing links:
-- gate output, conversations, offers. Everything IF NOT EXISTS.

-- 1. Qualification results (deterministic gate output per prospect)
CREATE TABLE IF NOT EXISTS public.qualification_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL REFERENCES public.business_prospects(id) ON DELETE CASCADE,
    outreach_lead_id UUID REFERENCES public.outreach_leads(id) ON DELETE SET NULL,
    status TEXT NOT NULL, -- VERIFIED, CALLABLE, NOT CALLABLE, DUPLICATE, SUPPRESSED, NEEDS REVIEW
    reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_class TEXT NOT NULL DEFAULT 'UNKNOWN', -- VERIFIED, INFERENCE, HYPOTHESIS, UNKNOWN
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb, -- authoritative source pointers, never copied PII
    runner_version TEXT, -- clean_leads.py / qualification_runner version or git sha
    ran_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_qualification_evidence_class CHECK (evidence_class IN ('VERIFIED', 'INFERENCE', 'HYPOTHESIS', 'UNKNOWN'))
);

CREATE INDEX IF NOT EXISTS idx_qualification_results_prospect ON public.qualification_results(prospect_id);
CREATE INDEX IF NOT EXISTS idx_qualification_results_status ON public.qualification_results(status);

-- 2. Conversations (reply tracking toward an offer)
CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL REFERENCES public.business_prospects(id) ON DELETE CASCADE,
    outreach_lead_id UUID REFERENCES public.outreach_leads(id) ON DELETE SET NULL,
    channel TEXT NOT NULL DEFAULT 'email', -- email, whatsapp, sms, call
    state TEXT NOT NULL DEFAULT 'open', -- open, replied, qualified, unresponsive, closed
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_prospect ON public.conversations(prospect_id);
CREATE INDEX IF NOT EXISTS idx_conversations_state ON public.conversations(state);

-- 3. Offers ($499 DFY / free sample / $49 subscription)
CREATE TABLE IF NOT EXISTS public.offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL REFERENCES public.business_prospects(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
    offer_type TEXT NOT NULL, -- free_sample, dfy_499, subscription_49
    amount_cents INT NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    state TEXT NOT NULL DEFAULT 'draft', -- draft, sent, accepted, paid, expired
    neteller_item TEXT, -- SKU passed to the canonical neteller_link builder
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_offers_prospect ON public.offers(prospect_id);
CREATE INDEX IF NOT EXISTS idx_offers_state ON public.offers(state);

-- RLS (same posture as 00021: admin/authenticated access, tighten later)
ALTER TABLE public.qualification_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.offers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow full access to qualification_results for auth users" ON public.qualification_results;
CREATE POLICY "Allow full access to qualification_results for auth users" ON public.qualification_results FOR ALL TO authenticated USING (true);
DROP POLICY IF EXISTS "Allow full access to conversations for auth users" ON public.conversations;
CREATE POLICY "Allow full access to conversations for auth users" ON public.conversations FOR ALL TO authenticated USING (true);
DROP POLICY IF EXISTS "Allow full access to offers for auth users" ON public.offers;
CREATE POLICY "Allow full access to offers for auth users" ON public.offers FOR ALL TO authenticated USING (true);

-- updated_at triggers
CREATE OR REPLACE FUNCTION update_p4_loop_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_conversations_updated_at ON public.conversations;
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON public.conversations FOR EACH ROW EXECUTE FUNCTION update_p4_loop_updated_at_column();
DROP TRIGGER IF EXISTS update_offers_updated_at ON public.offers;
CREATE TRIGGER update_offers_updated_at BEFORE UPDATE ON public.offers FOR EACH ROW EXECUTE FUNCTION update_p4_loop_updated_at_column();
