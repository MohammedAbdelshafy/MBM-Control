import React, { useState } from 'react';
import { Play, Pause, Volume2, Mic, Sliders, Sparkles, Download, CheckCircle, Zap, DollarSign, Phone, TrendingUp, Copy, Check } from 'lucide-react';

const VOICE_TIERS = [
  {
    id: 'real_estate_wholesaling',
    name: 'Deep Male Authority',
    voiceModel: 'en-US-ChristopherNeural',
    niche: 'Wholesaling & Real Estate',
    speed: 1.08,
    pitch: '0Hz',
    ducking: '-14dB',
    rpmRange: '$18.50 – $22.00',
    estEarnings100k: '$6,750.00 USD',
    pinnedComment: "💰 Want my $10,000 Wholesaling Contract Template & Cash Buyer Script for FREE? Tap link in bio or DM 'CONTRACT'! 👇",
    captionCTA: "📲 DM 'DEAL' to get added to our VIP Off-Market Cash Buyers List!",
    color: 'from-amber-500/20 to-amber-900/40',
    borderColor: 'border-amber-500/40',
    badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    description: 'High-impact, urgent, authoritative male tone for cold calling & contract deal breakdowns.'
  },
  {
    id: 'twists_revealed',
    name: 'Dramatic Mystery Narrator',
    voiceModel: 'en-US-EricNeural',
    niche: 'Twists Revealed & Mysteries',
    speed: 1.05,
    pitch: '-2Hz',
    ducking: '-16dB',
    rpmRange: '$2.80 – $3.50',
    estEarnings100k: '$1,200.00 USD',
    pinnedComment: "🔍 Subscribe & turn on notifications so you never miss a mind-blowing reveal! What was your reaction? 👇",
    captionCTA: "👀 Share this with a friend who needs to see the ending twist!",
    color: 'from-purple-500/20 to-purple-900/40',
    borderColor: 'border-purple-500/40',
    badgeColor: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    description: 'Suspenseful, deep narrator tone designed for plot twists, dark secrets, and hidden reveals.'
  },
  {
    id: 'reverse_psychology_warning',
    name: 'Intense Warning Gate',
    voiceModel: 'en-US-RogerNeural',
    niche: 'Don\'t Watch This (Warning Hooks)',
    speed: 1.08,
    pitch: '-1Hz',
    ducking: '-15dB',
    rpmRange: '$3.00 – $4.50',
    estEarnings100k: '$1,500.00 USD',
    pinnedComment: "⚠️ Warning: Do not attempt this unless you want high conversion! Save & share! 👇",
    captionCTA: "🛑 Stop scrolling! Tag someone who shouldn't see this!",
    color: 'from-rose-500/20 to-rose-900/40',
    borderColor: 'border-rose-500/40',
    badgeColor: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    description: 'Urgent, high-tension warning voice tailored for reverse psychology curiosity traps.'
  },
  {
    id: 'cute_dosage',
    name: 'Upbeat Wholesome Warmth',
    voiceModel: 'en-US-AnaNeural',
    niche: 'Cute Dosage & Wholesome',
    speed: 1.04,
    pitch: '+2Hz',
    ducking: '-10dB',
    rpmRange: '$1.80 – $2.80',
    estEarnings100k: '$930.00 USD',
    pinnedComment: "🐾 Share this daily dose of cute to make someone's day brighter! 💖 Subscribe for daily happiness!",
    captionCTA: "🐶 Double tap if this made you smile today!",
    color: 'from-emerald-500/20 to-emerald-900/40',
    borderColor: 'border-emerald-500/40',
    badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    description: 'Warm, cheerful, heartwarming tone for cute animals and daily positive boosters.'
  },
  {
    id: 'business_finance',
    name: 'High-Trust Corporate',
    voiceModel: 'en-US-GuyNeural',
    niche: 'Business, Money & Finance',
    speed: 1.08,
    pitch: '0Hz',
    ducking: '-12dB',
    rpmRange: '$8.50 – $14.00',
    estEarnings100k: '$4,450.00 USD',
    pinnedComment: "🚀 Want to automate your business & growth? Get our top tools guide in bio link! 👇",
    captionCTA: "💡 Save this post & follow for daily business insights!",
    color: 'from-blue-500/20 to-blue-900/40',
    borderColor: 'border-blue-500/40',
    badgeColor: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    description: 'Clean, analytical, executive voice for financial insights, SaaS, and market trends.'
  },
  {
    id: 'tech_ai',
    name: 'Modern Cyber Tech',
    voiceModel: 'en-US-SteffanNeural',
    niche: 'AI, Software & Coding',
    speed: 1.08,
    pitch: '0Hz',
    ducking: '-12dB',
    rpmRange: '$10.00 – $16.00',
    estEarnings100k: '$5,200.00 USD',
    pinnedComment: "🤖 Free AI Workflow Templates & Code Snippets link in bio! 👇",
    captionCTA: "⚡ Try this AI hack today & follow for daily tech updates!",
    color: 'from-cyan-500/20 to-cyan-900/40',
    borderColor: 'border-cyan-500/40',
    badgeColor: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
    description: 'Crisp, fast-paced voice tailored for software demos, AI tool reviews, and productivity hacks.'
  }
];

