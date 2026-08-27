import React, { useEffect, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  PhoneOff, PhoneCall, Voicemail, UserX,
  CalendarClock, Ban, CheckCircle, XCircle, Clock,
  AlertTriangle
} from 'lucide-react';
import { toast } from 'sonner';

const API = '/api';

const DISPOSITION_OUTCOMES = [
  { value: 'CONNECTED', label: 'Connected', icon: PhoneCall, color: 'emerald', description: 'Spoke with decision-maker' },
  { value: 'NO_ANSWER', label: 'No Answer', icon: PhoneOff, color: 'slate', description: 'Nobody picked up' },
  { value: 'VOICEMAIL', label: 'Voicemail', icon: Voicemail, color: 'sky', description: 'Left a voicemail' },
  { value: 'WRONG_NUMBER', label: 'Wrong Number', icon: UserX, color: 'amber', description: 'Number belongs to someone else' },
  { value: 'WRONG_PARTY', label: 'Wrong Party', icon: UserX, color: 'amber', description: 'Person is not the owner/contact' },
  { value: 'INTERESTED', label: 'Interested', icon: CheckCircle, color: 'emerald', description: 'Wants to discuss further' },
  { value: 'NOT_INTERESTED', label: 'Not Interested', icon: XCircle, color: 'red', description: 'Declined to proceed' },
  { value: 'CALLBACK', label: 'Callback', icon: Clock, color: 'violet', description: 'Requested callback at specific time' },
  { value: 'APPOINTMENT', label: 'Appointment', icon: CalendarClock, color: 'emerald', description: 'Meeting scheduled' },
  { value: 'DNC', label: 'Do Not Call', icon: Ban, color: 'red', description: 'Permanently suppressed — terminal state' },
];

const COLOR_MAP = {
  emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', dot: 'bg-emerald-500', active: 'bg-emerald-500/20 border-emerald-400' },
  sky: { bg: 'bg-sky-500/10', border: 'border-sky-500/30', text: 'text-sky-400', dot: 'bg-sky-500', active: 'bg-sky-500/20 border-sky-400' },
  violet: { bg: 'bg-violet-500/10', border: 'border-violet-500/30', text: 'text-violet-400', dot: 'bg-violet-500', active: 'bg-violet-500/20 border-violet-400' },
  amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', dot: 'bg-amber-500', active: 'bg-amber-500/20 border-amber-400' },
  red: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', dot: 'bg-red-500', active: 'bg-red-500/20 border-red-400' },
  slate: { bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', dot: 'bg-slate-500', active: 'bg-slate-500/20 border-slate-400' },
};

function DispositionButton({ outcome, selected, onSelect }) {
  const Icon = outcome.icon;
  const colors = COLOR_MAP[outcome.color] || COLOR_MAP.slate;
  const isSelected = selected === outcome.value;

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={() => onSelect(outcome.value)}
      className={`
        relative flex items-center gap-3 p-4 rounded-xl border transition-all cursor-pointer
        ${isSelected
          ? `${colors.active} shadow-lg shadow-${outcome.color}-500/10`
          : `border-white/5 bg-white/[0.02] hover:border-white/10 hover:bg-white/[0.04]`
        }
      `}
    >
      <div className={`p-2 rounded-lg ${colors.bg}`}>
        <Icon className={`w-5 h-5 ${colors.text}`} />
      </div>
      <div className="flex-1 text-left">
        <div className={`text-sm font-medium ${isSelected ? colors.text : 'text-white/90'}`}>
          {outcome.label}
        </div>
        <div className="text-xs text-white/40 mt-0.5">{outcome.description}</div>
      </div>
      {outcome.value === 'DNC' && (
        <AlertTriangle className="w-4 h-4 text-red-400 opacity-60" />
      )}
      {isSelected && (
        <motion.div
          layoutId="disposition-indicator"
          className={`absolute right-3 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full ${colors.dot}`}
        />
      )}
    </motion.button>
  );
}

