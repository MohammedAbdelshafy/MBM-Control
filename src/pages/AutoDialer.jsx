import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  PhoneOff, MapPin,
  Zap,
  FileText, Activity, Terminal
} from 'lucide-react';
import { toast } from 'sonner';

const API = '';

const WHOLESALER_RESOURCES = [
  { name: 'Wholesaling Inc', url: 'https://www.wholesalinginc.com', phone: '(800) 594-4127', desc: 'Top wholesaling coaching' },
  { name: 'BiggerPockets', url: 'https://www.biggerpockets.com', phone: '(888) 446-2121', desc: '#1 RE investor community' },
  { name: 'REIPro', url: 'https://www.reipro.com', phone: '(800) 832-1120', desc: 'Wholesaling CRM & software' },
];

const CASH_BUYERS = [
  { name: 'WeBuyHouses.com', url: 'https://www.webuyhouses.com', phone: '(800) 447-8960', desc: 'National cash buyer network' },
  { name: 'HomeVestors', url: 'https://www.homevestors.com', phone: '(800) 444-1616', desc: 'We Buy Ugly Houses' },
  { name: 'Offerpad', url: 'https://www.offerpad.com', phone: '(888) 890-1618', desc: 'iBuyer — instant cash offers' },
];

export default function AutoDialer() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentLead, setCurrentLead] = useState(null);
  const [callState, setCallState] = useState('idle'); // idle | ringing | connected | ended
  const [callTimer, setCallTimer] = useState(0);
  const [callStartTime, setCallStartTime] = useState(null);
  const [myPhone, setMyPhone] = useState('');
  const [showDisposition, setShowDisposition] = useState(false);
  const [showClosedResources, setShowClosedResources] = useState(false);
  const [dispositions, setDispositions] = useState({});
  const [completedCount, setCompletedCount] = useState(0);
  const [closedCount, setClosedCount] = useState(0);
  const [callBackCount, setCallBackCount] = useState(0);
  const [deadCount, setDeadCount] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    fetchLeads();
    loadDispositions();
  }, []);

  useEffect(() => {
    if (callState === 'connected' || callState === 'ringing') {
      timerRef.current = setInterval(() => {
        setCallTimer(prev => prev + 1);
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [callState]);

  const fetchLeads = async () => {
    try {
      let res = await fetch(`${API}/api/dialer/re-queue`);
      let data = await res.json();
      if (!data.prospects || !data.prospects.length) {
        res = await fetch(`${API}/api/dialer/top50`);
        data = await res.json();
      }
      if (data.prospects) {
        setLeads(data.prospects);
      }
    } catch (err) {
      console.error('Failed to load leads:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadDispositions = async () => {
    try {
      const res = await fetch(`${API}/api/dialer/dispositions`);
      const data = await res.json();
      if (data.dispositions) {
        const map = {};
        data.dispositions.forEach(d => {
          map[d.lead_id] = d.disposition;
        });
        setDispositions(map);
      }
    } catch (err) {}
  };

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const startCall = async (lead) => {
    if (!myPhone.trim()) {
      toast.error('ENTER PHONE NUMBER IN MIDDLE PANE', { style: { background: 'black', color: '#39FF14', border: '1px solid #39FF14' }});
      return;
    }

    setCurrentLead(lead);
    setCallState('ringing');
    setCallTimer(0);
    setCallStartTime(null);

    try {
      const res = await fetch(`${API}/api/dialer/call-bridge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to_number: lead.phone_number,
          prospect_name: lead.prospect_name,
          my_phone: myPhone,
        }),
      });
      const data = await res.json();

      if (data.status === 'ringing_your_phone') {
        toast.success(`CONNECTING: ${lead.prospect_name}`, { style: { background: 'black', color: '#39FF14', border: '1px solid #39FF14' }});
        setTimeout(() => {
          setCallState('connected');
          setCallStartTime(Date.now());
        }, 5000);
      } else if (data.status === 'demo_mode') {
        toast.info('DEMO MODE: SIMULATING CONNECTION', { style: { background: 'black', color: '#39FF14', border: '1px solid #39FF14' }});
        setTimeout(() => {
          setCallState('connected');
          setCallStartTime(Date.now());
        }, 3000);
      } else {
        toast.error('FAILED TO PLACE CALL', { style: { background: 'black', color: 'red', border: '1px solid red' }});
        setCallState('idle');
      }
    } catch (err) {
      toast.error('API DISCONNECTED', { style: { background: 'black', color: 'red', border: '1px solid red' }});
      setCallState('idle');
    }
  };

  const endCall = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setCallState('ended');
    setShowDisposition(true);
  };

  const saveDisposition = async (disposition, notes = '', callbackTime = null) => {
    if (!currentLead) return;

    try {
      await fetch(`${API}/api/dialer/disposition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead_id: currentLead.id,
          prospect_name: currentLead.prospect_name,
          disposition,
          notes,
          callback_time: callbackTime,
        }),
      });
    } catch (err) {}

    setDispositions(prev => ({ ...prev, [currentLead.id]: disposition }));
    setShowDisposition(false);

    if (disposition === 'closed') {
      setClosedCount(prev => prev + 1);
      setShowClosedResources(true);
    } else if (disposition === 'callback') {
      setCallBackCount(prev => prev + 1);
    } else if (disposition === 'dead') {
      setDeadCount(prev => prev + 1);
    }

    setCompletedCount(prev => prev + 1);
    setCallState('idle');
    setCallTimer(0);
    setCurrentLead(null);
  };

  const nextLead = () => {
    setShowClosedResources(false);
    setShowDisposition(false);
    setCallState('idle');
    setCallTimer(0);
    setCurrentLead(null);
  };

  const activeLeads = leads.filter(l => !dispositions[l.id]);

  return (
    <div className="min-h-screen bg-black text-[#39FF14] font-mono flex flex-col text-sm">
      {/* Header (Bloomberg Style) */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[#39FF14]/30 bg-black/90 backdrop-blur">
        <div className="flex items-center gap-4">
          <Terminal className="w-5 h-5 text-[#39FF14]" />
          <span className="font-bold tracking-widest uppercase">MBM Dialer.SYS :: Terminal_01</span>
          <span className="bg-[#39FF14]/10 text-[#39FF14] px-2 py-0.5 rounded text-xs border border-[#39FF14]/30 animate-pulse">
            LIVE_LINK
          </span>
        </div>
        <div className="flex items-center gap-6 text-xs font-bold">
          <div className="flex items-center gap-2"><Activity className="w-4 h-4"/> LATENCY: 24ms</div>
          <div>CALLED: {completedCount}</div>
          <div className="text-emerald-300">CLOSED: {closedCount}</div>
          <div className="text-amber-400">CB: {callBackCount}</div>
          <div className="text-red-500">DEAD: {deadCount}</div>
        </div>
      </div>

      {/* Main Tri-Pane Layout */}
      <div className="flex-1 grid grid-cols-12 gap-px bg-[#39FF14]/20 p-px">
        
        {/* Left Pane: Queue */}
        <div className="col-span-3 bg-black p-4 flex flex-col overflow-hidden h-[calc(100vh-45px)]">
          <div className="uppercase font-bold border-b border-[#39FF14]/30 pb-2 mb-4 tracking-widest text-[#39FF14]/70">
            [01] Prospect_Queue ({activeLeads.length})
          </div>
          <div className="flex-1 overflow-y-auto pr-2 space-y-2">
            {loading ? (
              <div className="animate-pulse">LOADING_DATA...</div>
            ) : (
              activeLeads.map((lead, i) => (
                <div 
                  key={lead.id} 
                  className={`border border-[#39FF14]/20 p-2 text-xs cursor-pointer hover:bg-[#39FF14]/10 transition-colors ${currentLead?.id === lead.id ? 'bg-[#39FF14]/20 border-[#39FF14]' : ''}`}
                  onClick={() => callState === 'idle' && startCall(lead)}
                >
                  <div className="flex justify-between font-bold mb-1">
                    <span className="truncate">{lead.prospect_name.toUpperCase()}</span>
                    <span>{lead.formatted_phone}</span>
                  </div>
                  <div className="text-[#39FF14]/60 truncate">{lead.address.toUpperCase()}</div>
                  <div className="flex justify-between mt-2 text-[#39FF14]/50">
                    <span>ASK: {lead.asking_price}</span>
                    <span>COM: {lead.est_commission}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Center Pane: Active Call Interface */}
        <div className="col-span-6 bg-black p-6 flex flex-col h-[calc(100vh-45px)] relative">
          <div className="uppercase font-bold border-b border-[#39FF14]/30 pb-2 mb-6 tracking-widest text-[#39FF14]/70">
            [02] War_Room
          </div>

          {!currentLead ? (
            <div className="flex-1 flex flex-col items-center justify-center opacity-50">
              <Zap className="w-16 h-16 mb-4" />
              <div className="text-xl tracking-widest">SYSTEM_IDLE</div>
              <div className="mt-2 text-sm">SELECT TARGET FROM QUEUE TO INITIATE</div>
              
              <div className="mt-8 border border-[#39FF14]/30 p-4 w-full max-w-md">
                <label className="block mb-2 text-xs font-bold uppercase">Verify Agent Bridge Number:</label>
                <input
                  type="tel"
                  value={myPhone}
                  onChange={(e) => setMyPhone(e.target.value)}
                  placeholder="+1 (555) 123-4567"
                  className="w-full bg-black border border-[#39FF14]/50 p-2 text-[#39FF14] placeholder-[#39FF14]/30 focus:outline-none focus:border-[#39FF14]"
                />
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col">
              {/* Call Status Header */}
              <div className="border border-[#39FF14] p-6 relative overflow-hidden bg-black shadow-[0_0_15px_rgba(57,255,20,0.1)]">
                {callState === 'ringing' && (
                  <motion.div 
                    initial={{ opacity: 0 }} 
                    animate={{ opacity: [0, 0.5, 0] }} 
                    transition={{ repeat: Infinity, duration: 1.5 }}
                    className="absolute inset-0 bg-[#39FF14]/10" 
                  />
                )}
                <div className="flex justify-between items-center relative z-10">
                  <div>
                    <h2 className="text-3xl font-bold mb-1 tracking-wider uppercase">{currentLead.prospect_name}</h2>
                    <div className="text-[#39FF14]/70 flex items-center gap-2 group">
                      <MapPin className="w-4 h-4"/> 
                      <span>{currentLead.address.toUpperCase()}</span>
                      <button 
                        onClick={() => {
                          navigator.clipboard.writeText(currentLead.address);
                          toast.success('ADDRESS COPIED');
                        }}
                        className="ml-2 opacity-0 group-hover:opacity-100 bg-[#39FF14]/20 px-2 py-0.5 rounded text-[10px] hover:bg-[#39FF14] hover:text-black transition-all"
                      >
                        COPY
                      </button>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-5xl font-bold tracking-tighter shadow-sm">{formatTime(callTimer)}</div>
                    <div className="text-sm font-bold uppercase mt-1 animate-pulse">
                      {callState === 'ringing' ? '>>> OUTBOUND_RINGING' : callState === 'connected' ? '>>> LINK_ESTABLISHED' : '>>> TERMINATED'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Data Grid */}
              <div className="grid grid-cols-3 gap-px bg-[#39FF14]/20 p-px mt-6">
                <div className="bg-black p-3">
                  <div className="text-[#39FF14]/50 text-xs mb-1">PHONE</div>
                  <div className="font-bold">{currentLead.formatted_phone}</div>
                </div>
                <div className="bg-black p-3">
                  <div className="text-[#39FF14]/50 text-xs mb-1">DISTRESS_SCORE</div>
                  <div className="font-bold">{currentLead.distress_score}/100</div>
                </div>
                <div className="bg-black p-3">
                  <div className="text-[#39FF14]/50 text-xs mb-1">PROPERTY_TYPE</div>
                  <div className="font-bold uppercase">{currentLead.property_type}</div>
                </div>
              </div>

              {/* Script Box */}
              <div className="mt-6 flex-1 border border-[#39FF14]/30 p-4 flex flex-col">
                <div className="text-[#39FF14]/50 text-xs mb-3 flex items-center gap-2 border-b border-[#39FF14]/20 pb-2">
                  <FileText className="w-4 h-4"/> EXECUTABLE_SCRIPT
                </div>
                <div className="flex-1 overflow-y-auto text-lg leading-relaxed whitespace-pre-wrap">
                  {currentLead.cold_calling_script}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Pane: Actions & Dispositions */}
        <div className="col-span-3 bg-black p-4 flex flex-col h-[calc(100vh-45px)]">
          <div className="uppercase font-bold border-b border-[#39FF14]/30 pb-2 mb-4 tracking-widest text-[#39FF14]/70">
            [03] Action_Panel
          </div>
          
          <div className="flex-1">
            {!currentLead ? (
              <div className="text-[#39FF14]/40 text-center mt-10">AWAITING_CONNECTION...</div>
            ) : (
              <div className="space-y-4">
                {callState !== 'ended' ? (
                  <button
                    onClick={endCall}
                    className="w-full bg-red-600/20 border border-red-500 text-red-500 hover:bg-red-600 hover:text-black font-bold uppercase py-4 transition-colors tracking-widest flex items-center justify-center gap-2"
                  >
                    <PhoneOff className="w-5 h-5"/> TERMINATE_LINK
                  </button>
                ) : (
                  <div className="space-y-3">
                    <div className="text-xs uppercase text-[#39FF14]/50 mb-2">Awaiting Disposition:</div>
                    <button
                      onClick={() => saveDisposition('closed')}
                      className="w-full bg-[#39FF14]/10 border border-[#39FF14] hover:bg-[#39FF14] hover:text-black font-bold uppercase py-3 transition-colors tracking-widest text-left px-4"
                    >
                      [1] DEAL_SECURED
                    </button>
                    <button
                      onClick={() => saveDisposition('callback')}
                      className="w-full bg-amber-500/10 border border-amber-500 text-amber-500 hover:bg-amber-500 hover:text-black font-bold uppercase py-3 transition-colors tracking-widest text-left px-4"
                    >
                      [2] REQUIRE_CALLBACK
                    </button>
                    <button
                      onClick={() => saveDisposition('dead')}
                      className="w-full bg-red-500/10 border border-red-500 text-red-500 hover:bg-red-500 hover:text-black font-bold uppercase py-3 transition-colors tracking-widest text-left px-4"
                    >
                      [3] DEAD_LEAD
                    </button>
                  </div>
                )}

                <div className="mt-8 border-t border-[#39FF14]/30 pt-4">
                  <div className="text-xs uppercase text-[#39FF14]/50 mb-2">Quick Intel:</div>
                  <div className="space-y-2 text-xs">
                    <div className="border border-[#39FF14]/20 p-2 flex justify-between">
                      <span className="text-[#39FF14]/50">Zestimate:</span> 
                      <span>{currentLead.zestimate || 'N/A'}</span>
                    </div>
                    <div className="border border-[#39FF14]/20 p-2 flex justify-between">
                      <span className="text-[#39FF14]/50">Days on Market:</span> 
                      <span>{currentLead.days_on_market || 'Off-Market'}</span>
                    </div>
                    <div className="border border-[#39FF14]/20 p-2 flex justify-between">
                      <span className="text-[#39FF14]/50">Year Built:</span> 
                      <span>{currentLead.year_built || 'Unknown'}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Closed Modal Override */}
      <AnimatePresence>
        {showClosedResources && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4 font-mono text-[#39FF14]"
          >
            <div className="border border-[#39FF14] p-8 max-w-4xl w-full bg-black shadow-[0_0_30px_rgba(57,255,20,0.2)]">
              <div className="text-center mb-8 border-b border-[#39FF14]/30 pb-6">
                <h2 className="text-4xl font-bold tracking-widest uppercase">{">>>"} CONTRACT_SECURED</h2>
                <div className="mt-2 text-[#39FF14]/70">WHOLESALING RESOURCES UNLOCKED</div>
              </div>
              
              <div className="grid grid-cols-2 gap-8">
                <div>
                  <h3 className="text-xl font-bold border-b border-[#39FF14]/50 pb-2 mb-4 uppercase">Buyer_Network</h3>
                  <div className="space-y-3">
                    {CASH_BUYERS.map((cb, i) => (
                      <div key={i} className="border border-[#39FF14]/30 p-3 hover:bg-[#39FF14]/10">
                        <div className="font-bold">{cb.name.toUpperCase()}</div>
                        <div className="text-xs mt-1 text-[#39FF14]/70 flex justify-between">
                          <span>{cb.phone || 'NO_PHONE'}</span>
                          <a href={cb.url} target="_blank" className="underline">ACCESS_LINK</a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="text-xl font-bold border-b border-[#39FF14]/50 pb-2 mb-4 uppercase">Wholesale_Desks</h3>
                  <div className="space-y-3">
                    {WHOLESALER_RESOURCES.map((ws, i) => (
                      <div key={i} className="border border-[#39FF14]/30 p-3 hover:bg-[#39FF14]/10">
                        <div className="font-bold">{ws.name.toUpperCase()}</div>
                        <div className="text-xs mt-1 text-[#39FF14]/70 flex justify-between">
                          <span>{ws.phone}</span>
                          <a href={ws.url} target="_blank" className="underline">ACCESS_LINK</a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-8 text-center">
                <button
                  onClick={nextLead}
                  className="bg-[#39FF14] text-black hover:bg-white font-bold uppercase py-3 px-8 transition-colors tracking-widest"
                >
                  ACKNOWLEDGE_AND_CONTINUE
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
