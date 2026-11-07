import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, Send, Sparkles, Copy, RefreshCw, ThumbsUp, ThumbsDown, 
  Paperclip, Mic, ShieldAlert, Cpu, CheckCircle2, ChevronRight,
  Layers, Database, Square, Plus, Trash2, Globe2, AlertCircle
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { t } from '../../i18n';
import { apiClient, getApiBaseUrl } from '../../services/apiClient';

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  modelUsed?: string;
}

interface AIModelOption {
  id: string;
  name: string;
  provider: string;
  provider_name: string;
  is_configured: boolean;
  indic_support: boolean;
}

interface ConversationItem {
  id: string;
  title: string;
  message_count: number;
  updated_at: string;
  last_message?: string;
}

export const AIAssistantView: React.FC = () => {
  const { preferences, activeTheme } = useApp();
  const { user, isAuthenticated, openLoginModal } = useAuth();

  const [models, setModels] = useState<AIModelOption[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('mock-indic-v1');
  const [selectedProvider, setSelectedProvider] = useState<string>('mock');
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  const [inputPrompt, setInputPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState<'chat' | 'orchestration' | 'memory'>('chat');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'msg_init',
      sender: 'assistant',
      text: `Namaste! I am the **Zynova AI Core Engine**.\n\nI support real-time token streaming, multilingual Indic reasoning (English, தமிழ், Tanglish, Hindi, Telugu, and more), and sovereign private conversations. How may I assist you today?`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      modelUsed: 'Zynova Sovereign Core',
    },
  ]);

  // 1. Fetch available models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const baseUrl = getApiBaseUrl();
        const res = await fetch(`${baseUrl}/ai/models`);
        if (res.ok) {
          const data = await res.json();
          if (data.models && data.models.length > 0) {
            setModels(data.models);
            // Default to first configured model, or mock
            const defaultModel = data.models.find((m: AIModelOption) => m.is_configured) || data.models[0];
            setSelectedModel(defaultModel.id);
            setSelectedProvider(defaultModel.provider);
          }
        }
      } catch (e) {
        console.warn('Failed to fetch AI models list:', e);
      }
    };
    fetchModels();
  }, []);

  // 2. Fetch user conversations if authenticated
  const loadConversations = async () => {
    if (!isAuthenticated) {
      setConversations([]);
      return;
    }
    try {
      const baseUrl = getApiBaseUrl();
      const token = apiClient.getToken();
      const res = await fetch(`${baseUrl}/ai/conversations`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (res.ok) {
        const data = await res.json();
        setConversations(data.conversations || []);
      }
    } catch (e) {
      console.warn('Failed to fetch conversations:', e);
    }
  };

  useEffect(() => {
    loadConversations();
  }, [isAuthenticated]);

  // Scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load a conversation thread
  const handleSelectConversation = async (convId: string) => {
    try {
      setErrorMessage(null);
      const baseUrl = getApiBaseUrl();
      const token = apiClient.getToken();
      const res = await fetch(`${baseUrl}/ai/conversations/${convId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (res.ok) {
        const data = await res.json();
        const loadedMsgs: Message[] = (data.conversation?.messages || []).map((m: any) => ({
          id: m.id,
          sender: m.role === 'user' ? 'user' : 'assistant',
          text: m.content,
          timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          modelUsed: m.model_used
        }));
        setMessages(loadedMsgs.length > 0 ? loadedMsgs : messages);
        setActiveConversationId(convId);
      }
    } catch (e) {
      setErrorMessage('Failed to load conversation history.');
    }
  };

  const handleNewConversation = () => {
    setActiveConversationId(null);
    setErrorMessage(null);
    setMessages([
      {
        id: 'msg_new',
        sender: 'assistant',
        text: 'Started a new sovereign conversation thread. What would you like to explore?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        modelUsed: selectedModel,
      }
    ]);
  };

  const handleDeleteConversation = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    try {
      const baseUrl = getApiBaseUrl();
      const token = apiClient.getToken();
      await fetch(`${baseUrl}/ai/conversations/${convId}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (activeConversationId === convId) {
        handleNewConversation();
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsGenerating(false);
    }
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputPrompt.trim() || isGenerating) return;

    if (!isAuthenticated) {
      openLoginModal();
      return;
    }

    setErrorMessage(null);
    const userPromptText = inputPrompt.trim();
    setInputPrompt('');

    const userMsg: Message = {
      id: 'usr_' + Date.now(),
      sender: 'user',
      text: userPromptText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const assistantMsgId = 'ast_' + Date.now();
    const assistantMsg: Message = {
      id: assistantMsgId,
      sender: 'assistant',
      text: '',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      modelUsed: selectedModel,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsGenerating(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const baseUrl = getApiBaseUrl();
      const token = apiClient.getToken();
      const payload = {
        conversation_id: activeConversationId || undefined,
        prompt: userPromptText,
        provider: selectedProvider,
        model: selectedModel,
        locale: preferences?.language || 'en'
      };

      const res = await fetch(`${baseUrl}/ai/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify(payload),
        signal: controller.signal
      });

      if (!res.ok) {
        throw new Error(`Inference request failed with HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('ReadableStream not supported.');

      const decoder = new TextDecoder();
      let streamedAcc = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6).trim();
            if (!jsonStr) continue;
            try {
              const parsed = JSON.parse(jsonStr);
              if (parsed.type === 'start') {
                if (!activeConversationId && parsed.conversation_id) {
                  setActiveConversationId(parsed.conversation_id);
                  loadConversations();
                }
              } else if (parsed.type === 'chunk' && parsed.text) {
                streamedAcc += parsed.text;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId ? { ...m, text: streamedAcc } : m
                  )
                );
              } else if (parsed.type === 'error') {
                setErrorMessage(parsed.message || 'Error received from AI provider');
              }
            } catch (err) {
              // skip non-json keepalive chunks
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setErrorMessage(err.message || 'Network error communicating with AI Core Engine.');
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId && !m.text
              ? { ...m, text: 'Service temporarily unavailable. Please retry or select another provider.' }
              : m
          )
        );
      }
    } finally {
      setIsGenerating(false);
      abortControllerRef.current = null;
      loadConversations();
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex flex-col md:flex-row h-full gap-4">
      {/* Sidebar: Conversation History (Desktop & Tablet) */}
      <div className={`w-full md:w-64 flex-shrink-0 flex flex-col p-4 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} shadow-sm space-y-3`}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Conversations</span>
          <button
            onClick={handleNewConversation}
            className="p-1.5 rounded-lg bg-violet-600/20 text-violet-400 hover:bg-violet-600/30 transition flex items-center space-x-1 text-xs"
            title="Start New Thread"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 max-h-48 md:max-h-full">
          {conversations.length === 0 ? (
            <div className="text-xs text-slate-500 p-3 text-center italic">
              {isAuthenticated ? 'No saved threads yet.' : 'Sign in to sync your conversation threads.'}
            </div>
          ) : (
            conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => handleSelectConversation(c.id)}
                className={`group flex items-center justify-between p-2.5 rounded-xl text-xs cursor-pointer transition ${
                  activeConversationId === c.id
                    ? 'bg-violet-600/20 text-violet-300 font-medium border border-violet-500/30'
                    : 'text-slate-300 hover:bg-white/5 border border-transparent'
                }`}
              >
                <div className="truncate flex-1 mr-2">
                  <div className="truncate">{c.title}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{c.message_count} messages</div>
                </div>
                <button
                  onClick={(e) => handleDeleteConversation(e, c.id)}
                  className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 p-1 rounded transition"
                  title="Delete Thread"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Locale indicator */}
        <div className="pt-2 border-t border-white/5 flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center space-x-1.5">
            <Globe2 className="w-3.5 h-3.5 text-cyan-400" />
            <span>Indic Locale:</span>
          </div>
          <span className="font-mono text-cyan-300 font-semibold uppercase">{preferences?.language || 'EN'}</span>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full space-y-4">
        {/* Top Control Bar */}
        <div className={`p-4 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} flex flex-wrap items-center justify-between gap-4 shadow-sm`}>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-violet-600/20 text-violet-400 border border-violet-500/30">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-white tracking-tight">Zynova Sovereign AI</h2>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  Ready (Indic v3)
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">Zero client secret exposure & sovereign cryptographic logging</p>
            </div>
          </div>

          {/* Model Selector Dropdown */}
          <div className="flex items-center space-x-2">
            <select
              value={`${selectedProvider}:${selectedModel}`}
              onChange={(e) => {
                const [prov, mod] = e.target.value.split(':');
                setSelectedProvider(prov);
                setSelectedModel(mod);
              }}
              className="bg-slate-800/80 border border-white/10 rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-violet-500"
            >
              {models.map((m) => (
                <option key={`${m.provider}:${m.id}`} value={`${m.provider}:${m.id}`}>
                  {m.provider_name} — {m.name} {!m.is_configured ? '(Sandbox Demo)' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-1 min-h-[300px]">
          {messages.map((m) => {
            const isUser = m.sender === 'user';
            return (
              <div key={m.id} className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
                <div className={`max-w-[85%] md:max-w-[75%] rounded-2xl p-4 text-sm leading-relaxed ${
                  isUser
                    ? 'bg-violet-600 text-white rounded-br-sm shadow-md'
                    : `border ${activeTheme.borderClass} ${activeTheme.surfaceClass} text-slate-200 rounded-bl-sm shadow-sm backdrop-blur-md`
                }`}>
                  <div className="whitespace-pre-wrap">{m.text}</div>

                  <div className="mt-2.5 pt-2 border-t border-white/10 flex items-center justify-between text-[11px] opacity-70">
                    <span className="font-mono">{m.modelUsed || 'Sovereign Core'}</span>
                    <div className="flex items-center space-x-2">
                      <span>{m.timestamp}</span>
                      <button
                        onClick={() => handleCopy(m.id, m.text)}
                        className="hover:text-white transition p-1"
                        title="Copy text"
                      >
                        {copiedId === m.id ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className={`p-3 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} shadow-lg backdrop-blur-xl`}>
          <form onSubmit={handleSendMessage} className="flex items-center space-x-2">
            <input
              type="text"
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              placeholder="Ask Zynova anything in English, தமிழ், Tanglish, or Hindi..."
              disabled={isGenerating}
              className="flex-1 bg-transparent px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none"
            />

            {isGenerating ? (
              <button
                type="button"
                onClick={handleStopGeneration}
                className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white font-medium text-xs flex items-center space-x-1.5 transition"
              >
                <Square className="w-3.5 h-3.5" />
                <span>Stop</span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={!inputPrompt.trim()}
                className="p-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white transition flex items-center justify-center"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
};
