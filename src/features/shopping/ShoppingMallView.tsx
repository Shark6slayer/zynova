import React, { useState } from 'react';
import { 
  ShoppingBag, Search, Star, Filter, Heart, 
  Check, ArrowRight, Zap, ShieldCheck 
} from 'lucide-react';
import { MOCK_PRODUCTS, type ProductItem } from '../../mocks/demoData';

export const ShoppingMallView: React.FC = () => {
  const [products, setProducts] = useState<ProductItem[]>(MOCK_PRODUCTS);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [cartAlert, setCartAlert] = useState<string | null>(null);

  const categories = ['All', 'Wearables', 'Audio', 'Personal Care', 'Apparel'];

  const filteredProducts = products.filter(
    (p) => selectedCategory === 'All' || p.category === selectedCategory
  );

  const handleAddToCart = (product: ProductItem) => {
    setCartAlert(`Added "${product.title}" to Super Mall Cart`);
    setTimeout(() => setCartAlert(null), 2500);
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto w-full">
      {/* Shopping Hero */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-pink-950/40 via-slate-900/80 to-purple-950/40 border border-pink-500/20 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-pink-400 text-xs font-semibold uppercase tracking-wider">
            <ShoppingBag className="w-4 h-4" />
            <span>ONDC-Powered Decentralized Super Mall</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Direct Brand Stores & Indian Artisans</h1>
          <p className="text-xs text-slate-400 mt-1 flex items-center gap-2">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> 100% Genuine Brands • Free Next-Day Metro Delivery
          </p>
        </div>

        {/* Categories Bar */}
        <div className="flex items-center space-x-1 overflow-x-auto text-xs">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setSelectedCategory(c)}
              className={`px-3 py-1.5 rounded-xl font-medium transition ${
                selectedCategory === c
                  ? 'bg-pink-600 text-white shadow'
                  : 'bg-white/5 text-slate-300 hover:bg-white/10'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {cartAlert && (
        <div className="p-3 rounded-xl bg-pink-500/20 border border-pink-500/30 text-pink-300 text-xs flex items-center gap-2">
          <Check className="w-4 h-4" />
          <span>{cartAlert}</span>
        </div>
      )}

      {/* Product Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {filteredProducts.map((p) => (
          <div
            key={p.id}
            className="rounded-2xl border border-white/5 bg-slate-900/40 overflow-hidden hover:border-pink-500/30 transition-all group flex flex-col justify-between"
          >
            <div>
              <div className="relative h-48 w-full overflow-hidden bg-slate-800">
                <img src={p.image} alt={p.title} className="w-full h-full object-cover group-hover:scale-105 transition duration-500" />
                {p.fastDelivery && (
                  <span className="absolute top-2 left-2 px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold flex items-center gap-1">
                    <Zap className="w-3 h-3" /> FAST DISPATCH
                  </span>
                )}
              </div>

              <div className="p-4 space-y-1.5">
                <span className="text-[10px] text-pink-400 font-bold uppercase">{p.brand}</span>
                <h4 className="text-xs font-semibold text-slate-100 line-clamp-2">{p.title}</h4>
                <div className="flex items-center space-x-1.5 text-xs pt-1">
                  <span className="text-emerald-400 font-bold">★ {p.rating}</span>
                  <span className="text-[10px] text-slate-500">({p.reviewsCount})</span>
                </div>
                <div className="flex items-baseline space-x-2 pt-2">
                  <span className="text-base font-bold text-white">₹{p.price.toLocaleString('en-IN')}</span>
                  <span className="text-xs text-slate-500 line-through">₹{p.originalPrice.toLocaleString('en-IN')}</span>
                </div>
              </div>
            </div>

            <div className="p-4 pt-0">
              <button
                onClick={() => handleAddToCart(p)}
                className="w-full py-2 bg-white/5 hover:bg-pink-600 hover:text-white text-slate-200 rounded-xl text-xs font-semibold border border-white/10 transition"
              >
                Add to Cart
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
