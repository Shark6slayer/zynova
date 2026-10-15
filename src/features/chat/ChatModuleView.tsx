import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Search, Phone, Video, MoreVertical, Send, Paperclip, 
  Smile, Mic, CheckCheck, Check, Users, Shield, Pin, 
  Plus, Edit2, Trash2, X, AlertCircle, Loader2, MessageSquare, LogIn 
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { 
  apiClient, 
  type ChatConversationResponse, 
  type ChatMessageResponse, 
  type UserPublicSummary 
} from '../../services/apiClient';
import { chatWebSocketService } from '../../services/chatWebSocket';
import { MOCK_USER } from '../../mocks/demoData';

export const ChatModuleView: React.FC = () => {
  const { user, isAuthenticated, openLoginModal } = useAuth();

  // State
  const [conversations, setConversations] = useState<ChatConversationResponse[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [typedMessage, setTypedMessage] = useState('');
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // User Search Modal
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [userSearchText, setUserSearchText] = useState('');
  const [userSearchResults, setUserSearchResults] = useState<UserPublicSummary[]>([]);
  const [isSearchingUsers, setIsSearchingUsers] = useState(false);

  // Edit Message
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Fetch Conversations list
  const loadConversations = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingConversations(true);
    try {
      const rooms = await apiClient.listConversations();
      setConversations(rooms);
      if (rooms.length > 0 && !activeConversationId) {
        setActiveConversationId(rooms[0].id);
      }
    } catch (err) {
      console.warn('Failed to load conversations:', err);
    } finally {
      setIsLoadingConversations(false);
    }
  }, [isAuthenticated, activeConversationId]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // Fetch Messages for active conversation
  const loadMessages = useCallback(async (convId: string) => {
    if (!isAuthenticated) return;
    setIsLoadingMessages(true);
    try {
      const msgs = await apiClient.getChatMessages(convId);
      setMessages(msgs);
      // Mark read
      await apiClient.markConversationRead(convId);
      // Reset unread count locally
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, unread_count: 0 } : c))
      );
    } catch (err) {
      console.warn('Failed to load chat messages:', err);
    } finally {
      setIsLoadingMessages(false);
      setTimeout(scrollToBottom, 100);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId);
    } else {
      setMessages([]);
    }
  }, [activeConversationId, loadMessages]);

  // Real-time WebSocket event listener
  useEffect(() => {
    if (!isAuthenticated) return;

    const unsubscribe = chatWebSocketService.subscribe((eventData) => {
      if (!eventData || !eventData.event) return;

      const { event, conversation_id, message, read_by_user_id } = eventData;

      if (event === 'new_message' && message) {
        // If current room is active, append message
        if (conversation_id === activeConversationId) {
          setMessages((prev) => {
            if (prev.some((m) => m.id === message.id)) return prev;
            return [...prev, message];
          });
          setTimeout(scrollToBottom, 50);
          apiClient.markConversationRead(conversation_id).catch(() => {});
        } else {
          // Increment unread count for that conversation
          setConversations((prev) =>
            prev.map((c) =>
              c.id === conversation_id ? { ...c, unread_count: c.unread_count + 1 } : c
            )
          );
        }

        // Update last message in conversation list
        setConversations((prev) =>
          prev.map((c) =>
            c.id === conversation_id
              ? {
                  ...c,
                  last_message: {
                    id: message.id,
                    sender_id: message.sender_id,
                    text: message.text,
                    created_at: message.created_at,
                  },
                  updated_at: message.created_at,
                }
              : c
          )
        );
      } else if (event === 'message_edited' && message) {
        if (conversation_id === activeConversationId) {
          setMessages((prev) =>
            prev.map((m) => (m.id === message.id ? message : m))
          );
        }
      } else if (event === 'message_deleted' && message) {
        if (conversation_id === activeConversationId) {
          setMessages((prev) =>
            prev.map((m) => (m.id === message.id ? message : m))
          );
        }
      } else if (event === 'conversation_read') {
        if (conversation_id === activeConversationId && read_by_user_id) {
          setMessages((prev) =>
            prev.map((m) => ({
              ...m,
              read_by: Array.from(new Set([...m.read_by, read_by_user_id])),
            }))
          );
        }
      }
    });

    return () => {
      unsubscribe();
    };
  }, [isAuthenticated, activeConversationId]);

  // Send Message
  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!typedMessage.trim() || !activeConversationId || isSending) return;

    const messageText = typedMessage.trim();
    setTypedMessage('');
    setIsSending(true);

    try {
      const created = await apiClient.sendChatMessage(activeConversationId, messageText);
      // Ensure it is in the list
      setMessages((prev) => {
        if (prev.some((m) => m.id === created.id)) return prev;
        return [...prev, created];
      });
      setTimeout(scrollToBottom, 50);
    } catch (err) {
      console.error('Failed to send message:', err);
      // Restore draft on failure
      setTypedMessage(messageText);
    } finally {
      setIsSending(false);
    }
  };

  // Edit Message
  const handleEditSubmit = async (messageId: string) => {
    if (!editingText.trim()) return;
    try {
      const updated = await apiClient.editChatMessage(messageId, editingText.trim());
      setMessages((prev) => prev.map((m) => (m.id === messageId ? updated : m)));
      setEditingMessageId(null);
      setEditingText('');
    } catch (err) {
      console.error('Failed to edit message:', err);
    }
  };

  // Delete Message
  const handleDeleteMessage = async (messageId: string) => {
    try {
      const deleted = await apiClient.deleteChatMessage(messageId);
      setMessages((prev) => prev.map((m) => (m.id === messageId ? deleted : m)));
    } catch (err) {
      console.error('Failed to delete message:', err);
    }
  };

  // Search and Start Conversation
  const handleSearchUsers = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userSearchText.trim()) return;
    setIsSearchingUsers(true);
    try {
      const results = await apiClient.searchUsers(userSearchText.trim());
      setUserSearchResults(results);
    } catch (err) {
      console.warn('User search error:', err);
    } finally {
      setIsSearchingUsers(false);
    }
  };

  const handleStartConversation = async (recipient: UserPublicSummary) => {
    try {
      const conv = await apiClient.getOrCreateConversation(recipient.id);
      setIsSearchModalOpen(false);
      setUserSearchText('');
      setUserSearchResults([]);
      setConversations((prev) => {
        if (prev.some((c) => c.id === conv.id)) return prev;
        return [conv, ...prev];
      });
      setActiveConversationId(conv.id);
    } catch (err) {
      console.error('Failed to start conversation:', err);
    }
  };

  // Determine active conversation info
  const activeConversation = conversations.find((c) => c.id === activeConversationId);
  const otherParticipantId = activeConversation?.participants.find((p) => p !== user?.id);
  const otherParticipant = otherParticipantId && activeConversation?.participant_meta?.[otherParticipantId]
    ? activeConversation.participant_meta[otherParticipantId]
    : null;

  const filteredConversations = conversations.filter((c) => {
    if (!searchQuery.trim()) return true;
    const otherId = c.participants.find((p) => p !== user?.id);
    const meta = otherId ? c.participant_meta[otherId] : null;
    return (
      meta?.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      meta?.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.last_message?.text.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 rounded-3xl border border-white/10 bg-slate-900/60 backdrop-blur-xl text-center space-y-4 max-w-lg mx-auto">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center text-white shadow-xl">
          <MessageSquare className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-white">Sign In for Sovereign P2P Messaging</h2>
        <p className="text-xs text-slate-400 leading-relaxed">
          Chat securely with other verified users in real time. Features include live WebSocket delivery, read receipts, message editing, and DPDP-compliant private messaging.
        </p>
        <button
          onClick={openLoginModal}
          className="px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 font-semibold text-xs text-white shadow-lg shadow-violet-500/25 flex items-center space-x-2 transition"
        >
          <LogIn className="w-4 h-4" />
          <span>Sign In / Create Account</span>
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col md:flex-row h-full rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-md overflow-hidden relative">
      {/* Left Conversations List Panel */}
      <div className="w-full md:w-80 border-r border-white/10 flex flex-col shrink-0">
        <div className="p-4 border-b border-white/10 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-white flex items-center gap-1.5">
              <span>Direct Messages</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400" title="Live WebSocket Active" />
            </h2>
            <button
              onClick={() => setIsSearchModalOpen(true)}
              className="p-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold flex items-center gap-1 transition shadow"
              title="New Message"
            >
              <Plus className="w-4 h-4" />
              <span>New</span>
            </button>
          </div>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search chats..."
              className="w-full pl-9 pr-3 py-2 bg-slate-800/80 border border-white/10 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-white/5">
          {isLoadingConversations ? (
            <div className="p-6 text-center text-slate-400 flex flex-col items-center gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-violet-400" />
              <span className="text-xs">Loading conversations...</span>
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="p-6 text-center text-slate-500 text-xs">
              {searchQuery ? 'No conversations match search' : 'No active chats. Click "New" to start messaging.'}
            </div>
          ) : (
            filteredConversations.map((c) => {
              const otherId = c.participants.find((p) => p !== user?.id);
              const meta = otherId ? c.participant_meta[otherId] : null;
              const name = meta?.full_name || 'Sovereign Contact';
              const avatar = meta?.avatar_url || MOCK_USER.avatar;
              const isActive = activeConversationId === c.id;

              return (
                <div
                  key={c.id}
                  onClick={() => setActiveConversationId(c.id)}
                  className={`p-3.5 flex items-center space-x-3 cursor-pointer transition-all ${
                    isActive ? 'bg-violet-600/15 border-l-2 border-violet-500' : 'hover:bg-white/5'
                  }`}
                >
                  <div className="relative shrink-0">
                    <img 
                      src={avatar} 
                      alt={name} 
                      className="w-11 h-11 rounded-full object-cover border border-violet-500/20"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = MOCK_USER.avatar;
                      }}
                    />
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 border border-slate-900 absolute bottom-0 right-0" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-semibold text-slate-200 truncate">{name}</h4>
                      {c.last_message && (
                        <span className="text-[10px] text-slate-400">
                          {new Date(c.last_message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 truncate mt-0.5">
                      {c.last_message ? c.last_message.text : 'Conversation started'}
                    </p>
                  </div>
                  {c.unread_count > 0 && (
                    <span className="w-4 h-4 rounded-full bg-violet-600 text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                      {c.unread_count}
                    </span>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Right Conversation Window */}
      <div className="flex-1 flex flex-col min-w-0">
        {activeConversation ? (
          <>
            {/* Conversation Header */}
            <div className="p-3.5 border-b border-white/10 flex items-center justify-between bg-slate-900/40">
              <div className="flex items-center space-x-3">
                <img 
                  src={otherParticipant?.avatar_url || MOCK_USER.avatar} 
                  alt={otherParticipant?.full_name || 'Contact'} 
                  className="w-9 h-9 rounded-full object-cover border border-violet-500/30"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = MOCK_USER.avatar;
                  }}
                />
                <div>
                  <h3 className="text-xs font-bold text-white flex items-center gap-1.5">
                    {otherParticipant?.full_name || 'Sovereign Contact'}
                    <span className="text-[10px] text-slate-400 font-mono">@{otherParticipant?.username}</span>
                  </h3>
                  <p className="text-[10px] text-emerald-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span>Live Channel & DPDP Protected</span>
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-2 text-slate-400">
                <button className="p-2 hover:text-white hover:bg-white/5 rounded-lg transition" title="Voice Call (P2P)">
                  <Phone className="w-4 h-4" />
                </button>
                <button className="p-2 hover:text-white hover:bg-white/5 rounded-lg transition" title="Video Call (P2P)">
                  <Video className="w-4 h-4" />
                </button>
                <button className="p-2 hover:text-white hover:bg-white/5 rounded-lg transition">
                  <MoreVertical className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Message Thread */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {isLoadingMessages ? (
                <div className="flex items-center justify-center h-full text-slate-400 gap-2">
                  <Loader2 className="w-5 h-5 animate-spin text-violet-400" />
                  <span className="text-xs">Loading message history...</span>
                </div>
              ) : messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-500 text-xs gap-1">
                  <p>Say hello to start the conversation!</p>
                  <p className="text-[10px] text-slate-600">Messages are sent over real-time WebSockets.</p>
                </div>
              ) : (
                messages.map((msg) => {
                  const isMe = msg.sender_id === user?.id;
                  const isRead = otherParticipantId && msg.read_by.includes(otherParticipantId);

                  return (
                    <div
                      key={msg.id}
                      className={`flex flex-col max-w-sm group ${isMe ? 'ml-auto items-end' : 'items-start'}`}
                    >
                      {editingMessageId === msg.id ? (
                        <div className="w-full p-2 bg-slate-800 rounded-2xl border border-violet-500/50 space-y-2">
                          <input
                            type="text"
                            value={editingText}
                            onChange={(e) => setEditingText(e.target.value)}
                            className="w-full px-2.5 py-1.5 bg-black/40 rounded-xl text-xs text-white focus:outline-none"
                            autoFocus
                          />
                          <div className="flex justify-end gap-1.5">
                            <button
                              onClick={() => setEditingMessageId(null)}
                              className="px-2.5 py-1 rounded bg-white/5 text-[10px] text-slate-400 hover:text-white"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleEditSubmit(msg.id)}
                              className="px-2.5 py-1 rounded bg-violet-600 text-[10px] text-white font-semibold"
                            >
                              Save
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div
                          className={`p-3 rounded-2xl text-xs leading-relaxed relative ${
                            isMe
                              ? 'bg-violet-600 text-white rounded-tr-sm shadow-md'
                              : 'bg-slate-800 text-slate-200 rounded-tl-sm border border-white/5 shadow-sm'
                          } ${msg.is_deleted ? 'italic opacity-60' : ''}`}
                        >
                          {msg.text}
                          {msg.is_edited && !msg.is_deleted && (
                            <span className="text-[9px] opacity-75 ml-1.5">(edited)</span>
                          )}

                          {/* Hover actions for sender */}
                          {isMe && !msg.is_deleted && (
                            <div className="absolute top-1 -left-14 hidden group-hover:flex items-center gap-1 bg-slate-900/90 rounded-lg p-1 border border-white/10 shadow">
                              <button
                                onClick={() => {
                                  setEditingMessageId(msg.id);
                                  setEditingText(msg.text);
                                }}
                                className="p-1 hover:text-violet-400 text-slate-400"
                                title="Edit"
                              >
                                <Edit2 className="w-3 h-3" />
                              </button>
                              <button
                                onClick={() => handleDeleteMessage(msg.id)}
                                className="p-1 hover:text-rose-400 text-slate-400"
                                title="Delete"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          )}
                        </div>
                      )}

                      <div className="flex items-center space-x-1 text-[10px] text-slate-400 mt-1 px-1">
                        <span>
                          {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        {isMe && (
                          isRead ? (
                            <span title="Read"><CheckCheck className="w-3 h-3 text-emerald-400" /></span>
                          ) : (
                            <span title="Sent"><Check className="w-3 h-3 text-slate-400" /></span>
                          )
                        )}

                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Message Input Box */}
            <form onSubmit={handleSend} className="p-3 border-t border-white/10 bg-slate-900/60 flex items-center space-x-2">
              <button type="button" className="p-2 text-slate-400 hover:text-white" title="Attach media">
                <Paperclip className="w-4 h-4" />
              </button>
              <input
                type="text"
                value={typedMessage}
                onChange={(e) => setTypedMessage(e.target.value)}
                placeholder="Type a message..."
                maxLength={2000}
                className="flex-1 bg-slate-800/80 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500"
              />
              <button
                type="submit"
                disabled={!typedMessage.trim() || isSending}
                className="p-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-40 transition flex items-center justify-center"
              >
                {isSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </form>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 p-6 space-y-3">
            <MessageSquare className="w-12 h-12 text-slate-600" />
            <h3 className="text-sm font-semibold text-white">Select or start a conversation</h3>
            <button
              onClick={() => setIsSearchModalOpen(true)}
              className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-xs font-semibold text-white transition flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>Search Users to Message</span>
            </button>
          </div>
        )}
      </div>

      {/* User Search & New Conversation Modal */}
      {isSearchModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in">
          <div className="w-full max-w-md bg-slate-900 border border-white/15 rounded-3xl p-6 shadow-2xl text-white space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold">New Direct Message</h3>
              <button
                onClick={() => {
                  setIsSearchModalOpen(false);
                  setUserSearchResults([]);
                  setUserSearchText('');
                }}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSearchUsers} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                <input
                  type="text"
                  value={userSearchText}
                  onChange={(e) => setUserSearchText(e.target.value)}
                  placeholder="Search by name or username..."
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-black/40 border border-white/10 text-xs text-white focus:outline-none focus:border-violet-500"
                  autoFocus
                />
              </div>
              <button
                type="submit"
                disabled={isSearchingUsers}
                className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-xs font-semibold text-white transition disabled:opacity-50"
              >
                {isSearchingUsers ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
              </button>
            </form>

            <div className="max-h-60 overflow-y-auto space-y-2 pt-2 divide-y divide-white/5">
              {userSearchResults.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-4">
                  {userSearchText ? 'No users found matching query' : 'Type a name or @username to discover users'}
                </p>
              ) : (
                userSearchResults.map((usr) => (
                  <div
                    key={usr.id}
                    onClick={() => handleStartConversation(usr)}
                    className="flex items-center justify-between p-2.5 rounded-xl hover:bg-white/5 cursor-pointer transition"
                  >
                    <div className="flex items-center space-x-3">
                      <img
                        src={usr.avatar_url || MOCK_USER.avatar}
                        alt={usr.full_name}
                        className="w-10 h-10 rounded-full object-cover border border-violet-500/30"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = MOCK_USER.avatar;
                        }}
                      />
                      <div>
                        <h4 className="text-xs font-semibold text-white">{usr.full_name}</h4>
                        <p className="text-[10px] text-slate-400 font-mono">@{usr.username}</p>
                      </div>
                    </div>
                    <button className="px-3 py-1 rounded-lg bg-violet-600/30 hover:bg-violet-600 text-violet-200 hover:text-white text-[11px] font-semibold transition">
                      Message
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
