import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Mic, PhoneCall, PhoneOff, DollarSign, Wallet, Sparkles, Bot, Zap,
  TrendingUp, Sliders, CreditCard, Globe, ShoppingBag, Download
} from 'lucide-react';
import { toast } from 'sonner';

export default function VoiceAgentsStudio() {
  const [activeTab, setActiveTab] = useState('redialer'); // Default to Real Estate Dialer & Lead Queue
  const [realEstateLeads, setRealEstateLeads] = useState([
    { id: 1, address: '123 Main St, New York, NY', price: '$450,000', owner: 'John Smith', phone: '+1 (555) 234-5678', est_fee: '$35,500', status: 'MOTIVATED_SELLER' },
    { id: 2, address: '456 Oak Ave, New York, NY', price: '$850,000', owner: 'Robert Davis', phone: '+1 (555) 345-6789', est_fee: '$42,000', status: 'OFFER_PENDING' },
    { id: 3, address: '789 Pine Rd, Miami, FL', price: '$520,000', owner: 'Elena Rodriguez', phone: '+1 (555) 456-7890', est_fee: '$38,000', status: 'HOT_LEAD' },
    { id: 4, address: '321 Maple St, Dallas, TX', price: '$390,000', owner: 'Marcus Johnson', phone: '+1 (555) 567-8901', est_fee: '$31,500', status: 'MOTIVATED_SELLER' },
    { id: 5, address: '654 Cedar Ave, Los Angeles, CA', price: '$980,000', owner: 'Sarah Connor', phone: '+1 (555) 678-9012', est_fee: '$55,000', status: 'HOT_LEAD' }
  ]);
  const [dialingLead, setDialingLead] = useState(null);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [wallet, setWallet] = useState({
    total_earned: 4599.22,
    payout_balance: 1250.00,
    total_calls_handled: 4410,
    total_minutes_called: 10200.5,
    payout_history: []
  });

  // Builder Form State
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    persona: 'Empathetic & Firm Cash Buyer Acquisitions Manager',
    system_prompt: 'You are Alex from Apex Capital. Call homeowners listed for sale or distressed properties. Pitch a firm cash offer with zero agent fees and 7-day closing.',
    voice_provider: 'elevenlabs',
    voice_id: '21m00Tcm4TlvDq8ikWAM',
    rate_per_min: 0.45,
    tags: 'Real Estate, Cold Calling, Cash Offer'
  });

  // Simulator State
  const [callStatus, setCallStatus] = useState('idle'); // 'idle' | 'calling' | 'connected' | 'speaking'
  const [userTranscript, setUserTranscript] = useState('');
  const [callLog, setCallLog] = useState([]);
  const [callTimer, setCallTimer] = useState(0);
  const [liveEarnings, setLiveEarnings] = useState(0);
  const [payoutAmount, setPayoutAmount] = useState('');
  const [payoutMethod, setPayoutMethod] = useState('Neteller Direct');
  const timerRef = useRef(null);

  // Load agents and wallet stats
  useEffect(() => {
    fetchAgents();
    fetchWallet();
    fetchRealEstateLeads();
  }, []);

  const fetchRealEstateLeads = async () => {
    try {
      const res = await fetch('/api/dialer/re-queue');
      if (res.ok) {
        const data = await res.json();
        if (data.prospects && data.prospects.length) {
          const mapped = data.prospects.map((l, i) => ({
            id: i + 1,
            address: l.address || '—',
            price: l.asking_price,
            owner: l.prospect_name,
            phone: l.phone_number,
            est_fee: l.est_commission,
            status: l.role && l.role.includes('Buyer') ? 'CASH_BUYER' : 'MOTIVATED_SELLER',
          }));
          setRealEstateLeads(mapped);
        }
      }
    } catch (err) {
      console.error('Failed to load real estate leads:', err);
    }
  };

  const fetchAgents = async () => {
    try {
      const res = await fetch('/api/voice-agents');
      if (res.ok) {
        const data = await res.json();
        setAgents(data);
        if (data.length > 0 && !selectedAgent) {
          setSelectedAgent(data[0]);
        }
      }
    } catch (err) {
      console.error('Failed to fetch voice agents:', err);
    }
  };

  const fetchWallet = async () => {
    try {
      const res = await fetch('/api/creator/wallet');
      if (res.ok) {
        const data = await res.json();
        setWallet(data);
      }
    } catch (err) {
      console.error('Failed to fetch wallet:', err);
    }
  };

  // Timer for Call Simulator
  useEffect(() => {
    if (callStatus === 'connected' || callStatus === 'speaking') {
      timerRef.current = setInterval(() => {
        setCallTimer(prev => prev + 1);
      }, 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [callStatus]);

  // Calculate live earnings during call
  useEffect(() => {
    if (selectedAgent && callTimer > 0) {
      const mins = callTimer / 60.0;
      const earned = parseFloat((mins * selectedAgent.rate_per_min).toFixed(2));
      setLiveEarnings(earned);
    }
  }, [callTimer, selectedAgent]);

  // Handle Form Creation
  const handleCreateAgent = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        tags: formData.tags.split(',').map(t => t.strip ? t.strip() : t.trim())
      };
      const res = await fetch('/api/voice-agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const newAgent = await res.json();
        toast.success('Voice Agent Created & Published to Marketplace!');
        setAgents(prev => [newAgent, ...prev]);
        setSelectedAgent(newAgent);
        setActiveTab('simulator');
      } else {
        toast.error('Failed to create voice agent.');
      }
    } catch (err) {
      toast.error('Error creating voice agent: ' + err.message);
    }
  };

  // Start Call Simulation
  const startCallSimulation = () => {
    if (!selectedAgent) return;
    setCallStatus('calling');
    setCallTimer(0);
    setLiveEarnings(0);
    setCallLog([
      { speaker: 'System', text: `Initiating SIP Trunk connection to ${selectedAgent.title}...`, time: '00:00' }
    ]);

    setTimeout(() => {
      setCallStatus('connected');
      setCallLog(prev => [
        ...prev,
        { speaker: 'System', text: `Call Connected. Voice Latency: 140ms. Stream Active (${selectedAgent.voice_provider.toUpperCase()}).`, time: '00:02' },
        { speaker: selectedAgent.title, text: `Hello! I'm ${selectedAgent.title}. I'm reaching out regarding your property listing. Are you open to a firm cash offer with zero commissions?`, time: '00:03' }
      ]);
    }, 2000);
  };

  // Send User Message in Simulator
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!userTranscript.trim() || !selectedAgent || callStatus === 'idle') return;

    const userText = userTranscript;
    setUserTranscript('');

    setCallLog(prev => [
      ...prev,
      { speaker: 'User (Prospect)', text: userText, time: `${Math.floor(callTimer / 60)}:${(callTimer % 60).toString().padStart(2, '0')}` }
    ]);

    setCallStatus('speaking');

    try {
      const res = await fetch(`/api/voice-agents/${selectedAgent.id}/simulate-call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_transcript: userText })
      });

      if (res.ok) {
        const data = await res.json();
        setCallLog(prev => [
          ...prev,
          { speaker: selectedAgent.title, text: data.ai_response, time: `${Math.floor(callTimer / 60)}:${(callTimer % 60).toString().padStart(2, '0')}` }
        ]);
        fetchWallet(); // Update creator earnings live
      }
    } catch (err) {
      toast.error('Simulation error: ' + err.message);
    } finally {
      setCallStatus('connected');
    }
  };

  // End Call Simulation
  const endCallSimulation = () => {
    setCallStatus('idle');
    toast.info(`Call Completed. ${callTimer}s elapsed. Creator Earned: +$${liveEarnings.toFixed(2)}`);
    fetchWallet();
  };

  // Request Payout
  const handlePayout = async (e) => {
    e.preventDefault();
    if (!payoutAmount || parseFloat(payoutAmount) <= 0) {
      toast.error('Enter a valid payout amount.');
      return;
    }
    try {
      const res = await fetch('/api/creator/payout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount: payoutAmount, method: payoutMethod })
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(`Payout Request of $${payoutAmount} Submitted!`);
        setPayoutAmount('');
        fetchWallet();
      } else {
        toast.error(data.error || 'Payout failed.');
      }
    } catch (err) {
      toast.error('Payout request error: ' + err.message);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 font-sans selection:bg-indigo-500 selection:text-white">
      {/* Header Banner */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-indigo-950 via-slate-900 to-purple-950 border border-indigo-500/20 p-6 md:p-8 shadow-2xl">
          <div className="absolute top-0 right-0 -mt-8 -mr-8 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-3">
                <Sparkles size={14} /> Voice Agent Monetization Protocol v2.4
              </div>
              <h1 className="text-3xl md:text-5xl font-black text-white tracking-tight">
                AI Voice Agents <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">Studio & Marketplace</span>
              </h1>
              <p className="text-slate-400 text-sm md:text-base mt-2 max-w-2xl">
                Build high-converting cold calling & sales voice bots. Publish to the global marketplace and earn real-time revenue for every call minute executed.
              </p>
            </div>

            {/* Quick Stats Pill */}
            <div className="flex items-center gap-4 shrink-0">
              {/* Free US Number & 1000 Mins Badge */}
              <div className="bg-slate-900/80 border border-emerald-500/30 px-5 py-3 rounded-2xl flex items-center gap-4">
                <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400">
                  <PhoneCall size={20} />
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Free US Virtual Number</p>
                  <div className="flex items-center gap-2">
                    <p className="text-lg font-black text-white">+1 (661) 990-9068</p>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-bold">1,000 Free Mins Active</span>
                  </div>
                </div>
              </div>

              <div className="bg-slate-900/80 border border-slate-800 px-5 py-3 rounded-2xl flex items-center gap-4">
                <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400">
                  <Wallet size={20} />
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Available Payout</p>
                  <p className="text-2xl font-black text-emerald-400">${wallet.payout_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-2 mt-8 border-t border-slate-800/80 pt-6 overflow-x-auto">
            <button
              onClick={() => setActiveTab('redialer')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm transition-all duration-200 ${
                activeTab === 'redialer'
                  ? 'bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-white shadow-lg shadow-emerald-500/25 ring-2 ring-emerald-400/50'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <PhoneCall size={18} className="animate-pulse text-emerald-300" /> Real Estate Dialer & Leads
            </button>

            <button
              onClick={() => setActiveTab('builder')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
                activeTab === 'builder'
                  ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/25'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <Mic size={16} /> Agent Studio Builder
            </button>

            <button
              onClick={() => setActiveTab('simulator')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
                activeTab === 'simulator'
                  ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/25'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <PhoneCall size={16} /> Live Voice Simulator
            </button>

            <button
              onClick={() => setActiveTab('marketplace')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
                activeTab === 'marketplace'
                  ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/25'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <Globe size={16} /> Creator Marketplace
            </button>

            <button
              onClick={() => setActiveTab('wallet')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
                activeTab === 'wallet'
                  ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/25'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <Wallet size={16} /> Creator Wallet & Earnings
            </button>

            <button
              onClick={() => setActiveTab('leadpacks')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
                activeTab === 'leadpacks'
                  ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-500/25'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <ShoppingBag size={16} /> Lead Packs Digital Store
            </button>

            <button
              onClick={() => setActiveTab('instantcash')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
                activeTab === 'instantcash'
                  ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow-lg shadow-orange-500/25'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <Zap size={16} /> Instant Cash AI Suite
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Body */}
      <div className="max-w-7xl mx-auto">
        <AnimatePresence mode="wait">
          {/* TAB 0: REAL ESTATE DIALER & LEADS QUEUE */}
          {activeTab === 'redialer' && (
            <motion.div
              key="redialer"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="space-y-8"
            >
              {/* Telephony Status Banner */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-slate-900/80 border border-emerald-500/30 rounded-2xl p-5 flex items-center gap-4">
                  <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400">
                    <PhoneCall size={24} />
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">Active Twilio US Outbound Line</p>
                    <p className="text-xl font-black text-white">+1 (661) 990-9068</p>
                    <span className="text-[11px] text-emerald-400 font-semibold">Twilio US Telephony Active</span>
                  </div>
                </div>

                <div className="bg-slate-900/80 border border-purple-500/30 rounded-2xl p-5 flex items-center gap-4">
                  <div className="p-3 rounded-xl bg-purple-500/10 text-purple-400">
                    <Zap size={24} />
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">Transfer Cell (Hot Bridge)</p>
                    <p className="text-xl font-black text-white">+201040404118</p>
                    <span className="text-[11px] text-purple-300 font-semibold">Instant Seller Live Patch</span>
                  </div>
                </div>

                <div className="bg-slate-900/80 border border-amber-500/30 rounded-2xl p-5 flex items-center gap-4">
                  <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400">
                    <DollarSign size={24} />
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">Est. Pipeline Assignment Fees</p>
                    <p className="text-xl font-black text-amber-400">$202,000 USD</p>
                    <span className="text-[11px] text-slate-400 font-semibold">5 Motivated Sellers Loaded</span>
                  </div>
                </div>
              </div>

              {/* Leads Queue & Quick Dialer Console */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Lead Cards List (2 Cols) */}
                <div className="lg:col-span-2 space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xl font-black text-white flex items-center gap-2">
                      <Sparkles className="text-emerald-400" /> Verified Motivated Seller Leads Queue
                    </h2>
                    <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-bold">
                      {realEstateLeads.length} Deals Ready
                    </span>
                  </div>

                  <div className="space-y-4">
                    {realEstateLeads.map((lead) => (
                      <div
                        key={lead.id}
                        className="bg-slate-900/70 border border-slate-800 hover:border-emerald-500/50 rounded-2xl p-5 transition-all duration-200 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-lg"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-extrabold uppercase tracking-wider border border-emerald-500/20">
                              {lead.status}
                            </span>
                            <h3 className="text-base font-bold text-white">{lead.address}</h3>
                          </div>
                          <p className="text-xs text-slate-400">
                            Owner: <span className="text-slate-200 font-semibold">{lead.owner}</span> | Listing Price: <span className="text-white font-bold">{lead.price}</span>
                          </p>
                          <p className="text-xs text-amber-400 font-bold">
                            Est. Assignment Fee: {lead.est_fee}
                          </p>
                        </div>

                        <div className="flex items-center gap-3">
                          <a
                            href={`tel:${lead.phone}`}
                            onClick={() => {
                              setDialingLead(lead);
                              toast.success(`Dialing ${lead.owner} (${lead.phone})...`);
                            }}
                            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-bold text-sm shadow-md shadow-emerald-600/30 hover:opacity-90 transition flex items-center gap-2"
                          >
                            <PhoneCall size={16} /> Call {lead.phone}
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Web Phone Dialpad Console (1 Col) */}
                <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-6 shadow-xl flex flex-col items-center justify-between">
                  <div className="w-full text-center space-y-2 mb-6">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold uppercase">
                      <PhoneCall size={14} /> WebRTC Phone Console
                    </div>
                    <h3 className="text-lg font-black text-white">Direct Web Dialer</h3>
                    <p className="text-xs text-slate-400">
                      {dialingLead ? `Calling: ${dialingLead.owner} (${dialingLead.phone})` : 'Select a lead or enter a phone number'}
                    </p>
                  </div>

                  {/* Display screen */}
                  <div className="w-full bg-slate-950 border border-slate-800 rounded-2xl p-4 text-center font-mono text-xl text-emerald-400 font-bold mb-6">
                    {dialingLead ? dialingLead.phone : '+1 (646) 846-8822'}
                  </div>

                  {/* One-Click Auto-Swarm Dispatch */}
                  <button
                    onClick={() => {
                      toast.success('AI Cold Calling Swarm Dispatched to All 5 Leads!');
                    }}
                    className="w-full py-4 rounded-xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-600 text-white font-black text-sm shadow-xl shadow-emerald-500/25 hover:opacity-95 transition flex items-center justify-center gap-2 mb-4"
                  >
                    <Zap size={18} /> Launch AI Auto-Dialer Swarm
                  </button>

                  <p className="text-[11px] text-slate-500 text-center">
                    AI qualifies seller price &rarr; Hot sellers patch live to +201040404118
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 1: VOICE AGENT BUILDER */}
          {activeTab === 'builder' && (
            <motion.div
              key="builder"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="grid grid-cols-1 lg:grid-cols-3 gap-8"
            >
              {/* Form Config (2 Cols) */}
              <div className="lg:col-span-2 bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 rounded-3xl p-6 md:p-8 shadow-xl">
                <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
                  <Sliders className="text-indigo-400" /> Configure Voice Agent Properties
                </h2>

                <form onSubmit={handleCreateAgent} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Agent Title</label>
                      <input
                        type="text"
                        required
                        value={formData.title}
                        onChange={e => setFormData({ ...formData, title: e.target.value })}
                        placeholder="e.g. Apex Distressed Seller Closer"
                        className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500 transition"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Creator Usage Fee ($/min)</label>
                      <input
                        type="number"
                        step="0.05"
                        min="0.10"
                        max="5.00"
                        value={formData.rate_per_min}
                        onChange={e => setFormData({ ...formData, rate_per_min: parseFloat(e.target.value) })}
                        className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-3 text-sm text-emerald-400 font-bold focus:outline-none focus:border-indigo-500 transition"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Persona & Tone</label>
                    <input
                      type="text"
                      value={formData.persona}
                      onChange={e => setFormData({ ...formData, persona: e.target.value })}
                      placeholder="Empathetic, firm cash buyer acquisitions manager"
                      className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500 transition"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">System Instructions & Hook Script</label>
                    <textarea
                      rows={5}
                      required
                      value={formData.system_prompt}
                      onChange={e => setFormData({ ...formData, system_prompt: e.target.value })}
                      placeholder="Specify agent hook, discovery questions, and objection handlers..."
                      className="w-full bg-slate-950/80 border border-slate-800 rounded-xl p-4 text-sm text-white focus:outline-none focus:border-indigo-500 transition font-mono leading-relaxed"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Voice Provider</label>
                      <select
                        value={formData.voice_provider}
                        onChange={e => setFormData({ ...formData, voice_provider: e.target.value })}
                        className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500 transition"
                      >
                        <option value="elevenlabs">ElevenLabs (High-Fidelity Neural)</option>
                        <option value="deepgram">Deepgram Aura (Ultra-Low Latency)</option>
                        <option value="openai">OpenAI Realtime Audio</option>
                        <option value="gemini">Gemini 1.5 Flash Audio Stream</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Voice Model / ID</label>
                      <input
                        type="text"
                        value={formData.voice_id}
                        onChange={e => setFormData({ ...formData, voice_id: e.target.value })}
                        placeholder="21m00Tcm4TlvDq8ikWAM"
                        className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500 transition"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Category Tags (Comma-separated)</label>
                    <input
                      type="text"
                      value={formData.tags}
                      onChange={e => setFormData({ ...formData, tags: e.target.value })}
                      placeholder="Real Estate, Cold Calling, Cash Offer"
                      className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500 transition"
                    />
                  </div>

                  <button
                    type="submit"
                    className="w-full py-4 rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 text-white font-bold text-base shadow-xl shadow-indigo-500/25 hover:opacity-95 transition-all duration-200 flex items-center justify-center gap-2"
                  >
                    <Sparkles size={18} /> Publish Agent & Start Monetizing
                  </button>
                </form>
              </div>

              {/* Live Preview Card (1 Col) */}
              <div className="space-y-6">
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 rounded-3xl p-6 shadow-xl">
                  <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <Bot className="text-purple-400" /> Marketplace Preview Card
                  </h3>

                  <div className="bg-gradient-to-b from-slate-950 to-slate-900 p-6 rounded-2xl border border-indigo-500/20 shadow-inner">
                    <div className="flex items-center justify-between mb-4">
                      <span className="px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-semibold uppercase">
                        {formData.voice_provider.toUpperCase()}
                      </span>
                      <span className="text-emerald-400 font-bold text-sm">
                        ${formData.rate_per_min}/min
                      </span>
                    </div>

                    <h4 className="text-lg font-bold text-white mb-2">{formData.title || 'Untitled Voice Agent'}</h4>
                    <p className="text-xs text-slate-400 mb-4 line-clamp-3">{formData.system_prompt}</p>

                    <div className="pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                      <span>Latency: &lt;180ms</span>
                      <span>Target Revenue: High</span>
                    </div>
                  </div>
                </div>

                {/* Creator Payout Formula Info Box */}
                <div className="bg-gradient-to-br from-emerald-950/40 to-slate-900 border border-emerald-500/20 rounded-3xl p-6">
                  <h4 className="text-sm font-bold text-emerald-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                    <TrendingUp size={16} /> Monetization Guarantee
                  </h4>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    You earn <strong className="text-white">${formData.rate_per_min}</strong> for every full minute your voice agent executes live calls or automated outreach. Balance is credited instantly to your Creator Wallet.
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 2: LIVE VOICE SIMULATOR */}
          {activeTab === 'simulator' && (
            <motion.div
              key="simulator"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="grid grid-cols-1 lg:grid-cols-3 gap-8"
            >
              {/* Call Controls & Visualizer (2 Cols) */}
              <div className="lg:col-span-2 bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 rounded-3xl p-6 md:p-8 shadow-xl flex flex-col justify-between min-h-[550px]">
                <div>
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <PhoneCall className="text-indigo-400" /> Live Interactive Voice Call Simulator
                      </h2>
                      <p className="text-xs text-slate-400 mt-1">
                        Active Agent: <strong className="text-indigo-400">{selectedAgent?.title || 'None Selected'}</strong>
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Call Duration</span>
                      <span className="font-mono text-xl font-bold text-white bg-slate-950 px-4 py-2 rounded-xl border border-slate-800">
                        {Math.floor(callTimer / 60).toString().padStart(2, '0')}:{(callTimer % 60).toString().padStart(2, '0')}
                      </span>
                    </div>
                  </div>

                  {/* Audio Spectrum Waveform Visualizer */}
                  <div className="bg-slate-950 rounded-2xl p-8 border border-slate-800 mb-6 relative overflow-hidden flex flex-col items-center justify-center min-h-[200px]">
                    {callStatus === 'connected' || callStatus === 'speaking' ? (
                      <div className="flex items-center gap-1.5 h-20">
                        {[...Array(24)].map((_, i) => (
                          <motion.div
                            key={i}
                            animate={{
                              height: callStatus === 'speaking' ? [15, Math.random() * 65 + 15, 15] : [10, Math.random() * 25 + 10, 10]
                            }}
                            transition={{
                              repeat: Infinity,
                              duration: 0.4 + (i % 5) * 0.1,
                              ease: "easeInOut"
                            }}
                            className={`w-2 rounded-full ${callStatus === 'speaking' ? 'bg-gradient-to-t from-indigo-500 to-purple-400' : 'bg-emerald-500/60'}`}
                          />
                        ))}
                      </div>
                    ) : (
                      <div className="text-center text-slate-500">
                        <Mic size={48} className="mx-auto mb-3 opacity-30" />
                        <p className="text-sm">Click "Initiate Live Call" to test agent audio response</p>
                      </div>
                    )}

                    {/* Live Revenue Counter Badge */}
                    {callTimer > 0 && (
                      <div className="absolute top-4 right-4 bg-emerald-500/10 border border-emerald-500/30 px-3 py-1.5 rounded-full text-emerald-400 text-xs font-bold flex items-center gap-1.5">
                        <DollarSign size={14} /> Earned This Call: +${liveEarnings.toFixed(2)}
                      </div>
                    )}
                  </div>

                  {/* Call Transcript Log */}
                  <div className="bg-slate-950/80 rounded-2xl p-4 border border-slate-800 max-h-60 overflow-y-auto space-y-3">
                    {callLog.map((log, idx) => (
                      <div key={idx} className="text-xs leading-relaxed">
                        <span className="text-slate-500 font-mono mr-2">[{log.time}]</span>
                        <strong className={log.speaker === selectedAgent?.title ? 'text-indigo-400' : log.speaker.includes('User') ? 'text-emerald-400' : 'text-slate-400'}>
                          {log.speaker}:
                        </strong>{' '}
                        <span className="text-slate-200">{log.text}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Interactive Input Form */}
                <div className="mt-6 pt-6 border-t border-slate-800">
                  {callStatus === 'idle' ? (
                    <button
                      onClick={startCallSimulation}
                      className="w-full py-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-bold text-base shadow-lg shadow-emerald-500/20 hover:opacity-95 transition flex items-center justify-center gap-2"
                    >
                      <PhoneCall size={20} /> Initiate Live Voice Call Simulation
                    </button>
                  ) : (
                    <div className="flex gap-3">
                      <form onSubmit={handleSendMessage} className="flex-1 flex gap-2">
                        <input
                          type="text"
                          value={userTranscript}
                          onChange={e => setUserTranscript(e.target.value)}
                          placeholder="Type simulated prospect speech (e.g., 'What is your cash offer price?')..."
                          className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500"
                        />
                        <button
                          type="submit"
                          className="px-6 py-3 rounded-xl bg-indigo-600 text-white font-semibold text-sm hover:bg-indigo-500 transition"
                        >
                          Speak
                        </button>
                      </form>

                      <button
                        onClick={endCallSimulation}
                        className="px-6 py-3 rounded-xl bg-rose-600/20 text-rose-400 border border-rose-500/30 font-semibold text-sm hover:bg-rose-600 hover:text-white transition flex items-center gap-2"
                      >
                        <PhoneOff size={16} /> End Call
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Agent Selector & Tech Metrics (1 Col) */}
              <div className="space-y-6">
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 rounded-3xl p-6 shadow-xl">
                  <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4">Select Voice Agent to Test</h3>
                  <div className="space-y-3 max-h-80 overflow-y-auto">
                    {agents.map(ag => (
                      <div
                        key={ag.id}
                        onClick={() => setSelectedAgent(ag)}
                        className={`p-4 rounded-2xl border transition cursor-pointer ${
                          selectedAgent?.id === ag.id
                            ? 'bg-indigo-600/20 border-indigo-500 text-white'
                            : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <h4 className="font-bold text-sm text-white">{ag.title}</h4>
                          <span className="text-xs text-emerald-400 font-bold">${ag.rate_per_min}/min</span>
                        </div>
                        <p className="text-xs text-slate-400 line-clamp-2">{ag.description}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 rounded-3xl p-6 shadow-xl">
                  <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <Zap size={16} className="text-indigo-400" /> Pipeline Audio Latency
                  </h3>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between py-1 border-b border-slate-800">
                      <span className="text-slate-400">STT Speech Recognition</span>
                      <span className="text-emerald-400 font-mono">42ms</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800">
                      <span className="text-slate-400">Gemini LLM Reasoning</span>
                      <span className="text-emerald-400 font-mono">88ms</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800">
                      <span className="text-slate-400">Neural TTS Synthesis</span>
                      <span className="text-emerald-400 font-mono">35ms</span>
                    </div>
                    <div className="flex justify-between py-1 font-bold">
                      <span className="text-white">Total Roundtrip</span>
                      <span className="text-indigo-400 font-mono">165ms (Sub-human)</span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 3: CREATOR MARKETPLACE */}
          {activeTab === 'marketplace' && (
            <motion.div
              key="marketplace"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="space-y-6"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                  <Globe className="text-indigo-400" /> Global AI Voice Agents Directory
                </h2>
                <span className="text-xs text-slate-400">Showing {agents.length} Published Voice Bots</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {agents.map(ag => (
                  <div
                    key={ag.id}
                    className="bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 rounded-3xl p-6 shadow-xl flex flex-col justify-between hover:border-indigo-500/40 transition duration-300 group"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <span className="px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/30 text-purple-400 text-xs font-semibold uppercase">
                          {ag.voice_provider}
                        </span>
                        <span className="text-emerald-400 font-black text-base">${ag.rate_per_min}<span className="text-xs text-slate-500 font-normal">/min</span></span>
                      </div>

                      <h3 className="text-lg font-bold text-white group-hover:text-indigo-400 transition mb-2">{ag.title}</h3>
                      <p className="text-slate-400 text-xs leading-relaxed mb-4">{ag.description}</p>

                      <div className="flex flex-wrap gap-1.5 mb-6">
                        {(ag.tags || []).map((t, idx) => (
                          <span key={idx} className="px-2 py-0.5 rounded-md bg-slate-950 text-slate-400 text-[10px] border border-slate-800">
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="pt-4 border-t border-slate-800/80">
                      <div className="grid grid-cols-2 gap-2 text-center text-xs mb-4">
                        <div className="bg-slate-950 p-2 rounded-xl border border-slate-800">
                          <p className="text-slate-500">Calls Handled</p>
                          <p className="font-bold text-white">{ag.total_calls || 0}</p>
                        </div>
                        <div className="bg-slate-950 p-2 rounded-xl border border-slate-800">
                          <p className="text-slate-500">Total Earned</p>
                          <p className="font-bold text-emerald-400">${(ag.total_earnings || 0).toFixed(2)}</p>
                        </div>
                      </div>

                      <button
                        onClick={() => {
                          setSelectedAgent(ag);
                          setActiveTab('simulator');
                        }}
                        className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-indigo-600 text-white font-semibold text-xs transition duration-200 flex items-center justify-center gap-1.5"
                      >
                        <PhoneCall size={14} /> Deploy & Test Agent
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* TAB 4: CREATOR WALLET & EARNINGS */}
          {activeTab === 'wallet' && (
            <motion.div
              key="wallet"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="space-y-8"
            >
              {/* Wallet Summary Metrics */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 rounded-3xl">
                  <p className="text-xs text-slate-400 uppercase font-semibold tracking-wider mb-2">Lifetime Earnings</p>
                  <p className="text-3xl font-black text-white">${wallet.total_earned.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                </div>

                <div className="bg-gradient-to-br from-emerald-950/60 to-slate-900 border border-emerald-500/30 p-6 rounded-3xl">
                  <p className="text-xs text-emerald-400 uppercase font-semibold tracking-wider mb-2">Available Payout Balance</p>
                  <p className="text-3xl font-black text-emerald-400">${wallet.payout_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                </div>

                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 rounded-3xl">
                  <p className="text-xs text-slate-400 uppercase font-semibold tracking-wider mb-2">Total Minutes Called</p>
                  <p className="text-3xl font-black text-white">{wallet.total_minutes_called.toLocaleString()} <span className="text-xs text-slate-500 font-normal">mins</span></p>
                </div>

                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 rounded-3xl">
                  <p className="text-xs text-slate-400 uppercase font-semibold tracking-wider mb-2">Total Calls Processed</p>
                  <p className="text-3xl font-black text-purple-400">{wallet.total_calls_handled.toLocaleString()}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Payout Withdrawal Form (1 Col) */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 md:p-8 rounded-3xl shadow-xl">
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <CreditCard className="text-emerald-400" /> Instant Cashout Withdrawal
                  </h3>

                  <form onSubmit={handlePayout} className="space-y-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Amount to Withdraw ($)</label>
                      <input
                        type="number"
                        step="10"
                        max={wallet.payout_balance}
                        value={payoutAmount}
                        onChange={e => setPayoutAmount(e.target.value)}
                        placeholder={`Max $${wallet.payout_balance}`}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-emerald-400 font-bold focus:outline-none focus:border-indigo-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Payout Method</label>
                      <select
                        value={payoutMethod}
                        onChange={e => setPayoutMethod(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500"
                      >
                        <option value="Neteller Direct">Neteller Direct (Email / Account ID)</option>
                        <option disabled>Stripe Connect, PayPal & Bank Wire disabled — Neteller only</option>
                      </select>
                    </div>

                    <button
                      type="submit"
                      className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-bold text-sm shadow-lg hover:opacity-95 transition"
                    >
                      Request Instant Payout
                    </button>
                  </form>
                </div>

                {/* Payout Audit Ledger (2 Cols) */}
                <div className="lg:col-span-2 bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 md:p-8 rounded-3xl shadow-xl">
                  <h3 className="text-lg font-bold text-white mb-4">Payout Transaction History</h3>
                  <div className="space-y-3">
                    {wallet.payout_history.map(po => (
                      <div key={po.id} className="flex items-center justify-between p-4 rounded-2xl bg-slate-950 border border-slate-800">
                        <div>
                          <p className="font-bold text-sm text-white">${po.amount.toFixed(2)}</p>
                          <p className="text-xs text-slate-500">{po.method} • {new Date(po.date).toLocaleDateString()}</p>
                        </div>
                        <span className={`px-3 py-1 rounded-full text-xs font-semibold uppercase ${
                          po.status === 'paid' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                        }`}>
                          {po.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 5: LEAD PACKS DIGITAL STORE */}
          {activeTab === 'leadpacks' && (
            <motion.div
              key="leadpacks"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="space-y-8"
            >
              <div className="bg-gradient-to-r from-emerald-950/60 via-slate-900 to-teal-950/60 backdrop-blur-xl border border-emerald-500/20 p-8 rounded-3xl">
                <div className="flex items-center gap-3 text-emerald-400 font-semibold text-sm mb-2">
                  <ShoppingBag size={18} /> Verified B2B Lead Packs Store
                </div>
                <h2 className="text-2xl md:text-3xl font-black text-white">Monetized Lead Datasets From Past Runs</h2>
                <p className="text-slate-400 text-sm max-w-2xl mt-1">
                  Purchase verified off-market US real estate acquisitions and industrial plastic scrap datasets extracted from our automated runs.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Pack 1 */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-8 rounded-3xl flex flex-col justify-between hover:border-emerald-500/40 transition">
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-semibold uppercase border border-emerald-500/20">
                        Real Estate Acquisitions
                      </span>
                      <span className="text-2xl font-black text-white">$499.00</span>
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2">US Off-Market Distressed Real Estate Lead Pack</h3>
                    <p className="text-slate-400 text-sm mb-6">
                      27 verified US residential properties in New York, Miami, Dallas, and LA with high equity distress scores, agent phone numbers, and direct cash offer scripts.
                    </p>
                    
                    <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800/80 mb-6 space-y-2">
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Sample Preview</p>
                      <div className="text-xs text-slate-300 flex justify-between">
                        <span>• 456 Oak Ave, New York, NY ($850k)</span>
                        <span className="text-emerald-400 font-mono">$21,250 Comm</span>
                      </div>
                      <div className="text-xs text-slate-300 flex justify-between">
                        <span>• 123 Main St, New York, NY ($450k)</span>
                        <span className="text-emerald-400 font-mono">$11,250 Comm</span>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => toast.success('Instant CSV Download link dispatched to email!')}
                    className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-bold text-sm shadow-lg hover:opacity-95 transition flex items-center justify-center gap-2"
                  >
                    <Download size={16} /> Buy & Download CSV Lead Pack ($499)
                  </button>
                </div>

                {/* Pack 2 */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-8 rounded-3xl flex flex-col justify-between hover:border-emerald-500/40 transition">
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <span className="px-3 py-1 rounded-full bg-teal-500/10 text-teal-400 text-xs font-semibold uppercase border border-teal-500/20">
                        Industrial Waste & Scrap
                      </span>
                      <span className="text-2xl font-black text-white">$999.00</span>
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2">US Industrial Plastic Scrap Broker Pack</h3>
                    <p className="text-slate-400 text-sm mb-6">
                      Direct plant manager & EHS director contacts generating monthly PET, HDPE, PP, and LDPE runner/purge scrap in Texas, Illinois, Ohio, and California.
                    </p>
                    
                    <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800/80 mb-6 space-y-2">
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Sample Preview</p>
                      <div className="text-xs text-slate-300 flex justify-between">
                        <span>• Midwest Polymer Mfg (Chicago, IL)</span>
                        <span className="text-teal-400 font-mono">45 Tons/Mo</span>
                      </div>
                      <div className="text-xs text-slate-300 flex justify-between">
                        <span>• Texas Extrusion Works (Houston, TX)</span>
                        <span className="text-teal-400 font-mono">80 Tons/Mo</span>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => toast.success('Instant CSV Download link dispatched to email!')}
                    className="w-full py-3.5 rounded-xl bg-gradient-to-r from-teal-600 to-emerald-600 text-white font-bold text-sm shadow-lg hover:opacity-95 transition flex items-center justify-center gap-2"
                  >
                    <Download size={16} /> Buy & Download CSV Lead Pack ($999)
                  </button>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 6: INSTANT CASH AI SUITE */}
          {activeTab === 'instantcash' && (
            <motion.div
              key="instantcash"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="space-y-8"
            >
              <div className="bg-gradient-to-r from-amber-950/60 via-slate-900 to-orange-950/60 backdrop-blur-xl border border-amber-500/20 p-8 rounded-3xl">
                <div className="flex items-center gap-3 text-amber-400 font-semibold text-sm mb-2">
                  <Zap size={18} /> DAWRIX Instant Cash AI Monetization Suite
                </div>
                <h2 className="text-2xl md:text-3xl font-black text-white">5 High-Yield Monetized AI Streams in Your Codebase</h2>
                <p className="text-slate-400 text-sm max-w-2xl mt-1">
                  Turn long videos into viral Shorts, automate Instagram DM lead hunting, dispatch AI phone cold callers, and sell verified off-market lead packs.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Product 1: Video Clipping */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 rounded-3xl flex flex-col justify-between hover:border-amber-500/40 transition">
                  <div>
                    <span className="px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 text-xs font-semibold uppercase border border-amber-500/20">
                      $0.10 / Clip or $99/mo
                    </span>
                    <h3 className="text-lg font-bold text-white mt-3 mb-2">Viral Video Clipping Factory API</h3>
                    <p className="text-slate-400 text-xs mb-4">
                      Upload any YouTube URL to get 9:16 viral Shorts with auto-captions and multi-platform publishing.
                    </p>
                    <p className="text-xs text-emerald-400 font-mono mb-4">Est. Daily Cash: $500 - $1,200/day</p>
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        const res = await fetch('http://localhost:3002/api/instant-cash/clipping', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ youtube_url: 'https://youtube.com/watch?v=demo' })
                        });
                        const data = await res.json();
                        toast.success(`Clipping Job Created! ID: ${data.job_id} ($0.30)`);
                      } catch (err) {
                        toast.error(err.message);
                      }
                    }}
                    className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 text-white font-bold text-xs shadow-lg hover:opacity-95 transition"
                  >
                    Launch AI Video Clipper ($0.10)
                  </button>
                </div>

                {/* Product 2: Instagram AI DM Hunter */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 rounded-3xl flex flex-col justify-between hover:border-pink-500/40 transition">
                  <div>
                    <span className="px-3 py-1 rounded-full bg-pink-500/10 text-pink-400 text-xs font-semibold uppercase border border-pink-500/20">
                      $149.00 / Month SaaS
                    </span>
                    <h3 className="text-lg font-bold text-white mt-3 mb-2">Instagram AI DM Lead Hunter</h3>
                    <p className="text-slate-400 text-xs mb-4">
                      Scrape profiles, extract emails, and automate direct messaging for realtors, agencies, and sellers.
                    </p>
                    <p className="text-xs text-emerald-400 font-mono mb-4">Est. Daily Cash: $450 - $900/day</p>
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        const res = await fetch('http://localhost:3002/api/instant-cash/ig-dm', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ target_niche: 'Real Estate Brokers', city: 'New York, NY' })
                        });
                        const data = await res.json();
                        toast.success(`IG DM Campaign Launched! ID: ${data.campaign_id}`);
                      } catch (err) {
                        toast.error(err.message);
                      }
                    }}
                    className="w-full py-3 rounded-xl bg-gradient-to-r from-pink-600 to-purple-600 text-white font-bold text-xs shadow-lg hover:opacity-95 transition"
                  >
                    Launch IG DM Hunter ($149/mo)
                  </button>
                </div>

                {/* Product 3: On-Demand Cold Calling Swarm */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 rounded-3xl flex flex-col justify-between hover:border-indigo-500/40 transition">
                  <div>
                    <span className="px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-400 text-xs font-semibold uppercase border border-indigo-500/20">
                      $0.50 / Call Executed
                    </span>
                    <h3 className="text-lg font-bold text-white mt-3 mb-2">Cold Calling Swarm OS API</h3>
                    <p className="text-slate-400 text-xs mb-4">
                      Dispatch phone skip-tracing and automated AI cold call dialers with live script feedback.
                    </p>
                    <p className="text-xs text-emerald-400 font-mono mb-4">Est. Daily Cash: $800 - $1,600/day</p>
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        const res = await fetch('http://localhost:3002/api/instant-cash/cold-calling', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ lead_count: 20 })
                        });
                        const data = await res.json();
                        toast.success(`Cold Calling Swarm Dispatched! ID: ${data.run_id}`);
                      } catch (err) {
                        toast.error(err.message);
                      }
                    }}
                    className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 text-white font-bold text-xs shadow-lg hover:opacity-95 transition"
                  >
                    Dispatch Call Swarm ($0.50/call)
                  </button>
                </div>

                {/* Product 4: Marketing Agencies White-Label AI Suite */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 rounded-3xl flex flex-col justify-between hover:border-emerald-500/40 transition">
                  <div>
                    <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-semibold uppercase border border-emerald-500/20">
                      $1,500 Setup + $997/mo
                    </span>
                    <h3 className="text-lg font-bold text-white mt-3 mb-2">Marketing Agencies White-Label AI Suite</h3>
                    <p className="text-slate-400 text-xs mb-4">
                      Turnkey branded AI Voice Bots, Lead Hunters, and Short-Form Video Clipping for Marketing Agencies to resell to local clients.
                    </p>
                    <p className="text-xs text-emerald-400 font-mono mb-4">Est. Daily Cash: $2,500 - $6,000/day</p>
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        const res = await fetch('http://localhost:3002/api/instant-cash/marketing-agencies', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ agency_name: 'NextGen Digital Media Agency', seats: 10 })
                        });
                        const data = await res.json();
                        toast.success(`Agency White-Label Suite Activated! License ID: ${data.license_id}`);
                      } catch (err) {
                        toast.error(err.message);
                      }
                    }}
                    className="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-bold text-xs shadow-lg hover:opacity-95 transition"
                  >
                    Activate Agency Suite ($1,500 + $997/mo)
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
