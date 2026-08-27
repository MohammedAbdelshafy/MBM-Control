import React, { useEffect, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  TrendingUp, Users, Home, MapPin, DollarSign,
  Clock, RefreshCw, Zap
} from 'lucide-react';
import { toast } from 'sonner';

const API = '/api';

const SIGNAL_META = {
  HOT: { color: 'emerald', label: 'HOT', description: '5+ active buyers' },
  WARM: { color: 'amber', label: 'WARM', description: '3-4 active buyers' },
  NORMAL: { color: 'sky', label: 'NORMAL', description: '1-2 active buyers' },
  WEAK: { color: 'slate', label: 'WEAK', description: 'Verified buyer only' },
  UNKNOWN: { color: 'red', label: 'UNKNOWN', description: 'No buyers in segment' },
};

const COLOR_CLASSES = {
  emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', dot: 'bg-emerald-500' },
  amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', dot: 'bg-amber-500' },
  sky: { bg: 'bg-sky-500/10', border: 'border-sky-500/30', text: 'text-sky-400', dot: 'bg-sky-500' },
  slate: { bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', dot: 'bg-slate-500' },
  red: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', dot: 'bg-red-500' },
};

function DemandSignalCard({ signal }) {
  const meta = SIGNAL_META[signal.signal] || SIGNAL_META.UNKNOWN;
  const colors = COLOR_CLASSES[meta.color];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-5 rounded-xl border ${colors.border} ${colors.bg}`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${colors.dot}`} />
          <span className={`text-sm font-bold ${colors.text}`}>{meta.label}</span>
        </div>
        <span className="text-xs text-white/30">{meta.description}</span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-white/40 mb-1">Market</div>
          <div className="text-sm font-medium text-white flex items-center gap-1">
            <MapPin className="w-3 h-3" />
            {signal.market}
          </div>
        </div>
        <div>
          <div className="text-xs text-white/40 mb-1">Property Type</div>
          <div className="text-sm font-medium text-white flex items-center gap-1">
            <Home className="w-3 h-3" />
            {signal.property_type}
          </div>
        </div>
        <div>
          <div className="text-xs text-white/40 mb-1">Price Band</div>
          <div className="text-sm font-medium text-white flex items-center gap-1">
            <DollarSign className="w-3 h-3" />
            {signal.price_band}
          </div>
        </div>
        <div>
          <div className="text-xs text-white/40 mb-1">Active / Verified Buyers</div>
          <div className="text-sm font-medium text-white flex items-center gap-1">
            <Users className="w-3 h-3" />
            {signal.active_buyers} / {signal.verified_buyers}
          </div>
        </div>
      </div>

      {signal.calculated_at && (
        <div className="mt-3 pt-3 border-t border-white/5 flex items-center gap-1 text-xs text-white/30">
          <Clock className="w-3 h-3" />
          Updated: {new Date(signal.calculated_at).toLocaleString()}
        </div>
      )}
    </motion.div>
  );
}

