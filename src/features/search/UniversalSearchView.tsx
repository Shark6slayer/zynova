import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Search, Users, MessageSquare, Globe, ArrowRight, Loader2, 
  X, AlertCircle, Calendar, Heart, MessageCircle, ExternalLink, RefreshCw
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { apiClient, type SearchResultItem } from '../../services/apiClient';

export const UniversalSearchView: React.FC = () => {
  const { searchQuery, setSearchQuery, setActiveModule } = useApp();
  const [localQuery, setLocalQuery] = useState(searchQuery || '');
  const [activeFilter, setActiveFilter] = useState<'all' | 'people' | 'posts'>('all');
  const [sortBy, setSortBy] = useState<'recency' | 'relevance'>('recency');
  
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState<boolean>(false);

  // Pagination
  const [pageOffset, setPageOffset] = useState<number>(0);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const pageSize = 15;

  // Stale request cancellation ref
  const abortControllerRef = useRef<AbortController | null>(null);

  // Execute Search
  const performSearch = useCallback(
    async (queryText: string, filterType: 'all' | 'people' | 'posts', offset: number, sortMode: 'recency' | 'relevance') => {
      const trimmed = queryText.trim();
      if (!trimmed) {
        setResults([]);
        setTotalCount(0);
        setHasMore(false);
        setIsLoading(false);
        setHasSearched(false);
        return;
      }

      // Cancel any ongoing stale request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setIsLoading(true);
      setSearchError(null);
      setHasSearched(true);

      try {
        const response = await apiClient.searchPlatform(
          trimmed,
          filterType,
          pageSize,
          offset,
          sortMode,
          controller.signal
        );

        if (offset === 0) {
          setResults(response.results);
        } else {
          setResults((prev) => [...prev, ...response.results]);
        }
        setTotalCount(response.total_count);
        setHasMore(response.has_more);
      } catch (err: any) {
        if (err.name === 'AbortError') {
          // Ignored cancelled stale query
          return;
        }
        setSearchError(err.message || 'Error occurred while searching');
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // Debounced search on typing
  useEffect(() => {
    const handler = setTimeout(() => {
      setPageOffset(0);
      performSearch(localQuery, activeFilter, 0, sortBy);
    }, 300);

    return () => clearTimeout(handler);
  }, [localQuery, activeFilter, sortBy, performSearch]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchQuery(localQuery);
    setPageOffset(0);
    performSearch(localQuery, activeFilter, 0, sortBy);
  };

  const handleClear = () => {
    setLocalQuery('');
    setSearchQuery('');
    setResults([]);
    setTotalCount(0);
    setHasSearched(false);
  };

  const handleLoadMore = () => {
    const nextOffset = pageOffset + pageSize;
    setPageOffset(nextOffset);
    performSearch(localQuery, activeFilter, nextOffset, sortBy);
  };

  const handleNavigate = (item: SearchResultItem) => {
    if (item.result_type === 'person') {
      // Navigate to social feed module to connect/interact
      setActiveModule('social');
    } else if (item.result_type === 'post') {
      setActiveModule('social');
    }
  };

  return (
    <div className="flex flex-col h-full space-y-6 max-w-4xl mx-auto w-full pb-12">
      {/* Header and Search Form */}
      <div className="space-y-4">
        <form onSubmit={handleSubmit} className="relative">
          <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            placeholder="Search verified people, usernames, bios, and public social posts..."
            maxLength={100}
            className="w-full pl-12 pr-28 py-3.5 bg-slate-900/80 border border-white/10 rounded-2xl text-base text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500 shadow-lg backdrop-blur-md transition"
          />
          <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center space-x-1.5">
            {localQuery && (
              <button
                type="button"
                onClick={handleClear}
                className="p-1.5 text-slate-400 hover:text-white rounded-lg transition"
                title="Clear input"
              >
                <X className="w-4 h-4" />
              </button>
            )}
            <button
              type="submit"
              className="px-4 py-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-semibold transition shadow-md flex items-center space-x-1"
            >
              <span>Search</span>
            </button>
          </div>
        </form>

        {/* Content Type Filter Tabs */}
        <div className="flex items-center justify-between border-b border-white/10 pb-2 text-xs">
          <div className="flex items-center space-x-1.5">
            {[
              { id: 'all', label: 'All Results', icon: Globe },
              { id: 'people', label: 'People & Creators', icon: Users },
              { id: 'posts', label: 'Public Posts', icon: MessageSquare },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeFilter === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveFilter(tab.id as any);
                    setPageOffset(0);
                  }}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl transition font-medium ${
                    isActive
                      ? 'bg-violet-600/20 text-violet-300 border border-violet-500/30'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Sort Selector */}
          <div className="flex items-center space-x-2 text-slate-400">
            <span className="text-[11px]">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-slate-800/80 border border-white/10 rounded-lg px-2 py-1 text-[11px] text-slate-200 focus:outline-none focus:border-violet-500"
            >
              <option value="recency">Most Recent</option>
              <option value="relevance">Relevance</option>
            </select>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      {searchError && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{searchError}</span>
        </div>
      )}

      {/* Loading state indicator */}
      {isLoading && (
        <div className="flex justify-center items-center py-10 space-x-2 text-slate-400 text-xs">
          <Loader2 className="w-5 h-5 animate-spin text-violet-400" />
          <span>Querying indexed platform database...</span>
        </div>
      )}

      {/* Initial Landing or Empty State */}
      {!isLoading && !hasSearched && (
        <div className="text-center py-16 bg-slate-900/40 rounded-2xl border border-white/5 p-8 space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-violet-600/10 text-violet-400 flex items-center justify-center mx-auto border border-violet-500/20">
            <Search className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-slate-200">Real-Time Platform Search</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Find registered developers, researchers, creators, and public social posts across the SUPER_AI network.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2 pt-2 text-xs">
            {['Indic', 'AI', 'Bangalore', 'ONDC', 'quantum'].map((tag) => (
              <button
                key={tag}
                onClick={() => setLocalQuery(tag)}
                className="px-2.5 py-1 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:text-violet-300 hover:border-violet-500/30 transition text-[11px]"
              >
                #{tag}
              </button>
            ))}
          </div>
        </div>
      )}

      {!isLoading && hasSearched && results.length === 0 && (
        <div className="text-center py-16 bg-slate-900/40 rounded-2xl border border-white/5 p-8 space-y-2">
          <p className="text-sm font-semibold text-slate-300">
            No matching {activeFilter === 'all' ? 'results' : activeFilter} found for "{localQuery}"
          </p>
          <p className="text-xs text-slate-500">
            Try checking for spelling, broadening your keywords, or switching categories.
          </p>
        </div>
      )}

      {/* Search Results Display */}
      {!isLoading && results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400 px-1">
            <span>
              Found <strong className="text-white">{totalCount}</strong> platform {totalCount === 1 ? 'match' : 'matches'}
            </span>
          </div>

          <div className="space-y-3">
            {results.map((item) => (
              <div
                key={`${item.result_type}-${item.id}`}
                onClick={() => handleNavigate(item)}
                className="p-4 rounded-2xl bg-slate-900/50 border border-white/5 hover:border-violet-500/30 transition group cursor-pointer space-y-2"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    {item.result_type === 'person' ? (
                      item.avatar_url ? (
                        <img
                          src={item.avatar_url}
                          alt={item.title}
                          className="w-10 h-10 rounded-full object-cover shrink-0 border border-white/10"
                        />
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-violet-600/20 text-violet-300 font-bold flex items-center justify-center shrink-0 border border-violet-500/20 text-xs uppercase">
                          {item.title.slice(0, 2)}
                        </div>
                      )
                    ) : item.avatar_url ? (
                      <img
                        src={item.avatar_url}
                        alt="Author"
                        className="w-8 h-8 rounded-full object-cover shrink-0 border border-white/10"
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-slate-800 text-slate-300 font-bold flex items-center justify-center shrink-0 border border-white/10 text-xs">
                        <MessageSquare className="w-4 h-4 text-slate-400" />
                      </div>
                    )}

                    <div>
                      <div className="flex items-center space-x-2">
                        <h4 className="text-sm font-semibold text-white group-hover:text-violet-300 transition">
                          {item.title}
                        </h4>
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider font-semibold border ${
                            item.result_type === 'person'
                              ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                              : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          }`}
                        >
                          {item.result_type}
                        </span>
                      </div>
                      {item.subtitle && <p className="text-xs text-slate-400">{item.subtitle}</p>}
                    </div>
                  </div>

                  {item.timestamp && (
                    <span className="text-[10px] text-slate-500 flex items-center space-x-1">
                      <Calendar className="w-3 h-3" />
                      <span>{new Date(item.timestamp).toLocaleDateString()}</span>
                    </span>
                  )}
                </div>

                <p className="text-xs text-slate-300 leading-relaxed pl-13 line-clamp-2">
                  {item.excerpt}
                </p>

                {item.image_url && (
                  <div className="pl-13 pt-1">
                    <img
                      src={item.image_url}
                      alt="Attachment"
                      className="rounded-xl max-h-40 object-cover border border-white/10"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />
                  </div>
                )}

                {/* Additional Metadata / Quick Stats */}
                {item.metadata && (
                  <div className="flex items-center space-x-4 pl-13 pt-1 text-[11px] text-slate-400 border-t border-white/5">
                    {item.result_type === 'post' && (
                      <>
                        <span className="flex items-center space-x-1">
                          <Heart className="w-3 h-3 text-pink-400" />
                          <span>{item.metadata.likes_count || 0}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <MessageCircle className="w-3 h-3 text-blue-400" />
                          <span>{item.metadata.comments_count || 0}</span>
                        </span>
                      </>
                    )}
                    <span className="text-violet-400 group-hover:underline flex items-center space-x-1 ml-auto">
                      <span>View in Social Feed</span>
                      <ArrowRight className="w-3 h-3" />
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Load More Pagination */}
          {hasMore && (
            <div className="flex justify-center pt-4">
              <button
                onClick={handleLoadMore}
                disabled={isLoading}
                className="px-6 py-2.5 bg-white/5 hover:bg-white/10 text-white border border-white/10 rounded-xl text-xs font-semibold transition flex items-center space-x-2"
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                <span>Load More Results</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
