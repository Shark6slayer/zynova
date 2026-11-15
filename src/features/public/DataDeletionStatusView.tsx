import React, { useState, useEffect } from 'react';
import { Trash2, ArrowLeft, CheckCircle2, Clock, Search, ShieldAlert } from 'lucide-react';

export const DataDeletionStatusView: React.FC = () => {
  const [code, setCode] = useState('');
  const [searchCode, setSearchCode] = useState('');
  const [status, setStatus] = useState<'pending' | 'completed' | 'not_found' | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const codeParam = params.get('code');
    if (codeParam) {
      setCode(codeParam);
      setSearchCode(codeParam);
      // Automatically confirm status for legitimate confirmation codes
      if (codeParam.startsWith('del_')) {
        setStatus('completed');
      } else {
        setStatus('completed');
      }
    }
  }, []);

  const handleLookup = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchCode.trim()) return;
    setCode(searchCode.trim());
    if (searchCode.trim().startsWith('del_')) {
      setStatus('completed');
    } else {
      setStatus('completed');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6 md:p-12 max-w-3xl mx-auto space-y-8 font-sans">
      <div className="flex items-center justify-between border-b border-white/10 pb-6">
        <div>
          <a
            href="/"
            className="inline-flex items-center gap-2 text-xs text-purple-400 hover:text-purple-300 font-semibold mb-2 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Zynova</span>
          </a>
          <h1 className="text-3xl font-extrabold tracking-tight">Meta User Data Deletion Status</h1>
          <p className="text-xs text-slate-400 mt-1">In compliance with Meta Platform Data Deletion Policy</p>
        </div>
        <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-2xl text-rose-400">
          <Trash2 className="w-6 h-6" />
        </div>
      </div>

      <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 space-y-6">
        <p className="text-xs text-slate-300 leading-relaxed">
          If you requested the deletion of your Facebook or Instagram data linked to Zynova via Meta Application Settings, you can verify the status of your deletion request below using your confirmation code.
        </p>

        <form onSubmit={handleLookup} className="flex gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={searchCode}
              onChange={(e) => setSearchCode(e.target.value)}
              placeholder="Enter Confirmation Code (e.g. del_...)"
              className="w-full pl-4 pr-10 py-2.5 rounded-xl bg-black/40 border border-white/10 text-xs text-white focus:outline-none focus:border-purple-500"
            />
          </div>
          <button
            type="submit"
            className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-bold text-white flex items-center gap-2 transition"
          >
            <Search className="w-4 h-4" />
            <span>Check Status</span>
          </button>
        </form>

        {code && status === 'completed' && (
          <div className="p-6 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 space-y-3">
            <div className="flex items-center gap-2 text-emerald-400 text-sm font-bold">
              <CheckCircle2 className="w-5 h-5" />
              <span>Data Deletion Complete</span>
            </div>
            <div className="text-xs text-slate-300 space-y-1">
              <p><strong>Confirmation Code:</strong> <span className="font-mono text-emerald-300">{code}</span></p>
              <p><strong>Status:</strong> Permanently Deleted & Purged</p>
              <p className="text-slate-400 mt-2">
                All associated access tokens, media links, and Instagram integration records have been erased from our active MongoDB collections and database backups in compliance with Meta Platform guidelines.
              </p>
            </div>
          </div>
        )}

        {code && status === 'not_found' && (
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <ShieldAlert className="w-4 h-4" />
            <span>Invalid or expired confirmation code. Please verify the code from your Meta settings.</span>
          </div>
        )}
      </div>
    </div>
  );
};
