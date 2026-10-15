import React, { useState, useEffect, useCallback } from 'react';
import { 
  Utensils, Search, Star, Clock, ShoppingBag, Plus, Minus, 
  MapPin, CheckCircle2, ChevronRight, X, Loader2, AlertCircle, 
  ArrowLeft, RefreshCw, Receipt, Ban, ChefHat, Edit3, Trash2, CheckCircle, Store, Power, Check
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { 
  apiClient, 
  type RestaurantResponse, 
  type MenuItemResponse, 
  type FoodOrderResponse, 
  type OrderItemInput,
  type RestaurantRegisterPayload,
  type MenuItemCreatePayload
} from '../../services/apiClient';

interface CartItem {
  itemId: string;
  restaurantId: string;
  restaurantName: string;
  name: string;
  pricePaise: number;
  qty: number;
  isVeg: boolean;
}

export const FoodDiningView: React.FC = () => {
  const { user, isAuthenticated, openLoginModal } = useAuth();

  // Active view: 'browse' | 'orders' | 'partner'
  const [activeTab, setActiveTab] = useState<'browse' | 'orders' | 'partner'>('browse');

  // Restaurant listings state
  const [restaurants, setRestaurants] = useState<RestaurantResponse[]>([]);
  const [isLoadingRestaurants, setIsLoadingRestaurants] = useState(true);
  const [restaurantError, setRestaurantError] = useState<string | null>(null);
  const [filterVegOnly, setFilterVegOnly] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');

  // Selected restaurant menu view
  const [selectedRestaurant, setSelectedRestaurant] = useState<RestaurantResponse | null>(null);
  const [isLoadingMenu, setIsLoadingMenu] = useState(false);

  // Cart state (Local persistence backed by authoritative backend calculation upon checkout)
  const [cart, setCart] = useState<CartItem[]>(() => {
    try {
      const saved = localStorage.getItem('super_ai_food_cart');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Delivery address & checkout
  const [deliveryAddress, setDeliveryAddress] = useState(
    'Flat 402, Embassy Habitat, 100ft Road, HAL 2nd Stage, Indiranagar, Bengaluru, 560038'
  );
  const [paymentMethod, setPaymentMethod] = useState<'cod' | 'test_mode_upi' | 'test_mode_card'>('cod');
  const [isPlacingOrder, setIsPlacingOrder] = useState(false);
  const [lastPlacedOrder, setLastPlacedOrder] = useState<FoodOrderResponse | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  // Order history state
  const [orders, setOrders] = useState<FoodOrderResponse[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);
  const [cancellingOrderId, setCancellingOrderId] = useState<string | null>(null);

  // Save cart to local storage
  useEffect(() => {
    localStorage.setItem('super_ai_food_cart', JSON.stringify(cart));
  }, [cart]);

  // Fetch Restaurants
  const fetchRestaurants = useCallback(async () => {
    setIsLoadingRestaurants(true);
    setRestaurantError(null);
    try {
      const data = await apiClient.listRestaurants(filterVegOnly, searchFilter || undefined);
      setRestaurants(data);
    } catch (err: any) {
      setRestaurantError(err.message || 'Failed to load restaurant directory');
    } finally {
      setIsLoadingRestaurants(false);
    }
  }, [filterVegOnly, searchFilter]);

  useEffect(() => {
    fetchRestaurants();
  }, [fetchRestaurants]);

  // Fetch Order History
  const fetchOrders = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingOrders(true);
    try {
      const data = await apiClient.listFoodOrders(25);
      setOrders(data);
    } catch {
      setOrders([]);
    } finally {
      setIsLoadingOrders(false);
    }
  }, [isAuthenticated]);

  // Restaurant Partner Operations State (Phase 4)
  const [partnerRestaurant, setPartnerRestaurant] = useState<RestaurantResponse | null>(null);
  const [partnerOrders, setPartnerOrders] = useState<FoodOrderResponse[]>([]);
  const [isLoadingPartner, setIsLoadingPartner] = useState(false);
  const [isRegisteringRestaurant, setIsRegisteringRestaurant] = useState(false);
  const [partnerError, setPartnerError] = useState<string | null>(null);
  const [partnerSuccess, setPartnerSuccess] = useState<string | null>(null);

  // Restaurant Registration Form
  const [rFormName, setRFormName] = useState('');
  const [rFormDesc, setRFormDesc] = useState('');
  const [rFormArea, setRFormArea] = useState('Indiranagar');
  const [rFormAddress, setRFormAddress] = useState('100ft Road, Indiranagar, Bengaluru');
  const [rFormCuisine, setRFormCuisine] = useState('South Indian, Biryani');
  const [rFormPriceForTwo, setRFormPriceForTwo] = useState('500');
  const [rFormIsVeg, setRFormIsVeg] = useState(false);

  // Menu Item Modal Form
  const [isMenuItemModalOpen, setIsMenuItemModalOpen] = useState(false);
  const [editingMenuItemId, setEditingMenuItemId] = useState<string | null>(null);
  const [mItemName, setMItemName] = useState('');
  const [mItemCat, setMItemCat] = useState('Main Course');
  const [mItemPriceRupees, setMItemPriceRupees] = useState('');
  const [mItemDesc, setMItemDesc] = useState('');
  const [mItemIsVeg, setMItemIsVeg] = useState(true);
  const [mItemImage, setMItemImage] = useState('https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=600');
  const [isSavingMenuItem, setIsSavingMenuItem] = useState(false);

  // Fetch Partner Data
  const fetchPartnerData = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingPartner(true);
    setPartnerError(null);
    try {
      const rest = await apiClient.getOwnerRestaurant();
      setPartnerRestaurant(rest);
      const incoming = await apiClient.listRestaurantOrders();
      setPartnerOrders(incoming);
    } catch (err: any) {
      if (err.message && err.message.includes('not found')) {
        setPartnerRestaurant(null);
      } else {
        setPartnerError(err.message || 'Could not load restaurant operations');
      }
    } finally {
      setIsLoadingPartner(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (activeTab === 'partner') {
      fetchPartnerData();
    }
  }, [activeTab, fetchPartnerData]);

  // Handle Restaurant Registration
  const handleRegisterRestaurant = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsRegisteringRestaurant(true);
    setPartnerError(null);
    try {
      const payload: RestaurantRegisterPayload = {
        name: rFormName.trim(),
        description: rFormDesc.trim() || undefined,
        service_area: rFormArea.trim(),
        address: rFormAddress.trim(),
        cuisine: rFormCuisine.trim(),
        price_for_two_inr: parseInt(rFormPriceForTwo) || 400,
        is_veg: rFormIsVeg,
        is_open: true
      };
      const res = await apiClient.registerRestaurant(payload);
      setPartnerRestaurant(res);
      setPartnerSuccess('Restaurant successfully registered with live kitchen order routing!');
      fetchPartnerData();
      fetchRestaurants();
      setTimeout(() => setPartnerSuccess(null), 3500);
    } catch (err: any) {
      setPartnerError(err.message || 'Failed to register restaurant.');
    } finally {
      setIsRegisteringRestaurant(false);
    }
  };

  // Toggle Restaurant Open / Closed
  const handleToggleOpen = async () => {
    if (!partnerRestaurant) return;
    const newOpen = !partnerRestaurant.is_open;
    try {
      const updated = await apiClient.updateOwnerRestaurant({ is_open: newOpen });
      setPartnerRestaurant(updated);
      setPartnerSuccess(`Restaurant is now ${newOpen ? 'OPEN for online orders' : 'CLOSED'}`);
      fetchRestaurants();
      setTimeout(() => setPartnerSuccess(null), 3000);
    } catch (err: any) {
      setPartnerError(err.message || 'Failed to toggle restaurant opening status.');
    }
  };

  // Handle Save Menu Item
  const handleSaveMenuItem = async (e: React.FormEvent) => {
    e.preventDefault();
    const priceRupees = parseFloat(mItemPriceRupees);
    if (isNaN(priceRupees) || priceRupees <= 0) {
      setPartnerError('Please enter a valid price in rupees.');
      return;
    }
    const pricePaise = Math.round(priceRupees * 100);

    setIsSavingMenuItem(true);
    setPartnerError(null);

    try {
      if (editingMenuItemId) {
        await apiClient.updateMenuItem(editingMenuItemId, {
          name: mItemName.trim(),
          category: mItemCat.trim(),
          price_paise: pricePaise,
          description: mItemDesc.trim(),
          is_veg: mItemIsVeg,
          image_url: mItemImage.trim()
        });
        setPartnerSuccess('Menu item updated!');
      } else {
        await apiClient.createMenuItem({
          name: mItemName.trim(),
          category: mItemCat.trim(),
          price_paise: pricePaise,
          description: mItemDesc.trim(),
          is_veg: mItemIsVeg,
          image_url: mItemImage.trim(),
          is_available: true
        });
        setPartnerSuccess('New dish added to restaurant menu!');
      }

      setIsMenuItemModalOpen(false);
      setEditingMenuItemId(null);
      fetchPartnerData();
      setTimeout(() => setPartnerSuccess(null), 3000);
    } catch (err: any) {
      setPartnerError(err.message || 'Failed to save menu item.');
    } finally {
      setIsSavingMenuItem(false);
    }
  };

  // Delete Menu Item
  const handleDeleteMenuItem = async (itemId: string) => {
    if (!confirm('Are you sure you want to remove this dish from the menu?')) return;
    try {
      await apiClient.deleteMenuItem(itemId);
      fetchPartnerData();
    } catch (err: any) {
      setPartnerError(err.message || 'Failed to remove menu item.');
    }
  };

  // Update Restaurant Order Status
  const handleUpdateRestaurantOrderStatus = async (
    orderId: string,
    newStatus: 'confirmed' | 'preparing' | 'out_for_delivery' | 'delivered' | 'cancelled'
  ) => {
    try {
      await apiClient.updateRestaurantOrderStatus(orderId, newStatus);
      fetchPartnerData();
      setPartnerSuccess(`Order status transitioned to ${newStatus.replace('_', ' ')}!`);
      setTimeout(() => setPartnerSuccess(null), 3000);
    } catch (err: any) {
      setPartnerError(err.message || 'Status transition failed.');
    }
  };

  // Open Restaurant Menu
  const handleOpenRestaurant = async (restaurantId: string) => {
    setIsLoadingMenu(true);
    try {
      const detail = await apiClient.getRestaurantDetail(restaurantId);
      setSelectedRestaurant(detail);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err: any) {
      alert(err.message || 'Failed to load restaurant menu');
    } finally {
      setIsLoadingMenu(false);
    }
  };

  // Add Item to Cart
  const handleAddToCart = (rest: RestaurantResponse, item: MenuItemResponse) => {
    // If cart has items from a different restaurant, confirm clearing
    if (cart.length > 0 && cart[0].restaurantId !== rest.id) {
      if (!confirm(`Your cart already contains dishes from ${cart[0].restaurantName}. Clear cart and add from ${rest.name}?`)) {
        return;
      }
      setCart([
        {
          itemId: item.id,
          restaurantId: rest.id,
          restaurantName: rest.name,
          name: item.name,
          pricePaise: item.price_paise,
          qty: 1,
          isVeg: item.is_veg,
        },
      ]);
      return;
    }

    setCart((prev) => {
      const existing = prev.find((i) => i.itemId === item.id);
      if (existing) {
        return prev.map((i) => (i.itemId === item.id ? { ...i, qty: i.qty + 1 } : i));
      }
      return [
        ...prev,
        {
          itemId: item.id,
          restaurantId: rest.id,
          restaurantName: rest.name,
          name: item.name,
          pricePaise: item.price_paise,
          qty: 1,
          isVeg: item.is_veg,
        },
      ];
    });
  };

  const handleUpdateQty = (itemId: string, delta: number) => {
    setCart((prev) =>
      prev
        .map((item) => (item.itemId === itemId ? { ...item, qty: item.qty + delta } : item))
        .filter((item) => item.qty > 0)
    );
  };

  // Cart Calculations (Estimated in frontend, strictly verified and enforced by backend in paise)
  const cartSubtotalPaise = cart.reduce((acc, i) => acc + i.pricePaise * i.qty, 0);
  const deliveryFeePaise = cart.length > 0 ? 3500 : 0;
  const taxesPaise = Math.round(cartSubtotalPaise * 0.05);
  const grandTotalPaise = cartSubtotalPaise + deliveryFeePaise + taxesPaise;

  // Submit Order to Backend
  const handlePlaceOrder = async () => {
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }
    if (cart.length === 0) return;

    setIsPlacingOrder(true);
    setCheckoutError(null);

    const itemsPayload: OrderItemInput[] = cart.map((i) => ({
      item_id: i.itemId,
      quantity: i.qty,
    }));

    try {
      const orderRes = await apiClient.placeFoodOrder({
        restaurant_id: cart[0].restaurantId,
        items: itemsPayload,
        delivery_address: deliveryAddress.trim(),
        payment_method: paymentMethod,
      });

      setLastPlacedOrder(orderRes);
      setCart([]);
      setActiveTab('orders');
      fetchOrders();
    } catch (err: any) {
      setCheckoutError(err.message || 'Order checkout failed');
    } finally {
      setIsPlacingOrder(false);
    }
  };

  // Cancel Order
  const handleCancelOrder = async (orderId: string) => {
    if (!confirm('Are you sure you want to cancel this order?')) return;
    setCancellingOrderId(orderId);
    try {
      const updated = await apiClient.cancelFoodOrder(orderId);
      setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
      if (lastPlacedOrder?.id === orderId) {
        setLastPlacedOrder(updated);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to cancel order');
    } finally {
      setCancellingOrderId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto w-full pb-12">
      {/* Header and Filter Controls */}
      <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-orange-400 text-xs font-semibold uppercase tracking-wider">
            <Utensils className="w-4 h-4" />
            <span>Indiranagar Delivery Zone • Bangalore</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">SUPER_AI Food & Dining</h1>
          <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5 text-violet-400" />
            <span>Serving HAL 2nd Stage, CMH Road, 100ft Road & surrounding areas</span>
          </p>
        </div>

        <div className="flex items-center space-x-2 w-full md:w-auto">
          <button
            onClick={() => {
              setActiveTab('browse');
              setSelectedRestaurant(null);
            }}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition ${
              activeTab === 'browse'
                ? 'bg-orange-600 text-white shadow'
                : 'bg-white/5 text-slate-300 hover:bg-white/10'
            }`}
          >
            Restaurants
          </button>
          <button
            onClick={() => {
              if (!isAuthenticated) {
                openLoginModal();
                return;
              }
              setActiveTab('orders');
            }}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center space-x-1.5 ${
              activeTab === 'orders'
                ? 'bg-orange-600 text-white shadow'
                : 'bg-white/5 text-slate-300 hover:bg-white/10'
            }`}
          >
            <Receipt className="w-3.5 h-3.5" />
            <span>My Orders</span>
          </button>
          <button
            onClick={() => {
              if (!isAuthenticated) {
                openLoginModal();
                return;
              }
              setActiveTab('partner');
            }}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center space-x-1.5 ${
              activeTab === 'partner'
                ? 'bg-orange-600 text-white shadow'
                : 'bg-white/5 text-slate-300 hover:bg-white/10'
            }`}
          >
            <ChefHat className="w-3.5 h-3.5" />
            <span>Restaurant Partner</span>
          </button>
        </div>
      </div>

      {/* VIEW: ORDER HISTORY */}
      {activeTab === 'orders' ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm uppercase tracking-wider text-slate-300 font-bold">Your Food Orders</h2>
            <button
              onClick={fetchOrders}
              disabled={isLoadingOrders}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5"
            >
              <RefreshCw className={`w-4 h-4 ${isLoadingOrders ? 'animate-spin text-orange-400' : ''}`} />
            </button>
          </div>

          {isLoadingOrders ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-orange-400" />
            </div>
          ) : orders.length === 0 ? (
            <div className="p-8 text-center bg-slate-900/40 border border-white/5 rounded-2xl space-y-2">
              <ShoppingBag className="w-8 h-8 text-slate-500 mx-auto" />
              <p className="text-sm font-semibold text-slate-300">No orders placed yet</p>
              <p className="text-xs text-slate-500">Explore authentic Indiranagar eateries and order freshly prepared meals.</p>
              <button
                onClick={() => setActiveTab('browse')}
                className="mt-2 px-4 py-1.5 bg-orange-600 text-white rounded-xl text-xs font-semibold hover:bg-orange-500 transition"
              >
                Browse Menus
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {orders.map((ord) => (
                <div key={ord.id} className="p-5 rounded-2xl bg-slate-900/50 border border-white/10 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2.5">
                    <div>
                      <h4 className="text-sm font-bold text-white">{ord.restaurant_name}</h4>
                      <p className="text-[10px] text-slate-400">
                        Order #{ord.id.slice(-6).toUpperCase()} • {new Date(ord.created_at).toLocaleString()}
                      </p>
                    </div>

                    <div className="flex items-center space-x-2">
                      <span
                        className={`text-[10px] px-2.5 py-1 rounded-full uppercase tracking-wider font-bold border ${
                          ord.order_status === 'delivered'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : ord.order_status === 'cancelled'
                            ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            : 'bg-orange-500/10 text-orange-400 border-orange-500/20 animate-pulse'
                        }`}
                      >
                        {ord.order_status.replace('_', ' ')}
                      </span>

                      {['placed', 'confirmed'].includes(ord.order_status) && (
                        <button
                          onClick={() => handleCancelOrder(ord.id)}
                          disabled={cancellingOrderId === ord.id}
                          className="px-3 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 rounded-lg text-xs font-semibold border border-rose-500/20 transition flex items-center space-x-1"
                        >
                          {cancellingOrderId === ord.id ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Ban className="w-3 h-3" />
                          )}
                          <span>Cancel Order</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Order items snapshot */}
                  <div className="space-y-1.5 text-xs text-slate-300">
                    {ord.items.map((it, idx) => (
                      <div key={idx} className="flex justify-between">
                        <span>{it.quantity}x {it.name}</span>
                        <span className="font-mono text-slate-400">₹{(it.total_price_paise / 100).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>

                  <div className="pt-2 border-t border-white/5 text-xs text-slate-400 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-[11px] truncate max-w-sm">
                        <span className="text-slate-500">Address:</span> {ord.delivery_address}
                      </p>
                      <p className="text-[10px] text-slate-500 mt-0.5">
                        Payment: {ord.payment_method.toUpperCase()} ({ord.payment_status})
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] text-slate-400">Total (Incl. GST + Delivery):</span>
                      <p className="text-base font-bold text-emerald-400 font-mono">₹{ord.total_inr.toFixed(2)}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : activeTab === 'partner' ? (
        /* VIEW: RESTAURANT PARTNER OPERATIONS (Phase 4) */
        <div className="space-y-6">
          {partnerSuccess && (
            <div className="p-4 rounded-2xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{partnerSuccess}</span>
            </div>
          )}

          {partnerError && (
            <div className="p-4 rounded-2xl bg-red-500/20 border border-red-500/30 text-red-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{partnerError}</span>
            </div>
          )}

          {isLoadingPartner ? (
            <div className="py-20 text-center space-y-3">
              <Loader2 className="w-8 h-8 text-orange-500 animate-spin mx-auto" />
              <p className="text-xs text-slate-400">Loading Restaurant Kitchen Operations...</p>
            </div>
          ) : !partnerRestaurant ? (
            /* RESTAURANT REGISTRATION */
            <div className="max-w-2xl mx-auto p-6 sm:p-8 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl space-y-6">
              <div className="text-center space-y-2">
                <div className="w-12 h-12 rounded-2xl bg-orange-500/20 border border-orange-500/30 flex items-center justify-center text-orange-400 mx-auto">
                  <ChefHat className="w-6 h-6" />
                </div>
                <h2 className="text-xl font-bold text-white">Register as a Restaurant Partner</h2>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  List your eatery on SUPER_AI Food & Dining. Receive customer orders in real-time, manage your menu, and grow your local delivery business.
                </p>
              </div>

              <form onSubmit={handleRegisterRestaurant} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Restaurant / Kitchen Name *</label>
                  <input
                    type="text"
                    required
                    value={rFormName}
                    onChange={e => setRFormName(e.target.value)}
                    placeholder="e.g. Bangalore Biryani Club"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Cuisines *</label>
                    <input
                      type="text"
                      required
                      value={rFormCuisine}
                      onChange={e => setRFormCuisine(e.target.value)}
                      placeholder="e.g. South Indian, Biryani, Mughlai"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Service Area *</label>
                    <input
                      type="text"
                      required
                      value={rFormArea}
                      onChange={e => setRFormArea(e.target.value)}
                      placeholder="e.g. Indiranagar"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Complete Address *</label>
                  <input
                    type="text"
                    required
                    value={rFormAddress}
                    onChange={e => setRFormAddress(e.target.value)}
                    placeholder="Street, locality, landmark..."
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Approx. Price for Two (₹) *</label>
                    <input
                      type="number"
                      required
                      value={rFormPriceForTwo}
                      onChange={e => setRFormPriceForTwo(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <div className="flex items-center gap-2 pt-6">
                    <input
                      type="checkbox"
                      id="pureVegCheck"
                      checked={rFormIsVeg}
                      onChange={e => setRFormIsVeg(e.target.checked)}
                      className="w-4 h-4 rounded text-emerald-500 focus:ring-0 bg-slate-800 border-white/10"
                    />
                    <label htmlFor="pureVegCheck" className="text-xs font-semibold text-slate-300">Pure Vegetarian Outlet</label>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Short Description</label>
                  <input
                    type="text"
                    value={rFormDesc}
                    onChange={e => setRFormDesc(e.target.value)}
                    placeholder="Signature dishes, heritage, or specialties..."
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isRegisteringRestaurant}
                  className="w-full py-3 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold text-xs shadow-lg shadow-orange-600/30 transition flex items-center justify-center gap-2 mt-4"
                >
                  {isRegisteringRestaurant ? <Loader2 className="w-4 h-4 animate-spin" /> : <Store className="w-4 h-4" />}
                  <span>Register Restaurant</span>
                </button>
              </form>
            </div>
          ) : (
            /* RESTAURANT KITCHEN DASHBOARD */
            <div className="space-y-6">
              {/* Partner Header Card */}
              <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-bold text-white">{partnerRestaurant.name}</h2>
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                      partnerRestaurant.is_open ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {partnerRestaurant.is_open ? 'Accepting Orders' : 'Kitchen Closed'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    {partnerRestaurant.cuisine} • {partnerRestaurant.service_area} • Price for Two: ₹{partnerRestaurant.price_for_two_inr}
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={handleToggleOpen}
                    className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition ${
                      partnerRestaurant.is_open
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30'
                        : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30'
                    }`}
                  >
                    <Power className="w-3.5 h-3.5" />
                    <span>{partnerRestaurant.is_open ? 'Pause Online Orders' : 'Open Restaurant'}</span>
                  </button>

                  <button
                    onClick={() => {
                      setEditingMenuItemId(null);
                      setMItemName('');
                      setMItemCat('Main Course');
                      setMItemPriceRupees('');
                      setMItemDesc('');
                      setMItemIsVeg(true);
                      setMItemImage('https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=600');
                      setIsMenuItemModalOpen(true);
                    }}
                    className="px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold shadow-lg shadow-orange-600/30 flex items-center gap-1.5 transition"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Add Dish</span>
                  </button>
                </div>
              </div>

              {/* INCOMING KITCHEN ORDERS */}
              <div className="p-5 rounded-3xl bg-slate-900/50 border border-white/10 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <Clock className="w-4 h-4 text-orange-400" />
                      <span>Live Kitchen Orders ({partnerOrders.length})</span>
                    </h3>
                    <p className="text-[11px] text-slate-400">Process preparation states and hand off to delivery.</p>
                  </div>
                  <button onClick={fetchPartnerData} className="p-2 rounded-xl bg-white/5 text-slate-300 hover:text-white">
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>

                {partnerOrders.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-500">
                    No active food orders at this moment.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {partnerOrders.map(ord => (
                      <div key={ord.id} className="p-4 rounded-2xl bg-slate-800/40 border border-white/5 space-y-3">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-2.5">
                          <div>
                            <span className="text-xs font-mono font-bold text-white">Order #{ord.id.slice(-8)}</span>
                            <p className="text-[10px] text-slate-400">
                              Customer: {ord.customer_name} ({ord.customer_email})
                            </p>
                          </div>
                          <span className={`px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                            ord.order_status === 'delivered' ? 'bg-emerald-500/20 text-emerald-400' :
                            ord.order_status === 'out_for_delivery' ? 'bg-cyan-500/20 text-cyan-400' :
                            ord.order_status === 'preparing' ? 'bg-amber-500/20 text-amber-400' :
                            ord.order_status === 'confirmed' ? 'bg-blue-500/20 text-blue-400' :
                            ord.order_status === 'cancelled' ? 'bg-red-500/20 text-red-400' :
                            'bg-orange-500/20 text-orange-400'
                          }`}>
                            {ord.order_status.replace('_', ' ')}
                          </span>
                        </div>

                        {/* Items in food order */}
                        <div className="space-y-1">
                          {ord.items.map((it, idx) => (
                            <div key={idx} className="flex items-center justify-between text-xs text-slate-300">
                              <span>{it.name} × {it.quantity}</span>
                              <span className="font-semibold text-white">₹{(it.total_price_paise / 100).toFixed(2)}</span>
                            </div>
                          ))}
                        </div>

                        {/* Order status actions */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-white/5 text-xs">
                          <span className="text-slate-400 text-[11px] truncate max-w-sm">
                            Delivery to: {ord.delivery_address}
                          </span>

                          <div className="flex items-center gap-2 shrink-0">
                            {ord.order_status === 'placed' && (
                              <button
                                onClick={() => handleUpdateRestaurantOrderStatus(ord.id, 'confirmed')}
                                className="px-3 py-1 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 border border-blue-500/30 font-semibold text-[11px]"
                              >
                                Accept Order
                              </button>
                            )}
                            {ord.order_status === 'confirmed' && (
                              <button
                                onClick={() => handleUpdateRestaurantOrderStatus(ord.id, 'preparing')}
                                className="px-3 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 font-semibold text-[11px]"
                              >
                                Start Preparing
                              </button>
                            )}
                            {ord.order_status === 'preparing' && (
                              <button
                                onClick={() => handleUpdateRestaurantOrderStatus(ord.id, 'out_for_delivery')}
                                className="px-3 py-1 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/30 font-semibold text-[11px]"
                              >
                                Out for Delivery
                              </button>
                            )}
                            {ord.order_status === 'out_for_delivery' && (
                              <button
                                onClick={() => handleUpdateRestaurantOrderStatus(ord.id, 'delivered')}
                                className="px-3 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 font-semibold text-[11px]"
                              >
                                Mark Delivered
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* RESTAURANT MENU ITEMS LIST */}
              <div className="p-5 rounded-3xl bg-slate-900/50 border border-white/10 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <Utensils className="w-4 h-4 text-orange-400" />
                      <span>Live Menu Catalog ({partnerRestaurant.menu?.length || 0})</span>
                    </h3>
                    <p className="text-[11px] text-slate-400">Available dishes and pricing shown to customers.</p>
                  </div>
                </div>

                {(!partnerRestaurant.menu || partnerRestaurant.menu.length === 0) ? (
                  <div className="py-8 text-center text-xs text-slate-500">
                    No dishes added to your menu yet. Click "Add Dish" above to create your restaurant menu.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {partnerRestaurant.menu.map(m => (
                      <div key={m.id} className="p-4 rounded-2xl bg-slate-800/40 border border-white/5 space-y-3 flex flex-col justify-between">
                        <div className="flex gap-3">
                          <img
                            src={m.image_url || 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=600'}
                            alt={m.name}
                            className="w-16 h-16 rounded-xl object-cover bg-slate-900 shrink-0"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              <span className={`w-2 h-2 rounded-full ${m.is_veg ? 'bg-emerald-400' : 'bg-rose-500'}`} />
                              <span className="text-[10px] text-slate-400 uppercase font-semibold">{m.category}</span>
                            </div>
                            <h4 className="text-xs font-bold text-white truncate">{m.name}</h4>
                            <p className="text-sm font-extrabold text-white mt-1">₹{m.price_inr.toFixed(2)}</p>
                          </div>
                        </div>

                        <div className="flex items-center justify-between pt-2 border-t border-white/5 text-xs">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${m.is_available ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                            {m.is_available ? 'Available' : 'Unavailable'}
                          </span>

                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => {
                                setEditingMenuItemId(m.id);
                                setMItemName(m.name);
                                setMItemCat(m.category);
                                setMItemPriceRupees(m.price_inr.toString());
                                setMItemDesc(m.description || '');
                                setMItemIsVeg(m.is_veg);
                                setMItemImage(m.image_url || '');
                                setIsMenuItemModalOpen(true);
                              }}
                              className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white"
                              title="Edit Dish"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteMenuItem(m.id)}
                              className="p-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400"
                              title="Delete Dish"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* MENU ITEM CREATE / EDIT MODAL */}
          {isMenuItemModalOpen && (
            <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-white/10 rounded-3xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6 space-y-5 animate-scaleUp">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold text-white">
                    {editingMenuItemId ? 'Edit Dish' : 'Add New Menu Dish'}
                  </h3>
                  <button onClick={() => setIsMenuItemModalOpen(false)} className="p-1 rounded-full bg-white/5 text-slate-400 hover:text-white">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleSaveMenuItem} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Dish Name *</label>
                    <input
                      type="text"
                      required
                      value={mItemName}
                      onChange={e => setMItemName(e.target.value)}
                      placeholder="e.g. Special Dum Mutton Biryani"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">Category *</label>
                      <input
                        type="text"
                        required
                        value={mItemCat}
                        onChange={e => setMItemCat(e.target.value)}
                        placeholder="e.g. Starters, Main Course"
                        className="w-full px-3.5 py-2 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">Price (in Rupees ₹) *</label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        value={mItemPriceRupees}
                        onChange={e => setMItemPriceRupees(e.target.value)}
                        placeholder="e.g. 299.00"
                        className="w-full px-3.5 py-2 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Image URL</label>
                    <input
                      type="url"
                      value={mItemImage}
                      onChange={e => setMItemImage(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="itemVegCheck"
                      checked={mItemIsVeg}
                      onChange={e => setMItemIsVeg(e.target.checked)}
                      className="w-4 h-4 rounded text-emerald-500 focus:ring-0 bg-slate-800 border-white/10"
                    />
                    <label htmlFor="itemVegCheck" className="text-xs font-semibold text-slate-300">Vegetarian Dish</label>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Description</label>
                    <textarea
                      rows={2}
                      value={mItemDesc}
                      onChange={e => setMItemDesc(e.target.value)}
                      placeholder="Ingredients, preparation style..."
                      className="w-full px-3.5 py-2 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-orange-500 resize-none"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSavingMenuItem}
                    className="w-full py-3 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold text-xs shadow-lg shadow-orange-600/30 transition flex items-center justify-center gap-2"
                  >
                    {isSavingMenuItem ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                    <span>{editingMenuItemId ? 'Save Dish Changes' : 'Add Dish to Menu'}</span>
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>
      ) : selectedRestaurant ? (
        /* VIEW: RESTAURANT MENU */
        <div className="space-y-6">
          <button
            onClick={() => setSelectedRestaurant(null)}
            className="text-xs text-orange-400 hover:text-orange-300 flex items-center space-x-1 font-semibold"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to All Restaurants</span>
          </button>

          {/* Restaurant Banner */}
          <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex items-center space-x-4">
              {selectedRestaurant.image_url && (
                <img
                  src={selectedRestaurant.image_url}
                  alt={selectedRestaurant.name}
                  className="w-20 h-20 rounded-2xl object-cover border border-white/10"
                />
              )}
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  {selectedRestaurant.name}
                  {selectedRestaurant.is_veg && (
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 border border-emerald-300" title="Pure Veg" />
                  )}
                </h2>
                <p className="text-xs text-slate-400 mt-1">{selectedRestaurant.cuisine}</p>
                <p className="text-xs text-slate-400 mt-0.5">{selectedRestaurant.address}</p>
                <div className="flex items-center space-x-3 text-xs text-slate-300 mt-2">
                  <span className="flex items-center gap-1 text-amber-400 font-bold">
                    <Star className="w-3.5 h-3.5 fill-current" /> {selectedRestaurant.rating}
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1 text-slate-400">
                    <Clock className="w-3.5 h-3.5" /> {selectedRestaurant.time_mins} mins delivery
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Menu Items List */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <h3 className="text-sm uppercase tracking-wider text-slate-400 font-bold">Menu Offerings</h3>
              <div className="space-y-3">
                {selectedRestaurant.menu && selectedRestaurant.menu.length > 0 ? (
                  selectedRestaurant.menu.map((dish) => (
                    <div
                      key={dish.id}
                      className="p-4 rounded-2xl bg-slate-900/40 border border-white/5 flex items-start justify-between gap-4 hover:border-white/15 transition"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span
                            className={`w-2.5 h-2.5 rounded-full border ${
                              dish.is_veg ? 'bg-emerald-500 border-emerald-400' : 'bg-rose-500 border-rose-400'
                            }`}
                          />
                          <h4 className="text-sm font-semibold text-white">{dish.name}</h4>
                          <span className="text-[10px] text-slate-400 px-2 py-0.5 rounded bg-white/5 font-mono">
                            {dish.category}
                          </span>
                        </div>
                        <p className="text-xs font-bold text-slate-200 font-mono">₹{dish.price_inr.toFixed(2)}</p>
                        {dish.description && (
                          <p className="text-xs text-slate-400 leading-relaxed max-w-md">{dish.description}</p>
                        )}
                      </div>

                      <button
                        onClick={() => handleAddToCart(selectedRestaurant, dish)}
                        className="px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-xl text-xs font-semibold flex items-center space-x-1 shrink-0 transition shadow"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>Add</span>
                      </button>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-500 py-6">No menu items listed currently.</p>
                )}
              </div>
            </div>

            {/* Cart Column */}
            <div>
              {renderCartPanel()}
            </div>
          </div>
        </div>
      ) : (
        /* VIEW: BROWSE RESTAURANTS */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Restaurants Column */}
          <div className="lg:col-span-2 space-y-4">
            {/* Search and Veg Toggle */}
            <div className="flex items-center gap-3">
              <div className="relative flex-1">
                <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search restaurants, dosas, Andhra biryani..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-white/10 rounded-2xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-orange-500"
                />
              </div>
              <button
                onClick={() => setFilterVegOnly(!filterVegOnly)}
                className={`px-3 py-2 rounded-2xl text-xs font-semibold border transition flex items-center gap-1.5 shrink-0 ${
                  filterVegOnly
                    ? 'bg-emerald-600 text-white border-emerald-500'
                    : 'bg-white/5 text-slate-300 border-white/10 hover:bg-white/10'
                }`}
              >
                <span className="w-2.5 h-2.5 rounded-full border border-emerald-400 bg-emerald-500" />
                <span>Pure Veg</span>
              </button>
            </div>

            {restaurantError && (
              <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{restaurantError}</span>
              </div>
            )}

            {isLoadingRestaurants ? (
              <div className="flex justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-orange-400" />
              </div>
            ) : restaurants.length === 0 ? (
              <div className="p-8 text-center bg-slate-900/40 border border-white/5 rounded-2xl space-y-2">
                <p className="text-sm font-semibold text-slate-300">No restaurants found matching filters</p>
                <p className="text-xs text-slate-500">Try turning off Pure Veg or changing your search keyword.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {restaurants.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => handleOpenRestaurant(r.id)}
                    className="rounded-2xl overflow-hidden border border-white/5 bg-slate-900/40 hover:border-orange-500/40 transition-all cursor-pointer group flex flex-col justify-between"
                  >
                    <div>
                      <div className="relative h-44 w-full bg-slate-950 overflow-hidden">
                        {r.image_url ? (
                          <img
                            src={r.image_url}
                            alt={r.name}
                            className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-slate-600">
                            <Utensils className="w-8 h-8" />
                          </div>
                        )}
                        <span className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/80 text-[10px] text-white font-mono">
                          {r.time_mins} mins
                        </span>
                        {r.is_veg && (
                          <span className="absolute top-2 left-2 px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/40 text-[10px] text-emerald-300 font-semibold">
                            Pure Veg
                          </span>
                        )}
                      </div>

                      <div className="p-4 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-bold text-white group-hover:text-orange-400 transition">
                            {r.name}
                          </h4>
                          <span className="flex items-center gap-1 text-xs text-amber-400 font-bold">
                            <Star className="w-3.5 h-3.5 fill-current" /> {r.rating}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400">{r.cuisine}</p>
                        <p className="text-[10px] text-slate-500">₹{r.price_for_two_inr} for two • {r.service_area}</p>
                      </div>
                    </div>

                    <div className="p-4 pt-0">
                      <div className="w-full py-2 bg-white/5 group-hover:bg-orange-600 group-hover:text-white text-slate-200 rounded-xl text-xs font-semibold border border-white/10 transition flex items-center justify-center gap-1">
                        <span>View Full Menu</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Cart & Checkout Panel */}
          <div>
            {renderCartPanel()}
          </div>
        </div>
      )}
    </div>
  );

  function renderCartPanel() {
    return (
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-white/10 backdrop-blur-md space-y-4 sticky top-4">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <ShoppingBag className="w-4 h-4 text-orange-400" />
            <span>Super Food Cart</span>
          </h3>
          <span className="text-xs text-slate-400 font-mono">
            {cart.reduce((a, b) => a + b.qty, 0)} items
          </span>
        </div>

        {cart.length === 0 ? (
          <p className="text-xs text-slate-500 text-center py-6">Your cart is empty. Add delicacies from restaurant menus!</p>
        ) : (
          <div className="space-y-3">
            <div className="text-[11px] text-orange-400 font-semibold border-b border-white/5 pb-1">
              Ordering from: {cart[0].restaurantName}
            </div>

            {cart.map((item) => (
              <div key={item.itemId} className="flex items-center justify-between text-xs py-1.5 border-b border-white/5">
                <div>
                  <h5 className="font-semibold text-slate-200">{item.name}</h5>
                  <span className="text-[10px] text-slate-400">₹{(item.pricePaise / 100).toFixed(2)} each</span>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleUpdateQty(item.itemId, -1)}
                    className="p-1 rounded bg-white/5 hover:bg-white/10 text-slate-300"
                  >
                    <Minus className="w-3 h-3" />
                  </button>
                  <span className="text-xs font-bold text-white w-4 text-center">{item.qty}</span>
                  <button
                    onClick={() => handleUpdateQty(item.itemId, 1)}
                    className="p-1 rounded bg-white/5 hover:bg-white/10 text-slate-300"
                  >
                    <Plus className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}

            {/* Calculations Breakdown */}
            <div className="pt-2 space-y-1.5 text-xs text-slate-400 border-t border-white/5">
              <div className="flex justify-between">
                <span>Items Subtotal:</span>
                <span className="font-mono">₹{(cartSubtotalPaise / 100).toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span>Flat Delivery Fee:</span>
                <span className="font-mono">₹{(deliveryFeePaise / 100).toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span>Restaurant GST (5%):</span>
                <span className="font-mono">₹{(taxesPaise / 100).toFixed(2)}</span>
              </div>
              <div className="flex justify-between font-bold text-sm text-white pt-2 border-t border-white/10">
                <span>Grand Total:</span>
                <span className="text-emerald-400 font-mono">₹{(grandTotalPaise / 100).toFixed(2)}</span>
              </div>
            </div>

            {/* Address Input */}
            <div className="space-y-1 pt-1">
              <label className="text-[11px] text-slate-400 font-medium">Delivery Address</label>
              <textarea
                value={deliveryAddress}
                onChange={(e) => setDeliveryAddress(e.target.value)}
                rows={2}
                maxLength={300}
                className="w-full bg-slate-800 border border-white/10 rounded-xl p-2 text-xs text-slate-200 focus:outline-none focus:border-orange-500 resize-none"
              />
            </div>

            {/* Payment Mode Selector (Phase 4H: Cash on Delivery or Test Mode) */}
            <div className="space-y-1">
              <label className="text-[11px] text-slate-400 font-medium">Payment Mode</label>
              <select
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value as any)}
                className="w-full bg-slate-800 border border-white/10 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-orange-500"
              >
                <option value="cod">Cash on Delivery (Pay upon delivery)</option>
                <option value="test_mode_upi">Test Mode UPI (Development Simulation)</option>
                <option value="test_mode_card">Test Mode Card (Development Simulation)</option>
              </select>
              {paymentMethod.startsWith('test_mode') && (
                <p className="text-[10px] text-amber-400/90 italic">
                  Note: This is a sandbox simulated checkout test mode. No real payment is deducted.
                </p>
              )}
            </div>

            {checkoutError && (
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-1.5">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{checkoutError}</span>
              </div>
            )}

            <button
              onClick={handlePlaceOrder}
              disabled={isPlacingOrder || cart.length === 0}
              className="w-full py-2.5 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white rounded-xl text-xs font-bold transition shadow-lg mt-2 flex items-center justify-center space-x-1.5 disabled:opacity-50"
            >
              {isPlacingOrder ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Validating & Placing...</span>
                </>
              ) : (
                <span>Confirm & Place Order</span>
              )}
            </button>
          </div>
        )}
      </div>
    );
  }
};
