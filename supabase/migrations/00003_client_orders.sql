-- supabase/migrations/00003_client_orders.sql

CREATE TABLE IF NOT EXISTS public.client_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_name TEXT,
  customer_email TEXT NOT NULL,
  customer_phone TEXT,
  company TEXT,
  plan TEXT NOT NULL CHECK (plan IN ('lead_pack_daily', 'lead_pack_monthly', 'ai_email', 'ai_full_stack', 'ai_enterprise', 'custom')),
  amount NUMERIC NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USD',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'failed', 'refunded', 'cancelled')),
  payment_method TEXT CHECK (payment_method IN ('stripe', 'bank_transfer', 'cash', 'crypto')),
  stripe_payment_id TEXT,
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.client_orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anonymous insert" ON public.client_orders
  FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "Allow service role full access" ON public.client_orders
  FOR ALL TO service_role USING (true);
