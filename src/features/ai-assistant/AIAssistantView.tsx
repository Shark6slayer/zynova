import React, { useState } from 'react';
import { 
  Bot, Send, Sparkles, Copy, RefreshCw, ThumbsUp, ThumbsDown, 
  Paperclip, Mic, ShieldAlert, Cpu, CheckCircle2, ChevronRight,
  Layers, Database
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { t } from '../../i18n';

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  modelUsed?: string;
  isSimulatedAction?: boolean;
}

export const AIAssistantView: React.FC = () => {
  const { preferences, activeTheme } = useApp();
  const [selectedModel, setSelectedModel] = useState('SUPER Multilingual (Indic-v2)');
  const [inputPrompt, setInputPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState<'chat' | 'orchestration' | 'memory'>('chat');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'msg_1',
      sender: 'assistant',
      text: `Namaste Ananya! I am **SUPER_AI Universal Assistant**. \n\nI can seamlessly orchestrate tasks across your digital life: search the web, compose emails, plan itineraries in Tamil/Hindi/English, order from A2B or Meghana Foods, analyze financial spending, or write TypeScript code. \n\nHow can I empower your day today?`,
      timestamp: '10:00 AM',
      modelUsed: 'SUPER Multilingual (Indic-v2)',
    },
  ]);

  // Orchestrator simulation state
  const [orchestratorRunning, setOrchestratorRunning] = useState(false);
  const [orchestratorStep, setOrchestratorStep] = useState(0);

  const handleSendMessage = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputPrompt.trim() || isGenerating) return;

    const userMsg: Message = {
      id: 'usr_' + Date.now(),
      sender: 'user',
      text: inputPrompt,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    const promptSnapshot = inputPrompt;
    setInputPrompt('');
    setIsGenerating(true);

    setTimeout(() => {
      let reply = `Here is the comprehensive response from **${selectedModel}**:\n\n`;
      if (promptSnapshot.toLowerCase().includes('food') || promptSnapshot.toLowerCase().includes('order')) {
        reply += `I have inspected your food preferences. I found **A2B - Adyar Ananda Bhavan** (Rating 4.6, 22 mins away) with fresh Ghee Roast Dosa, or **Meghana Foods** for Andhra Biryani. Would you like me to prepare a cart for review?`;
      } else if (promptSnapshot.toLowerCase().includes('code') || promptSnapshot.toLowerCase().includes('react')) {
        reply += `Here is an optimized TypeScript hook for managing state with localStorage and auto-sync:\n\n\`\`\`typescript\nexport function useLocalStorage<T>(key: string, initial: T): [T, (val: T) => void] {\n  const [val, setVal] = useState<T>(() => JSON.parse(localStorage.getItem(key) || JSON.stringify(initial)));\n  return [val, (newVal) => { localStorage.setItem(key, JSON.stringify(newVal)); setVal(newVal); }];\n}\n\`\`\``;
      } else {
        reply += `I processed your request: "${promptSnapshot}".\n\nCross-referencing your personal workspace notes and Indian regional context, all insights have been aggregated with zero data leakage.`;
      }

      const assistantMsg: Message = {
        id: 'ast_' + Date.now(),
        sender: 'assistant',
        text: reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        modelUsed: selectedModel,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setIsGenerating(false);
    }, 900);
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const startDemoOrchestration = () => {
    setOrchestratorRunning(true);
    setOrchestratorStep(1);

    setTimeout(() => setOrchestratorStep(2), 1200);
    setTimeout(() => setOrchestratorStep(3), 2400);
    setTimeout(() => setOrchestratorStep(4), 3800);
  };

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Top Bar with Model Selection and Mode Tabs */}
      <div className={`p-4 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} flex flex-wrap items-center justify-between gap-4 shadow-sm`}>
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-violet-600/20 text-violet-400 border border-violet-500/30">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-semibold text-lg flex items-center gap-2">
              SUPER_AI Universal Copilot
              <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                ACTIVE
              </span>
            </h1>
            <p className="text-xs text-slate-400">Indic-First Multi-Engine Agentic Architecture</p>
          </div>
        </div>

        {/* Mode Switcher */}
        <div className="flex items-center p-1 rounded-xl bg-black/30 border border-white/5 text-xs">
          <button
            onClick={() => setActiveTab('chat')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'chat' ? 'bg-violet-600 text-white shadow' : 'text-slate-400 hover:text-white'
            }`}
          >
            Universal Chat
          </button>
          <button
            onClick={() => setActiveTab('orchestration')}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
              activeTab === 'orchestration' ? 'bg-violet-600 text-white shadow' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5" /> Multi-Agent Workflow
          </button>
          <button
            onClick={() => setActiveTab('memory')}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
              activeTab === 'memory' ? 'bg-violet-600 text-white shadow' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Database className="w-3.5 h-3.5" /> Sovereign Memory
          </button>
        </div>

        {/* Model Dropdown */}
        <div className="flex items-center space-x-2">
          <Cpu className="w-4 h-4 text-violet-400" />
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="text-xs bg-slate-800/80 border border-white/10 rounded-lg px-3 py-1.5 text-slate-200 focus:outline-none focus:border-violet-500"
          >
            <option value="SUPER Multilingual (Indic-v2)">SUPER Multilingual (Indic-v2)</option>
            <option value="SUPER Reasoning (Chain-of-Thought)">SUPER Reasoning (CoT)</option>
            <option value="SUPER Code (Agentic v3)">SUPER Code (Agentic v3)</option>
            <option value="SUPER Research (Deep Web)">SUPER Research (Deep Web)</option>
            <option value="SUPER Vision (Multimodal)">SUPER Vision (Multimodal)</option>
          </select>
        </div>
      </div>

      {/* Main Content Area */}
      {activeTab === 'chat' && (
        <div className="flex-1 flex flex-col min-h-0 rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur-md overflow-hidden">
          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex gap-3 max-w-3xl ${m.sender === 'user' ? 'ml-auto flex-row-reverse' : ''}`}
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold ${
                    m.sender === 'user'
                      ? 'bg-gradient-to-tr from-violet-600 to-indigo-600 text-white'
                      : 'bg-slate-800 text-violet-400 border border-violet-500/30'
                  }`}
                >
                  {m.sender === 'user' ? 'ME' : <Bot className="w-4 h-4" />}
                </div>

                <div className={`space-y-1.5 ${m.sender === 'user' ? 'items-end' : ''}`}>
                  <div className="flex items-center space-x-2 text-[11px] text-slate-400">
                    <span className="font-medium text-slate-300">
                      {m.sender === 'user' ? 'You' : m.modelUsed || 'SUPER_AI'}
                    </span>
                    <span>•</span>
                    <span>{m.timestamp}</span>
                  </div>

                  <div
                    className={`p-4 rounded-2xl text-sm leading-relaxed ${
                      m.sender === 'user'
                        ? 'bg-violet-600 text-white rounded-tr-sm shadow-md'
                        : 'bg-slate-800/90 text-slate-200 rounded-tl-sm border border-white/5 shadow-sm'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{m.text}</div>
                  </div>

                  {m.sender === 'assistant' && (
                    <div className="flex items-center space-x-2 pt-1 text-slate-400 text-xs">
                      <button
                        onClick={() => handleCopy(m.id, m.text)}
                        className="p-1 hover:text-white rounded hover:bg-white/5 transition flex items-center gap-1"
                        title="Copy Response"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        {copiedId === m.id && <span className="text-[10px] text-emerald-400">Copied</span>}
                      </button>
                      <button className="p-1 hover:text-white rounded hover:bg-white/5 transition" title="Helpful">
                        <ThumbsUp className="w-3.5 h-3.5" />
                      </button>
                      <button className="p-1 hover:text-white rounded hover:bg-white/5 transition" title="Not Helpful">
                        <ThumbsDown className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isGenerating && (
              <div className="flex gap-3 max-w-xl">
                <div className="w-8 h-8 rounded-full bg-slate-800 text-violet-400 border border-violet-500/30 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 animate-spin" />
                </div>
                <div className="p-3.5 rounded-2xl bg-slate-800/80 border border-white/5 flex items-center space-x-2">
                  <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
                  <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse delay-150" />
                  <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse delay-300" />
                  <span className="text-xs text-slate-400 pl-2">Synthesizing multi-modal knowledge...</span>
                </div>
              </div>
            )}
          </div>

          {/* Quick Prompt Suggestions */}
          <div className="px-4 py-2 flex items-center space-x-2 overflow-x-auto text-xs text-slate-300 border-t border-white/5 bg-black/20">
            <span className="text-slate-500 shrink-0 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Suggested:
            </span>
            {[
              'Compare top Bangalore restaurants for dinner',
              'Draft an invoice remittance receipt in Tamil & English',
              'Write a high-performance React virtualized list component',
              'Summarize Indian Digital Personal Data Protection (DPDP) Act',
            ].map((s, idx) => (
              <button
                key={idx}
                onClick={() => setInputPrompt(s)}
                className="px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 border border-white/5 shrink-0 transition text-slate-300 hover:text-white"
              >
                {s}
              </button>
            ))}
          </div>

          {/* Message Composer */}
          <form
            onSubmit={handleSendMessage}
            className="p-4 border-t border-white/10 bg-slate-900/80 flex items-end space-x-2"
          >
            <div className="flex items-center space-x-1 pb-2 text-slate-400">
              <button
                type="button"
                className="p-2 hover:text-white hover:bg-white/5 rounded-lg transition"
                title="Attach Document or Image"
              >
                <Paperclip className="w-4 h-4" />
              </button>
              <button
                type="button"
                className="p-2 hover:text-white hover:bg-white/5 rounded-lg transition"
                title="Voice Input (Tamil/Hindi/English)"
              >
                <Mic className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 relative">
              <textarea
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder={t('ai.send_placeholder', preferences.language)}
                rows={2}
                className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500 resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={!inputPrompt.trim() || isGenerating}
              className="p-3 rounded-xl bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-40 disabled:hover:bg-violet-600 transition shadow-lg shrink-0 flex items-center justify-center"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}

      {/* Orchestration View */}
      {activeTab === 'orchestration' && (
        <div className="flex-1 p-6 rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-md overflow-y-auto space-y-6">
          <div className="max-w-3xl space-y-2">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-400" />
              Autonomous Cross-Module Task Orchestration
            </h2>
            <p className="text-sm text-slate-400">
              SUPER_AI coordinates sub-agents across Dining, UPI Payments, Calendar, and Messaging while maintaining human-in-the-loop authorization for consequential transactions.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-black/30 border border-white/10 flex flex-col md:flex-row items-center justify-between gap-4">
            <div>
              <span className="text-xs uppercase tracking-wider text-violet-400 font-semibold">Simulated Workflow</span>
              <p className="text-sm font-medium text-white">
                "Find dinner for 4 in Indiranagar, verify table availability, reserve, and notify the team chat."
              </p>
            </div>
            <button
              onClick={startDemoOrchestration}
              disabled={orchestratorRunning && orchestratorStep < 4}
              className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-medium text-sm transition shadow-md shrink-0 flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${orchestratorRunning && orchestratorStep < 4 ? 'animate-spin' : ''}`} />
              {orchestratorRunning && orchestratorStep < 4 ? 'Executing...' : 'Run Simulated Workflow'}
            </button>
          </div>

          {/* Stepper Timeline */}
          <div className="space-y-4 max-w-2xl">
            <div className={`p-4 rounded-xl border transition-all ${
              orchestratorStep >= 1 ? 'border-violet-500/40 bg-violet-950/20' : 'border-white/5 bg-slate-900/30 opacity-50'
            }`}>
              <div className="flex items-center space-x-3">
                {orchestratorStep > 1 ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                ) : orchestratorStep === 1 ? (
                  <RefreshCw className="w-5 h-5 text-violet-400 animate-spin" />
                ) : (
                  <div className="w-5 h-5 rounded-full border border-slate-600 flex items-center justify-center text-xs">1</div>
                )}
                <div>
                  <h4 className="text-sm font-semibold text-white">Step 1: Restaurant Discovery & Menu Aggregation</h4>
                  <p className="text-xs text-slate-400">Sub-agent queries Indiranagar food delivery & dining database.</p>
                </div>
              </div>
            </div>

            <div className={`p-4 rounded-xl border transition-all ${
              orchestratorStep >= 2 ? 'border-violet-500/40 bg-violet-950/20' : 'border-white/5 bg-slate-900/30 opacity-50'
            }`}>
              <div className="flex items-center space-x-3">
                {orchestratorStep > 2 ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                ) : orchestratorStep === 2 ? (
                  <RefreshCw className="w-5 h-5 text-violet-400 animate-spin" />
                ) : (
                  <div className="w-5 h-5 rounded-full border border-slate-600 flex items-center justify-center text-xs">2</div>
                )}
                <div>
                  <h4 className="text-sm font-semibold text-white">Step 2: Table Availability Check at Truffles Bistro</h4>
                  <p className="text-xs text-slate-400">Available slots: 7:30 PM, 8:15 PM for party of 4.</p>
                </div>
              </div>
            </div>

            <div className={`p-4 rounded-xl border transition-all ${
              orchestratorStep >= 3 ? 'border-amber-500/40 bg-amber-950/20' : 'border-white/5 bg-slate-900/30 opacity-50'
            }`}>
              <div className="flex items-center space-x-3">
                {orchestratorStep > 3 ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                ) : orchestratorStep === 3 ? (
                  <ShieldAlert className="w-5 h-5 text-amber-400" />
                ) : (
                  <div className="w-5 h-5 rounded-full border border-slate-600 flex items-center justify-center text-xs">3</div>
                )}
                <div className="flex-1">
                  <h4 className="text-sm font-semibold text-white flex items-center justify-between">
                    <span>Step 3: User Confirmation & Security Boundary</span>
                    {orchestratorStep === 3 && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        APPROVAL REQUIRED
                      </span>
                    )}
                  </h4>
                  <p className="text-xs text-slate-400">Consequential actions (booking deposit & external messages) require your explicit sign-off.</p>
                </div>
              </div>
            </div>

            <div className={`p-4 rounded-xl border transition-all ${
              orchestratorStep >= 4 ? 'border-emerald-500/40 bg-emerald-950/20' : 'border-white/5 bg-slate-900/30 opacity-50'
            }`}>
              <div className="flex items-center space-x-3">
                {orchestratorStep >= 4 ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                ) : (
                  <div className="w-5 h-5 rounded-full border border-slate-600 flex items-center justify-center text-xs">4</div>
                )}
                <div>
                  <h4 className="text-sm font-semibold text-white">Step 4: Calendar Invitation Dispatched & Chat Notified</h4>
                  <p className="text-xs text-slate-400">Simulated calendar event booked for 7:30 PM with map directions.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sovereign Memory View */}
      {activeTab === 'memory' && (
        <div className="flex-1 p-6 rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-md overflow-y-auto space-y-6">
          <div className="max-w-2xl space-y-2">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Database className="w-5 h-5 text-emerald-400" />
              Sovereign User Memory & Context Vault
            </h2>
            <p className="text-sm text-slate-400">
              You own your contextual memory. Memories are stored locally or in your encrypted private cloud, completely under your control.
            </p>
          </div>

          <div className="space-y-3 max-w-xl">
            {[
              { id: 'mem_1', title: 'Dietary Preference', desc: 'Strict vegetarian on Tuesdays and Thursdays. Prefers South Indian & Italian.' },
              { id: 'mem_2', title: 'Work Location', desc: 'Primary office at Indiranagar 100ft Road, Bengaluru.' },
              { id: 'mem_3', title: 'Tech Stack Preference', desc: 'Prefers React, TypeScript, Tailwind CSS, and serverless architectures.' },
            ].map((mem) => (
              <div key={mem.id} className="p-4 rounded-xl bg-slate-800/80 border border-white/5 flex items-start justify-between gap-4">
                <div>
                  <h4 className="text-sm font-semibold text-slate-200">{mem.title}</h4>
                  <p className="text-xs text-slate-400 mt-1">{mem.desc}</p>
                </div>
                <button className="text-xs text-red-400 hover:text-red-300 font-medium">Delete</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
