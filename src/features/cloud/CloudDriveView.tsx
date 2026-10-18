import React, { useState, useEffect } from 'react';
import { 
  Cloud, HardDrive, Upload, FileText,
  Trash2, ShieldCheck, CloudOff, Info
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export interface LocalFileItem {
  id: string;
  name: string;
  type: string;
  size: string;
  updatedAt: string;
}

export const CloudDriveView: React.FC = () => {
  const { user } = useAuth();
  const storageKey = user ? `super_ai_local_files_${user.id}` : 'super_ai_local_files_guest';

  const [files, setFiles] = useState<LocalFileItem[]>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [newFileName, setNewFileName] = useState('');
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      setFiles(saved ? JSON.parse(saved) : []);
    } catch {
      setFiles([]);
    }
  }, [storageKey]);

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(files));
    } catch {
      // ignore localstorage write failure
    }
  }, [files, storageKey]);

  const handleSaveLocal = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFileName.trim()) return;

    const newFile: LocalFileItem = {
      id: 'f_' + Date.now(),
      name: newFileName.trim(),
      type: 'document',
      size: '2.4 MB',
      updatedAt: 'Just now',
    };

    setFiles([newFile, ...files]);
    setUploadNotice(`Saved "${newFileName.trim()}" to local browser vault`);
    setNewFileName('');
    setTimeout(() => setUploadNotice(null), 3000);
  };

  const handleDelete = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto w-full">
      {/* Header */}
      <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-cyan-400 text-xs font-semibold uppercase tracking-wider">
            <HardDrive className="w-4 h-4" />
            <span>Local Sovereign Vault</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Client Vault & Cloud Storage</h1>
          <p className="text-xs text-slate-400 mt-1">
            Browser-isolated offline storage. Files remain in local client storage.
          </p>
        </div>

        {/* Upload Form */}
        <form onSubmit={handleSaveLocal} className="flex items-center space-x-2 w-full md:w-auto">
          <input
            type="text"
            value={newFileName}
            onChange={(e) => setNewFileName(e.target.value)}
            placeholder="New file title (e.g. Notes.md)..."
            className="px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
          <button
            type="submit"
            disabled={!newFileName.trim()}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-xs font-semibold disabled:opacity-40 transition shadow shrink-0 flex items-center gap-1.5"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Save to Vault</span>
          </button>
        </form>
      </div>

      {/* Cloud Integration Status Banner */}
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <CloudOff className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            <strong>Cloud Backup: Not Configured.</strong> Remote S3/GCS cloud backend storage is currently not attached. Stored files are kept locally in your browser session.
          </span>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono shrink-0">
          Local Mode Only
        </span>
      </div>

      {uploadNotice && (
        <div className="p-3 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-xs flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>{uploadNotice}</span>
        </div>
      )}

      {/* Files Table */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-white/10 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">Local Browser Files</h3>
            <p className="text-[11px] text-slate-400">Isolated to account: {user?.username || 'Guest'}</p>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {files.length === 0 ? '0 files' : `${files.length} ${files.length === 1 ? 'file' : 'files'} (~${(files.length * 2.4).toFixed(1)} MB)`}
          </span>
        </div>

        {files.length > 0 ? (
          <div className="divide-y divide-white/5">
            {files.map((file) => (
              <div key={file.id} className="py-3 flex items-center justify-between text-xs hover:bg-white/5 px-2 rounded-xl transition">
                <div className="flex items-center space-x-3">
                  <FileText className="w-5 h-5 text-cyan-400 shrink-0" />
                  <div>
                    <h5 className="font-semibold text-slate-200">{file.name}</h5>
                    <span className="text-[10px] text-slate-400">{file.size} • {file.updatedAt}</span>
                  </div>
                </div>

                <div className="flex items-center space-x-2 text-slate-400">
                  <button
                    onClick={() => handleDelete(file.id)}
                    className="p-1.5 hover:text-red-400 rounded transition"
                    title="Delete File"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 rounded-xl bg-black/10 dark:bg-slate-800/20 border border-dashed border-white/10 text-center space-y-2">
            <HardDrive className="w-8 h-8 mx-auto text-slate-500" />
            <h4 className="text-sm font-semibold text-slate-300">Local Vault is Empty</h4>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              Save local documents or model checkpoints in your browser's private vault using the form above.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
