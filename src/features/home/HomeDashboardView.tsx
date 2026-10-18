import React, { useState, useEffect } from 'react';
import { 
  Sparkles, Search, MessageSquare, Utensils, ShoppingBag, 
  CreditCard, Cloud, ArrowUpRight, CheckCircle2, Clock, 
  ChevronRight, ChevronDown, TrendingUp, Bell, Calendar, Bot, Share2, Video, Loader2, MapPin
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { t } from '../../i18n';
import { apiClient, type RestaurantResponse, type PaymentTransactionResponse } from '../../services/apiClient';

interface WeatherState {
  status: 'idle' | 'loading' | 'success' | 'permission_denied' | 'unavailable';
  temp?: number;
  condition?: string;
  locationName?: string;
}

export const CITIES_FALLBACK = [
  { name: 'Bengaluru', lat: 12.9716, lon: 77.5946 },
  { name: 'Mumbai', lat: 19.0760, lon: 72.8777 },
  { name: 'Delhi', lat: 28.6139, lon: 77.2090 },
  { name: 'Chennai', lat: 13.0827, lon: 80.2707 },
  { name: 'Hyderabad', lat: 17.3850, lon: 78.4867 },
  { name: 'Kolkata', lat: 22.5726, lon: 88.3639 },
  { name: 'Pune', lat: 18.5204, lon: 73.8567 },
];

export const HomeDashboardView: React.FC = () => {
  const { preferences, activeTheme, setActiveModule } = useApp();
  const { user, isAuthenticated, openLoginModal } = useAuth();
  const [quickInput, setQuickInput] = useState('');

  // Live Backend Data
  const [restaurants, setRestaurants] = useState<RestaurantResponse[]>([]);
  const [isLoadingRestaurants, setIsLoadingRestaurants] = useState(false);
  const [transactions, setTransactions] = useState<PaymentTransactionResponse[]>([]);
  const [isLoadingTransactions, setIsLoadingTransactions] = useState(false);

  // Weather state (live with honest empty/error states)
  const [weather, setWeather] = useState<WeatherState>({ status: 'loading' });

  // Sovereign Cloud local storage size
  const [cloudFileCount, setCloudFileCount] = useState<number>(0);

  // User-scoped isolated tasks
  const [tasks, setTasks] = useState<Array<{ id: string; title: string; completed: boolean; dueDate?: string }>>([]);

  // Dynamic Time-of-Day Greeting Key
  const getGreetingKey = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return 'home.greeting_morning';
    if (hour >= 12 && hour < 17) return 'home.greeting_afternoon';
    return 'home.greeting_evening';
  };

  useEffect(() => {
    let isMounted = true;

    // Load actual local vault file count (user-isolated)
    const fileStorageKey = user ? `super_ai_local_files_${user.id}` : 'super_ai_local_files_guest';
    try {
      const savedFiles = localStorage.getItem(fileStorageKey);
      if (savedFiles) {
        const parsed = JSON.parse(savedFiles);
        if (Array.isArray(parsed) && isMounted) {
          setCloudFileCount(parsed.length);
        }
      } else if (isMounted) {
        setCloudFileCount(0);
      }
    } catch {
      if (isMounted) setCloudFileCount(0);
    }

    // Load actual user tasks
    const taskStorageKey = user ? `super_ai_workspace_tasks_${user.id}` : 'super_ai_workspace_tasks_guest';
    try {
      const savedTasks = localStorage.getItem(taskStorageKey);
      if (savedTasks) {
        const parsed = JSON.parse(savedTasks);
        if (Array.isArray(parsed) && isMounted) {
          setTasks(parsed);
        }
      } else if (isMounted) {
        setTasks([]);
      }
    } catch {
      if (isMounted) setTasks([]);
    }

    // Weather: check permission state if available without triggering a prompt automatically
    const checkWeatherOnMount = async () => {
      // If user previously selected a manual city, load it
      const savedCityName = localStorage.getItem('super_ai_selected_city');
      if (savedCityName) {
        const found = CITIES_FALLBACK.find(c => c.name.toLowerCase() === savedCityName.toLowerCase());
        if (found) {
          fetchWeatherForCoordinates(found.lat, found.lon, found.name);
          return;
        }
      }

      if (typeof navigator !== 'undefined' && 'permissions' in navigator && (navigator.permissions as any).query) {
        try {
          const status = await (navigator.permissions as any).query({ name: 'geolocation' });
          if (status.state === 'granted') {
            requestUserLocation(false);
            return;
          } else if (status.state === 'denied') {
            if (isMounted) setWeather({ status: 'permission_denied', locationName: 'Location disabled' });
            return;
          }
        } catch {
          // Query not supported for geolocation in some environments
        }
      }
      // If prompt or not granted, start in idle state allowing user to trigger or pick city
      if (isMounted) {
        setWeather({ status: 'idle', locationName: 'Local Climate' });
      }
    };

    checkWeatherOnMount();

    setIsLoadingRestaurants(true);
    apiClient.listRestaurants()
      .then((data) => {
        if (isMounted) setRestaurants(data.slice(0, 2));
      })
      .catch((err) => {
        console.warn('Could not load home restaurants:', err);
      })
      .finally(() => {
        if (isMounted) setIsLoadingRestaurants(false);
      });

    if (isAuthenticated) {
      setIsLoadingTransactions(true);
      apiClient.listPaymentTransactions({ limit: 3 })
        .then((txs) => {
          if (isMounted) setTransactions(txs);
        })
        .catch((err) => {
          console.warn('Could not load home transactions:', err);
        })
        .finally(() => {
          if (isMounted) setIsLoadingTransactions(false);
        });
    } else {
      setTransactions([]);
    }

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, user]);

  const [isCityDropdownOpen, setIsCityDropdownOpen] = useState(false);

  const fetchWeatherForCoordinates = async (latitude: number, longitude: number, cityName: string) => {
    setWeather({ status: 'loading', locationName: cityName });
    try {
      const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,weather_code&timezone=auto`);
      if (!res.ok) throw new Error('Weather API error');
      const data = await res.json();
      if (data.current) {
        const temp = Math.round(data.current.temperature_2m);
        setWeather({
          status: 'success',
          temp,
          condition: temp > 28 ? 'Warm' : temp < 15 ? 'Cool' : 'Pleasant',
          locationName: cityName
        });
      } else {
        setWeather({ status: 'unavailable', locationName: cityName });
      }
    } catch {
      setWeather({ status: 'unavailable', locationName: `${cityName} (offline)` });
    }
  };

  const requestUserLocation = (userInitiated = true) => {
    if (typeof navigator === 'undefined' || !('geolocation' in navigator)) {
      setWeather({ status: 'unavailable', locationName: 'Geolocation unsupported' });
      return;
    }

    setWeather({ status: 'loading', locationName: 'Detecting...' });

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        localStorage.removeItem('super_ai_selected_city');
        fetchWeatherForCoordinates(latitude, longitude, 'Local Climate');
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setWeather({ status: 'permission_denied', locationName: 'Location disabled' });
        } else {
          setWeather({ status: 'unavailable', locationName: 'Location unavailable' });
        }
      },
      { timeout: 8000, maximumAge: 300000 }
    );
  };

  const handleSelectCity = (city: typeof CITIES_FALLBACK[0]) => {
    setIsCityDropdownOpen(false);
    localStorage.setItem('super_ai_selected_city', city.name);
    fetchWeatherForCoordinates(city.lat, city.lon, city.name);
  };

  const handleQuickAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickInput.trim()) return;
    setActiveModule('ai-assistant');
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto w-full">
      {/* Hero Greeting and Universal AI Input */}
      <div className={`relative overflow-hidden rounded-3xl p-6 md:p-8 border ${activeTheme.borderClass} ${activeTheme.surfaceClass} shadow-xl`}>
        <div className="relative z-10 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="text-xs uppercase tracking-widest font-semibold" style={{ color: preferences.accentColor || '#8b5cf6' }}>
                {new Date().toLocaleDateString(preferences.language === 'en' ? 'en-IN' : preferences.language, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
              </span>
              <h1 className="text-2xl md:text-3xl font-extrabold text-inherit tracking-tight">
                {t(getGreetingKey(), preferences.language, { name: user?.full_name?.split(' ')[0] || user?.username || 'Sovereign Explorer' })}
              </h1>
            </div>
            <div className="relative flex items-center space-x-2">
              {weather.status === 'success' ? (
                <div className="flex items-center gap-1.5">
                  <span className="px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                    {weather.locationName} {weather.temp}°C • {weather.condition}
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsCityDropdownOpen(prev => !prev)}
                    className="p-1 rounded-full text-slate-400 hover:text-white hover:bg-white/10 transition"
                    title="Change location or city"
                    aria-label="Change city"
                  >
                    <ChevronDown className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : weather.status === 'loading' ? (
                <span className="px-3 py-1 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20 flex items-center gap-1.5">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Updating climate...
                </span>
              ) : weather.status === 'permission_denied' ? (
                <div className="flex items-center gap-1.5">
                  <span className="px-3 py-1 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20 flex items-center gap-1.5">
                    <MapPin className="w-3 h-3 text-amber-400" />
                    Location disabled
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsCityDropdownOpen(prev => !prev)}
                    className="px-2 py-1 rounded-lg text-xs font-medium bg-white/5 hover:bg-white/10 text-slate-300 transition flex items-center gap-1"
                  >
                    <span>Choose city</span>
                    <ChevronDown className="w-3 h-3" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => requestUserLocation(true)}
                    className="px-3 py-1 rounded-full text-xs font-medium bg-violet-500/10 text-violet-400 border border-violet-500/20 hover:bg-violet-500/20 flex items-center gap-1.5 transition"
                  >
                    <MapPin className="w-3 h-3" />
                    Detect Climate
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsCityDropdownOpen(prev => !prev)}
                    className="px-2 py-1 rounded-lg text-xs font-medium bg-white/5 hover:bg-white/10 text-slate-300 transition flex items-center gap-1"
                  >
                    <span>Cities</span>
                    <ChevronDown className="w-3 h-3" />
                  </button>
                </div>
              )}

              {/* City Selection Dropdown */}
              {isCityDropdownOpen && (
                <div className="absolute right-0 top-full mt-2 w-48 py-1.5 bg-slate-900/95 border border-white/10 rounded-2xl shadow-2xl backdrop-blur-xl z-50 text-xs">
                  <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider border-b border-white/5 flex items-center justify-between">
                    <span>Select City</span>
                    <button
                      type="button"
                      onClick={() => requestUserLocation(true)}
                      className="text-violet-400 hover:text-violet-300 font-normal underline"
                    >
                      Use GPS
                    </button>
                  </div>
                  <div className="max-h-48 overflow-y-auto py-1">
                    {CITIES_FALLBACK.map((city) => (
                      <button
                        key={city.name}
                        type="button"
                        onClick={() => handleSelectCity(city)}
                        className="w-full px-3 py-1.5 text-left text-slate-300 hover:text-white hover:bg-white/10 transition flex items-center justify-between"
                      >
                        <span>{city.name}</span>
                        {weather.locationName === city.name && (
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <p className="text-xs md:text-sm text-slate-400 max-w-2xl leading-relaxed">
            {t('home.daily_briefing', preferences.language)}
          </p>

          {/* Quick Universal Input */}
          <form onSubmit={handleQuickAsk} className="relative max-w-2xl mt-4">
            <Bot className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2" style={{ color: preferences.accentColor || '#8b5cf6' }} />
            <input
              type="text"
              value={quickInput}
              onChange={(e) => setQuickInput(e.target.value)}
              placeholder="Ask anything, summon an action, or order lunch..."
              className="w-full pl-12 pr-28 py-3.5 bg-black/10 dark:bg-black/40 border border-white/10 rounded-2xl text-sm text-inherit placeholder-slate-400 focus:outline-none focus:border-violet-500 shadow-inner"
            />
            <button
              type="submit"
              style={{ backgroundColor: preferences.accentColor || '#8b5cf6' }}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 hover:opacity-90 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1 shadow-md"
            >
              <span>Ask AI</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>

        {/* Ambient Glow Graphic */}
        <div 
          className="absolute -right-20 -bottom-20 w-80 h-80 rounded-full blur-3xl pointer-events-none opacity-20"
          style={{ background: preferences.accentColor || '#8b5cf6' }}
        />
      </div>

      {/* Quick Launch Service Grid (Supported active services only) */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs uppercase tracking-wider text-slate-400 font-semibold">{t('home.explore_super_ai', preferences.language)}</h3>
          <span className="text-xs font-medium" style={{ color: preferences.accentColor || '#8b5cf6' }}>Unified Sovereign Hub</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {[
            { id: 'search', labelKey: 'nav.search', label: 'Search', icon: Search, color: 'text-violet-400 bg-violet-500/10' },
            { id: 'chat', labelKey: 'nav.chat', label: 'Chat', icon: MessageSquare, color: 'text-emerald-400 bg-emerald-500/10' },
            { id: 'social', labelKey: 'nav.social', label: 'Social', icon: Share2, color: 'text-blue-400 bg-blue-500/10' },
            { id: 'video', labelKey: 'nav.video', label: 'Video', icon: Video, color: 'text-rose-400 bg-rose-500/10' },
            { id: 'shopping', labelKey: 'nav.shopping', label: 'Zaviro', icon: ShoppingBag, color: 'text-pink-400 bg-pink-500/10' },
            { id: 'food', labelKey: 'nav.food', label: 'Food & Dining', icon: Utensils, color: 'text-orange-400 bg-orange-500/10' },
          ].map((item) => {
            const Icon = item.icon;
            const itemLabel = t(item.labelKey, preferences.language) || item.label;
            return (
              <button
                key={item.id}
                onClick={() => setActiveModule(item.id as any)}
                className={`p-4 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} hover:border-violet-500/40 transition-all text-left group flex flex-col justify-between space-y-3 shadow-sm`}
              >
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${item.color} group-hover:scale-105 transition-transform`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-inherit group-hover:opacity-100 opacity-90 transition">{itemLabel}</span>
                  <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-0.5 transition" />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Widgets 2-Column Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 spans): Food & Payments Live Previews */}
        <div className="lg:col-span-2 space-y-6">
          {/* Food Discovery Widget */}
          <div className={`p-5 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} space-y-4 shadow-sm`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Utensils className="w-4 h-4 text-orange-400" />
                <h3 className="text-sm font-bold text-inherit">Popular Restaurants</h3>
              </div>
              <button
                onClick={() => setActiveModule('food')}
                className="text-xs hover:underline font-medium flex items-center gap-1"
                style={{ color: preferences.accentColor || '#8b5cf6' }}
              >
                View All <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {isLoadingRestaurants ? (
              <div className="py-8 flex items-center justify-center text-slate-400 gap-2 text-xs">
                <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
                <span>Loading restaurants...</span>
              </div>
            ) : restaurants.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {restaurants.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => setActiveModule('food')}
                    className="p-3 rounded-xl bg-black/5 dark:bg-slate-800/50 hover:bg-black/10 dark:hover:bg-slate-800 border border-white/5 cursor-pointer transition flex items-center space-x-3"
                  >
                    {r.image_url ? (
                      <img src={r.image_url} alt={r.name} className="w-16 h-16 rounded-lg object-cover shrink-0" />
                    ) : (
                      <div className="w-16 h-16 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-orange-400 shrink-0">
                        <Utensils className="w-6 h-6" />
                      </div>
                    )}
                    <div className="space-y-0.5 overflow-hidden">
                      <h4 className="text-xs font-semibold text-inherit truncate">{r.name}</h4>
                      <p className="text-[11px] text-slate-400 truncate">{r.cuisine || r.service_area}</p>
                      <div className="flex items-center space-x-2 text-[10px] text-slate-400 pt-1">
                        <span className="text-emerald-400 font-semibold">★ {r.rating.toFixed(1)}</span>
                        <span>•</span>
                        <span>{r.time_mins} mins</span>
                        <span>•</span>
                        <span>₹{r.price_for_two_inr} for two</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 rounded-xl bg-black/5 dark:bg-slate-800/20 border border-dashed border-white/10 text-center space-y-2">
                <Utensils className="w-7 h-7 mx-auto text-slate-500" />
                <p className="text-xs text-slate-400">No restaurants currently listed in your area.</p>
                <button
                  onClick={() => setActiveModule('food')}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition shadow-sm"
                  style={{ backgroundColor: preferences.accentColor || '#8b5cf6' }}
                >
                  Explore Food & Dining
                </button>
              </div>
            )}
          </div>

          {/* Recent UPI Activity */}
          <div className={`p-5 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} space-y-4 shadow-sm`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <CreditCard className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-bold text-inherit">Recent UPI Transactions</h3>
              </div>
              <button
                onClick={() => setActiveModule('payments')}
                className="text-xs hover:underline font-medium flex items-center gap-1"
                style={{ color: preferences.accentColor || '#8b5cf6' }}
              >
                Manage Payments <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {isAuthenticated ? (
              isLoadingTransactions ? (
                <div className="py-6 flex items-center justify-center text-slate-400 gap-2 text-xs">
                  <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
                  <span>Loading recent transactions...</span>
                </div>
              ) : transactions.length > 0 ? (
                <div className="space-y-2">
                  <div className="text-[10px] uppercase font-mono tracking-wider text-slate-400 pb-1 flex items-center justify-between">
                    <span>Authorized Account Activity</span>
                    <span className="text-emerald-400">Encrypted Vault</span>
                  </div>
                  {transactions.map((tx) => (
                    <div key={tx.id} className="p-3 rounded-xl bg-black/5 dark:bg-slate-800/40 border border-white/5 flex items-center justify-between text-xs">
                      <div className="flex items-center space-x-3">
                        <div className={`p-2 rounded-lg ${tx.category === 'p2p' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-500/20 text-slate-400'}`}>
                          {tx.category === 'p2p' ? '+₹' : '-₹'}
                        </div>
                        <div>
                          <h5 className="font-semibold text-inherit">{tx.recipient_name || tx.transaction_ref}</h5>
                          <span className="text-[10px] text-slate-400">{new Date(tx.created_at).toLocaleDateString()} • {tx.recipient_identifier || 'UPI Payment'}</span>
                        </div>
                      </div>
                      <span className={`font-semibold ${tx.status === 'success' ? 'text-emerald-400' : 'text-slate-300'}`}>
                        ₹{(tx.amount_paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-6 rounded-xl bg-black/5 dark:bg-slate-800/20 border border-dashed border-white/10 text-center space-y-2">
                  <CreditCard className="w-6 h-6 mx-auto text-slate-500" />
                  <p className="text-xs text-slate-400">No payment transactions yet. Transfer funds or pay bills via UPI.</p>
                  <button
                    onClick={() => setActiveModule('payments')}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition shadow-sm"
                    style={{ backgroundColor: preferences.accentColor || '#8b5cf6' }}
                  >
                    Make a Payment
                  </button>
                </div>
              )
            ) : (
              <div className="p-4 rounded-xl bg-black/5 dark:bg-slate-800/20 border border-dashed border-white/10 text-center space-y-2">
                <p className="text-xs text-slate-400">Sign in to view your UPI transaction history and live bank account balances.</p>
                <button
                  onClick={openLoginModal}
                  className="px-4 py-1.5 rounded-lg text-xs font-semibold text-white transition shadow-sm"
                  style={{ backgroundColor: preferences.accentColor || '#8b5cf6' }}
                >
                  Sign In to View
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Sovereign Cloud & Quick Priorities */}
        <div className="space-y-6">
          {/* Client Vault Widget */}
          <div className={`p-5 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} space-y-3 shadow-sm`}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-inherit flex items-center gap-2">
                <Cloud className="w-4 h-4 text-cyan-400" /> Client Vault & Storage
              </h3>
              <button
                onClick={() => setActiveModule('cloud')}
                className="text-xs hover:underline font-medium"
                style={{ color: preferences.accentColor || '#8b5cf6' }}
              >
                Vault
              </button>
            </div>
            <p className="text-xs text-slate-400">
              {cloudFileCount === 0
                ? '0 local files stored (~0 MB) • Cloud unattached'
                : `${cloudFileCount} local ${cloudFileCount === 1 ? 'file' : 'files'} (~${(cloudFileCount * 2.4).toFixed(1)} MB) • Cloud unattached`}
            </p>
            <div className="w-full bg-black/10 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                className="h-2 rounded-full"
                style={{
                  width: `${cloudFileCount > 0 ? Math.min(100, Math.max(cloudFileCount * 10, 4)) : 0}%`,
                  background: `linear-gradient(to right, #06b6d4, ${preferences.accentColor || '#8b5cf6'})`
                }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-400 pt-1">
              <span>{user ? `Account: ${user.username}` : 'Guest session'}</span>
              <span className="text-amber-400/90 font-mono text-[10px]">Local only</span>
            </div>
          </div>

          {/* Quick Priorities */}
          <div className={`p-5 rounded-2xl border ${activeTheme.borderClass} ${activeTheme.surfaceClass} space-y-3 shadow-sm`}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-inherit flex items-center gap-2">
                <Calendar className="w-4 h-4 text-emerald-400" /> Today's Priorities
              </h3>
              <button
                onClick={() => setActiveModule('notifications')}
                className="text-xs hover:underline font-medium"
                style={{ color: preferences.accentColor || '#8b5cf6' }}
              >
                Notifications
              </button>
            </div>
            {tasks.length > 0 ? (
              <div className="space-y-2 text-xs">
                {tasks.slice(0, 4).map((item) => (
                  <div key={item.id} className="flex items-center space-x-2.5 p-2 rounded-lg bg-black/5 dark:bg-slate-800/30">
                    <CheckCircle2 className={`w-4 h-4 ${item.completed ? 'text-emerald-400' : 'text-slate-400'}`} />
                    <span className={`flex-1 ${item.completed ? 'line-through text-slate-400' : 'text-inherit'}`}>
                      {item.title}
                    </span>
                    {item.dueDate && <span className="text-[10px] text-slate-400">{item.dueDate}</span>}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-black/5 dark:bg-slate-800/20 border border-dashed border-white/10 text-center space-y-2">
                <p className="text-xs text-slate-400">No pending priorities recorded.</p>
                <button
                  onClick={() => setActiveModule('notifications')}
                  className="px-3 py-1 rounded-lg text-xs font-semibold text-white transition shadow-sm"
                  style={{ backgroundColor: preferences.accentColor || '#8b5cf6' }}
                >
                  View Alerts
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
