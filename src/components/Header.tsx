import React, { useState } from 'react';
import { UserAccount, BotConfig } from '../types.ts';
import { 
  Bot, 
  Wallet, 
  PlusCircle, 
  Shield, 
  User, 
  MessageSquare, 
  Sparkles, 
  ShoppingBag, 
  Clock, 
  CreditCard 
} from 'lucide-react';

interface HeaderProps {
  activeTab: 'services' | 'orders' | 'wallet' | 'bot' | 'admin';
  setActiveTab: (tab: 'services' | 'orders' | 'wallet' | 'bot' | 'admin') => void;
  currentUser: UserAccount;
  allUsers: UserAccount[];
  onSwitchUser: (userId: number) => void;
  onOpenAddFunds: () => void;
  config: BotConfig | null;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  currentUser,
  allUsers,
  onSwitchUser,
  onOpenAddFunds,
  config
}) => {
  const [showUserDropdown, setShowUserDropdown] = useState(false);

  const isAdmin = currentUser.user_id === 881394179;

  return (
    <header className="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('services')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20 text-white font-bold text-lg">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight text-white">
                  {config?.bot_username || 'Bobby SMM Panel'}
                </span>
                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20 rounded">
                  v2.4
                </span>
              </div>
              <p className="text-xs text-slate-400">Telegram Bot & Social Growth Store</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center space-x-1">
            <button
              onClick={() => setActiveTab('services')}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'services'
                  ? 'bg-sky-500/10 text-sky-400 border border-sky-500/30'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <ShoppingBag className="w-4 h-4" />
              <span>Services</span>
            </button>

            <button
              onClick={() => setActiveTab('orders')}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'orders'
                  ? 'bg-sky-500/10 text-sky-400 border border-sky-500/30'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Clock className="w-4 h-4" />
              <span>My Orders</span>
              {currentUser.orders_count > 0 && (
                <span className="px-1.5 py-0.2 text-xs bg-slate-800 text-slate-300 rounded-full">
                  {currentUser.orders_count}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('wallet')}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'wallet'
                  ? 'bg-sky-500/10 text-sky-400 border border-sky-500/30'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <CreditCard className="w-4 h-4" />
              <span>Wallet & Bonus</span>
            </button>

            <button
              onClick={() => setActiveTab('bot')}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'bot'
                  ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/30'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <MessageSquare className="w-4 h-4" />
              <span>Telegram Bot UI</span>
            </button>

            <button
              onClick={() => setActiveTab('admin')}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'admin'
                  ? 'bg-purple-500/10 text-purple-400 border border-purple-500/30'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Shield className="w-4 h-4 text-purple-400" />
              <span>Admin Panel</span>
            </button>
          </nav>

          {/* User Controls & Balance */}
          <div className="flex items-center space-x-3">
            {/* Balance Pill */}
            <div 
              onClick={onOpenAddFunds}
              className="flex items-center space-x-2 bg-slate-800/90 hover:bg-slate-800 border border-slate-700/80 rounded-xl px-3 py-1.5 cursor-pointer transition-colors group"
              title="Click to recharge wallet"
            >
              <Wallet className="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform" />
              <div className="flex flex-col text-left">
                <span className="text-[10px] text-slate-400 leading-none">Wallet</span>
                <span className="text-sm font-bold text-emerald-400 leading-tight">
                  ₹{currentUser.balance.toFixed(2)}
                </span>
              </div>
              <PlusCircle className="w-4 h-4 text-sky-400 opacity-80 group-hover:opacity-100" />
            </div>

            {/* User Profile Switcher */}
            <div className="relative">
              <button
                onClick={() => setShowUserDropdown(!showUserDropdown)}
                className="flex items-center space-x-2 bg-slate-800 border border-slate-700 rounded-xl px-3 py-1.5 hover:bg-slate-750 transition"
              >
                <div className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-xs font-semibold text-sky-400">
                  {currentUser.first_name[0] || 'U'}
                </div>
                <div className="text-left hidden sm:block">
                  <div className="text-xs font-medium text-slate-200 truncate max-w-[100px]">
                    {currentUser.first_name}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    ID: {currentUser.user_id}
                  </div>
                </div>
              </button>

              {/* User Dropdown */}
              {showUserDropdown && (
                <div className="absolute right-0 mt-2 w-64 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl py-2 z-50">
                  <div className="px-4 py-2 border-b border-slate-800">
                    <p className="text-xs font-semibold text-slate-400">Switch Telegram Account</p>
                    <p className="text-[11px] text-slate-500">Test different user roles & balances</p>
                  </div>

                  <div className="max-h-52 overflow-y-auto py-1">
                    {allUsers.map((u) => (
                      <button
                        key={u.user_id}
                        onClick={() => {
                          onSwitchUser(u.user_id);
                          setShowUserDropdown(false);
                        }}
                        className={`w-full flex items-center justify-between px-4 py-2 text-xs transition ${
                          u.user_id === currentUser.user_id
                            ? 'bg-sky-500/10 text-sky-400 font-semibold'
                            : 'text-slate-300 hover:bg-slate-800'
                        }`}
                      >
                        <div className="flex items-center space-x-2">
                          <User className="w-3.5 h-3.5" />
                          <div className="text-left">
                            <div>{u.first_name}</div>
                            <div className="text-[10px] text-slate-500">ID: {u.user_id}</div>
                          </div>
                        </div>
                        <span className="font-mono text-emerald-400">₹{u.balance.toFixed(2)}</span>
                      </button>
                    ))}
                  </div>

                  <div className="px-3 pt-2 border-t border-slate-800">
                    <button
                      onClick={() => {
                        const newId = Math.floor(100000000 + Math.random() * 900000000);
                        onSwitchUser(newId);
                        setShowUserDropdown(false);
                      }}
                      className="w-full text-center py-1.5 text-xs bg-slate-800 hover:bg-slate-750 text-slate-300 rounded-lg transition"
                    >
                      + Create New Test User
                    </button>
                  </div>
                </div>
              )}
            </div>

          </div>

        </div>

        {/* Mobile Navigation bar */}
        <div className="flex md:hidden items-center justify-between py-2 border-t border-slate-800 text-xs">
          <button
            onClick={() => setActiveTab('services')}
            className={`px-2.5 py-1.5 rounded-lg ${activeTab === 'services' ? 'bg-sky-500/20 text-sky-400 font-semibold' : 'text-slate-400'}`}
          >
            Services
          </button>
          <button
            onClick={() => setActiveTab('orders')}
            className={`px-2.5 py-1.5 rounded-lg ${activeTab === 'orders' ? 'bg-sky-500/20 text-sky-400 font-semibold' : 'text-slate-400'}`}
          >
            Orders ({currentUser.orders_count})
          </button>
          <button
            onClick={() => setActiveTab('wallet')}
            className={`px-2.5 py-1.5 rounded-lg ${activeTab === 'wallet' ? 'bg-sky-500/20 text-sky-400 font-semibold' : 'text-slate-400'}`}
          >
            Wallet
          </button>
          <button
            onClick={() => setActiveTab('bot')}
            className={`px-2.5 py-1.5 rounded-lg ${activeTab === 'bot' ? 'bg-indigo-500/20 text-indigo-400 font-semibold' : 'text-slate-400'}`}
          >
            Bot UI
          </button>
          <button
            onClick={() => setActiveTab('admin')}
            className={`px-2.5 py-1.5 rounded-lg ${activeTab === 'admin' ? 'bg-purple-500/20 text-purple-400 font-semibold' : 'text-slate-400'}`}
          >
            Admin
          </button>
        </div>

      </div>
    </header>
  );
};
