-- VOICE AGENTS
CREATE TABLE IF NOT EXISTS public.voice_agents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title TEXT NOT NULL,
  description TEXT,
  persona TEXT,
  system_prompt TEXT,
  voice_provider TEXT DEFAULT 'elevenlabs',
  voice_id TEXT,
  model_name TEXT DEFAULT 'gemini-1.5-flash-audio',
  rate_per_min DECIMAL DEFAULT 0.45,
  creator_id UUID REFERENCES public.users(id),
  creator_name TEXT DEFAULT 'Jarvis AI Studio',
  total_calls INTEGER DEFAULT 0,
  total_minutes DECIMAL DEFAULT 0.0,
  total_earnings DECIMAL DEFAULT 0.0,
  status TEXT DEFAULT 'active',
  tags TEXT[] DEFAULT ARRAY['Cold Calling', 'Real Estate'],
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- CREATOR EARNINGS LEDGER
CREATE TABLE IF NOT EXISTS public.creator_earnings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  creator_id UUID REFERENCES public.users(id),
  agent_id UUID REFERENCES public.voice_agents(id),
  call_duration_secs INTEGER DEFAULT 60,
  amount_earned DECIMAL NOT NULL,
  payout_status TEXT DEFAULT 'pending',
  payout_method TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- RLS POLICIES (Stubbed)
ALTER TABLE public.voice_agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.creator_earnings ENABLE ROW LEVEL SECURITY;
