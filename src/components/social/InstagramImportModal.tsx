import React, { useState, useEffect } from 'react';
import { Loader2, Check, AlertCircle, X, Download, ExternalLink, Image as ImageIcon, Video as VideoIcon } from 'lucide-react';
import { apiClient } from '../../services/apiClient';

interface InstagramMediaItem {
  id: string;
  caption?: string | null;
  media_type: string;
  media_url?: string | null;
  thumbnail_url?: string | null;
  permalink?: string | null;
  timestamp?: string | null;
  already_imported: boolean;
}

interface InstagramImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: () => void;
}

export const InstagramImportModal: React.FC<InstagramImportModalProps> = ({
  isOpen,
  onClose,
  onImportComplete,
}) => {
  const [loading, setLoading] = useState(true);
  const [mediaItems, setMediaItems] = useState<InstagramMediaItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [importing, setImporting] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [importResults, setImportResults] = useState<Array<{ id: string; status: string; message: string | null }> | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadMedia();
    } else {
      setSelectedIds([]);
      setImportResults(null);
      setErrorMsg(null);
    }
  }, [isOpen]);

  const loadMedia = async (afterCursor?: string) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.getInstagramMedia(afterCursor);
      if (afterCursor) {
        setMediaItems((prev) => [...prev, ...res.data]);
      } else {
        setMediaItems(res.data);
      }
      setNextCursor(res.paging?.cursors?.after || null);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch Instagram media. Ensure your account is connected.');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSelect = (item: InstagramMediaItem) => {
    if (item.already_imported) return;
    if (selectedIds.includes(item.id)) {
      setSelectedIds(selectedIds.filter((id) => id !== item.id));
    } else {
      if (selectedIds.length >= 20) {
        alert('You can select a maximum of 20 media items per import batch.');
        return;
      }
      setSelectedIds([...selectedIds, item.id]);
    }
  };

  const handleExecuteImport = async () => {
    if (selectedIds.length === 0) return;
    setImporting(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.importInstagramMedia(selectedIds);
      setImportResults(res.results);
      onImportComplete();
    } catch (err: any) {
      setErrorMsg(err.message || 'Import operation failed.');
    } finally {
      setImporting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in">
      <div className="w-full max-w-4xl bg-slate-900 border border-white/10 rounded-3xl p-6 shadow-2xl flex flex-col max-h-[90vh] text-white">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div>
            <h2 className="text-xl font-bold flex items-center gap-2">
              <span className="bg-gradient-to-tr from-amber-500 via-rose-500 to-purple-600 p-1.5 rounded-xl text-white">
                <ImageIcon className="w-4 h-4" />
              </span>
              <span>Import Instagram Posts & Reels</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Select up to 20 items to import directly into your Zynova Social feed. Media is safely re-hosted to private Cloudflare R2 storage.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {errorMsg && (
            <div className="p-3.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {importResults ? (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-emerald-400">Import Results</h3>
              <div className="divide-y divide-white/5 bg-black/40 rounded-2xl border border-white/10 overflow-hidden">
                {importResults.map((res) => (
                  <div key={res.id} className="p-3 flex items-center justify-between text-xs">
                    <span className="font-mono text-slate-300">ID: {res.id}</span>
                    <span
                      className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase ${
                        res.status === 'imported'
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : res.status === 'skipped'
                          ? 'bg-amber-500/20 text-amber-300'
                          : 'bg-rose-500/20 text-rose-300'
                      }`}
                    >
                      {res.status} {res.message ? `(${res.message})` : ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : loading && mediaItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
              <p className="text-xs">Fetching your Instagram media via Meta Graph API...</p>
            </div>
          ) : mediaItems.length === 0 ? (
            <div className="text-center py-16 text-slate-400 text-xs">
              No recent media found on your connected Instagram business account.
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {mediaItems.map((item) => {
                const isSelected = selectedIds.includes(item.id);
                const isImported = item.already_imported;
                const displayUrl = item.thumbnail_url || item.media_url;

                return (
                  <div
                    key={item.id}
                    onClick={() => handleToggleSelect(item)}
                    className={`group relative aspect-square rounded-2xl overflow-hidden border transition cursor-pointer select-none ${
                      isImported
                        ? 'opacity-40 border-white/5 cursor-not-allowed'
                        : isSelected
                        ? 'border-purple-500 ring-2 ring-purple-500/50 scale-[0.98]'
                        : 'border-white/10 hover:border-white/30'
                    }`}
                  >
                    {displayUrl ? (
                      <img src={displayUrl} alt="IG media" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full bg-slate-800 flex items-center justify-center text-slate-500 text-xs">
                        No Preview
                      </div>
                    )}

                    {/* Media Type Badge */}
                    <div className="absolute top-2 left-2 bg-black/60 backdrop-blur-md px-2 py-0.5 rounded-md text-[10px] font-bold uppercase flex items-center gap-1">
                      {item.media_type === 'VIDEO' ? (
                        <>
                          <VideoIcon className="w-3 h-3 text-purple-400" />
                          <span>Reel/Video</span>
                        </>
                      ) : (
                        <>
                          <ImageIcon className="w-3 h-3 text-amber-400" />
                          <span>Photo</span>
                        </>
                      )}
                    </div>

                    {/* Already Imported Overlay */}
                    {isImported && (
                      <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center text-slate-300 text-xs font-semibold gap-1">
                        <Check className="w-5 h-5 text-emerald-400" />
                        <span>Imported</span>
                      </div>
                    )}

                    {/* Selection Checkbox */}
                    {!isImported && (
                      <div className="absolute top-2 right-2">
                        <div
                          className={`w-6 h-6 rounded-lg flex items-center justify-center border transition ${
                            isSelected
                              ? 'bg-purple-600 border-purple-400 text-white'
                              : 'bg-black/50 border-white/30 group-hover:border-white'
                          }`}
                        >
                          {isSelected && <Check className="w-4 h-4 stroke-[3]" />}
                        </div>
                      </div>
                    )}

                    {/* Caption Preview Footer */}
                    {item.caption && (
                      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent p-2 pt-6 text-[10px] text-slate-200 line-clamp-1">
                        {item.caption}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {nextCursor && !importResults && (
            <div className="pt-2 flex justify-center">
              <button
                type="button"
                disabled={loading}
                onClick={() => loadMedia(nextCursor)}
                className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs text-slate-300 border border-white/10 flex items-center gap-2"
              >
                {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Load More</span>
              </button>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between pt-4 border-t border-white/10 text-xs">
          <div className="text-slate-400">
            {!importResults && (
              <span>
                Selected: <strong className="text-white">{selectedIds.length}</strong> / 20 max
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition"
            >
              {importResults ? 'Close' : 'Cancel'}
            </button>
            {!importResults && (
              <button
                type="button"
                disabled={selectedIds.length === 0 || importing}
                onClick={handleExecuteImport}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-rose-600 hover:from-purple-500 hover:to-rose-500 text-white font-bold flex items-center gap-2 disabled:opacity-50 transition shadow-lg shadow-purple-600/30"
              >
                {importing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Importing ({selectedIds.length})...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" />
                    <span>Import Selected</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
