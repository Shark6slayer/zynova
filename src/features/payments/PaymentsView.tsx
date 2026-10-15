import React, { useState, useEffect, useCallback } from 'react';
import { 
  CreditCard, Send, QrCode, ArrowDownLeft, ArrowUpRight, 
  ShieldCheck, CheckCircle2, History, AlertCircle, RefreshCw,
  Building2, Plus, Smartphone, Zap, Droplet, Flame, Tv, Wifi, Car,
  ChevronRight, Lock, Check, Loader2, X, Eye, EyeOff, Receipt,
  Clock, ArrowRight
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { 
  apiClient,
  type BankAccountResponse,
  type RuPayCardResponse,
  type PaymentTransactionResponse,
  type BillerResponse,
  type BillDetailResponse,
  type SendPaymentPayload
} from '../../services/apiClient';

export const PaymentsView: React.FC = () => {
  const { user, isAuthenticated, openLoginModal } = useAuth();

  // Active Tab
  const [activeTab, setActiveTab] = useState<'home' | 'accounts' | 'bills' | 'history'>('home');

  // Linked Bank Accounts & RuPay Cards
  const [accounts, setAccounts] = useState<BankAccountResponse[]>([]);
  const [rupayCards, setRupayCards] = useState<RuPayCardResponse[]>([]);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);

  // Balance Check Status
  const [checkingBalanceId, setCheckingBalanceId] = useState<string | null>(null);

  // Transactions Ledger
  const [transactions, setTransactions] = useState<PaymentTransactionResponse[]>([]);
  const [isLoadingTxs, setIsLoadingTxs] = useState(false);
  const [selectedTx, setSelectedTx] = useState<PaymentTransactionResponse | null>(null);

  // Quick Send / UPI Transfer Form
  const [isSendModalOpen, setIsSendModalOpen] = useState(false);
  const [recipientType, setRecipientType] = useState<'upi_id' | 'phone' | 'merchant'>('upi_id');
  const [recipientInput, setRecipientInput] = useState('');
  const [amountInput, setAmountInput] = useState('');
  const [noteInput, setNoteInput] = useState('');
  const [selectedSourceId, setSelectedSourceId] = useState('');
  const [selectedSourceType, setSelectedSourceType] = useState<'bank_account' | 'rupay_credit_card'>('bank_account');
  const [isVerifyingVpa, setIsVerifyingVpa] = useState(false);
  const [verifiedRecipientName, setVerifiedRecipientName] = useState<string | null>(null);
  const [isExecutingPayment, setIsExecutingPayment] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [completedPayment, setCompletedPayment] = useState<PaymentTransactionResponse | null>(null);

  // Link Bank Account Modal
  const [isLinkBankOpen, setIsLinkBankOpen] = useState(false);
  const [newBankName, setNewBankName] = useState('HDFC Bank');
  const [newIfsc, setNewIfsc] = useState('HDFC0001234');
  const [newAccountNumber, setNewAccountNumber] = useState('');
  const [newAccountNickname, setNewAccountNickname] = useState('');
  const [isLinkingAccount, setIsLinkingAccount] = useState(false);

  // Link RuPay Card Modal
  const [isLinkRuPayOpen, setIsLinkRuPayOpen] = useState(false);
  const [rupayBank, setRupayBank] = useState('ICICI Bank');
  const [rupayLast4, setRupayLast4] = useState('');
  const [rupayExpiryMonth, setRupayExpiryMonth] = useState('12');
  const [rupayExpiryYear, setRupayExpiryYear] = useState('2028');
  const [rupayNickname, setRupayNickname] = useState('');
  const [isLinkingRuPay, setIsLinkingRuPay] = useState(false);

  // BBPS Bills & Recharges
  const [billers, setBillers] = useState<BillerResponse[]>([]);
  const [selectedBillerCategory, setSelectedBillerCategory] = useState<string>('electricity');
  const [selectedBiller, setSelectedBiller] = useState<BillerResponse | null>(null);
  const [billerConsumerId, setBillerConsumerId] = useState('');
  const [isFetchingBill, setIsFetchingBill] = useState(false);
  const [fetchedBill, setFetchedBill] = useState<BillDetailResponse | null>(null);
  const [billError, setBillError] = useState<string | null>(null);

  // Initial Data Fetching
  const fetchData = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingAccounts(true);
    setIsLoadingTxs(true);
    try {
      const [accs, cards, txList, billerList] = await Promise.all([
        apiClient.listBankAccounts(),
        apiClient.listRuPayCards(),
        apiClient.listPaymentTransactions({ limit: 30 }),
        apiClient.listBillers()
      ]);
      setAccounts(accs);
      setRupayCards(cards);
      setTransactions(txList);
      setBillers(billerList);

      if (accs.length > 0 && !selectedSourceId) {
        setSelectedSourceId(accs[0].id);
        setSelectedSourceType('bank_account');
      }
    } catch (e) {
      console.warn('Error fetching payment data:', e);
    } finally {
      setIsLoadingAccounts(false);
      setIsLoadingTxs(false);
    }
  }, [isAuthenticated, selectedSourceId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Balance Check
  const handleCheckBalance = async (accId: string) => {
    setCheckingBalanceId(accId);
    try {
      const updated = await apiClient.checkAccountBalance(accId);
      setAccounts(prev => prev.map(a => a.id === accId ? updated : a));
    } catch (err: any) {
      alert(err.message || 'Balance enquiry failed. Please retry.');
    } finally {
      setCheckingBalanceId(null);
    }
  };

  // VPA verification debounce
  useEffect(() => {
    if (!recipientInput.includes('@') && recipientInput.length < 10) {
      setVerifiedRecipientName(null);
      return;
    }
    const timer = setTimeout(async () => {
      setIsVerifyingVpa(true);
      try {
        const res = await apiClient.verifyVpa(recipientInput);
        if (res.is_valid) {
          setVerifiedRecipientName(res.recipient_name);
        }
      } catch {
        setVerifiedRecipientName(null);
      } finally {
        setIsVerifyingVpa(false);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [recipientInput]);

  // Send Payment Submit
  const handleExecutePayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }

    const amtInr = parseFloat(amountInput);
    if (isNaN(amtInr) || amtInr <= 0) {
      setSendError('Please enter a valid transfer amount.');
      return;
    }
    const amountPaise = Math.round(amtInr * 100);

    setIsExecutingPayment(true);
    setSendError(null);

    const idempotencyKey = `pay_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

    const payload: SendPaymentPayload = {
      recipient_type: recipientType,
      recipient_identifier: recipientInput.trim(),
      recipient_name: verifiedRecipientName || undefined,
      amount_paise: amountPaise,
      source_type: selectedSourceType,
      source_id: selectedSourceId,
      note: noteInput.trim() || undefined,
      idempotency_key: idempotencyKey
    };

    try {
      const tx = await apiClient.sendPayment(payload);
      setCompletedPayment(tx);
      setTransactions(prev => [tx, ...prev]);
      setIsSendModalOpen(false);
      setRecipientInput('');
      setAmountInput('');
      setNoteInput('');
      setVerifiedRecipientName(null);
    } catch (err: any) {
      setSendError(err.message || 'Payment execution failed');
    } finally {
      setIsExecutingPayment(false);
    }
  };

  // Link Bank Submit
  const handleLinkBankSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAccountNumber || newAccountNumber.length < 6) {
      alert('Please enter a valid account number');
      return;
    }
    setIsLinkingAccount(true);
    try {
      const newAcc = await apiClient.linkBankAccount({
        bank_name: newBankName,
        ifsc_code: newIfsc,
        account_number: newAccountNumber,
        nickname: newAccountNickname || undefined
      });
      setAccounts(prev => [newAcc, ...prev]);
      setIsLinkBankOpen(false);
      setNewAccountNumber('');
      setNewAccountNickname('');
    } catch (err: any) {
      alert(err.message || 'Account linking failed');
    } finally {
      setIsLinkingAccount(false);
    }
  };

  // Link RuPay Submit
  const handleLinkRuPaySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (rupayLast4.length !== 4) {
      alert('Enter valid 4 digits');
      return;
    }
    setIsLinkingRuPay(true);
    try {
      const newCard = await apiClient.linkRuPayCard({
        issuing_bank: rupayBank,
        last_four_digits: rupayLast4,
        expiry_month: parseInt(rupayExpiryMonth, 10),
        expiry_year: parseInt(rupayExpiryYear, 10),
        nickname: rupayNickname || undefined
      });
      setRupayCards(prev => [newCard, ...prev]);
      setIsLinkRuPayOpen(false);
      setRupayLast4('');
      setRupayNickname('');
    } catch (err: any) {
      alert(err.message || 'RuPay card linking failed');
    } finally {
      setIsLinkingRuPay(false);
    }
  };

  // Fetch BBPS Bill Submit
  const handleFetchBillSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBiller || !billerConsumerId.trim()) return;

    setIsFetchingBill(true);
    setBillError(null);
    setFetchedBill(null);

    try {
      const detail = await apiClient.fetchBill({
        category: selectedBiller.category,
        biller_id: selectedBiller.id,
        customer_identifier: billerConsumerId.trim()
      });
      setFetchedBill(detail);
    } catch (err: any) {
      setBillError(err.message || 'Could not fetch bill from provider');
    } finally {
      setIsFetchingBill(false);
    }
  };

  const billerCategories = [
    { id: 'mobile_prepaid', label: 'Mobile Prepaid', icon: Smartphone },
    { id: 'electricity', label: 'Electricity', icon: Zap },
    { id: 'water', label: 'Water', icon: Droplet },
    { id: 'gas', label: 'Piped Gas / LPG', icon: Flame },
    { id: 'dth', label: 'DTH TV', icon: Tv },
    { id: 'broadband', label: 'Broadband', icon: Wifi },
    { id: 'fastag', label: 'FASTag', icon: Car },
  ];

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto w-full p-8 rounded-3xl bg-slate-900/60 border border-white/10 text-center space-y-4">
        <CreditCard className="w-12 h-12 text-cyan-400 mx-auto" />
        <h2 className="text-xl font-bold text-white">Unified Indian Payments & Banking</h2>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          Sign in to link bank accounts, check verified balances, scan QR codes, pay contacts, and recharge utility bills.
        </p>
        <button
          onClick={openLoginModal}
          className="px-6 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs transition"
        >
          Sign In to Access Payments
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto w-full pb-16 px-2 sm:px-4">
      {/* GPay Inspired Hero Card */}
      <div className="p-6 md:p-8 rounded-3xl bg-gradient-to-br from-cyan-950/50 via-slate-900/90 to-blue-950/40 border border-cyan-500/20 backdrop-blur-xl shadow-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center space-x-2 text-cyan-400 text-xs font-semibold uppercase tracking-wider">
            <CreditCard className="w-4 h-4" />
            <span>SUPER_AI UPI & Banking Platform</span>
          </div>
          <span className="text-xs text-slate-400">NPCI Certified Interface • Connected Bank Accounts: {accounts.length}</span>
          <div className="text-2xl md:text-3xl font-extrabold text-white tracking-tight flex items-baseline gap-2">
            <span>Fast & Sovereign Payments</span>
          </div>
          <p className="text-xs text-slate-400 flex items-center gap-1.5 pt-1">
            <ShieldCheck className="w-4 h-4 text-emerald-400" /> Device Binding • RuPay Credit on UPI • BBPS Authorized
          </p>
        </div>

        {/* Quick Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button 
            onClick={() => {
              setRecipientType('merchant');
              setIsSendModalOpen(true);
            }}
            className="px-4 py-2.5 rounded-2xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition shadow-lg shadow-cyan-600/30 flex items-center gap-2"
          >
            <QrCode className="w-4 h-4" />
            <span>Scan Any QR</span>
          </button>

          <button 
            onClick={() => {
              setRecipientType('upi_id');
              setIsSendModalOpen(true);
            }}
            className="px-4 py-2.5 rounded-2xl bg-white/10 hover:bg-white/15 text-white text-xs font-bold border border-white/15 transition flex items-center gap-2"
          >
            <Send className="w-4 h-4 text-cyan-400" />
            <span>Pay UPI / Phone</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center space-x-1 p-1.5 rounded-2xl bg-slate-900/60 border border-white/5 overflow-x-auto text-xs">
        <button
          onClick={() => setActiveTab('home')}
          className={`px-4 py-2 rounded-xl font-semibold transition ${
            activeTab === 'home' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white'
          }`}
        >
          Overview & Quick Pay
        </button>
        <button
          onClick={() => setActiveTab('accounts')}
          className={`px-4 py-2 rounded-xl font-semibold transition flex items-center gap-1.5 ${
            activeTab === 'accounts' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white'
          }`}
        >
          <Building2 className="w-3.5 h-3.5" />
          <span>Bank Accounts & RuPay ({accounts.length + rupayCards.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('bills')}
          className={`px-4 py-2 rounded-xl font-semibold transition flex items-center gap-1.5 ${
            activeTab === 'bills' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white'
          }`}
        >
          <Zap className="w-3.5 h-3.5" />
          <span>Bills & Recharges (BBPS)</span>
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 rounded-xl font-semibold transition flex items-center gap-1.5 ${
            activeTab === 'history' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white'
          }`}
        >
          <History className="w-3.5 h-3.5" />
          <span>Passbook Statements</span>
        </button>
      </div>

      {/* TAB 1: OVERVIEW & GPAY-STYLE SHORTCUTS */}
      {activeTab === 'home' && (
        <div className="space-y-6">
          {/* People & Merchants Circular Grid */}
          <div className="p-5 rounded-3xl bg-slate-900/40 border border-white/5 space-y-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Frequent Contacts & Merchants</h3>
            <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-3 text-center">
              {[
                { name: 'Rahul Sharma', handle: 'rahul@oksbi', avatar: 'R' },
                { name: 'Priya Patel', handle: 'priya@icici', avatar: 'P' },
                { name: 'A2B Foods', handle: 'a2b.merchant@hdfc', avatar: 'A' },
                { name: 'Swiggy', handle: 'swiggy@kotak', avatar: 'S' },
                { name: 'Aarav', handle: '9876543210', avatar: 'A' },
                { name: 'Indiranagar Mart', handle: 'indiranagar.store@paytm', avatar: 'I' },
              ].map((c, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setRecipientInput(c.handle);
                    setVerifiedRecipientName(c.name);
                    setIsSendModalOpen(true);
                  }}
                  className="group flex flex-col items-center space-y-1.5 focus:outline-none"
                >
                  <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-md group-hover:scale-105 transition">
                    {c.avatar}
                  </div>
                  <span className="text-[11px] font-semibold text-slate-300 truncate w-16 group-hover:text-cyan-400">
                    {c.name}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Quick Utility Bill Grid */}
          <div className="p-5 rounded-3xl bg-slate-900/40 border border-white/5 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">BBPS Recharges & Bill Pay</h3>
              <button 
                onClick={() => setActiveTab('bills')}
                className="text-xs text-cyan-400 hover:underline flex items-center gap-1"
              >
                <span>View all billers</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-3">
              {billerCategories.map(cat => {
                const Icon = cat.icon;
                return (
                  <button
                    key={cat.id}
                    onClick={() => {
                      setSelectedBillerCategory(cat.id);
                      setActiveTab('bills');
                    }}
                    className="p-3.5 rounded-2xl bg-slate-800/40 hover:bg-slate-800/80 border border-white/5 hover:border-cyan-500/30 transition flex flex-col items-center space-y-2 text-center group"
                  >
                    <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-400 group-hover:bg-cyan-500/20 transition">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[11px] font-semibold text-slate-300 group-hover:text-white">
                      {cat.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Bank Accounts & RuPay Cards Preview */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Primary Bank Card */}
            <div className="p-5 rounded-3xl bg-slate-900/40 border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                  <Building2 className="w-4 h-4 text-cyan-400" />
                  <span>Primary Bank Account</span>
                </span>
                <button 
                  onClick={() => setIsLinkBankOpen(true)}
                  className="text-[11px] text-cyan-400 hover:underline flex items-center gap-1"
                >
                  <Plus className="w-3 h-3" />
                  <span>Add Bank</span>
                </button>
              </div>

              {accounts.length === 0 ? (
                <div className="p-6 rounded-2xl bg-slate-800/30 text-center space-y-2 border border-white/5">
                  <p className="text-xs text-slate-400">No bank accounts linked yet.</p>
                  <button 
                    onClick={() => setIsLinkBankOpen(true)}
                    className="px-3 py-1.5 rounded-xl bg-cyan-600 text-white text-xs font-semibold"
                  >
                    Link Bank Account
                  </button>
                </div>
              ) : (
                <div className="p-4 rounded-2xl bg-slate-800/50 border border-white/5 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-white">{accounts[0].bank_name}</h4>
                      <p className="text-xs text-slate-400 font-mono">{accounts[0].masked_account_number}</p>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                      DEFAULT
                    </span>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-white/5">
                    <div>
                      <span className="text-[10px] text-slate-500">Verified Balance</span>
                      <p className="text-sm font-extrabold text-white">
                        {accounts[0].balance_inr !== null && accounts[0].balance_inr !== undefined
                          ? `₹${accounts[0].balance_inr.toLocaleString('en-IN')}`
                          : '••••••'}
                      </p>
                    </div>
                    <button
                      onClick={() => handleCheckBalance(accounts[0].id)}
                      disabled={checkingBalanceId === accounts[0].id}
                      className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-cyan-400 text-xs font-semibold border border-white/10 transition flex items-center gap-1"
                    >
                      {checkingBalanceId === accounts[0].id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                      <span>Check Balance</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* RuPay on UPI Card */}
            <div className="p-5 rounded-3xl bg-slate-900/40 border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                  <CreditCard className="w-4 h-4 text-emerald-400" />
                  <span>RuPay Credit Card on UPI</span>
                </span>
                <button 
                  onClick={() => setIsLinkRuPayOpen(true)}
                  className="text-[11px] text-cyan-400 hover:underline flex items-center gap-1"
                >
                  <Plus className="w-3 h-3" />
                  <span>Link RuPay</span>
                </button>
              </div>

              {rupayCards.length === 0 ? (
                <div className="p-6 rounded-2xl bg-slate-800/30 text-center space-y-2 border border-white/5">
                  <p className="text-xs text-slate-400">No RuPay credit cards linked for UPI merchant payments.</p>
                  <button 
                    onClick={() => setIsLinkRuPayOpen(true)}
                    className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-200 text-xs font-semibold border border-white/10"
                  >
                    Link RuPay Card
                  </button>
                </div>
              ) : (
                <div className="p-4 rounded-2xl bg-gradient-to-r from-emerald-950/40 to-slate-900 border border-emerald-500/20 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-white">{rupayCards[0].issuing_bank}</h4>
                      <p className="text-xs text-slate-400 font-mono">•••• {rupayCards[0].last_four_digits}</p>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                      RUPAY UPI
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 pt-1">
                    Permitted strictly for authorized merchant QR scans and online store checkouts.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: BANK ACCOUNTS & RUPAY MANAGEMENT */}
      {activeTab === 'accounts' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Building2 className="w-5 h-5 text-cyan-400" />
              <span>Linked Bank Accounts & RuPay Cards</span>
            </h3>
            <div className="flex gap-2">
              <button
                onClick={() => setIsLinkBankOpen(true)}
                className="px-3.5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Bank Account</span>
              </button>
              <button
                onClick={() => setIsLinkRuPayOpen(true)}
                className="px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-200 text-xs font-bold border border-white/10 transition flex items-center gap-1.5"
              >
                <CreditCard className="w-3.5 h-3.5 text-emerald-400" />
                <span>Link RuPay</span>
              </button>
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Bank Accounts</h4>
            {accounts.map(acc => (
              <div 
                key={acc.id}
                className="p-4 rounded-2xl bg-slate-900/50 border border-white/5 hover:border-white/15 transition flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-white">{acc.bank_name}</span>
                    {acc.is_default && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                        DEFAULT
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 font-mono">
                    Account: {acc.masked_account_number} • IFSC: {acc.ifsc_code}
                  </p>
                  {acc.last_balance_enquiry && (
                    <p className="text-[10px] text-slate-500">
                      Balance enquired: {new Date(acc.last_balance_enquiry).toLocaleTimeString()}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-left sm:text-right">
                    <span className="text-[10px] text-slate-500">Available Balance</span>
                    <p className="text-base font-bold text-white">
                      {acc.balance_inr !== null && acc.balance_inr !== undefined
                        ? `₹${acc.balance_inr.toLocaleString('en-IN')}`
                        : '••••••'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleCheckBalance(acc.id)}
                    disabled={checkingBalanceId === acc.id}
                    className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-cyan-400 border border-white/10 transition"
                    title="Enquire verified balance"
                  >
                    {checkingBalanceId === acc.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="space-y-3 pt-2">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">RuPay Credit Cards</h4>
            {rupayCards.map(c => (
              <div 
                key={c.id}
                className="p-4 rounded-2xl bg-slate-900/50 border border-white/5 flex items-center justify-between"
              >
                <div>
                  <h5 className="text-sm font-bold text-white">{c.issuing_bank} RuPay Credit</h5>
                  <p className="text-xs text-slate-400 font-mono">•••• {c.last_four_digits}</p>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  CREDIT ON UPI
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: BBPS BILL PAYMENTS & RECHARGES */}
      {activeTab === 'bills' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Zap className="w-5 h-5 text-cyan-400" />
              <span>Bharat BillPay (BBPS) Portal</span>
            </h3>
            <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
              <ShieldCheck className="w-4 h-4" /> Provider Connected
            </span>
          </div>

          {/* Biller Categories Pills */}
          <div className="flex items-center space-x-1 overflow-x-auto text-xs py-1">
            {billerCategories.map(cat => (
              <button
                key={cat.id}
                onClick={() => {
                  setSelectedBillerCategory(cat.id);
                  setSelectedBiller(null);
                  setFetchedBill(null);
                }}
                className={`px-3 py-1.5 rounded-xl font-medium capitalize transition whitespace-nowrap ${
                  selectedBillerCategory === cat.id
                    ? 'bg-cyan-600 text-white shadow'
                    : 'bg-white/5 text-slate-300 hover:bg-white/10'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Billers list in category */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {billers
              .filter(b => b.category === selectedBillerCategory)
              .map(b => (
                <div
                  key={b.id}
                  onClick={() => {
                    setSelectedBiller(b);
                    setFetchedBill(null);
                  }}
                  className={`p-4 rounded-2xl border cursor-pointer transition ${
                    selectedBiller?.id === b.id
                      ? 'border-cyan-500 bg-cyan-950/20 shadow'
                      : 'border-white/5 bg-slate-900/40 hover:border-white/15'
                  }`}
                >
                  <h5 className="text-xs font-bold text-white">{b.name}</h5>
                  <p className="text-[10px] text-slate-400 font-mono mt-0.5">{b.sample_identifier_label}</p>
                </div>
              ))}
          </div>

          {/* Fetch Bill Form */}
          {selectedBiller && (
            <form onSubmit={handleFetchBillSubmit} className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 space-y-4 max-w-lg">
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                <span>Fetch Bill: {selectedBiller.name}</span>
              </h4>

              <div>
                <label className="text-xs text-slate-300">{selectedBiller.sample_identifier_label}</label>
                <input
                  type="text"
                  placeholder={`Enter ${selectedBiller.sample_identifier_label}`}
                  value={billerConsumerId}
                  onChange={e => setBillerConsumerId(e.target.value)}
                  required
                  className="w-full mt-1.5 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white"
                />
              </div>

              {billError && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs">
                  {billError}
                </div>
              )}

              <button
                type="submit"
                disabled={isFetchingBill || !billerConsumerId.trim()}
                className="w-full py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-white font-bold text-xs transition flex items-center justify-center gap-2"
              >
                {isFetchingBill ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                <span>Fetch Bill Details</span>
              </button>

              {/* Fetched Bill Details Card */}
              {fetchedBill && (
                <div className="p-4 rounded-2xl bg-slate-800/80 border border-cyan-500/30 space-y-3 pt-4">
                  <div className="flex justify-between items-start border-b border-white/5 pb-2">
                    <div>
                      <span className="text-[10px] text-slate-400 font-mono">Bill #{fetchedBill.bill_number}</span>
                      <h5 className="text-sm font-bold text-white">{fetchedBill.customer_name}</h5>
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] text-slate-400">Due: {fetchedBill.due_date}</span>
                      <p className="text-base font-extrabold text-cyan-400">₹{fetchedBill.amount_inr.toLocaleString('en-IN')}</p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      setRecipientType('merchant');
                      setRecipientInput(`${fetchedBill.biller_id}@bbps`);
                      setVerifiedRecipientName(fetchedBill.biller_name);
                      setAmountInput(fetchedBill.amount_inr.toString());
                      setNoteInput(`Bill Payment: ${fetchedBill.bill_number}`);
                      setIsSendModalOpen(true);
                    }}
                    className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition shadow-md flex items-center justify-center gap-1.5"
                  >
                    <Check className="w-4 h-4" />
                    <span>Confirm & Pay Bill • ₹{fetchedBill.amount_inr.toLocaleString('en-IN')}</span>
                  </button>
                </div>
              )}
            </form>
          )}
        </div>
      )}

      {/* TAB 4: PASSBOOK STATEMENTS */}
      {activeTab === 'history' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <History className="w-5 h-5 text-cyan-400" />
              <span>UPI Passbook & Statements</span>
            </h3>
            <span className="text-xs text-slate-400 font-mono">Real-time ledger</span>
          </div>

          {isLoadingTxs ? (
            <div className="py-20 text-center space-y-3">
              <Loader2 className="w-8 h-8 text-cyan-500 animate-spin mx-auto" />
              <p className="text-xs text-slate-400">Loading verified transactions...</p>
            </div>
          ) : transactions.length === 0 ? (
            <div className="p-12 rounded-3xl border border-white/5 bg-slate-900/30 text-center space-y-2">
              <Receipt className="w-10 h-10 text-slate-600 mx-auto" />
              <p className="text-sm font-semibold text-slate-300">No payment transactions yet</p>
              <p className="text-xs text-slate-500">Your completed UPI transfers, QR scans, and bill payments will appear here.</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {transactions.map(tx => (
                <div
                  key={tx.id}
                  onClick={() => setSelectedTx(tx)}
                  className="p-4 rounded-2xl bg-slate-900/40 border border-white/5 hover:border-cyan-500/30 transition flex items-center justify-between cursor-pointer"
                >
                  <div className="flex items-center space-x-3.5 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center font-bold text-xs shrink-0 text-cyan-400">
                      <ArrowUpRight className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <h5 className="font-semibold text-xs text-white truncate">{tx.recipient_name}</h5>
                      <p className="text-[11px] text-slate-400 font-mono">
                        {new Date(tx.created_at).toLocaleDateString()} • {tx.recipient_identifier}
                      </p>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-sm font-bold text-white">-₹{tx.amount_inr.toLocaleString('en-IN')}</span>
                    <div className="flex items-center gap-1 justify-end text-[10px]">
                      <span className={`font-bold uppercase ${tx.status === 'success' ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {tx.status}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* QUICK SEND MODAL */}
      {isSendModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-white/10 rounded-3xl max-w-md w-full p-6 space-y-5 animate-scaleUp">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Send className="w-4 h-4 text-cyan-400" />
                <span>Send Money via UPI</span>
              </h3>
              <button 
                onClick={() => setIsSendModalOpen(false)}
                className="p-1.5 rounded-full bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleExecutePayment} className="space-y-4">
              {/* Recipient Input */}
              <div>
                <label className="text-[11px] font-semibold text-slate-300">Recipient UPI ID, Mobile, or Merchant VPA</label>
                <input
                  type="text"
                  placeholder="e.g. rahul@oksbi, 9876543210"
                  value={recipientInput}
                  onChange={e => setRecipientInput(e.target.value)}
                  required
                  className="w-full mt-1.5 px-3 py-2.5 bg-slate-800 border border-white/10 rounded-xl text-xs text-white"
                />
                {isVerifyingVpa && (
                  <p className="text-[10px] text-cyan-400 flex items-center gap-1 mt-1">
                    <Loader2 className="w-3 h-3 animate-spin" /> Verifying VPA with NPCI...
                  </p>
                )}
                {verifiedRecipientName && (
                  <p className="text-[10px] text-emerald-400 flex items-center gap-1 mt-1 font-semibold">
                    <CheckCircle2 className="w-3 h-3" /> Verified Name: {verifiedRecipientName}
                  </p>
                )}
              </div>

              {/* Amount Input */}
              <div>
                <label className="text-[11px] font-semibold text-slate-300">Amount (INR ₹)</label>
                <div className="relative mt-1.5">
                  <span className="absolute left-3.5 top-2.5 text-slate-400 text-sm font-bold">₹</span>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={amountInput}
                    onChange={e => setAmountInput(e.target.value)}
                    required
                    className="w-full pl-8 pr-3 py-2.5 bg-slate-800 border border-white/10 rounded-xl text-sm font-bold text-white"
                  />
                </div>
              </div>

              {/* Debit Source Selector */}
              <div>
                <label className="text-[11px] font-semibold text-slate-300">Pay From (Debit Source):</label>
                <select
                  value={`${selectedSourceType}:${selectedSourceId}`}
                  onChange={e => {
                    const [sType, sId] = e.target.value.split(':');
                    setSelectedSourceType(sType as any);
                    setSelectedSourceId(sId);
                  }}
                  className="w-full mt-1.5 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white focus:outline-none"
                >
                  {accounts.map(a => (
                    <option key={a.id} value={`bank_account:${a.id}`}>
                      {a.bank_name} ({a.masked_account_number}) - Bank Account
                    </option>
                  ))}
                  {rupayCards.map(c => (
                    <option key={c.id} value={`rupay_credit_card:${c.id}`}>
                      {c.issuing_bank} (•••• {c.last_four_digits}) - RuPay on UPI
                    </option>
                  ))}
                </select>
              </div>

              {/* Optional Note */}
              <div>
                <label className="text-[11px] font-semibold text-slate-300">Add a note (optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Rent, Groceries, Lunch"
                  value={noteInput}
                  onChange={e => setNoteInput(e.target.value)}
                  className="w-full mt-1 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white"
                />
              </div>

              {sendError && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs">
                  {sendError}
                </div>
              )}

              <button
                type="submit"
                disabled={isExecutingPayment || !recipientInput.trim() || !amountInput.trim()}
                className="w-full py-3 rounded-2xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-white font-bold text-xs transition shadow-lg shadow-cyan-600/30 flex items-center justify-center gap-2"
              >
                {isExecutingPayment ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Processing UPI Payment...</span>
                  </>
                ) : (
                  <>
                    <Lock className="w-4 h-4" />
                    <span>Pay ₹{parseFloat(amountInput || '0').toLocaleString('en-IN')} Securely</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* LINK BANK MODAL */}
      {isLinkBankOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={handleLinkBankSubmit} className="bg-slate-900 border border-white/10 rounded-3xl max-w-md w-full p-6 space-y-4 animate-scaleUp">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Building2 className="w-4 h-4 text-cyan-400" />
                <span>Link Bank Account</span>
              </h3>
              <button 
                type="button"
                onClick={() => setIsLinkBankOpen(false)}
                className="p-1.5 rounded-full bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="text-xs text-slate-300">Bank Name</label>
              <select
                value={newBankName}
                onChange={e => setNewBankName(e.target.value)}
                className="w-full mt-1 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white"
              >
                <option value="State Bank of India">State Bank of India</option>
                <option value="HDFC Bank">HDFC Bank</option>
                <option value="ICICI Bank">ICICI Bank</option>
                <option value="Axis Bank">Axis Bank</option>
                <option value="Kotak Mahindra Bank">Kotak Mahindra Bank</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-slate-300">IFSC Code (11 digits)</label>
              <input
                type="text"
                value={newIfsc}
                onChange={e => setNewIfsc(e.target.value.toUpperCase())}
                required
                className="w-full mt-1 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white font-mono"
              />
            </div>

            <div>
              <label className="text-xs text-slate-300">Account Number</label>
              <input
                type="password"
                placeholder="Enter bank account number"
                value={newAccountNumber}
                onChange={e => setNewAccountNumber(e.target.value)}
                required
                className="w-full mt-1 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white font-mono"
              />
            </div>

            <div>
              <label className="text-xs text-slate-300">Nickname (optional)</label>
              <input
                type="text"
                placeholder="e.g. Salary, Business"
                value={newAccountNickname}
                onChange={e => setNewAccountNickname(e.target.value)}
                className="w-full mt-1 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white"
              />
            </div>

            <button
              type="submit"
              disabled={isLinkingAccount}
              className="w-full py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs transition shadow-md"
            >
              {isLinkingAccount ? 'Linking Account...' : 'Confirm & Link Account'}
            </button>
          </form>
        </div>
      )}

      {/* LINK RUPAY MODAL */}
      {isLinkRuPayOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={handleLinkRuPaySubmit} className="bg-slate-900 border border-white/10 rounded-3xl max-w-md w-full p-6 space-y-4 animate-scaleUp">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-emerald-400" />
                <span>Link RuPay Credit Card</span>
              </h3>
              <button 
                type="button"
                onClick={() => setIsLinkRuPayOpen(false)}
                className="p-1.5 rounded-full bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="text-xs text-slate-300">Issuing Bank</label>
              <input
                type="text"
                value={rupayBank}
                onChange={e => setRupayBank(e.target.value)}
                required
                className="w-full mt-1 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white"
              />
            </div>

            <div>
              <label className="text-xs text-slate-300">Last 4 Digits of RuPay Card</label>
              <input
                type="text"
                maxLength={4}
                placeholder="•••• 1234"
                value={rupayLast4}
                onChange={e => setRupayLast4(e.target.value)}
                required
                className="w-full mt-1 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white font-mono"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-slate-300">Expiry Month</label>
                <input
                  type="number"
                  min="1"
                  max="12"
                  value={rupayExpiryMonth}
                  onChange={e => setRupayExpiryMonth(e.target.value)}
                  className="w-full mt-1 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white"
                />
              </div>
              <div>
                <label className="text-xs text-slate-300">Expiry Year</label>
                <input
                  type="number"
                  min="2024"
                  max="2040"
                  value={rupayExpiryYear}
                  onChange={e => setRupayExpiryYear(e.target.value)}
                  className="w-full mt-1 px-3 py-2 bg-slate-800 border border-white/10 rounded-xl text-xs text-white"
                />
              </div>
            </div>

            <p className="text-[10px] text-slate-400">
              *Full card numbers, CVVs, and ATM PINs are NEVER stored. Used exclusively for eligible UPI merchant payments.
            </p>

            <button
              type="submit"
              disabled={isLinkingRuPay}
              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition shadow-md"
            >
              {isLinkingRuPay ? 'Linking Card...' : 'Link RuPay on UPI'}
            </button>
          </form>
        </div>
      )}

      {/* PAYMENT RECEIPT MODAL */}
      {(completedPayment || selectedTx) && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-emerald-500/30 rounded-3xl max-w-md w-full p-6 space-y-4 text-center animate-scaleUp">
            <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto border border-emerald-500/30">
              <CheckCircle2 className="w-6 h-6" />
            </div>

            <div>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider">Payment Receipt</span>
              <h3 className="text-2xl font-black text-white mt-0.5">
                ₹{(completedPayment || selectedTx)!.amount_inr.toLocaleString('en-IN')}
              </h3>
              <p className="text-xs text-emerald-400 font-semibold mt-1">
                Paid to {(completedPayment || selectedTx)!.recipient_name}
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-800/60 border border-white/5 text-left text-xs space-y-1.5 font-mono">
              <div className="flex justify-between">
                <span className="text-slate-400">NPCI Ref (RRN):</span>
                <span className="text-white font-bold">{(completedPayment || selectedTx)!.npci_ref || 'PENDING'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Txn Reference:</span>
                <span className="text-white truncate max-w-[200px]">{(completedPayment || selectedTx)!.transaction_ref}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Debited From:</span>
                <span className="text-white">{(completedPayment || selectedTx)!.source_title}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Timestamp:</span>
                <span className="text-white">{new Date((completedPayment || selectedTx)!.created_at).toLocaleString()}</span>
              </div>
            </div>

            <button
              onClick={() => {
                setCompletedPayment(null);
                setSelectedTx(null);
              }}
              className="w-full py-2.5 rounded-xl bg-white/10 hover:bg-white/15 text-white font-bold text-xs transition"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
