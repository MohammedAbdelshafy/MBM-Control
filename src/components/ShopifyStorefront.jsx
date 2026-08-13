import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Sparkles, Video, Crown,
  ArrowRight, Lock, Check, ShieldCheck, Zap,
} from 'lucide-react';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

/* 4 flagship products — mirroring MBM/Shopify/logs/shopify_catalog.json */
const PRODUCTS = [
  {
    id: 'prod_ai_agent_suite',
    title: 'Contec AI Agent Suite',
    subtitle: 'Full License',
    price: 299,
    compare_at: 399,
    icon: Sparkles,
    blurb: 'Complete autonomous AI agent suite — clipping factory, lead engine, auto-dialer.',
    accent: ['AI Agent', 'Automation', 'Flagship'],
    checkout: 'https://contec-ai-store.myshopify.com/cart/40112233:1',
    gradient: 'from-indigo-500/25 via-purple-500/10 to-transparent',
  },
  {
    id: 'prod_clipping_sub_pro',
    title: 'Clipping Factory Pro',
    subtitle: '30-Day Subscription',
    price: 99,
    period: '/mo',
    compare_at: 149,
    icon: Video,
    blurb: 'Autonomous 1080p60 short video generation & multi-channel posting daemon.',
    accent: ['Subscription', 'Reels', 'Shorts'],
    checkout: 'https://contec-ai-store.myshopify.com/cart/40112234:1',
    gradient: 'from-cyan-500/25 via-sky-500/10 to-transparent',
  },
  {
    id: 'prod_lead_engine_pass',
    title: 'Buyer & Seller Lead Pack',
    subtitle: '300 Verified Leads',
    price: 250,
    compare_at: 399,
    icon: Zap,
    blurb: 'Verified skip-traced real estate leads across US, UK & EU markets.',
    accent: ['Real Estate', 'B2B', 'Data'],
    checkout: 'https://contec-ai-store.myshopify.com/cart/40112235:1',
    gradient: 'from-emerald-500/25 via-green-500/10 to-transparent',
  },
  {
    id: 'prod_enterprise_setup',
    title: 'Custom Enterprise AI Setup',
    subtitle: 'Dedicated Setup',
    price: 1499,
    compare_at: 2499,
    icon: Crown,
    blurb: '1-on-1 custom agent setup, private server deployment, 24/7 support.',
    accent: ['Enterprise', 'High-Ticket'],
    checkout: 'https://contec-ai-store.myshopify.com/cart/40112236:1',
    gradient: 'from-amber-500/25 via-orange-500/10 to-transparent',
  },
];

const TRUST = [
  { icon: ShieldCheck, label: 'Instant digital delivery' },
  { icon: Lock, label: 'Encrypted checkout' },
  { icon: Zap, label: 'License in your inbox' },
];

export default function ShopifyStorefront() {
  const [ordered, setOrdered] = useState(null);

  const handleCheckout = (p) => {
    setOrdered(p.id);
    window.open(p.checkout, '_blank', 'noopener,noreferrer');
    setTimeout(() => setOrdered(null), 2500);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Ambient glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/4 h-96 w-96 rounded-full bg-indigo-600/20 blur-[120px]" />
        <div className="absolute right-0 top-1/3 h-96 w-96 rounded-full bg-purple-600/10 blur-[120px]" />
      </div>

      <main className="relative mx-auto max-w-6xl px-6 py-14">
        {/* Hero */}
        <motion.header
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center"
        >
          <Badge variant="secondary" className="mb-4 border-white/10 bg-white/5 text-indigo-200">
            <Sparkles className="mr-1 h-3 w-3" /> Official Export
          </Badge>
          <h1 className="text-4xl font-bold tracking-tight md:text-5xl">
            Contec AI{' '}
            <span className="bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Revenue Engine
            </span>
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-slate-400">
            Deploy the autonomous AI building that runs your clipping pipeline, lead engine and dialer overnight.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-5">
            {TRUST.map((t) => (
              <div key={t.label} className="flex items-center gap-1.5 text-xs text-slate-400">
                <t.icon className="h-4 w-4 text-emerald-400" /> {t.label}
              </div>
            ))}
          </div>
        </motion.header>

        {/* Product grid */}
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {PRODUCTS.map((p, i) => (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="h-full"
            >
              <Card className="group relative flex h-full flex-col overflow-hidden border-white/10 bg-white/[0.03] backdrop-blur-xl transition-all hover:-translate-y-1 hover:border-white/20">
                <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${p.gradient} opacity-60`} />
                <CardHeader className="relative">
                  <div className="mb-2 flex items-center justify-between">
                    <p.icon className="h-6 w-6 text-indigo-300" />
                    <Badge variant="secondary" className="border-white/10 bg-white/10 text-[10px]">
                      {p.accent[0]}
                    </Badge>
                  </div>
                  <CardTitle className="text-base leading-tight">{p.title}</CardTitle>
                  <p className="text-xs text-slate-400">{p.subtitle}</p>
                </CardHeader>
                <CardContent className="relative flex flex-1 flex-col">
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold">${p.price}</span>
                    {p.period && <span className="text-sm text-slate-400">{p.period}</span>}
                    <span className="text-sm text-slate-500 line-through">${p.compare_at}</span>
                  </div>
                  <p className="mt-3 text-xs leading-relaxed text-slate-400">{p.blurb}</p>
                  <div className="mt-auto flex flex-wrap gap-1 pt-3">
                    {p.accent.map((a) => (
                      <Badge key={a} variant="outline" className="border-white/10 bg-white/5 text-[10px] text-slate-300">
                        {a}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
                <CardFooter className="relative">
                  <Button
                    className="w-full bg-indigo-500 hover:bg-indigo-400"
                    disabled={ordered === p.id}
                    onClick={() => handleCheckout(p)}
                  >
                    {ordered === p.id ? (
                      <>
                        <Check className="h-4 w-4" /> Ordered
                      </>
                    ) : (
                      <>
                        Checkout · ${p.price} <ArrowRight className="ml-1 h-4 w-4" />
                      </>
                    )}
                  </Button>
                </CardFooter>
              </Card>
            </motion.div>
          ))}
        </div>

        <p className="mt-10 text-center text-xs text-slate-500">
          <Lock className="mr-1 inline h-3 w-3" /> Secure checkout · Instant license delivery · 24/7 support
        </p>
      </main>
    </div>
  );
}