function BuyerCard({ buyer }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/10 transition-colors"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-white">{buyer.buyer_name}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${
          buyer.verification_status === 'VERIFIED'
            ? 'bg-emerald-500/20 text-emerald-300'
            : 'bg-white/10 text-white/50'
        }`}>
          {buyer.verification_status}
        </span>
      </div>

      <div className="flex items-center gap-4 text-xs text-white/40">
        <span className="flex items-center gap-1">
          <MapPin className="w-3 h-3" />
          {buyer.markets?.join(', ') || 'N/A'}
        </span>
        <span className="flex items-center gap-1">
          <Home className="w-3 h-3" />
          {buyer.property_types?.join(', ') || 'N/A'}
        </span>
      </div>

      <div className="flex items-center gap-4 mt-2 text-xs text-white/40">
        <span>${buyer.price_min?.toLocaleString()} - ${buyer.price_max?.toLocaleString()}</span>
        <span className="flex items-center gap-1">
          <Zap className="w-3 h-3" />
          Activity: {buyer.activity_score}
        </span>
      </div>

      {buyer.total_closes > 0 && (
        <div className="mt-2 text-xs text-emerald-400">
          {buyer.total_closes} closes | Avg {buyer.avg_days_to_close} days
        </div>
      )}
    </motion.div>
  );
}

function DemandMarketSection({ market, signals }) {
  const avgScore = signals.reduce((sum, s) => {
    const scoreMap = { HOT: 100, WARM: 75, NORMAL: 50, WEAK: 25, UNKNOWN: 0 };
    return sum + (scoreMap[s.signal] || 0);
  }, 0) / signals.length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <MapPin className="w-4 h-4 text-emerald-400" />
          {market}
        </h3>
        <span className="text-sm text-white/40">{signals.length} segments</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {signals.map((s, i) => (
          <DemandSignalCard key={`${s.market}-${s.property_type}-${s.price_band}-${i}`} signal={s} />
        ))}
      </div>
    </div>
  );
}

export default function BuyerDemand() {
  const [dashboard, setDashboard] = useState(null);
  const [buyers, setBuyers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('signals');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [dashRes, buyerRes] = await Promise.all([
        fetch(`${API}/ad/demand`),
        fetch(`${API}/ad/buyers`),
      ]);
      const dashData = await dashRes.json();
      const buyerData = await buyerRes.json();
      setDashboard(dashData);
      setBuyers(buyerData.buyers || []);
    } catch (err) {
      toast.error('Failed to load demand data');
    } finally {
      setLoading(false);
    }
  };

  const marketGroups = useMemo(() => {
    if (!dashboard?.market_demand) return {};
    return dashboard.market_demand;
  }, [dashboard]);

  return (
    <div className="min-h-screen bg-[#06080f] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Buyer Demand</h1>
            <p className="text-white/40 text-sm mt-1">Market intelligence and buyer activity</p>
          </div>
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-2 bg-white/5 hover:bg-white/10 text-white/70 px-4 py-2 rounded-xl text-sm transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Summary Cards */}
        {dashboard && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10">
              <div className="text-xs text-white/40 mb-1">Total Segments</div>
              <div className="text-2xl font-bold text-emerald-400">{dashboard.total_segments}</div>
            </div>
            <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10">
              <div className="text-xs text-white/40 mb-1">Hot Segments</div>
              <div className="text-2xl font-bold text-emerald-400">{dashboard.hot_segments}</div>
            </div>
            <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10">
              <div className="text-xs text-white/40 mb-1">Warm Segments</div>
              <div className="text-2xl font-bold text-amber-400">{dashboard.warm_segments}</div>
            </div>
            <div className="p-4 rounded-xl border border-sky-500/30 bg-sky-500/10">
              <div className="text-xs text-white/40 mb-1">Active Buyers</div>
              <div className="text-2xl font-bold text-sky-400">{buyers.length}</div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 border-b border-white/10 pb-2">
          {[
            { key: 'signals', label: 'Demand Signals', icon: TrendingUp },
            { key: 'buyers', label: 'Buyer Pool', icon: Users },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? 'bg-white/10 text-white'
                  : 'text-white/40 hover:text-white/60'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        {loading ? (
          <div className="text-center py-12 text-white/30">Loading...</div>
        ) : activeTab === 'signals' ? (
          <div className="space-y-8">
            {Object.keys(marketGroups).length === 0 ? (
              <div className="text-center py-12 text-white/30">
                No demand signals yet. Register buyers to generate signals.
              </div>
            ) : (
              Object.entries(marketGroups).map(([market, signals]) => (
                <DemandMarketSection key={market} market={market} signals={signals} />
              ))
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {buyers.length === 0 ? (
              <div className="text-center py-12 text-white/30">
                No buyers registered yet.
              </div>
            ) : (
              buyers.map(buyer => (
                <BuyerCard key={buyer.buyer_id} buyer={buyer} />
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
