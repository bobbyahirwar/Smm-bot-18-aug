import React, { useState, useEffect } from 'react';
import { UserAccount, SMMService, SMMOrder, BotConfig, WalletLedgerEntry } from './types.ts';
import { Header } from './components/Header.tsx';
import { ServiceCatalog } from './components/ServiceCatalog.tsx';
import { MyOrders } from './components/MyOrders.tsx';
import { WalletView } from './components/WalletView.tsx';
import { TelegramBotSimulator } from './components/TelegramBotSimulator.tsx';
import { AdminPanel } from './components/AdminPanel.tsx';
import { OrderModal } from './components/OrderModal.tsx';
import { AddFundsModal } from './components/AddFundsModal.tsx';
import { Loader2 } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<'services' | 'orders' | 'wallet' | 'bot' | 'admin'>('services');
  const [currentUserId, setCurrentUserId] = useState<number>(881394179);
  const [currentUser, setCurrentUser] = useState<UserAccount | null>(null);
  const [allUsers, setAllUsers] = useState<UserAccount[]>([]);
  const [services, setServices] = useState<SMMService[]>([]);
  const [orders, setOrders] = useState<SMMOrder[]>([]);
  const [ledger, setLedger] = useState<WalletLedgerEntry[]>([]);
  const [config, setConfig] = useState<BotConfig | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Modals
  const [selectedServiceForOrder, setSelectedServiceForOrder] = useState<SMMService | null>(null);
  const [showAddFundsModal, setShowAddFundsModal] = useState<boolean>(false);

  // Fetch initial services & config
  const fetchServicesAndConfig = async () => {
    try {
      const [svcRes, cfgRes, usersRes] = await Promise.all([
        fetch('/api/services').then(r => r.json()),
        fetch('/api/config').then(r => r.json()),
        fetch('/api/admin/users').then(r => r.json())
      ]);
      setServices(svcRes);
      setConfig(cfgRes);
      if (Array.isArray(usersRes)) setAllUsers(usersRes);
    } catch (err) {
      console.error('Error fetching services/config:', err);
    }
  };

  // Fetch user specific data
  const fetchUserData = async (userId: number) => {
    try {
      const [uRes, oRes, lRes] = await Promise.all([
        fetch(`/api/user/${userId}`).then(r => r.json()),
        fetch(`/api/orders/user/${userId}`).then(r => r.json()),
        fetch(`/api/wallet/ledger/${userId}`).then(r => r.json())
      ]);
      setCurrentUser(uRes);
      setOrders(oRes);
      setLedger(lRes);
    } catch (err) {
      console.error('Error fetching user data:', err);
    }
  };

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await fetchServicesAndConfig();
      await fetchUserData(currentUserId);
      setLoading(false);
    };
    init();
  }, [currentUserId]);

  const handleSwitchUser = async (userId: number) => {
    setCurrentUserId(userId);
    await fetchUserData(userId);
  };

  const handlePlaceOrder = async (serviceId: string, link: string, quantity: number): Promise<boolean> => {
    if (!currentUser) return false;

    const res = await fetch('/api/orders/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUser.user_id,
        service_id: serviceId,
        link,
        quantity
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Failed to place order.');
    }

    // Refresh user info and orders
    await fetchUserData(currentUser.user_id);
    return true;
  };

  const handleDeposit = async (amount: number, utr: string): Promise<boolean> => {
    if (!currentUser) return false;

    const res = await fetch('/api/wallet/deposit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUser.user_id,
        amount,
        utr
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Deposit failed');
    }

    await fetchUserData(currentUser.user_id);
    return true;
  };

  const handleClaimBonus = async (): Promise<{ success: boolean; message: string }> => {
    if (!currentUser) return { success: false, message: 'No user active' };

    const res = await fetch('/api/wallet/bonus', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUser.user_id })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Could not claim daily bonus');
    }

    await fetchUserData(currentUser.user_id);
    return { success: true, message: data.message };
  };

  const handleRedeemGiftCode = async (code: string): Promise<{ success: boolean; message: string }> => {
    if (!currentUser) return { success: false, message: 'No user active' };

    const res = await fetch('/api/wallet/giftcode/redeem', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUser.user_id,
        code
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Invalid or expired gift code');
    }

    await fetchUserData(currentUser.user_id);
    return { success: true, message: data.message };
  };

  if (loading || !currentUser) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center space-y-4 text-slate-300">
        <Loader2 className="w-8 h-8 text-sky-500 animate-spin" />
        <p className="text-sm font-medium">Starting Bobby SMM Engine...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-sky-500 selection:text-white">
      
      {/* App Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        currentUser={currentUser}
        allUsers={allUsers}
        onSwitchUser={handleSwitchUser}
        onOpenAddFunds={() => setShowAddFundsModal(true)}
        config={config}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {activeTab === 'services' && (
          <ServiceCatalog
            services={services}
            currentUser={currentUser}
            onSelectService={(svc) => setSelectedServiceForOrder(svc)}
            onOpenAddFunds={() => setShowAddFundsModal(true)}
          />
        )}

        {activeTab === 'orders' && (
          <MyOrders
            orders={orders}
            onRefresh={() => fetchUserData(currentUser.user_id)}
          />
        )}

        {activeTab === 'wallet' && (
          <WalletView
            currentUser={currentUser}
            ledger={ledger}
            config={config}
            onOpenAddFunds={() => setShowAddFundsModal(true)}
            onClaimBonus={handleClaimBonus}
            onRedeemGiftCode={handleRedeemGiftCode}
          />
        )}

        {activeTab === 'bot' && (
          <TelegramBotSimulator
            currentUser={currentUser}
            services={services}
            config={config}
            onPlaceOrder={handlePlaceOrder}
            onOpenAddFunds={() => setShowAddFundsModal(true)}
            onClaimBonus={handleClaimBonus}
            onRedeemGiftCode={handleRedeemGiftCode}
          />
        )}

        {activeTab === 'admin' && (
          <AdminPanel
            services={services}
            config={config}
            onRefreshServices={fetchServicesAndConfig}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-900/60 py-6 text-xs text-slate-500 text-center">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Bobby SMM Panel • Fully Automated Social Media Marketing Platform</span>
          <span>Fast API Integrations • Instant Delivery Engine</span>
        </div>
      </footer>

      {/* Place Order Modal */}
      {selectedServiceForOrder && (
        <OrderModal
          service={selectedServiceForOrder}
          currentUser={currentUser}
          onClose={() => setSelectedServiceForOrder(null)}
          onPlaceOrder={handlePlaceOrder}
          onOpenAddFunds={() => {
            setSelectedServiceForOrder(null);
            setShowAddFundsModal(true);
          }}
        />
      )}

      {/* Add Funds Modal */}
      {showAddFundsModal && (
        <AddFundsModal
          currentUser={currentUser}
          config={config}
          onClose={() => setShowAddFundsModal(false)}
          onDeposit={handleDeposit}
        />
      )}

    </div>
  );
}

export default App;
