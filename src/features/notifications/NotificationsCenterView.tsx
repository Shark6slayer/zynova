import React, { useState, useEffect, useCallback } from 'react';
import { 
  Bell, Check, Trash2, Filter, AlertCircle, 
  MessageSquare, ShoppingBag, CreditCard, Sparkles,
  Utensils, Share2, CheckCheck, RefreshCw, Loader2, ArrowRight,
  ExternalLink, Clock
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useApp } from '../../context/AppContext';
import { apiClient, type NotificationResponse } from '../../services/apiClient';

export const NotificationsCenterView: React.FC = () => {
  const { user, isAuthenticated, openLoginModal } = useAuth();
  const { setActiveModule, setUnreadNotificationsCount } = useApp();

  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'chat' | 'social' | 'food' | 'shopping' | 'system'>('all');
  const [unreadOnly, setUnreadOnly] = useState<boolean>(false);
  const [page, setPage] = useState<number>(1);
  const [hasMore, setHasMore] = useState<boolean>(false);

  // Action busy states
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [isMarkingAll, setIsMarkingAll] = useState<boolean>(false);

  const fetchNotifications = useCallback(async (isBackground = false) => {
    if (!isAuthenticated) {
      setIsLoading(false);
      setNotifications([]);
      setTotalCount(0);
      setUnreadCount(0);
      return;
    }

    if (!isBackground) setIsLoading(true);
    else setIsRefreshing(true);
    setError(null);

    try {
      const data = await apiClient.listNotifications({
        category: selectedCategory,
        unreadOnly,
        page: 1,
        limit: 30
      });

      setNotifications(data.notifications);
      setTotalCount(data.total);
      setUnreadCount(data.unread_count);
      setHasMore(data.has_more);
      setUnreadNotificationsCount(data.unread_count);
    } catch (err: any) {
      setError(err.message || 'Failed to load notifications');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [isAuthenticated, selectedCategory, unreadOnly, setUnreadNotificationsCount]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const handleMarkOneRead = async (notif: NotificationResponse, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (notif.read) return;

    setActionLoadingId(notif.id);
    try {
      const updated = await apiClient.markNotificationRead(notif.id);
      setNotifications(prev => prev.map(n => n.id === notif.id ? updated : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
      setUnreadNotificationsCount(Math.max(0, unreadCount - 1));
    } catch (err: any) {
      console.warn('Error marking notification read:', err);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleMarkAllRead = async () => {
    if (unreadCount === 0) return;
    setIsMarkingAll(true);
    try {
      await apiClient.markAllNotificationsRead();
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
      setUnreadNotificationsCount(0);
    } catch (err: any) {
      console.warn('Error marking all notifications read:', err);
    } finally {
      setIsMarkingAll(false);
    }
  };

  const handleDeleteNotification = async (notificationId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setActionLoadingId(notificationId);
    try {
      await apiClient.deleteNotification(notificationId);
      const target = notifications.find(n => n.id === notificationId);
      setNotifications(prev => prev.filter(n => n.id !== notificationId));
      setTotalCount(prev => Math.max(0, prev - 1));
      if (target && !target.read) {
        setUnreadCount(prev => Math.max(0, prev - 1));
        setUnreadNotificationsCount(Math.max(0, unreadCount - 1));
      }
    } catch (err: any) {
      alert(err.message || 'Failed to dismiss notification');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleNotificationClick = async (notif: NotificationResponse) => {
    if (!notif.read) {
      handleMarkOneRead(notif);
    }

    const target = notif.metadata?.navigation_target;
    if (!target) return;

    // Navigate to appropriate module based on target URI
    if (target.startsWith('chat')) {
      setActiveModule('chat');
    } else if (target.startsWith('social')) {
      setActiveModule('social');
    } else if (target.startsWith('food')) {
      setActiveModule('food');
    } else if (target.startsWith('shopping')) {
      setActiveModule('shopping');
    }
  };

  const getCategoryBadge = (category: string) => {
    switch (category) {
      case 'chat':
        return { icon: MessageSquare, bg: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' };
      case 'social':
        return { icon: Share2, bg: 'bg-violet-500/20 text-violet-400 border-violet-500/30' };
      case 'food':
        return { icon: Utensils, bg: 'bg-amber-500/20 text-amber-400 border-amber-500/30' };
      case 'shopping':
        return { icon: ShoppingBag, bg: 'bg-rose-500/20 text-rose-400 border-rose-500/30' };
      default:
        return { icon: Bell, bg: 'bg-slate-500/20 text-slate-300 border-slate-500/30' };
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto w-full p-8 rounded-3xl bg-slate-900/60 border border-white/10 text-center space-y-4">
        <Bell className="w-12 h-12 text-slate-500 mx-auto" />
        <h2 className="text-xl font-bold text-white">Sign In to View Notifications</h2>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          Keep track of your direct messages, social mentions, live food orders, and shopping deliveries.
        </p>
        <button
          onClick={openLoginModal}
          className="px-6 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs transition"
        >
          Sign In / Register
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto w-full pb-16">
      {/* Header & Controls */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-violet-950/40 via-slate-900/90 to-indigo-950/40 border border-violet-500/20 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-violet-400 text-xs font-semibold uppercase tracking-wider">
            <Bell className="w-4 h-4" />
            <span>Activity Stream</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1 flex items-center gap-2.5">
            <span>Notifications & Updates</span>
            {unreadCount > 0 && (
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-violet-600 text-white font-mono font-bold">
                {unreadCount} unread
              </span>
            )}
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time verified events across messages, social activity, food orders, and shopping shipments.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => fetchNotifications(true)}
            disabled={isRefreshing}
            className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-medium border border-white/10 transition flex items-center gap-1.5"
            title="Refresh feed"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          <button
            onClick={handleMarkAllRead}
            disabled={isMarkingAll || unreadCount === 0}
            className="px-3 py-2 rounded-xl bg-white/5 hover:bg-white/10 disabled:opacity-40 text-slate-300 text-xs font-semibold border border-white/10 transition flex items-center gap-1.5"
          >
            {isMarkingAll ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCheck className="w-3.5 h-3.5" />}
            <span>Mark all read</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded-2xl bg-slate-900/40 border border-white/5">
        <div className="flex items-center space-x-1 overflow-x-auto text-xs py-1">
          {(['all', 'chat', 'social', 'food', 'shopping'] as const).map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-xl font-medium capitalize transition ${
                selectedCategory === cat
                  ? 'bg-violet-600 text-white shadow'
                  : 'bg-white/5 text-slate-300 hover:bg-white/10'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 px-2">
          <label className="text-xs text-slate-400 flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={e => setUnreadOnly(e.target.checked)}
              className="rounded bg-slate-800 border-white/20 text-violet-600 focus:ring-0"
            />
            <span>Unread only</span>
          </label>
        </div>
      </div>

      {/* Notifications List */}
      {isLoading ? (
        <div className="py-20 text-center space-y-3">
          <Loader2 className="w-8 h-8 text-violet-500 animate-spin mx-auto" />
          <p className="text-xs text-slate-400">Loading activity stream...</p>
        </div>
      ) : error ? (
        <div className="p-8 rounded-3xl bg-red-500/10 border border-red-500/20 text-center space-y-3">
          <AlertCircle className="w-8 h-8 text-red-400 mx-auto" />
          <p className="text-sm font-semibold text-red-300">{error}</p>
          <button
            onClick={() => fetchNotifications()}
            className="px-4 py-2 rounded-xl bg-violet-600 text-white text-xs font-semibold hover:bg-violet-500 transition"
          >
            Retry
          </button>
        </div>
      ) : notifications.length === 0 ? (
        <div className="p-12 rounded-3xl border border-white/5 bg-slate-900/30 text-center space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center mx-auto text-slate-500">
            <Bell className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-slate-200">No notifications found</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {unreadOnly 
              ? 'You have caught up with all your unread alerts!' 
              : 'As you send messages, interact on social feeds, or place orders, real-time alerts will appear here.'}
          </p>
          {unreadOnly && (
            <button
              onClick={() => setUnreadOnly(false)}
              className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold"
            >
              Show all notifications
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-2.5">
          {notifications.map(n => {
            const badge = getCategoryBadge(n.category);
            const BadgeIcon = badge.icon;
            const isClickable = Boolean(n.metadata?.navigation_target);

            return (
              <div
                key={n.id}
                onClick={() => handleNotificationClick(n)}
                role={isClickable ? "button" : undefined}
                tabIndex={isClickable ? 0 : undefined}
                onKeyDown={e => {
                  if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
                    e.preventDefault();
                    handleNotificationClick(n);
                  }
                }}
                className={`p-4 rounded-2xl border transition-all flex items-start justify-between gap-4 group cursor-pointer ${
                  n.read
                    ? 'border-white/5 bg-slate-900/40 opacity-75 hover:opacity-100 hover:border-white/10'
                    : 'border-violet-500/30 bg-slate-900/80 shadow-md shadow-violet-950/20 hover:border-violet-500/50'
                }`}
              >
                <div className="flex items-start space-x-3.5 min-w-0 flex-1">
                  {/* Category Icon */}
                  <div className={`p-2.5 rounded-xl border mt-0.5 shrink-0 ${badge.bg}`}>
                    <BadgeIcon className="w-4 h-4" />
                  </div>

                  {/* Text Content */}
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="text-xs font-bold text-white group-hover:text-violet-300 transition">
                        {n.title}
                      </h4>
                      {!n.read && (
                        <span className="w-2 h-2 rounded-full bg-violet-400 shrink-0" title="Unread" />
                      )}
                    </div>
                    
                    <p className="text-xs text-slate-300 leading-relaxed break-words">
                      {n.desc}
                    </p>

                    <div className="flex items-center gap-3 pt-1 text-[11px] text-slate-500">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>{n.time}</span>
                      </span>
                      {isClickable && (
                        <span className="text-violet-400 group-hover:underline flex items-center gap-1">
                          <span>View Details</span>
                          <ArrowRight className="w-2.5 h-2.5" />
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Inline Action Buttons */}
                <div className="flex items-center space-x-1 shrink-0 opacity-80 group-hover:opacity-100 transition">
                  {!n.read && (
                    <button
                      onClick={e => handleMarkOneRead(n, e)}
                      disabled={actionLoadingId === n.id}
                      className="p-1.5 rounded-lg bg-white/5 hover:bg-violet-600/30 text-slate-400 hover:text-white transition"
                      title="Mark as read"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <button
                    onClick={e => handleDeleteNotification(n.id, e)}
                    disabled={actionLoadingId === n.id}
                    className="p-1.5 rounded-lg bg-white/5 hover:bg-red-500/20 text-slate-400 hover:text-red-400 transition"
                    title="Dismiss notification"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
