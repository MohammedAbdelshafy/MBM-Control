import React, { useState, useEffect } from 'react';
import { Terminal, Activity, Zap, Play, CheckCircle, Mail, Briefcase } from 'lucide-react';
import { toast } from 'sonner';

export default function AgencyDashboard() {
  const [painPointApps, setPainPointApps] = useState([]);
  const [clientClips, setClientClips] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock fetching data from backend for the UI demonstration
    setTimeout(() => {
      setPainPointApps([
        { id: 1, company: 'acme-corp.com', ceo: 'Alex Founder', pain_point: 'High support volume', status: 'Pitch Queued', date: '2026-08-08' },
        { id: 2, company: 'techflow.io', ceo: 'Sarah Tech', pain_point: 'Lead leakage', status: 'Sent', date: '2026-08-07' }
      ]);
      setClientClips([
        { id: 'clip_001', client: 'RealEstatePro', niche: 'Real Estate Investing', status: 'pending_client_approval', file: 'client_RealEstatePro_12345.mp3' },
        { id: 'clip_002', client: 'DentalGrowth', niche: 'Dental Marketing', status: 'approved', file: 'client_DentalGrowth_98765.mp3' }
      ]);
      setLoading(false);
    }, 1000);
  }, []);

  const approveClip = (id) => {
    toast.success(`CLIP ${id} APPROVED. QUEUED FOR PUBLISHING.`, { style: { background: 'black', color: '#39FF14', border: '1px solid #39FF14' }});
    setClientClips(prev => prev.map(c => c.id === id ? { ...c, status: 'approved' } : c));
  };

  const generateNewApp = () => {
    toast.info('INITIATING PAIN-POINT APP GENERATOR...', { style: { background: 'black', color: '#39FF14', border: '1px solid #39FF14' }});
    setTimeout(() => {
      setPainPointApps([{ id: 3, company: 'newlead.com', ceo: 'John Doe', pain_point: 'Manual data entry', status: 'Pitch Queued', date: new Date().toISOString().split('T')[0] }, ...painPointApps]);
      toast.success('APP GENERATED & PITCH QUEUED!', { style: { background: 'black', color: '#39FF14', border: '1px solid #39FF14' }});
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-black text-[#39FF14] font-mono flex flex-col text-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[#39FF14]/30 bg-black/90 backdrop-blur">
        <div className="flex items-center gap-4">
          <Terminal className="w-5 h-5 text-[#39FF14]" />
          <span className="font-bold tracking-widest uppercase">AGENCY_OS :: Terminal_02</span>
          <span className="bg-[#39FF14]/10 text-[#39FF14] px-2 py-0.5 rounded text-xs border border-[#39FF14]/30 animate-pulse">
            B2B_ACTIVE
          </span>
        </div>
        <div className="flex items-center gap-6 text-xs font-bold">
          <div className="flex items-center gap-2"><Activity className="w-4 h-4"/> LATENCY: 12ms</div>
          <div>APPS GENERATED: {painPointApps.length}</div>
          <div className="text-amber-400">PENDING APPROVAL: {clientClips.filter(c => c.status === 'pending_client_approval').length}</div>
        </div>
      </div>

      {/* Main Tri-Pane Layout */}
      <div className="flex-1 grid grid-cols-12 gap-px bg-[#39FF14]/20 p-px">
        
        {/* Left Pane: Pain-Point Apps (Lead Gen) */}
        <div className="col-span-5 bg-black p-4 flex flex-col overflow-hidden h-[calc(100vh-45px)]">
          <div className="flex justify-between items-center border-b border-[#39FF14]/30 pb-2 mb-4">
            <div className="uppercase font-bold tracking-widest text-[#39FF14]/70">
              [01] Pain-Point_Apps (Lead Gen)
            </div>
            <button onClick={generateNewApp} className="px-3 py-1 border border-[#39FF14] hover:bg-[#39FF14]/20 text-xs font-bold flex items-center gap-2">
              <Zap className="w-3 h-3" /> GENERATE NEW
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto pr-2 space-y-4">
            {loading ? (
              <div className="animate-pulse">LOADING_LEADS...</div>
            ) : (
              painPointApps.map(app => (
                <div key={app.id} className="border border-[#39FF14]/30 p-3 hover:bg-[#39FF14]/5 transition-colors">
                  <div className="flex justify-between items-center mb-2">
                    <div className="font-bold text-lg">{app.company}</div>
                    <div className={`px-2 py-1 text-xs border ${app.status === 'Sent' ? 'border-emerald-500 text-emerald-500' : 'border-amber-500 text-amber-500'}`}>
                      {app.status}
                    </div>
                  </div>
                  <div className="text-[#39FF14]/70 flex items-center gap-2 mb-1">
                    <Briefcase className="w-4 h-4" /> CEO: {app.ceo}
                  </div>
                  <div className="text-[#39FF14]/70 flex items-center gap-2">
                    <Zap className="w-4 h-4" /> Solves: {app.pain_point}
                  </div>
                  <div className="mt-3 pt-3 border-t border-[#39FF14]/20 text-xs text-[#39FF14]/50 flex justify-between">
                    <span>Generated: {app.date}</span>
                    <span className="flex items-center gap-1"><Mail className="w-3 h-3"/> Pitch Ready</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Pane: Client Clip Approval (Fulfillment) */}
        <div className="col-span-7 bg-black p-4 flex flex-col h-[calc(100vh-45px)] relative">
          <div className="uppercase font-bold border-b border-[#39FF14]/30 pb-2 mb-4 tracking-widest text-[#39FF14]/70">
            [02] Client_Approval_Queue (Faceless Agency)
          </div>

          <div className="flex-1 overflow-y-auto pr-2 space-y-4">
            {loading ? (
              <div className="animate-pulse">LOADING_CLIENT_FILES...</div>
            ) : (
              clientClips.map(clip => (
                <div key={clip.id} className="border border-[#39FF14]/30 p-4 bg-[#39FF14]/5">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <div className="font-bold text-xl mb-1">{clip.client}</div>
                      <div className="text-[#39FF14]/70 tracking-wider text-xs uppercase">Niche: {clip.niche}</div>
                    </div>
                    <div className={`px-3 py-1 text-xs font-bold border ${clip.status === 'approved' ? 'border-emerald-500 text-emerald-500' : 'border-amber-500 text-amber-500 animate-pulse'}`}>
                      {clip.status.replace('_', ' ').toUpperCase()}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-4 bg-black border border-[#39FF14]/20 p-3 mb-4">
                    <button className="p-2 border border-[#39FF14] hover:bg-[#39FF14] hover:text-black transition-colors">
                      <Play className="w-4 h-4" />
                    </button>
                    <div className="flex-1 text-xs text-[#39FF14]/60 truncate">
                      {clip.file}
                    </div>
                  </div>

                  {clip.status === 'pending_client_approval' && (
                    <div className="flex gap-4 border-t border-[#39FF14]/20 pt-4">
                      <button onClick={() => approveClip(clip.id)} className="flex-1 py-2 bg-[#39FF14]/10 border border-[#39FF14] text-[#39FF14] font-bold hover:bg-[#39FF14] hover:text-black transition-colors flex justify-center items-center gap-2">
                        <CheckCircle className="w-4 h-4" /> APPROVE & PUBLISH
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
