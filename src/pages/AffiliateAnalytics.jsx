import React, { useState } from 'react';
import { 
  TrendingUp, 
  DollarSign, 
  Eye, 
  MousePointer, 
  BarChart3, 
  RefreshCw, 
  ShieldCheck,
  Zap,
  Layers,
  ArrowUpRight
} from 'lucide-react';

export default function AffiliateAnalytics() {
  const [timeframe, setTimeframe] = useState('7d');
  
  const metrics = [
    { title: 'Total Projected Revenue', value: '$4,850.20', change: '+24.5%', icon: DollarSign, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
    { title: 'Affiliate Clicks', value: '18,420', change: '+18.2%', icon: MousePointer, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20' },
    { title: 'Total Clip Views', value: '248,900', change: '+32.1%', icon: Eye, color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/20' },
    { title: 'Conversion Rate', value: '3.42%', change: '+0.6%', icon: TrendingUp, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
  ];

  const campaigns = [
    { name: 'Vyro MrBeast Bounty', platform: 'Vyro', category: 'Performance', views: '112,400', clicks: '6,210', conversions: 240, revenue: '$1,200.00', status: 'Active' },
    { name: 'Dynamiq 50% Comm', platform: 'Dynamiq', category: 'Voice AI', views: '45,200', clicks: '2,890', conversions: 38, revenue: '$1,520.00', status: 'Active' },
    { name: 'OpusClip 25% Recurring', platform: 'OpusClip', category: 'SaaS', views: '38,100', clicks: '3,100', conversions: 85, revenue: '$850.00', status: 'Active' },
    { name: 'Invideo AI Faceless', platform: 'Invideo', category: 'SaaS', views: '28,900', clicks: '2,450', conversions: 42, revenue: '$630.00', status: 'Active' },
    { name: 'Islamic Reminders Dawah', platform: 'MuslimsClipping', category: 'Dawah', views: '15,800', clicks: '2,120', conversions: 110, revenue: '$420.00', status: 'Active' },
    { name: 'Whop Reseller Blueprint', platform: 'Whop', category: 'Digital Products', views: '8,500', clicks: '1,650', conversions: 15, revenue: '$230.20', status: 'Active' }
  ];

  return (
    <div className="p-6 bg-slate-950 min-h-screen text-slate-100 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-7 h-7 text-indigo-400" />
            Affiliate Clicks & Revenue Engine
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time analytics across Vyro, Whop, OpusClip, Dynamiq, Synthflow, and MuslimsClipping campaigns.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select 
            value={timeframe} 
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-sm rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
          </select>
          <button className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            <RefreshCw className="w-4 h-4" />
            Sync Networks
          </button>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((m, idx) => (
          <div key={idx} className={`p-4 rounded-xl border ${m.bg} flex justify-between items-start`}>
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">{m.title}</p>
              <h3 className="text-2xl font-extrabold text-white mt-1">{m.value}</h3>
              <span className="inline-block text-xs font-semibold text-emerald-400 mt-2">{m.change} vs previous</span>
            </div>
            <div className={`p-2.5 rounded-lg bg-slate-900/80 ${m.color}`}>
              <m.icon className="w-5 h-5" />
            </div>
          </div>
        ))}
      </div>

      {/* Campaign Performance Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-400" />
            Active Monetization Campaigns ({campaigns.length})
          </h2>
          <span className="text-xs bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-2.5 py-1 rounded-full font-medium flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5" /> All Systems Monetized
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950 text-slate-400 uppercase text-xs border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Campaign Name</th>
                <th className="py-3 px-4">Platform</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Clip Views</th>
                <th className="py-3 px-4">Clicks</th>
                <th className="py-3 px-4">Conversions</th>
                <th className="py-3 px-4">Est. Revenue</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {campaigns.map((c, idx) => (
                <tr key={idx} className="hover:bg-slate-800/50 transition-colors">
                  <td className="py-3.5 px-4 font-semibold text-white flex items-center gap-2">
                    <Layers className="w-4 h-4 text-indigo-400" />
                    {c.name}
                  </td>
                  <td className="py-3.5 px-4 font-medium text-slate-300">{c.platform}</td>
                  <td className="py-3.5 px-4">
                    <span className="bg-slate-800 border border-slate-700 text-slate-300 text-xs px-2.5 py-0.5 rounded">
                      {c.category}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-purple-300 font-mono">{c.views}</td>
                  <td className="py-3.5 px-4 text-blue-300 font-mono">{c.clicks}</td>
                  <td className="py-3.5 px-4 text-amber-300 font-mono">{c.conversions}</td>
                  <td className="py-3.5 px-4 font-bold text-emerald-400 font-mono">{c.revenue}</td>
                  <td className="py-3.5 px-4 text-right">
                    <button className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center gap-1">
                      Details <ArrowUpRight className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