export default function VoiceAgencyStudio() {
  const [selectedVoice, setSelectedVoice] = useState(VOICE_TIERS[0]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(selectedVoice.speed);
  const [ducking, setDucking] = useState(-14);
  const [scriptHook, setScriptHook] = useState('The $10,000 Wholesaling Contract Secret Nobody Mentions...');
  const [scriptBody, setScriptBody] = useState('When negotiating with a motivated seller, always include an assignment clause allowing you to transfer purchase rights directly to your cash buyer.');
  const [scriptCTA, setScriptCTA] = useState("DM 'CONTRACT' for free template!");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedAudioUrl, setGeneratedAudioUrl] = useState(null);
  const [copied, setCopied] = useState(false);
  const [dialerStatus, setDialerStatus] = useState(null);

  const fullScript = `${scriptHook} ${scriptBody} ${scriptCTA}`.trim();
  const wordCount = fullScript.split(/\s+/).filter(Boolean).length;
  const estDurationSec = ((wordCount / (170 * speed)) * 60).toFixed(1);

  const handleVoiceSelect = (voice) => {
    setSelectedVoice(voice);
    setSpeed(voice.speed);
    setDucking(parseInt(voice.ducking));
    setIsPlaying(false);
  };

  const handleGenerateVoice = () => {
    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      setGeneratedAudioUrl('simulated_voiceover.mp3');
    }, 1000);
  };

  const handleCopyPinnedComment = () => {
    navigator.clipboard.writeText(selectedVoice.pinnedComment);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleLaunchDialer = () => {
    setDialerStatus('Launching AI Dialer Session...');
    setTimeout(() => {
      setDialerStatus('AI Predictive Dialer Connected to Retell Bridge! (Caller ID +16619909068)');
    }, 1200);
  };

  return (
    <div className="w-full bg-slate-950 text-slate-100 min-h-screen p-6 md:p-8 font-sans">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/30 rounded-xl text-indigo-400">
              <Mic className="w-6 h-6" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-purple-300 to-pink-400">
              Voice Agency Studio & Monetization Engine
            </h1>
            <span className="px-3 py-1 text-xs font-semibold rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              Monetized & Live
            </span>
          </div>
          <p className="text-slate-400 text-sm">
            Niche-Optimized AI Neural Voices • 1.08x Pacing Acceleration • Dynamic Audio Ducking • Live Monetization RPM Tracker
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleLaunchDialer}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-emerald-400 border border-emerald-500/30 font-medium rounded-xl transition-all text-sm"
          >
            <Phone className="w-4 h-4" />
            Launch AI Dialer
          </button>

          <button 
            onClick={handleGenerateVoice}
            disabled={isGenerating}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-medium rounded-xl shadow-lg shadow-indigo-500/25 transition-all text-sm disabled:opacity-50"
          >
            {isGenerating ? (
              <>
                <Sparkles className="w-4 h-4 animate-spin" />
                Synthesizing...
              </>
            ) : (
              <>
                <Zap className="w-4 h-4" />
                Synthesize Voiceover
              </>
            )}
          </button>
        </div>
      </div>

      {dialerStatus && (
        <div className="max-w-7xl mx-auto mb-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-300 text-sm flex items-center justify-between">
          <span className="flex items-center gap-2 font-medium">
            <Phone className="w-4 h-4 text-emerald-400" />
            {dialerStatus}
          </span>
          <button onClick={() => setDialerStatus(null)} className="text-xs text-emerald-400/70 hover:text-emerald-300">Dismiss</button>
        </div>
      )}

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Voice Tier Selection */}
        <div className="lg:col-span-5 space-y-4">
          <h2 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
            <Mic className="w-5 h-5 text-indigo-400" />
            Select Voice Agency Tier
          </h2>

          <div className="grid grid-cols-1 gap-3">
            {VOICE_TIERS.map((voice) => {
              const isSelected = selectedVoice.id === voice.id;
              return (
                <div
                  key={voice.id}
                  onClick={() => handleVoiceSelect(voice)}
                  className={`cursor-pointer p-4 rounded-2xl border transition-all relative overflow-hidden bg-gradient-to-r ${voice.color} ${
                    isSelected ? `${voice.borderColor} ring-2 ring-indigo-500/50 shadow-lg shadow-indigo-950/50` : 'border-slate-800 hover:border-slate-700 bg-slate-900/60'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-slate-100 text-base">{voice.name}</h3>
                        {isSelected && (
                          <CheckCircle className="w-4 h-4 text-indigo-400" />
                        )}
                      </div>
                      <span className={`inline-block px-2.5 py-0.5 text-xs font-medium rounded-full border mb-2 ${voice.badgeColor}`}>
                        {voice.niche}
                      </span>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        {voice.description}
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                    <span className="text-emerald-400 font-semibold flex items-center gap-1">
                      <DollarSign className="w-3.5 h-3.5" /> RPM: {voice.rpmRange}
                    </span>
                    <span className="font-medium text-indigo-300">Pacing: {voice.speed}x</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Audio Studio & Monetization Controls */}
        <div className="lg:col-span-7 space-y-6">
          {/* Active Monetization Tracker Card */}
          <div className="bg-slate-900/90 border border-emerald-500/30 rounded-2xl p-6 backdrop-blur-sm space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg">
                  <TrendingUp className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-100">Live Monetization & Revenue Projections</h3>
                  <p className="text-xs text-slate-400">Estimated earnings based on {selectedVoice.niche} niche CPM benchmarks</p>
                </div>
              </div>

              <div className="text-right">
                <span className="text-xs text-slate-400">Est. / 100k Views</span>
                <p className="text-xl font-bold text-emerald-400">{selectedVoice.estEarnings100k}</p>
              </div>
            </div>

            {/* Monetized Pinned Comment & CTA Copy */}
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">Monetized Pinned Comment & Lead Capture Link</span>
                <button
                  onClick={handleCopyPinnedComment}
                  className="flex items-center gap-1.5 px-3 py-1 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 rounded-lg text-xs transition-all"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? 'Copied!' : 'Copy Pinned Comment'}
                </button>
              </div>
              <p className="text-xs text-indigo-300/90 font-mono bg-indigo-950/40 p-2.5 rounded-lg border border-indigo-500/20">
                {selectedVoice.pinnedComment}
              </p>

              <div className="text-xs text-slate-400 pt-1 flex items-center justify-between">
                <span>Caption CTA: <strong className="text-slate-200">{selectedVoice.captionCTA}</strong></span>
              </div>
            </div>
          </div>

          {/* Active Voice Controls */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                  <Sliders className="w-5 h-5 text-indigo-400" />
                  Studio Controls — {selectedVoice.name}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">Adjust pacing acceleration and audio ducking in real-time</p>
              </div>

              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 border border-indigo-500/40 rounded-xl text-sm font-medium transition-all"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-current" />}
                {isPlaying ? 'Pause Sample' : 'Audition Voice'}
              </button>
            </div>

            {/* Controls Sliders */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <div className="flex justify-between items-center text-xs font-medium text-slate-300 mb-2">
                  <span>Pacing Speed (WPM Acceleration)</span>
                  <span className="text-indigo-400 font-bold">{speed}x</span>
                </div>
                <input
                  type="range"
                  min="1.0"
                  max="1.25"
                  step="0.01"
                  value={speed}
                  onChange={(e) => setSpeed(parseFloat(e.target.value))}
                  className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                  <span>1.0x (Normal)</span>
                  <span>1.08x (Viral WPM Sweet Spot)</span>
                  <span>1.25x (Fast)</span>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center text-xs font-medium text-slate-300 mb-2">
                  <span>Background Music Ducking</span>
                  <span className="text-purple-400 font-bold">{ducking} dB</span>
                </div>
                <input
                  type="range"
                  min="-20"
                  max="-6"
                  step="1"
                  value={ducking}
                  onChange={(e) => setDucking(parseInt(e.target.value))}
                  className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                  <span>-20 dB (Quiet Music)</span>
                  <span>-14 dB (Standard)</span>
                  <span>-6 dB (Loud)</span>
                </div>
              </div>
            </div>
          </div>

          {/* Script Studio Panel */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-pink-400" />
                Script & Timing Breakdown
              </h3>
              <div className="flex items-center gap-4 text-xs">
                <span className="text-slate-400">Words: <strong className="text-slate-200">{wordCount}</strong></span>
                <span className="text-slate-400">Est. Duration: <strong className="text-indigo-400">{estDurationSec}s</strong></span>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">0-1.5s Opening Visual Hook Header</label>
                <input
                  type="text"
                  value={scriptHook}
                  onChange={(e) => setScriptHook(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Core Delivery Arc</label>
                <textarea
                  rows={3}
                  value={scriptBody}
                  onChange={(e) => setScriptBody(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Closing CTA & Infinite Loop Transition</label>
                <input
                  type="text"
                  value={scriptCTA}
                  onChange={(e) => setScriptCTA(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            {/* Generated Audio Download Bar */}
            {generatedAudioUrl && (
              <div className="mt-4 p-4 bg-indigo-500/10 border border-indigo-500/30 rounded-xl flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-indigo-500/20 text-indigo-400 rounded-lg">
                    <Volume2 className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-indigo-200">Voiceover Synthesized Successfully!</p>
                    <p className="text-xs text-indigo-400/80">Ready to export into Clipping Factory campaigns</p>
                  </div>
                </div>

                <button className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-all">
                  <Download className="w-4 h-4" />
                  Export MP3
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
