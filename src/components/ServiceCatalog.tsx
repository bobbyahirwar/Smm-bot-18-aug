import React, { useState, useMemo } from 'react';
import { SMMService, UserAccount } from '../types.ts';
import { 
  Search, 
  Sparkles, 
  Flame, 
  ArrowRight, 
  CheckCircle, 
  TrendingUp, 
  Eye, 
  ThumbsUp, 
  Users, 
  MessageCircle,
  Share2,
  Filter
} from 'lucide-react';

interface ServiceCatalogProps {
  services: SMMService[];
  currentUser: UserAccount;
  onSelectService: (service: SMMService) => void;
  onOpenAddFunds: () => void;
}

export const ServiceCatalog: React.FC<ServiceCatalogProps> = ({
  services,
  currentUser,
  onSelectService,
  onOpenAddFunds
}) => {
  const [selectedPlatform, setSelectedPlatform] = useState<string>('All');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const platforms = useMemo(() => {
    const set = new Set<string>();
    services.forEach(s => {
      if (s.platform) set.add(s.platform);
    });
    return ['All', ...Array.from(set)];
  }, [services]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    services
      .filter(s => selectedPlatform === 'All' || s.platform === selectedPlatform)
      .forEach(s => {
        if (s.category) set.add(s.category);
      });
    return ['All', ...Array.from(set)];
  }, [services, selectedPlatform]);

  const filteredServices = useMemo(() => {
    return services.filter(s => {
      if (!s.enabled) return false;
      const matchesPlatform = selectedPlatform === 'All' || s.platform.toLowerCase() === selectedPlatform.toLowerCase();
      const matchesCategory = selectedCategory === 'All' || s.category.toLowerCase() === selectedCategory.toLowerCase();
      const matchesSearch = !searchQuery.trim() || 
        s.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.platform.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.category.toLowerCase().includes(searchQuery.toLowerCase());

      return matchesPlatform && matchesCategory && matchesSearch;
    });
  }, [services, selectedPlatform, selectedCategory, searchQuery]);

  const getPlatformIcon = (platform: string) => {
    switch (platform.toLowerCase()) {
      case 'instagram': return '📸';
      case 'youtube': return '▶️';
      case 'telegram': return '✈️';
      case 'facebook': return '👍';
      case 'twitter/x':
      case 'twitter': return '🐦';
      case 'tiktok': return '🎵';
      default: return '⚡';
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-sky-900/40 via-indigo-900/30 to-purple-900/30 border border-sky-500/20 p-6 sm:p-8">
        <div className="relative z-10 max-w-3xl space-y-3">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-semibold">
            <Flame className="w-3.5 h-3.5 text-amber-400" />
            <span>Instant Automated SMM Delivery</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
            Grow Your Social Media Presence Faster
          </h1>
          <p className="text-sm text-slate-300 max-w-xl">
            Direct Telegram bot & provider rates for Instagram, YouTube, Telegram, Twitter/X and TikTok. Real views, high-quality likes, non-drop members & engagement.
          </p>

          <div className="pt-2 flex flex-wrap items-center gap-4 text-xs text-slate-300">
            <div className="flex items-center space-x-1.5">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              <span>0% Risk • 100% Safe</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              <span>24/7 Automated API Queue</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              <span>Instant Wallet Settlement</span>
            </div>
          </div>
        </div>

        {/* Decorative background glow */}
        <div className="absolute top-0 right-0 -mt-8 -mr-8 w-64 h-64 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 space-y-4">
        
        {/* Search & Stats */}
        <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
          
          <div className="relative w-full sm:w-96">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search services (e.g., Reels Views, Members, Likes)..."
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 pl-9 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500"
            />
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
          </div>

          <div className="flex items-center space-x-2 text-xs text-slate-400 self-end sm:self-auto">
            <span>Showing <strong className="text-slate-100">{filteredServices.length}</strong> active services</span>
          </div>

        </div>

        {/* Platform Tabs */}
        <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-none">
          {platforms.map(platform => (
            <button
              key={platform}
              onClick={() => {
                setSelectedPlatform(platform);
                setSelectedCategory('All');
              }}
              className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                selectedPlatform === platform
                  ? 'bg-sky-500 text-white shadow-md shadow-sky-500/20'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-750 hover:text-white'
              }`}
            >
              <span>{platform === 'All' ? '🌐' : getPlatformIcon(platform)}</span>
              <span>{platform}</span>
            </button>
          ))}
        </div>

        {/* Category Pills (if applicable) */}
        {categories.length > 2 && (
          <div className="flex items-center space-x-2 overflow-x-auto pt-1 text-xs">
            <span className="text-slate-500 flex items-center space-x-1">
              <Filter className="w-3 h-3" />
              <span>Category:</span>
            </span>
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2.5 py-1 rounded-lg transition ${
                  selectedCategory === cat
                    ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40 font-medium'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        )}

      </div>

      {/* Services Grid */}
      {filteredServices.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-800 text-slate-500 mx-auto flex items-center justify-center">
            <Search className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-slate-200">No Services Found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            We couldn't find any services matching "{searchQuery}". Try selecting another category or platform.
          </p>
          <button
            onClick={() => {
              setSelectedPlatform('All');
              setSelectedCategory('All');
              setSearchQuery('');
            }}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-750 text-xs font-semibold text-sky-400 rounded-xl transition"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredServices.map(service => (
            <div
              key={service._id}
              className="bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 flex flex-col justify-between space-y-4 hover:shadow-xl hover:shadow-sky-950/20 transition group"
            >
              {/* Header */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 text-xs font-medium">
                    <span>{getPlatformIcon(service.platform)}</span>
                    <span>{service.platform}</span>
                  </span>

                  <span className="text-[11px] font-mono text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                    ID: {service.provider_service_id}
                  </span>
                </div>

                <h3 className="font-semibold text-slate-100 text-sm leading-snug line-clamp-2">
                  {service.display_name}
                </h3>
              </div>

              {/* Service Specs */}
              <div className="bg-slate-950/80 rounded-xl p-3 border border-slate-800/80 space-y-1.5 text-xs">
                <div className="flex items-center justify-between text-slate-400">
                  <span>Price per 1,000:</span>
                  <span className="font-mono font-bold text-base text-emerald-400">
                    ₹{service.selling_price.toFixed(2)}
                  </span>
                </div>

                <div className="flex items-center justify-between text-slate-400 text-[11px] pt-1 border-t border-slate-800/60">
                  <span>Min / Max Quantity:</span>
                  <span className="text-slate-300 font-medium">
                    {service.min.toLocaleString()} — {service.max.toLocaleString()}
                  </span>
                </div>

                <div className="flex items-center justify-between text-slate-400 text-[11px]">
                  <span>Speed / Guarantee:</span>
                  <span className="text-sky-400 font-medium">Instant • Non-Drop</span>
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={() => onSelectService(service)}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-sky-500 text-slate-200 hover:text-white text-xs font-bold transition flex items-center justify-center space-x-2 group-hover:bg-sky-500 group-hover:text-white shadow-sm"
              >
                <span>Order Service</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              </button>

            </div>
          ))}
        </div>
      )}

    </div>
  );
};
