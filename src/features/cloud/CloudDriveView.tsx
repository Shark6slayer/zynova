import React, { useState } from 'react';
import { 
  Cloud, FolderPlus, Upload, FileText, Image, FileSpreadsheet, 
  Trash2, Star, Download, Search, HardDrive 
} from 'lucide-react';
import type { CloudFileItem } from '../../mocks/demoData';

export const CloudDriveView: React.FC = () => {
  const [files, setFiles] = useState<CloudFileItem[]>([
    { id: 'f_1', name: 'Indic_LLM_Tamil_Tokenizer_v2.bin', type: 'code', size: '4.2 GB', updatedAt: 'Today, 09:30 AM', isFavorite: true },
    { id: 'f_2', name: 'SUPER_AI_Product_Spec_2026.pdf', type: 'pdf', size: '12.4 MB', updatedAt: 'Yesterday', isFavorite: true },
    { id: 'f_3', name: 'Bangalore_Transit_Survey_Data.xlsx', type: 'spreadsheet', size: '1.8 MB', updatedAt: '12 Oct', isFavorite: false },
    { id: 'f_4', name: 'Architecture_System_Diagram.png', type: 'image', size: '8.4 MB', updatedAt: '10 Oct', isFavorite: false },
  ]);

  const [newFileName, setNewFileName] = useState('');
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);

  const handleUploadSimulated = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFileName.trim()) return;

    const newFile: CloudFileItem = {
      id: 'f_' + Date.now(),
      name: newFileName,
      type: 'document',
      size: '2.4 MB',
      updatedAt: 'Just now',
      isFavorite: false,
    };

    setFiles([newFile, ...files]);
    setUploadNotice(`Saved "${newFileName}" to local encrypted drive`);
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
          <div className="flex items-center space-x-2 text-blue-400 text-xs font-semibold uppercase tracking-wider">
            <Cloud className="w-4 h-4" />
            <span>Sovereign Storage Architecture</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Super Cloud & Local Drive</h1>
          <p className="text-xs text-slate-400 mt-1">
            End-to-end encrypted storage running locally on client machine with decentralized backup options.
          </p>
        </div>

        {/* Upload Form */}
        <form onSubmit={handleUploadSimulated} className="flex items-center space-x-2 w-full md:w-auto">
          <input
            type="text"
            value={newFileName}
            onChange={(e) => setNewFileName(e.target.value)}
            placeholder="New file title (e.g. Notes.md)..."
            className="px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            disabled={!newFileName.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold disabled:opacity-40 transition shadow shrink-0 flex items-center gap-1.5"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Save File</span>
          </button>
        </form>
      </div>

      {uploadNotice && (
        <div className="p-3 rounded-xl bg-blue-500/20 border border-blue-500/30 text-blue-300 text-xs">
          {uploadNotice}
        </div>
      )}

      {/* Files Table */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-white/10 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white">Stored Files & Models</h3>
          <span className="text-xs text-slate-400 font-mono">18.4 GB Used / 100 GB</span>
        </div>

        <div className="divide-y divide-white/5">
          {files.map((file) => (
            <div key={file.id} className="py-3 flex items-center justify-between text-xs hover:bg-white/5 px-2 rounded-xl transition">
              <div className="flex items-center space-x-3">
                <FileText className="w-5 h-5 text-blue-400 shrink-0" />
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
      </div>
    </div>
  );
};
