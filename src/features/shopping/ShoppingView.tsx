import React, { useState, useEffect, useCallback } from 'react';
import { 
  ShoppingBag, Search, Star, Filter, Heart, 
  Check, ArrowRight, Zap, ShieldCheck, Plus, Minus, 
  MapPin, CheckCircle2, ChevronRight, X, Loader2, AlertCircle, 
  ArrowLeft, RefreshCw, Receipt, Ban, Package, Truck, Clock, Sparkles,
  Store, BarChart3, Edit3, Trash2, CheckCircle, AlertTriangle
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { 
  apiClient, 
  type ProductResponse, 
  type ShoppingOrderResponse, 
  type CreateShoppingOrderPayload,
  type SellerResponse,
  type SellerDashboardResponse,
  type ProductCreatePayload,
  type ProductUpdatePayload
} from '../../services/apiClient';

interface CartItem {
  productId: string;
  name: string;
  brand: string;
  sku: string;
  pricePaise: number;
  qty: number;
  imageUrl?: string;
  maxStock: number;
}

export const ShoppingView: React.FC = () => {
  const { user, isAuthenticated, openLoginModal } = useAuth();

  // Active Tab
  const [activeTab, setActiveTab] = useState<'catalog' | 'orders' | 'seller'>('catalog');

  // Product Catalog State
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [isLoadingProducts, setIsLoadingProducts] = useState(true);
  const [productError, setProductError] = useState<string | null>(null);

  // Filters & Sorting
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [sortOption, setSortOption] = useState<'featured' | 'price_asc' | 'price_desc' | 'rating' | 'newest'>('featured');
  const [priceRange, setPriceRange] = useState<string>('all');

  // Selected Product Detail Modal
  const [selectedProduct, setSelectedProduct] = useState<ProductResponse | null>(null);

  // Cart State (Persisted in LocalStorage, verified authoritatively by backend during checkout)
  const [cart, setCart] = useState<CartItem[]>(() => {
    try {
      const saved = localStorage.getItem('super_ai_shopping_cart');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [isCartOpen, setIsCartOpen] = useState(false);
  const [cartAlert, setCartAlert] = useState<string | null>(null);

  // Checkout Form State
  const [shippingFullName, setShippingFullName] = useState(user?.full_name || 'Karthik Rao');
  const [shippingPhone, setShippingPhone] = useState('+919876543210');
  const [shippingAddress, setShippingAddress] = useState('Flat 402, Highrise Heights, 100ft Road, Indiranagar');
  const [shippingCity, setShippingCity] = useState('Bengaluru');
  const [shippingPostalCode, setShippingPostalCode] = useState('560038');
  const [paymentMethod, setPaymentMethod] = useState<'cod' | 'test_mode_upi' | 'test_mode_card'>('cod');
  const [isPlacingOrder, setIsPlacingOrder] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [lastPlacedOrder, setLastPlacedOrder] = useState<ShoppingOrderResponse | null>(null);

  // Orders History State
  const [orders, setOrders] = useState<ShoppingOrderResponse[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);
  const [cancellingOrderId, setCancellingOrderId] = useState<string | null>(null);

  // Seller Operations State (Phase 4)
  const [sellerProfile, setSellerProfile] = useState<SellerResponse | null>(null);
  const [sellerDashboard, setSellerDashboard] = useState<SellerDashboardResponse | null>(null);
  const [sellerProducts, setSellerProducts] = useState<ProductResponse[]>([]);
  const [sellerOrders, setSellerOrders] = useState<ShoppingOrderResponse[]>([]);
  const [isLoadingSeller, setIsLoadingSeller] = useState(false);
  const [isRegisteringSeller, setIsRegisteringSeller] = useState(false);
  const [sellerError, setSellerError] = useState<string | null>(null);
  const [sellerSuccess, setSellerSuccess] = useState<string | null>(null);

  // Seller Onboarding Form
  const [bizName, setBizName] = useState('');
  const [bizCategory, setBizCategory] = useState('Electronics');
  const [bizPhone, setBizPhone] = useState('+919876543299');
  const [bizAddress, setBizAddress] = useState('88 Merchant Lane, Indiranagar');
  const [bizCity, setBizCity] = useState('Bengaluru');
  const [bizState, setBizState] = useState('Karnataka');
  const [bizPincode, setBizPincode] = useState('560038');
  const [bizGstin, setBizGstin] = useState('29ABCDE1234F1Z5');

  // Seller New Product Modal Form
  const [isProductModalOpen, setIsProductModalOpen] = useState(false);
  const [editingProductId, setEditingProductId] = useState<string | null>(null);
  const [prodFormName, setProdFormName] = useState('');
  const [prodFormBrand, setProdFormBrand] = useState('');
  const [prodFormCat, setProdFormCat] = useState('Electronics');
  const [prodFormDesc, setProdFormDesc] = useState('');
  const [prodFormPriceRupees, setProdFormPriceRupees] = useState('');
  const [prodFormStock, setProdFormStock] = useState('10');
  const [prodFormImage, setProdFormImage] = useState('https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600');
  const [isSavingProduct, setIsSavingProduct] = useState(false);

  const categories = ['All', 'Electronics', 'Fashion', 'Footwear', 'Home & Kitchen', 'Accessories'];

  // Save Cart to LocalStorage
  useEffect(() => {
    localStorage.setItem('super_ai_shopping_cart', JSON.stringify(cart));
  }, [cart]);

  // Fetch Products
  const fetchProducts = useCallback(async () => {
    setIsLoadingProducts(true);
    setProductError(null);
    try {
      let minPrice: number | undefined;
      let maxPrice: number | undefined;

      if (priceRange === 'under_2k') {
        maxPrice = 200000;
      } else if (priceRange === '2k_to_10k') {
        minPrice = 200000;
        maxPrice = 1000000;
      } else if (priceRange === 'above_10k') {
        minPrice = 1000000;
      }

      const data = await apiClient.listProducts({
        category: selectedCategory === 'All' ? undefined : selectedCategory,
        search: searchQuery.trim() || undefined,
        minPrice,
        maxPrice,
        sort: sortOption,
        limit: 30
      });
      setProducts(data);
    } catch (err: any) {
      setProductError(err.message || 'Failed to load products');
    } finally {
      setIsLoadingProducts(false);
    }
  }, [selectedCategory, searchQuery, priceRange, sortOption]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  // Fetch Orders
  const fetchOrders = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingOrders(true);
    try {
      const data = await apiClient.listShoppingOrders(25);
      setOrders(data);
    } catch {
      setOrders([]);
    } finally {
      setIsLoadingOrders(false);
    }
  }, [isAuthenticated]);

  // Fetch Seller Hub Data
  const fetchSellerData = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingSeller(true);
    setSellerError(null);
    try {
      const profile = await apiClient.getSellerProfile();
      setSellerProfile(profile);
      const [dash, prods, ords] = await Promise.all([
        apiClient.getSellerDashboard(),
        apiClient.listSellerProducts(),
        apiClient.listSellerOrders()
      ]);
      setSellerDashboard(dash);
      setSellerProducts(prods);
      setSellerOrders(ords);
    } catch (err: any) {
      if (err.message && err.message.includes('not found')) {
        setSellerProfile(null);
      } else {
        setSellerError(err.message || 'Could not load seller data');
      }
    } finally {
      setIsLoadingSeller(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (activeTab === 'seller') {
      fetchSellerData();
    }
  }, [activeTab, fetchSellerData]);

  // Handle Seller Registration
  const handleRegisterSeller = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsRegisteringSeller(true);
    setSellerError(null);
    try {
      const res = await apiClient.registerSeller({
        business_name: bizName.trim(),
        business_category: bizCategory.trim(),
        contact_phone: bizPhone.trim(),
        business_address: bizAddress.trim(),
        city: bizCity.trim(),
        state: bizState.trim(),
        pincode: bizPincode.trim(),
        gstin_or_pan: bizGstin.trim() || undefined
      });
      setSellerProfile(res);
      setSellerSuccess('Seller onboarding completed! You can now manage catalog and orders.');
      fetchSellerData();
      setTimeout(() => setSellerSuccess(null), 3500);
    } catch (err: any) {
      setSellerError(err.message || 'Failed to complete seller registration');
    } finally {
      setIsRegisteringSeller(false);
    }
  };

  // Handle Save Product (Create or Edit)
  const handleSaveSellerProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    const priceRupees = parseFloat(prodFormPriceRupees);
    if (isNaN(priceRupees) || priceRupees <= 0) {
      setSellerError('Please enter a valid price in rupees.');
      return;
    }
    const pricePaise = Math.round(priceRupees * 100);
    const stock = parseInt(prodFormStock) || 0;

    setIsSavingProduct(true);
    setSellerError(null);

    try {
      if (editingProductId) {
        await apiClient.updateSellerProduct(editingProductId, {
          name: prodFormName.trim(),
          brand: prodFormBrand.trim(),
          category: prodFormCat.trim(),
          description: prodFormDesc.trim(),
          price_paise: pricePaise,
          stock: stock,
          images: [prodFormImage.trim()]
        });
        setSellerSuccess('Product updated successfully!');
      } else {
        await apiClient.createSellerProduct({
          name: prodFormName.trim(),
          brand: prodFormBrand.trim(),
          category: prodFormCat.trim(),
          description: prodFormDesc.trim(),
          price_paise: pricePaise,
          stock: stock,
          images: [prodFormImage.trim()]
        });
        setSellerSuccess('New product published to live Zaviro marketplace!');
      }

      setIsProductModalOpen(false);
      setEditingProductId(null);
      fetchSellerData();
      fetchProducts(); // Update customer catalog view as well
      setTimeout(() => setSellerSuccess(null), 3000);
    } catch (err: any) {
      setSellerError(err.message || 'Failed to save product.');
    } finally {
      setIsSavingProduct(false);
    }
  };

  // Delete product
  const handleDeleteProduct = async (productId: string) => {
    if (!window.confirm('Are you sure you want to unpublish this product?')) return;
    try {
      await apiClient.deleteSellerProduct(productId);
      fetchSellerData();
      fetchProducts();
    } catch (err: any) {
      setSellerError(err.message || 'Failed to delete product.');
    }
  };

  // Update seller order status
  const handleUpdateSellerOrderStatus = async (orderId: string, newStatus: 'processing' | 'shipped' | 'delivered') => {
    try {
      await apiClient.updateSellerOrderStatus(orderId, newStatus);
      fetchSellerData();
      setSellerSuccess(`Order status updated to ${newStatus}!`);
      setTimeout(() => setSellerSuccess(null), 3000);
    } catch (err: any) {
      setSellerError(err.message || 'Status transition failed.');
    }
  };

  // Cart operations
  const addToCart = (prod: ProductResponse) => {
    if (prod.stock <= 0 || !prod.is_available) {
      setCartAlert(`Sorry, "${prod.name}" is currently out of stock.`);
      setTimeout(() => setCartAlert(null), 3000);
      return;
    }

    setCart(prev => {
      const existing = prev.find(item => item.productId === prod.id);
      if (existing) {
        if (existing.qty >= prod.stock) {
          setCartAlert(`Maximum stock reached for "${prod.name}" (${prod.stock} available)`);
          setTimeout(() => setCartAlert(null), 3000);
          return prev;
        }
        return prev.map(item =>
          item.productId === prod.id
            ? { ...item, qty: item.qty + 1 }
            : item
        );
      }
      return [...prev, {
        productId: prod.id,
        name: prod.name,
        brand: prod.brand,
        sku: prod.sku,
        pricePaise: prod.price_paise,
        qty: 1,
        imageUrl: prod.images?.[0],
        maxStock: prod.stock
      }];
    });

    setCartAlert(`Added "${prod.name}" to cart`);
    setTimeout(() => setCartAlert(null), 2500);
  };

  const updateCartQty = (productId: string, delta: number) => {
    setCart(prev => {
      return prev.map(item => {
        if (item.productId === productId) {
          const newQty = item.qty + delta;
          if (newQty <= 0) return null;
          if (newQty > item.maxStock) {
            setCartAlert(`Maximum available stock is ${item.maxStock}`);
            setTimeout(() => setCartAlert(null), 2500);
            return item;
          }
          return { ...item, qty: newQty };
        }
        return item;
      }).filter(Boolean) as CartItem[];
    });
  };

  const removeFromCart = (productId: string) => {
    setCart(prev => prev.filter(i => i.productId !== productId));
  };

  // Cart financial preview in integer paise
  const cartSubtotalPaise = cart.reduce((acc, it) => acc + (it.pricePaise * it.qty), 0);
  const cartShippingPaise = cartSubtotalPaise >= 99900 || cartSubtotalPaise === 0 ? 0 : 4900;
  const cartTaxesPaise = Math.round(cartSubtotalPaise * 0.18);
  const cartTotalPaise = cartSubtotalPaise + cartShippingPaise + cartTaxesPaise;
  const cartTotalCount = cart.reduce((acc, it) => acc + it.qty, 0);

  // Place Order
  const handlePlaceOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }

    if (cart.length === 0) return;

    if (!shippingFullName.trim() || !shippingPhone.trim() || !shippingAddress.trim() || !shippingCity.trim() || !shippingPostalCode.trim()) {
      setCheckoutError('Please provide complete recipient and shipping address details.');
      return;
    }

    setIsPlacingOrder(true);
    setCheckoutError(null);

    const idempotencyKey = `shop_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

    const payload: CreateShoppingOrderPayload = {
      items: cart.map(c => ({
        product_id: c.productId,
        quantity: c.qty
      })),
      shipping_full_name: shippingFullName.trim(),
      shipping_phone: shippingPhone.trim(),
      shipping_address: shippingAddress.trim(),
      shipping_city: shippingCity.trim(),
      shipping_postal_code: shippingPostalCode.trim(),
      payment_method: paymentMethod,
      idempotency_key: idempotencyKey
    };

    try {
      const order = await apiClient.placeShoppingOrder(payload);
      setLastPlacedOrder(order);
      setCart([]);
      setIsCartOpen(false);
      fetchProducts(); // Refresh stock counts in UI
    } catch (err: any) {
      setCheckoutError(err.message || 'Failed to place order. Please review stock and retry.');
    } finally {
      setIsPlacingOrder(false);
    }
  };

  // Cancel Order
  const handleCancelOrder = async (orderId: string) => {
    if (!window.confirm('Are you sure you want to cancel this order? Stock will be restored.')) return;
    setCancellingOrderId(orderId);
    try {
      const updated = await apiClient.cancelShoppingOrder(orderId);
      setOrders(prev => prev.map(o => o.id === orderId ? updated : o));
      fetchProducts(); // Refresh stock
    } catch (err: any) {
      alert(err.message || 'Unable to cancel order');
    } finally {
      setCancellingOrderId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto w-full px-2 sm:px-4 pb-16">
      {/* Top Banner & Mode Selector */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-rose-950/40 via-slate-900/90 to-amber-950/40 border border-rose-500/20 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-rose-400 text-xs font-semibold uppercase tracking-wider">
            <ShoppingBag className="w-4 h-4" />
            <span>Super Mall & E-Commerce</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Verified Brands & Native Catalog</h1>
          <p className="text-xs text-slate-400 mt-1 flex items-center gap-2">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> 100% Genuine Inventory • Free Delivery on Orders Over ₹999 • All Prices in Integer Paise
          </p>
        </div>

        {/* Tab & Cart Trigger */}
        <div className="flex items-center gap-3">
          <div className="flex items-center bg-white/5 p-1 rounded-2xl border border-white/10">
            <button
              onClick={() => setActiveTab('catalog')}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition ${
                activeTab === 'catalog'
                  ? 'bg-rose-600 text-white shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Browse Catalog
            </button>
            <button
              onClick={() => {
                if (!isAuthenticated) openLoginModal();
                else setActiveTab('orders');
              }}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
                activeTab === 'orders'
                  ? 'bg-rose-600 text-white shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Package className="w-3.5 h-3.5" />
              <span>My Orders</span>
            </button>
            <button
              onClick={() => {
                if (!isAuthenticated) openLoginModal();
                else setActiveTab('seller');
              }}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
                activeTab === 'seller'
                  ? 'bg-rose-600 text-white shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Store className="w-3.5 h-3.5" />
              <span>Seller Hub</span>
            </button>
          </div>

          <button
            onClick={() => setIsCartOpen(true)}
            className="relative p-2.5 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white font-medium shadow-lg shadow-rose-600/30 flex items-center gap-2 text-xs transition"
          >
            <ShoppingBag className="w-4 h-4" />
            <span className="hidden sm:inline">Cart</span>
            {cartTotalCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-white text-rose-700 font-extrabold text-[10px]">
                {cartTotalCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Cart Toast Notification */}
      {cartAlert && (
        <div className="p-3.5 rounded-2xl bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2 animate-fadeIn">
          <CheckCircle2 className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{cartAlert}</span>
        </div>
      )}

      {/* CATALOG VIEW */}
      {activeTab === 'catalog' && (
        <div className="space-y-6">
          {/* Filters & Search Bar */}
          <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 p-4 rounded-2xl bg-slate-900/40 border border-white/5 backdrop-blur-md">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              <input
                type="text"
                placeholder="Search products by title, brand, or SKU..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-rose-500"
              />
            </div>

            {/* Category Dropdown / Scroll */}
            <div className="flex items-center gap-1.5 overflow-x-auto text-xs py-1">
              {categories.map(c => (
                <button
                  key={c}
                  onClick={() => setSelectedCategory(c)}
                  className={`px-3 py-1.5 rounded-xl whitespace-nowrap font-medium transition ${
                    selectedCategory === c
                      ? 'bg-rose-600 text-white shadow'
                      : 'bg-white/5 text-slate-300 hover:bg-white/10'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>

            {/* Sort & Price Range */}
            <div className="flex items-center gap-2">
              <select
                value={sortOption}
                onChange={e => setSortOption(e.target.value as any)}
                aria-label="Sort products by"
                className="px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-xs text-slate-300 focus:outline-none focus:border-rose-500"
              >
                <option value="featured">Featured</option>
                <option value="price_asc">Price: Low to High</option>
                <option value="price_desc">Price: High to Low</option>
                <option value="rating">Top Rated</option>
                <option value="newest">New Arrivals</option>
              </select>

              <select
                value={priceRange}
                onChange={e => setPriceRange(e.target.value)}
                aria-label="Filter by price range"
                className="px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-xs text-slate-300 focus:outline-none focus:border-rose-500"
              >
                <option value="all">All Prices</option>
                <option value="under_2k">Under ₹2,000</option>
                <option value="2k_to_10k">₹2,000 – ₹10,000</option>
                <option value="above_10k">Above ₹10,000</option>
              </select>
            </div>
          </div>

          {/* Product Grid State Handling */}
          {isLoadingProducts ? (
            <div className="py-24 text-center space-y-3">
              <Loader2 className="w-8 h-8 text-rose-500 animate-spin mx-auto" />
              <p className="text-xs text-slate-400">Loading verified products catalog...</p>
            </div>
          ) : productError ? (
            <div className="p-8 rounded-3xl bg-rose-500/10 border border-rose-500/20 text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-rose-400 mx-auto" />
              <p className="text-sm font-semibold text-rose-300">{productError}</p>
              <button
                onClick={fetchProducts}
                className="px-4 py-2 rounded-xl bg-rose-600 text-white text-xs font-semibold hover:bg-rose-500 transition"
              >
                Retry
              </button>
            </div>
          ) : products.length === 0 ? (
            <div className="py-20 text-center space-y-3 bg-slate-900/30 rounded-3xl border border-white/5">
              <Package className="w-10 h-10 text-slate-600 mx-auto" />
              <h3 className="text-sm font-semibold text-slate-300">No products matched your criteria</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Try clearing search filters or selecting another category.
              </p>
              <button
                onClick={() => { setSelectedCategory('All'); setSearchQuery(''); setPriceRange('all'); }}
                className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-xl text-xs text-slate-300"
              >
                Reset All Filters
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
              {products.map(p => (
                <div
                  key={p.id}
                  className="rounded-2xl border border-white/5 bg-slate-900/40 overflow-hidden hover:border-rose-500/30 transition-all group flex flex-col justify-between shadow-sm"
                >
                  <div>
                    {/* Image Box */}
                    <div 
                      onClick={() => setSelectedProduct(p)}
                      className="relative h-48 w-full overflow-hidden bg-slate-800 cursor-pointer"
                    >
                      <img 
                        src={p.images?.[0] || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600'} 
                        alt={p.name} 
                        className="w-full h-full object-cover group-hover:scale-105 transition duration-500" 
                      />
                      {p.is_seed_data && (
                        <span className="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-900/80 text-amber-300 border border-amber-500/30 text-[9px] font-bold">
                          DEVELOPMENT SEED
                        </span>
                      )}
                      {p.stock <= 5 && p.stock > 0 && (
                        <span className="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-500/30 text-[10px] font-bold">
                          Only {p.stock} left!
                        </span>
                      )}
                      {p.stock === 0 && (
                        <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-xs flex items-center justify-center">
                          <span className="px-3 py-1 rounded-xl bg-red-500/20 text-red-400 border border-red-500/30 text-xs font-bold">
                            OUT OF STOCK
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Metadata & Pricing */}
                    <div className="p-4 space-y-1.5">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-rose-400 font-bold uppercase">{p.brand}</span>
                        <span className="text-slate-500 font-mono">{p.sku}</span>
                      </div>
                      
                      <h4 
                        onClick={() => setSelectedProduct(p)}
                        className="text-xs font-semibold text-slate-100 line-clamp-2 cursor-pointer hover:text-rose-400 transition"
                      >
                        {p.name}
                      </h4>
                      
                      <div className="flex items-center space-x-1.5 text-xs pt-0.5">
                        <span className="text-emerald-400 font-bold">★ {p.rating}</span>
                        <span className="text-[10px] text-slate-500">({p.reviews_count} reviews)</span>
                      </div>

                      <div className="flex items-baseline space-x-2 pt-2">
                        <span className="text-base font-bold text-white">₹{p.price_inr.toLocaleString('en-IN')}</span>
                        {p.mrp_inr && p.mrp_inr > p.price_inr && (
                          <span className="text-xs text-slate-500 line-through">₹{p.mrp_inr.toLocaleString('en-IN')}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="p-4 pt-0">
                    <button
                      onClick={() => addToCart(p)}
                      disabled={p.stock <= 0 || !p.is_available}
                      className={`w-full py-2.5 rounded-xl text-xs font-semibold border transition flex items-center justify-center gap-1.5 ${
                        p.stock > 0 && p.is_available
                          ? 'bg-rose-600/90 hover:bg-rose-600 text-white border-rose-500/30 shadow-md shadow-rose-600/20'
                          : 'bg-white/5 text-slate-500 border-white/5 cursor-not-allowed'
                      }`}
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>{p.stock > 0 && p.is_available ? 'Add to Cart' : 'Out of Stock'}</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ORDERS VIEW */}
      {activeTab === 'orders' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Package className="w-5 h-5 text-rose-400" />
              <span>Your Orders & Shipments</span>
            </h2>
            <button
              onClick={fetchOrders}
              className="p-2 bg-white/5 hover:bg-white/10 rounded-xl text-slate-300 text-xs flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingOrders ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>

          {isLoadingOrders ? (
            <div className="py-20 text-center space-y-3">
              <Loader2 className="w-8 h-8 text-rose-500 animate-spin mx-auto" />
              <p className="text-xs text-slate-400">Loading order history...</p>
            </div>
          ) : orders.length === 0 ? (
            <div className="py-20 text-center space-y-3 bg-slate-900/30 rounded-3xl border border-white/5">
              <ShoppingBag className="w-10 h-10 text-slate-600 mx-auto" />
              <h3 className="text-sm font-semibold text-slate-300">No orders placed yet</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Explore our catalog and experience fast, transparent e-commerce shopping.
              </p>
              <button
                onClick={() => setActiveTab('catalog')}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold"
              >
                Start Shopping
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {orders.map(order => (
                <div 
                  key={order.id}
                  className="p-5 rounded-2xl bg-slate-900/40 border border-white/5 hover:border-white/10 transition space-y-4"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white font-mono">Order #{order.id.slice(-8)}</span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          order.order_status === 'delivered' ? 'bg-emerald-500/20 text-emerald-400' :
                          order.order_status === 'cancelled' ? 'bg-red-500/20 text-red-400' :
                          'bg-amber-500/20 text-amber-400'
                        }`}>
                          {order.order_status}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        Placed on {new Date(order.created_at).toLocaleString()} • {order.payment_method.toUpperCase()}
                      </p>
                    </div>

                    <div className="text-left sm:text-right">
                      <span className="text-base font-bold text-white">₹{order.total_inr.toLocaleString('en-IN')}</span>
                      <p className="text-[10px] text-slate-400">Includes Taxes & Delivery</p>
                    </div>
                  </div>

                  {/* Items snapshot */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                    {order.items.map((itm, idx) => (
                      <div key={idx} className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-800/40 border border-white/5">
                        {itm.image_url && (
                          <img src={itm.image_url} alt={itm.name} className="w-12 h-12 rounded-lg object-cover bg-slate-900" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-slate-200 truncate">{itm.name}</p>
                          <p className="text-[10px] text-slate-400">
                            {itm.quantity} × ₹{(itm.unit_price_paise / 100).toLocaleString('en-IN')}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Shipping address & cancellation */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 text-xs text-slate-400 border-t border-white/5">
                    <div className="flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                      <span className="truncate">Shipping to: {order.shipping_address}, {order.shipping_city} {order.shipping_postal_code}</span>
                    </div>

                    {(order.order_status === 'placed' || order.order_status === 'confirmed') && (
                      <button
                        onClick={() => handleCancelOrder(order.id)}
                        disabled={cancellingOrderId === order.id}
                        className="px-3 py-1.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 text-xs font-semibold flex items-center gap-1 transition shrink-0"
                      >
                        {cancellingOrderId === order.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Ban className="w-3 h-3" />}
                        <span>Cancel Order</span>
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SELLER HUB VIEW (Phase 4: Merchant Operations) */}
      {activeTab === 'seller' && (
        <div className="space-y-6">
          {sellerSuccess && (
            <div className="p-4 rounded-2xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{sellerSuccess}</span>
            </div>
          )}

          {sellerError && (
            <div className="p-4 rounded-2xl bg-red-500/20 border border-red-500/30 text-red-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{sellerError}</span>
            </div>
          )}

          {isLoadingSeller ? (
            <div className="py-20 text-center space-y-3">
              <Loader2 className="w-8 h-8 text-rose-500 animate-spin mx-auto" />
              <p className="text-xs text-slate-400">Loading Seller Operations & Live Metrics...</p>
            </div>
          ) : !sellerProfile ? (
            /* SELLER ONBOARDING REGISTRATION */
            <div className="max-w-2xl mx-auto p-6 sm:p-8 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl space-y-6">
              <div className="text-center space-y-2">
                <div className="w-12 h-12 rounded-2xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400 mx-auto">
                  <Store className="w-6 h-6" />
                </div>
                <h2 className="text-xl font-bold text-white">Join Zaviro Marketplace as a Seller</h2>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  Expand your business reach across India. Publish products, fulfill orders with transparent pricing, and receive direct settlement.
                </p>
              </div>

              <form onSubmit={handleRegisterSeller} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Business / Store Name *</label>
                    <input
                      type="text"
                      required
                      value={bizName}
                      onChange={e => setBizName(e.target.value)}
                      placeholder="e.g. Apex Tech Retail"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Category *</label>
                    <select
                      value={bizCategory}
                      onChange={e => setBizCategory(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                    >
                      <option value="Electronics">Electronics</option>
                      <option value="Fashion">Fashion</option>
                      <option value="Footwear">Footwear</option>
                      <option value="Home & Kitchen">Home & Kitchen</option>
                      <option value="Accessories">Accessories</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Contact Phone *</label>
                    <input
                      type="text"
                      required
                      value={bizPhone}
                      onChange={e => setBizPhone(e.target.value)}
                      placeholder="+91..."
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">GSTIN / Business PAN</label>
                    <input
                      type="text"
                      value={bizGstin}
                      onChange={e => setBizGstin(e.target.value)}
                      placeholder="e.g. 29ABCDE1234F1Z5"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Business Address *</label>
                  <input
                    type="text"
                    required
                    value={bizAddress}
                    onChange={e => setBizAddress(e.target.value)}
                    placeholder="Full street address..."
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                  />
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">City *</label>
                    <input
                      type="text"
                      required
                      value={bizCity}
                      onChange={e => setBizCity(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">State *</label>
                    <input
                      type="text"
                      required
                      value={bizState}
                      onChange={e => setBizState(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">PIN Code *</label>
                    <input
                      type="text"
                      required
                      value={bizPincode}
                      onChange={e => setBizPincode(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isRegisteringSeller}
                  className="w-full py-3 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs shadow-lg shadow-rose-600/30 transition flex items-center justify-center gap-2 mt-4"
                >
                  {isRegisteringSeller ? <Loader2 className="w-4 h-4 animate-spin" /> : <Store className="w-4 h-4" />}
                  <span>Complete Seller Onboarding</span>
                </button>
              </form>
            </div>
          ) : (
            /* SELLER DASHBOARD & MANAGEMENT PORTAL */
            <div className="space-y-6">
              {/* Header Overview Card */}
              <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-bold text-white">{sellerProfile.business_name}</h2>
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-bold uppercase tracking-wider">
                      {sellerProfile.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    {sellerProfile.business_category} • {sellerProfile.city}, {sellerProfile.state} • Contact: {sellerProfile.contact_phone}
                  </p>
                </div>

                <button
                  onClick={() => {
                    setEditingProductId(null);
                    setProdFormName('');
                    setProdFormBrand(sellerProfile.business_name);
                    setProdFormCat('Electronics');
                    setProdFormDesc('');
                    setProdFormPriceRupees('');
                    setProdFormStock('10');
                    setProdFormImage('https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600');
                    setIsProductModalOpen(true);
                  }}
                  className="px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-lg shadow-rose-600/30 flex items-center gap-2 transition"
                >
                  <Plus className="w-4 h-4" />
                  <span>Add New Product</span>
                </button>
              </div>

              {/* 5 Real Metric Cards */}
              {sellerDashboard && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <div className="p-4 rounded-2xl bg-slate-900/40 border border-white/5 space-y-1">
                    <span className="text-[11px] text-slate-400">Active Products</span>
                    <p className="text-xl font-bold text-white">{sellerDashboard.active_products}</p>
                    <p className="text-[10px] text-emerald-400">Live in catalog</p>
                  </div>
                  <div className="p-4 rounded-2xl bg-slate-900/40 border border-white/5 space-y-1">
                    <span className="text-[11px] text-slate-400">Low Stock Alert</span>
                    <p className="text-xl font-bold text-amber-400">{sellerDashboard.low_stock_products}</p>
                    <p className="text-[10px] text-slate-500">Stock ≤ 5 units</p>
                  </div>
                  <div className="p-4 rounded-2xl bg-slate-900/40 border border-white/5 space-y-1">
                    <span className="text-[11px] text-slate-400">Pending Orders</span>
                    <p className="text-xl font-bold text-rose-400">{sellerDashboard.pending_orders}</p>
                    <p className="text-[10px] text-slate-500">Requires fulfillment</p>
                  </div>
                  <div className="p-4 rounded-2xl bg-slate-900/40 border border-white/5 space-y-1">
                    <span className="text-[11px] text-slate-400">Fulfilled Orders</span>
                    <p className="text-xl font-bold text-emerald-400">{sellerDashboard.fulfilled_orders}</p>
                    <p className="text-[10px] text-slate-500">Shipped / Delivered</p>
                  </div>
                  <div className="p-4 rounded-2xl bg-slate-900/40 border border-white/5 space-y-1 col-span-2 md:col-span-1">
                    <span className="text-[11px] text-slate-400">Gross Sales</span>
                    <p className="text-xl font-bold text-white">₹{sellerDashboard.gross_sales_inr.toLocaleString('en-IN')}</p>
                    <p className="text-[10px] text-slate-500">Total item billings</p>
                  </div>
                </div>
              )}

              {/* SELLER INCOMING ORDERS TABLE */}
              <div className="p-5 rounded-3xl bg-slate-900/50 border border-white/10 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <Package className="w-4 h-4 text-rose-400" />
                      <span>Customer Orders Requiring Fulfillment ({sellerOrders.length})</span>
                    </h3>
                    <p className="text-[11px] text-slate-400">Update shipping and delivery progress for customer packages.</p>
                  </div>
                  <button onClick={fetchSellerData} className="p-2 rounded-xl bg-white/5 text-slate-300 hover:text-white">
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>

                {sellerOrders.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-500">
                    No orders have been placed for your products yet.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {sellerOrders.map(ord => (
                      <div key={ord.id} className="p-4 rounded-2xl bg-slate-800/40 border border-white/5 space-y-3">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-2.5">
                          <div className="space-y-0.5">
                            <span className="text-xs font-mono font-bold text-white">Order #{ord.id.slice(-8)}</span>
                            <p className="text-[10px] text-slate-400">
                              Recipient: {ord.shipping_full_name} ({ord.shipping_phone}) • {ord.shipping_city}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              ord.order_status === 'delivered' ? 'bg-emerald-500/20 text-emerald-400' :
                              ord.order_status === 'shipped' ? 'bg-cyan-500/20 text-cyan-400' :
                              ord.order_status === 'processing' ? 'bg-amber-500/20 text-amber-400' :
                              'bg-slate-700 text-slate-300'
                            }`}>
                              {ord.order_status}
                            </span>
                          </div>
                        </div>

                        {/* Items in order belonging to this seller */}
                        <div className="space-y-1.5">
                          {ord.items.map((it, idx) => (
                            <div key={idx} className="flex items-center justify-between text-xs text-slate-300">
                              <span>{it.name} × {it.quantity}</span>
                              <span className="font-semibold text-white">₹{(it.total_price_paise / 100).toLocaleString('en-IN')}</span>
                            </div>
                          ))}
                        </div>

                        {/* Valid Order Status Transitions */}
                        <div className="flex items-center justify-between pt-2 border-t border-white/5 text-xs">
                          <span className="text-slate-400 text-[11px]">
                            Address: {ord.shipping_address}, {ord.shipping_city} {ord.shipping_postal_code}
                          </span>

                          <div className="flex items-center gap-2 shrink-0">
                            {ord.order_status === 'placed' && (
                              <button
                                onClick={() => handleUpdateSellerOrderStatus(ord.id, 'processing')}
                                className="px-3 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 font-semibold text-[11px]"
                              >
                                Mark Processing
                              </button>
                            )}
                            {ord.order_status === 'processing' && (
                              <button
                                onClick={() => handleUpdateSellerOrderStatus(ord.id, 'shipped')}
                                className="px-3 py-1 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/30 font-semibold text-[11px]"
                              >
                                Mark Shipped
                              </button>
                            )}
                            {ord.order_status === 'shipped' && (
                              <button
                                onClick={() => handleUpdateSellerOrderStatus(ord.id, 'delivered')}
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

              {/* SELLER PRODUCT CATALOG LIST */}
              <div className="p-5 rounded-3xl bg-slate-900/50 border border-white/10 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-rose-400" />
                      <span>My Product Catalog ({sellerProducts.length})</span>
                    </h3>
                    <p className="text-[11px] text-slate-400">Real-time inventory levels, pricing, and active status.</p>
                  </div>
                </div>

                {sellerProducts.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-500">
                    No products published yet. Click "Add New Product" above to publish your first inventory item.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {sellerProducts.map(p => (
                      <div key={p.id} className="p-4 rounded-2xl bg-slate-800/40 border border-white/5 space-y-3 flex flex-col justify-between">
                        <div className="flex gap-3">
                          <img
                            src={p.images[0] || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600'}
                            alt={p.name}
                            className="w-16 h-16 rounded-xl object-cover bg-slate-900 shrink-0"
                          />
                          <div className="min-w-0 flex-1">
                            <span className="text-[10px] text-rose-400 font-bold uppercase">{p.category}</span>
                            <h4 className="text-xs font-bold text-white truncate">{p.name}</h4>
                            <p className="text-sm font-extrabold text-white mt-1">₹{p.price_inr.toLocaleString('en-IN')}</p>
                            <div className="flex items-center gap-2 mt-1">
                              <span className={`text-[10px] font-semibold ${p.stock <= 5 ? 'text-amber-400' : 'text-emerald-400'}`}>
                                Stock: {p.stock} units
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center justify-between pt-2 border-t border-white/5 text-xs">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${p.is_published ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                            {p.is_published ? 'Active' : 'Unpublished'}
                          </span>

                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => {
                                setEditingProductId(p.id);
                                setProdFormName(p.name);
                                setProdFormBrand(p.brand);
                                setProdFormCat(p.category);
                                setProdFormDesc(p.description);
                                setProdFormPriceRupees(p.price_inr.toString());
                                setProdFormStock(p.stock.toString());
                                setProdFormImage(p.images[0] || '');
                                setIsProductModalOpen(true);
                              }}
                              className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white"
                              title="Edit Product"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteProduct(p.id)}
                              className="p-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400"
                              title="Delete Product"
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

          {/* PRODUCT CREATE / EDIT MODAL */}
          {isProductModalOpen && (
            <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-white/10 rounded-3xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6 space-y-5 animate-scaleUp">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold text-white">
                    {editingProductId ? 'Edit Product Details' : 'Publish New Product'}
                  </h3>
                  <button onClick={() => setIsProductModalOpen(false)} className="p-1 rounded-full bg-white/5 text-slate-400 hover:text-white">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleSaveSellerProduct} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Product Title *</label>
                    <input
                      type="text"
                      required
                      value={prodFormName}
                      onChange={e => setProdFormName(e.target.value)}
                      placeholder="e.g. Wireless Noise-Cancelling Headphones"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">Brand *</label>
                      <input
                        type="text"
                        required
                        value={prodFormBrand}
                        onChange={e => setProdFormBrand(e.target.value)}
                        className="w-full px-3.5 py-2 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">Category *</label>
                      <select
                        value={prodFormCat}
                        onChange={e => setProdFormCat(e.target.value)}
                        className="w-full px-3.5 py-2 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                      >
                        <option value="Electronics">Electronics</option>
                        <option value="Fashion">Fashion</option>
                        <option value="Footwear">Footwear</option>
                        <option value="Home & Kitchen">Home & Kitchen</option>
                        <option value="Accessories">Accessories</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">Price (in Rupees ₹) *</label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        value={prodFormPriceRupees}
                        onChange={e => setProdFormPriceRupees(e.target.value)}
                        placeholder="e.g. 1499.00"
                        className="w-full px-3.5 py-2 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">Available Stock *</label>
                      <input
                        type="number"
                        required
                        min="0"
                        value={prodFormStock}
                        onChange={e => setProdFormStock(e.target.value)}
                        className="w-full px-3.5 py-2 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Image URL</label>
                    <input
                      type="url"
                      value={prodFormImage}
                      onChange={e => setProdFormImage(e.target.value)}
                      placeholder="https://..."
                      className="w-full px-3.5 py-2 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Description *</label>
                    <textarea
                      required
                      rows={3}
                      value={prodFormDesc}
                      onChange={e => setProdFormDesc(e.target.value)}
                      placeholder="Detailed item description and specifications..."
                      className="w-full px-3.5 py-2 rounded-xl bg-slate-800 border border-white/10 text-white text-xs focus:outline-none focus:border-rose-500 resize-none"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSavingProduct}
                    className="w-full py-3 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs shadow-lg shadow-rose-600/30 transition flex items-center justify-center gap-2"
                  >
                    {isSavingProduct ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                    <span>{editingProductId ? 'Save Product Changes' : 'Publish Product'}</span>
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* PRODUCT DETAIL MODAL */}
      {selectedProduct && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-white/10 rounded-3xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-5 animate-scaleUp">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[10px] text-rose-400 font-bold uppercase">{selectedProduct.brand} • {selectedProduct.category}</span>
                <h3 className="text-lg font-bold text-white">{selectedProduct.name}</h3>
              </div>
              <button 
                onClick={() => setSelectedProduct(null)}
                className="p-1.5 rounded-full bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="h-64 w-full rounded-2xl overflow-hidden bg-slate-800">
              <img 
                src={selectedProduct.images?.[0] || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600'} 
                alt={selectedProduct.name} 
                className="w-full h-full object-cover" 
              />
            </div>

            <div className="space-y-3">
              <p className="text-xs text-slate-300 leading-relaxed">{selectedProduct.description}</p>
              
              {selectedProduct.features && selectedProduct.features.length > 0 && (
                <div className="space-y-1.5">
                  <h5 className="text-xs font-bold text-white">Key Specifications:</h5>
                  <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
                    {selectedProduct.features.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex items-center justify-between p-4 rounded-2xl bg-slate-800/60 border border-white/5">
                <div>
                  <span className="text-[10px] text-slate-400">Total Price</span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-xl font-bold text-white">₹{selectedProduct.price_inr.toLocaleString('en-IN')}</span>
                    {selectedProduct.mrp_inr && selectedProduct.mrp_inr > selectedProduct.price_inr && (
                      <span className="text-xs text-slate-500 line-through">₹{selectedProduct.mrp_inr.toLocaleString('en-IN')}</span>
                    )}
                  </div>
                </div>

                <button
                  onClick={() => {
                    addToCart(selectedProduct);
                    setSelectedProduct(null);
                  }}
                  disabled={selectedProduct.stock <= 0 || !selectedProduct.is_available}
                  className="px-6 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs shadow-lg shadow-rose-600/30 transition disabled:opacity-50"
                >
                  {selectedProduct.stock > 0 ? 'Add to Cart' : 'Out of Stock'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CART & CHECKOUT DRAWER */}
      {isCartOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex justify-end">
          <div className="w-full max-w-md bg-slate-900 border-l border-white/10 h-full flex flex-col justify-between p-6 overflow-y-auto animate-slideLeft">
            <div className="space-y-6">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <ShoppingBag className="w-5 h-5 text-rose-400" />
                  <h3 className="text-base font-bold text-white">Your Shopping Cart</h3>
                </div>
                <button 
                  onClick={() => setIsCartOpen(false)}
                  className="p-1.5 rounded-xl bg-white/5 text-slate-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {cart.length === 0 ? (
                <div className="py-16 text-center space-y-3">
                  <ShoppingBag className="w-12 h-12 text-slate-600 mx-auto" />
                  <p className="text-xs text-slate-400">Your cart is currently empty.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {cart.map(item => (
                    <div key={item.productId} className="flex items-center justify-between p-3 rounded-2xl bg-slate-800/40 border border-white/5 gap-3">
                      {item.imageUrl && (
                        <img src={item.imageUrl} alt={item.name} className="w-12 h-12 rounded-xl object-cover bg-slate-900 shrink-0" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold text-white truncate">{item.name}</p>
                        <p className="text-[11px] text-rose-400 font-bold">₹{(item.pricePaise / 100).toLocaleString('en-IN')}</p>
                      </div>

                      {/* Quantity Controls */}
                      <div className="flex items-center gap-2 bg-slate-900 px-2 py-1 rounded-xl border border-white/10">
                        <button 
                          onClick={() => updateCartQty(item.productId, -1)}
                          className="text-slate-400 hover:text-white"
                        >
                          <Minus className="w-3 h-3" />
                        </button>
                        <span className="text-xs font-bold text-white px-1">{item.qty}</span>
                        <button 
                          onClick={() => updateCartQty(item.productId, 1)}
                          className="text-slate-400 hover:text-white"
                        >
                          <Plus className="w-3 h-3" />
                        </button>
                      </div>

                      <button
                        onClick={() => removeFromCart(item.productId)}
                        className="text-slate-500 hover:text-red-400 p-1"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Checkout Form & Address */}
              {cart.length > 0 && (
                <form onSubmit={handlePlaceOrder} className="space-y-4 pt-4 border-t border-white/10">
                  <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                    <Truck className="w-4 h-4 text-rose-400" />
                    <span>Shipping Address & Delivery Info</span>
                  </h4>

                  <div className="space-y-2">
                    <input
                      type="text"
                      placeholder="Full Name"
                      value={shippingFullName}
                      onChange={e => setShippingFullName(e.target.value)}
                      required
                      className="w-full px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-xs text-white"
                    />

                    <input
                      type="text"
                      placeholder="Mobile Phone Number (+91...)"
                      value={shippingPhone}
                      onChange={e => setShippingPhone(e.target.value)}
                      required
                      className="w-full px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-xs text-white"
                    />

                    <input
                      type="text"
                      placeholder="Street Address / Flat / Landmark"
                      value={shippingAddress}
                      onChange={e => setShippingAddress(e.target.value)}
                      required
                      className="w-full px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-xs text-white"
                    />

                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="text"
                        placeholder="City"
                        value={shippingCity}
                        onChange={e => setShippingCity(e.target.value)}
                        required
                        className="px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-xs text-white"
                      />
                      <input
                        type="text"
                        placeholder="PIN Code"
                        value={shippingPostalCode}
                        onChange={e => setShippingPostalCode(e.target.value)}
                        required
                        className="px-3 py-2 rounded-xl bg-slate-800/80 border border-white/10 text-xs text-white"
                      />
                    </div>
                  </div>

                  {/* Payment Options */}
                  <div className="space-y-1.5 pt-2">
                    <label className="text-[11px] font-semibold text-slate-300">Payment Option:</label>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <button
                        type="button"
                        onClick={() => setPaymentMethod('cod')}
                        className={`p-2 rounded-xl border font-medium text-center transition ${
                          paymentMethod === 'cod'
                            ? 'bg-rose-600/30 border-rose-500 text-white'
                            : 'bg-white/5 border-white/10 text-slate-400'
                        }`}
                      >
                        Cash on Delivery
                      </button>
                      <button
                        type="button"
                        onClick={() => setPaymentMethod('test_mode_upi')}
                        className={`p-2 rounded-xl border font-medium text-center transition ${
                          paymentMethod === 'test_mode_upi'
                            ? 'bg-rose-600/30 border-rose-500 text-white'
                            : 'bg-white/5 border-white/10 text-slate-400'
                        }`}
                      >
                        Test UPI
                      </button>
                      <button
                        type="button"
                        onClick={() => setPaymentMethod('test_mode_card')}
                        className={`p-2 rounded-xl border font-medium text-center transition ${
                          paymentMethod === 'test_mode_card'
                            ? 'bg-rose-600/30 border-rose-500 text-white'
                            : 'bg-white/5 border-white/10 text-slate-400'
                        }`}
                      >
                        Test Card
                      </button>
                    </div>
                  </div>

                  {/* Financial Breakdown */}
                  <div className="p-3.5 rounded-2xl bg-slate-800/50 border border-white/5 space-y-1.5 text-xs">
                    <div className="flex justify-between text-slate-400">
                      <span>Items Subtotal:</span>
                      <span>₹{(cartSubtotalPaise / 100).toLocaleString('en-IN')}</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Standard Shipping:</span>
                      <span>{cartShippingPaise === 0 ? <span className="text-emerald-400 font-bold">FREE</span> : `₹${cartShippingPaise / 100}`}</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Estimated GST (18%):</span>
                      <span>₹{(cartTaxesPaise / 100).toLocaleString('en-IN')}</span>
                    </div>
                    <div className="flex justify-between font-bold text-white pt-2 border-t border-white/10 text-sm">
                      <span>Total Amount:</span>
                      <span className="text-rose-400">₹{(cartTotalPaise / 100).toLocaleString('en-IN')}</span>
                    </div>
                  </div>

                  {checkoutError && (
                    <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                      {checkoutError}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={isPlacingOrder}
                    className="w-full py-3 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow-lg shadow-rose-600/30 transition flex items-center justify-center gap-2"
                  >
                    {isPlacingOrder ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Reserving Stock & Placing Order...</span>
                      </>
                    ) : (
                      <>
                        <Check className="w-4 h-4" />
                        <span>Confirm Order • ₹{(cartTotalPaise / 100).toLocaleString('en-IN')}</span>
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ORDER CONFIRMATION MODAL */}
      {lastPlacedOrder && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-emerald-500/30 rounded-3xl max-w-md w-full p-6 space-y-4 text-center animate-scaleUp">
            <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto border border-emerald-500/30">
              <CheckCircle2 className="w-6 h-6" />
            </div>

            <div className="space-y-1">
              <h3 className="text-lg font-bold text-white">Order Confirmed!</h3>
              <p className="text-xs text-slate-400">
                Order ID: <span className="font-mono text-emerald-400 font-bold">#{lastPlacedOrder.id.slice(-8)}</span>
              </p>
            </div>

            <p className="text-xs text-slate-300">
              We received your order of ₹{lastPlacedOrder.total_inr.toLocaleString('en-IN')}. Stock has been reserved and your package is being prepared for dispatch.
            </p>

            <div className="p-3.5 rounded-2xl bg-slate-800/60 text-left text-xs space-y-1 border border-white/5">
              <div className="flex justify-between text-slate-400">
                <span>Payment Mode:</span>
                <span className="font-semibold text-white uppercase">{lastPlacedOrder.payment_method}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Payment Status:</span>
                <span className="font-semibold text-emerald-400 uppercase">{lastPlacedOrder.payment_status}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Shipping To:</span>
                <span className="font-semibold text-white truncate max-w-[200px]">{lastPlacedOrder.shipping_address}</span>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => {
                  setLastPlacedOrder(null);
                  setActiveTab('orders');
                }}
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs transition"
              >
                Track in My Orders
              </button>
              <button
                onClick={() => setLastPlacedOrder(null)}
                className="px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 font-semibold text-xs transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