function DispositionForm({ leadId, onSubmit, onCancel }) {
  const [outcome, setOutcome] = useState('');
  const [notes, setNotes] = useState('');
  const [followUpChannel, setFollowUpChannel] = useState('CALL');
  const [dncReason, setDncReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const requiresFollowUp = ['CONNECTED', 'INTERESTED', 'CALLBACK', 'APPOINTMENT'].includes(outcome);
  const isDNC = outcome === 'DNC';

  const handleSubmit = async () => {
    if (!outcome) {
      toast.error('Select a disposition outcome');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/ad/disposition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead_id: leadId,
          outcome,
          notes,
          follow_up_channel: requiresFollowUp ? followUpChannel : undefined,
          dnc_reason: isDNC ? dnc_reason : undefined,
        }),
      });
      const data = await res.json();
      if (data.ok) {
        toast.success(`Disposition recorded: ${outcome}`);
        onSubmit(data);
      } else {
        toast.error(data.errors?.join(', ') || 'Failed to record disposition');
      }
    } catch (err) {
      toast.error('Network error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="bg-[#0a0e1a] border border-white/10 rounded-2xl p-6 space-y-6"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Record Disposition</h3>
        <button onClick={onCancel} className="text-white/40 hover:text-white/70 text-sm">Cancel</button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {DISPOSITION_OUTCOMES.map(o => (
          <DispositionButton key={o.value} outcome={o} selected={outcome} onSelect={setOutcome} />
        ))}
      </div>

      <div className="space-y-4">
        <div>
          <label className="text-sm text-white/50 mb-1 block">Notes</label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="What happened on this call..."
            className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white placeholder-white/30 focus:outline-none focus:border-emerald-500/50 resize-none"
            rows={3}
          />
        </div>

        {requiresFollowUp && (
          <div>
            <label className="text-sm text-white/50 mb-1 block">Follow-Up Channel</label>
            <select
              value={followUpChannel}
              onChange={e => setFollowUpChannel(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white focus:outline-none focus:border-emerald-500/50"
            >
              <option value="CALL">Phone Call</option>
              <option value="SMS">SMS</option>
              <option value="EMAIL">Email</option>
              <option value="WHATSAPP">WhatsApp</option>
            </select>
          </div>
        )}

        {isDNC && (
          <div>
            <label className="text-sm text-white/50 mb-1 block">DNC Reason</label>
            <input
              value={dncReason}
              onChange={e => setDncReason(e.target.value)}
              placeholder="Why is this lead being suppressed?"
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white placeholder-white/30 focus:outline-none focus:border-red-500/50"
            />
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            onClick={handleSubmit}
            disabled={!outcome || submitting}
            className="flex-1 bg-emerald-600 hover:bg-emerald-500 disabled:bg-white/10 disabled:text-white/30 text-white font-medium py-3 rounded-xl transition-colors"
          >
            {submitting ? 'Saving...' : 'Record Disposition'}
          </button>
        </div>
      </div>
    </motion.div>
  );
}

export default function DispositionCenter() {
  const [dispositions, setDispositions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedLead, setSelectedLead] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [sumRes, dispRes] = await Promise.all([
        fetch(`${API}/ad/disposition/summary`),
        fetch(`${API}/ad/disposition/recent?limit=50`),
      ]);
      const sumData = await sumRes.json();
      const dispData = await dispRes.json();
      setSummary(sumData);
      setDispositions(dispData.dispositions || []);
    } catch (err) {
      toast.error('Failed to load disposition data');
    } finally {
      setLoading(false);
    }
  };

  const filteredDispositions = useMemo(() => {
    if (filter === 'ALL') return dispositions;
    return dispositions.filter(d => d.outcome === filter);
  }, [dispositions, filter]);

  const outcomeCounts = useMemo(() => {
    const counts = {};
    dispositions.forEach(d => {
      counts[d.outcome] = (counts[d.outcome] || 0) + 1;
    });
    return counts;
  }, [dispositions]);

  return (
    <div className="min-h-screen bg-[#06080f] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Disposition Center</h1>
            <p className="text-white/40 text-sm mt-1">Record and track call outcomes</p>
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-xl font-medium transition-colors"
          >
            {showForm ? 'Close Form' : '+ Record Disposition'}
          </button>
        </div>

        {/* Summary Cards */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {DISPOSITION_OUTCOMES.slice(0, 5).map(o => {
              const Icon = o.icon;
              const colors = COLOR_MAP[o.color];
              return (
                <div key={o.value} className={`p-4 rounded-xl border ${colors.border} ${colors.bg}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className={`w-4 h-4 ${colors.text}`} />
                    <span className="text-xs text-white/50">{o.label}</span>
                  </div>
                  <div className={`text-2xl font-bold ${colors.text}`}>
                    {outcomeCounts[o.value] || 0}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* DNC Warning */}
        {summary?.dnc_count > 0 && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3">
            <Ban className="w-5 h-5 text-red-400" />
            <span className="text-red-300 text-sm">
              {summary.dnc_count} lead(s) permanently suppressed (DNC)
            </span>
          </div>
        )}

        {/* Disposition Form */}
        <AnimatePresence>
          {showForm && (
            <DispositionForm
              leadId={selectedLead}
              onSubmit={() => { setShowForm(false); loadData(); }}
              onCancel={() => setShowForm(false)}
            />
          )}
        </AnimatePresence>

        {/* Filter Bar */}
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setFilter('ALL')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === 'ALL' ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/60'
            }`}
          >
            All ({dispositions.length})
          </button>
          {DISPOSITION_OUTCOMES.map(o => (
            <button
              key={o.value}
              onClick={() => setFilter(o.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filter === o.value ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/60'
              }`}
            >
              {o.label} ({outcomeCounts[o.value] || 0})
            </button>
          ))}
        </div>

        {/* Dispositions List */}
        <div className="space-y-2">
          {loading ? (
            <div className="text-center py-12 text-white/30">Loading...</div>
          ) : filteredDispositions.length === 0 ? (
            <div className="text-center py-12 text-white/30">No dispositions recorded yet</div>
          ) : (
            filteredDispositions.map(d => {
              const outcome = DISPOSITION_OUTCOMES.find(o => o.value === d.outcome);
              const colors = COLOR_MAP[outcome?.color || 'slate'];
              return (
                <motion.div
                  key={d.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className={`flex items-center gap-4 p-4 rounded-xl border ${colors.border} ${colors.bg}`}
                >
                  <div className={`p-2 rounded-lg ${colors.bg}`}>
                    {outcome && <outcome.icon className={`w-4 h-4 ${colors.text}`} />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium ${colors.text}`}>{d.outcome}</span>
                      <span className="text-xs text-white/30">Lead: {d.lead_id}</span>
                      {d.is_dnc && <Ban className="w-3 h-3 text-red-400" />}
                    </div>
                    {d.notes && <p className="text-xs text-white/40 mt-1">{d.notes}</p>}
                  </div>
                  <div className="text-xs text-white/30">
                    {new Date(d.created_at).toLocaleString()}
                  </div>
                </motion.div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
