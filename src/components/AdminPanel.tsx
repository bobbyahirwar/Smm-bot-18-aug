import React, { useState, useEffect } from 'react';
import { SMMService, UserAccount, GiftCode, BotConfig, AdminStats, WalletReservation } from '../types.ts';
import { 
  Shield, 
  Users, 
  ShoppingBag, 
  Gift, 
  Settings, 
  Radio, 
  DollarSign, 
  RefreshCw, 
  Plus, 
  Trash2, 
  Edit, 
  Check, 
  AlertCircle, 
  Send,
  Database,
  Lock,
  Unlock,
  Coins
} from 'lucide-react';

interface AdminPanelProps {
  services: SMMService[];
  config: BotConfig | null;
  onRefreshServices: () => void;
}

export const AdminPanel: React.FC<AdminPanelProps> = ({
  services,
  config: initialConfig,
  onRefreshServices
}) => {
  const [activeAdminTab, setActiveAdminTab] = useState<'stats' | 'services' | 'users' | 'giftcodes' | 'settings' | 'broadcast'>('stats');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [usersList, setUsersList] = useState<UserAccount[]>([]);
  const [giftCodesList, setGiftCodesList] = useState<GiftCode[]>([]);
  const [reservations, setReservations] = useState<WalletReservation[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusNotice, setStatusNotice] = useState<{ ok: boolean; msg: string } | null>(null);

  // Forms
  const [newGiftCode, setNewGiftCode] = useState({ code: '', amount: 50, max_claims: 100 });
  const [newService, setNewService] = useState({
    display_name: '',
    platform: 'Instagram',
    category: 'Followers',
    provider_service_id: 1001,
    min: 10,
    max: 50000,
    provider_rate: 20,
    selling_price: 30
  });
  const [showAddServiceModal, setShowAddServiceModal] = useState(false);
  const [editingService, setEditingService] = useState<SMMService | null>(null);

  // User Balance Edit State
  const [balanceTargetUser, setBalanceTargetUser] = useState<UserAccount | null>(null);
  const [balanceAmount, setBalanceAmount] = useState<number>(100);
  const [balanceAction, setBalanceAction] = useState<'add' | 'remove'>('add');

  // Broadcast Message State
  const [broadcastMessage, setBroadcastMessage] = useState('');

  // Config Form State
  const [configForm, setConfigForm] = useState<BotConfig>(initialConfig || {
    smm_panel_url: 'https://vcprovider.shop/api/v2',
    provider_rate_reactions: 10,
    provider_rate_views: 100,
    provider_rate_members: 1,
    markup_percentage: 50.0,
    referral_reward_inr: 25.0,
    daily_bonus_inr: 10.0,
    service_id_reactions: 476,
    service_id_views: 500,
    service_id_members: 470,
    logs_channel: '-1004434715037',
    channels: [],
    qr_code_url: 'https://t.me/bobbyQr/2',
    payment_contact: '@BOBBY_2606',
    bot_username: 'Bobby SMM Bot'
  });

  const fetchAdminData = async () => {
    setLoading(true);
    try {
      const [statsRes, usersRes, giftsRes, resRes] = await Promise.all([
        fetch('/api/admin/stats').then(r => r.json()),
        fetch('/api/admin/users').then(r => r.json()),
        fetch('/api/admin/giftcodes').then(r => r.json()),
        fetch('/api/admin/reservations').then(r => r.json())
      ]);
      setStats(statsRes);
      setUsersList(usersRes);
      setGiftCodesList(giftsRes);
      setReservations(resRes);
    } catch (err: any) {
      console.error('Failed to load admin data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  const handleSyncProvider = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/services/sync', { method: 'POST' });
      const data = await res.json();
      setStatusNotice({ ok: true, msg: data.message || 'Provider services synced successfully.' });
      onRefreshServices();
      fetchAdminData();
    } catch (err: any) {
      setStatusNotice({ ok: false, msg: err.message || 'Failed to sync with provider.' });
    } finally {
      setLoading(false);
    }
  };

  const handleToggleService = async (serviceId: string) => {
    try {
      await fetch(`/api/services/${serviceId}/toggle`, { method: 'PATCH' });
      onRefreshServices();
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveServicePrice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingService) return;

    try {
      await fetch(`/api/services/${editingService._id}/price`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selling_price: editingService.selling_price,
          provider_service_id: editingService.provider_service_id
        })
      });
      setEditingService(null);
      setStatusNotice({ ok: true, msg: `Updated ${editingService.display_name} selling price!` });
      onRefreshServices();
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateService = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/services', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newService)
      });
      if (res.ok) {
        setShowAddServiceModal(false);
        setStatusNotice({ ok: true, msg: 'New service created and enabled in catalog!' });
        onRefreshServices();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteService = async (id: string) => {
    if (!confirm('Are you sure you want to remove this service?')) return;
    try {
      await fetch(`/api/services/${id}`, { method: 'DELETE' });
      setStatusNotice({ ok: true, msg: 'Service deleted.' });
      onRefreshServices();
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateGiftCode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGiftCode.code.trim()) return;

    try {
      const res = await fetch('/api/admin/giftcodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newGiftCode)
      });
      if (res.ok) {
        setNewGiftCode({ code: '', amount: 50, max_claims: 100 });
        setStatusNotice({ ok: true, msg: `Gift code ${newGiftCode.code} created!` });
        fetchAdminData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteGiftCode = async (code: string) => {
    try {
      await fetch(`/api/admin/giftcodes/${code}`, { method: 'DELETE' });
      setStatusNotice({ ok: true, msg: `Gift code ${code} deleted.` });
      fetchAdminData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAdjustBalance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!balanceTargetUser) return;

    try {
      await fetch(`/api/admin/users/${balanceTargetUser.user_id}/balance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount: balanceAmount, action: balanceAction })
      });
      setBalanceTargetUser(null);
      setStatusNotice({ ok: true, msg: `User balance ${balanceAction === 'add' ? 'credited' : 'debited'} by ₹${balanceAmount}!` });
      fetchAdminData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleBan = async (userId: number) => {
    try {
      await fetch(`/api/admin/users/${userId}/ban`, { method: 'POST' });
      setStatusNotice({ ok: true, msg: `User ${userId} ban status toggled!` });
      fetchAdminData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configForm)
      });
      setStatusNotice({ ok: true, msg: 'Configuration settings updated!' });
    } catch (err) {
      console.error(err);
    }
  };

  const handleSendBroadcast = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!broadcastMessage.trim()) return;

    try {
      const res = await fetch('/api/admin/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: broadcastMessage })
      });
      const data = await res.json();
      setBroadcastMessage('');
      setStatusNotice({ ok: true, msg: data.message });
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Admin Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900 border border-purple-500/30 p-5 rounded-2xl">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-100">Admin Control Center</h2>
            <p className="text-xs text-slate-400">SMM Panel Management, Pricing, Users & Automation</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={fetchAdminData}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs font-semibold"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Data</span>
          </button>
        </div>
      </div>

      {/* Global Status Notice */}
      {statusNotice && (
        <div className={`p-3.5 rounded-xl text-xs flex items-center justify-between ${
          statusNotice.ok ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
        }`}>
          <span>{statusNotice.msg}</span>
          <button onClick={() => setStatusNotice(null)} className="text-slate-400 hover:text-white">✕</button>
        </div>
      )}

      {/* Admin Navigation Tabs */}
      <div className="flex items-center space-x-1 bg-slate-900/90 border border-slate-800 p-1.5 rounded-xl overflow-x-auto text-xs">
        <button
          onClick={() => setActiveAdminTab('stats')}
          className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg font-semibold transition ${
            activeAdminTab === 'stats' ? 'bg-purple-500 text-white shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Dashboard Stats</span>
        </button>

        <button
          onClick={() => setActiveAdminTab('services')}
          className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg font-semibold transition ${
            activeAdminTab === 'services' ? 'bg-purple-500 text-white shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <ShoppingBag className="w-3.5 h-3.5" />
          <span>Services & Rates ({services.length})</span>
        </button>

        <button
          onClick={() => setActiveAdminTab('users')}
          className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg font-semibold transition ${
            activeAdminTab === 'users' ? 'bg-purple-500 text-white shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>User Accounts ({usersList.length})</span>
        </button>

        <button
          onClick={() => setActiveAdminTab('giftcodes')}
          className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg font-semibold transition ${
            activeAdminTab === 'giftcodes' ? 'bg-purple-500 text-white shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Gift className="w-3.5 h-3.5" />
          <span>Gift Codes ({giftCodesList.length})</span>
        </button>

        <button
          onClick={() => setActiveAdminTab('settings')}
          className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg font-semibold transition ${
            activeAdminTab === 'settings' ? 'bg-purple-500 text-white shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Settings className="w-3.5 h-3.5" />
          <span>System Config</span>
        </button>

        <button
          onClick={() => setActiveAdminTab('broadcast')}
          className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg font-semibold transition ${
            activeAdminTab === 'broadcast' ? 'bg-purple-500 text-white shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Radio className="w-3.5 h-3.5" />
          <span>Broadcast</span>
        </button>
      </div>

      {/* Tab: Stats */}
      {activeAdminTab === 'stats' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-slate-400 text-xs font-medium">Total Registered Users</span>
              <div className="text-2xl font-bold font-mono text-slate-100 mt-1">{stats?.total_users || usersList.length}</div>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-slate-400 text-xs font-medium">Total INR Balance Held</span>
              <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">₹{(stats?.total_inr_held || 0).toFixed(2)}</div>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-slate-400 text-xs font-medium">Total Placed Orders</span>
              <div className="text-2xl font-bold font-mono text-sky-400 mt-1">{stats?.total_orders || 0}</div>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-slate-400 text-xs font-medium">Active Services</span>
              <div className="text-2xl font-bold font-mono text-purple-400 mt-1">{services.filter(s => s.enabled).length} / {services.length}</div>
            </div>
          </div>

          {/* Quick Actions Card */}
          <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-3">
            <h3 className="text-sm font-bold text-slate-200">Provider Synchronization</h3>
            <p className="text-xs text-slate-400">
              Synchronize live services catalog and rate cards directly from your SMM provider endpoint: <code className="text-slate-300">{configForm.smm_panel_url}</code>
            </p>
            <div className="flex space-x-3 pt-2">
              <button
                onClick={handleSyncProvider}
                disabled={loading}
                className="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white text-xs font-bold rounded-xl transition flex items-center space-x-2"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                <span>{loading ? 'Syncing...' : 'Sync Provider Services Now'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Services & Rates */}
      {activeAdminTab === 'services' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center bg-slate-900 p-4 rounded-xl border border-slate-800">
            <div>
              <h3 className="text-sm font-bold text-slate-100">Curated SMM Services</h3>
              <p className="text-xs text-slate-400">Manage client pricing, provider mappings, and visibility</p>
            </div>
            <button
              onClick={() => setShowAddServiceModal(true)}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg transition"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Custom Service</span>
            </button>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase tracking-wider font-semibold">
                  <tr>
                    <th className="p-3">Status</th>
                    <th className="p-3">Platform & Display Name</th>
                    <th className="p-3">Provider ID</th>
                    <th className="p-3">Cost Rate / 1k</th>
                    <th className="p-3">Selling Price / 1k</th>
                    <th className="p-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {services.map(svc => (
                    <tr key={svc._id} className="hover:bg-slate-850 transition">
                      <td className="p-3">
                        <button
                          onClick={() => handleToggleService(svc._id)}
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            svc.enabled ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-500'
                          }`}
                        >
                          {svc.enabled ? 'ENABLED' : 'DISABLED'}
                        </button>
                      </td>
                      <td className="p-3">
                        <div className="font-semibold text-slate-200">{svc.display_name}</div>
                        <div className="text-[11px] text-slate-500">{svc.platform} • {svc.category}</div>
                      </td>
                      <td className="p-3 font-mono text-slate-300">
                        {svc.provider_service_id}
                      </td>
                      <td className="p-3 font-mono text-slate-400">
                        ₹{(svc.provider_rate || 10).toFixed(2)}
                      </td>
                      <td className="p-3 font-mono font-bold text-emerald-400 text-sm">
                        ₹{svc.selling_price.toFixed(2)}
                      </td>
                      <td className="p-3 space-x-2">
                        <button
                          onClick={() => setEditingService(svc)}
                          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded transition"
                          title="Edit Price & ID"
                        >
                          <Edit className="w-3 h-3 inline mr-1" />
                          <span>Edit</span>
                        </button>
                        <button
                          onClick={() => handleDeleteService(svc._id)}
                          className="px-2 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded transition"
                          title="Delete Service"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Edit Service Modal */}
      {editingService && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
            <h3 className="font-bold text-slate-100 text-sm">Edit Service Selling Rate</h3>
            <p className="text-xs text-slate-400">{editingService.display_name}</p>

            <form onSubmit={handleSaveServicePrice} className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Customer Selling Price per 1,000 (INR ₹)</label>
                <input
                  type="number"
                  step="0.01"
                  value={editingService.selling_price}
                  onChange={(e) => setEditingService({ ...editingService, selling_price: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-100 font-mono"
                  required
                />
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Provider Service ID</label>
                <input
                  type="number"
                  value={editingService.provider_service_id}
                  onChange={(e) => setEditingService({ ...editingService, provider_service_id: parseInt(e.target.value) || 0 })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-100 font-mono"
                  required
                />
              </div>

              <div className="flex space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingService(null)}
                  className="flex-1 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-white text-xs font-bold"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Service Modal */}
      {showAddServiceModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <h3 className="font-bold text-slate-100 text-base">Add New Curated SMM Service</h3>

            <form onSubmit={handleCreateService} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Display Name (Client Facing)</label>
                <input
                  type="text"
                  value={newService.display_name}
                  onChange={(e) => setNewService({ ...newService, display_name: e.target.value })}
                  placeholder="e.g. Instagram Followers (Real & Fast)"
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Platform</label>
                  <select
                    value={newService.platform}
                    onChange={(e) => setNewService({ ...newService, platform: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100"
                  >
                    <option value="Instagram">Instagram</option>
                    <option value="YouTube">YouTube</option>
                    <option value="Telegram">Telegram</option>
                    <option value="Facebook">Facebook</option>
                    <option value="Twitter/X">Twitter/X</option>
                    <option value="TikTok">TikTok</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Category</label>
                  <input
                    type="text"
                    value={newService.category}
                    onChange={(e) => setNewService({ ...newService, category: e.target.value })}
                    placeholder="e.g. Followers, Views, Likes"
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Provider Service ID</label>
                  <input
                    type="number"
                    value={newService.provider_service_id}
                    onChange={(e) => setNewService({ ...newService, provider_service_id: parseInt(e.target.value) || 0 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
                    required
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Selling Rate per 1,000 (INR ₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={newService.selling_price}
                    onChange={(e) => setNewService({ ...newService, selling_price: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono font-bold text-emerald-400"
                    required
                  />
                </div>
              </div>

              <div className="flex space-x-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddServiceModal(false)}
                  className="flex-1 py-2.5 rounded-xl bg-slate-800 text-slate-300 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold"
                >
                  Add Service
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Tab: Users Management */}
      {activeAdminTab === 'users' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase tracking-wider font-semibold">
                  <tr>
                    <th className="p-3">User ID & Name</th>
                    <th className="p-3">Wallet Balance</th>
                    <th className="p-3">Orders</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {usersList.map(u => (
                    <tr key={u.user_id} className="hover:bg-slate-850 transition">
                      <td className="p-3">
                        <div className="font-semibold text-slate-200">{u.first_name}</div>
                        <div className="text-[11px] text-slate-500 font-mono">ID: {u.user_id} (@{u.username})</div>
                      </td>
                      <td className="p-3 font-mono font-bold text-emerald-400 text-sm">
                        ₹{u.balance.toFixed(2)}
                      </td>
                      <td className="p-3 font-mono text-slate-300">
                        {u.orders_count || 0}
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          u.banned ? 'bg-rose-500/20 text-rose-400' : 'bg-emerald-500/20 text-emerald-400'
                        }`}>
                          {u.banned ? 'BANNED' : 'ACTIVE'}
                        </span>
                      </td>
                      <td className="p-3 space-x-2">
                        <button
                          onClick={() => setBalanceTargetUser(u)}
                          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-sky-400 rounded font-medium transition"
                        >
                          <Coins className="w-3 h-3 inline mr-1" />
                          <span>Adjust Balance</span>
                        </button>
                        <button
                          onClick={() => handleToggleBan(u.user_id)}
                          className={`px-2.5 py-1 rounded font-medium transition ${
                            u.banned ? 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20' : 'bg-rose-500/10 text-rose-400 hover:bg-rose-500/20'
                          }`}
                        >
                          {u.banned ? <Unlock className="w-3 h-3 inline mr-1" /> : <Lock className="w-3 h-3 inline mr-1" />}
                          <span>{u.banned ? 'Unban' : 'Ban'}</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Adjust Balance Modal */}
      {balanceTargetUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-sm p-5 space-y-4 shadow-2xl">
            <h3 className="font-bold text-slate-100 text-sm">Adjust User Balance</h3>
            <p className="text-xs text-slate-400">User: {balanceTargetUser.first_name} (ID: {balanceTargetUser.user_id})</p>

            <form onSubmit={handleAdjustBalance} className="space-y-3 text-xs">
              <div className="flex space-x-2">
                <button
                  type="button"
                  onClick={() => setBalanceAction('add')}
                  className={`flex-1 py-2 rounded-lg font-bold transition ${
                    balanceAction === 'add' ? 'bg-emerald-500 text-white' : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  + Add INR (Credit)
                </button>
                <button
                  type="button"
                  onClick={() => setBalanceAction('remove')}
                  className={`flex-1 py-2 rounded-lg font-bold transition ${
                    balanceAction === 'remove' ? 'bg-rose-500 text-white' : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  - Deduct (Debit)
                </button>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Amount (INR ₹)</label>
                <input
                  type="number"
                  min="1"
                  value={balanceAmount}
                  onChange={(e) => setBalanceAmount(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono text-sm font-bold"
                  required
                />
              </div>

              <div className="flex space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setBalanceTargetUser(null)}
                  className="flex-1 py-2 rounded-xl bg-slate-800 text-slate-300 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold"
                >
                  Apply
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Tab: Gift Codes */}
      {activeAdminTab === 'giftcodes' && (
        <div className="space-y-5">
          {/* Create Gift Code Card */}
          <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-3">
            <h3 className="text-sm font-bold text-slate-100">Create Promotional Gift Code</h3>
            
            <form onSubmit={handleCreateGiftCode} className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
              <input
                type="text"
                value={newGiftCode.code}
                onChange={(e) => setNewGiftCode({ ...newGiftCode, code: e.target.value.toUpperCase() })}
                placeholder="PROMO CODE (e.g. FESTIVE2026)"
                className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono uppercase"
                required
              />

              <input
                type="number"
                value={newGiftCode.amount}
                onChange={(e) => setNewGiftCode({ ...newGiftCode, amount: parseFloat(e.target.value) || 0 })}
                placeholder="INR Value (e.g. 50)"
                className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
                required
              />

              <input
                type="number"
                value={newGiftCode.max_claims}
                onChange={(e) => setNewGiftCode({ ...newGiftCode, max_claims: parseInt(e.target.value) || 100 })}
                placeholder="Max Claims"
                className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
              />

              <button
                type="submit"
                className="py-2 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl transition"
              >
                + Create Code
              </button>
            </form>
          </div>

          {/* Active Codes List */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase font-semibold">
                <tr>
                  <th className="p-3">Gift Code</th>
                  <th className="p-3">INR Value</th>
                  <th className="p-3">Claims</th>
                  <th className="p-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {giftCodesList.map(gc => (
                  <tr key={gc.code} className="hover:bg-slate-850 transition">
                    <td className="p-3 font-mono font-bold text-sky-400">{gc.code}</td>
                    <td className="p-3 font-mono text-emerald-400 font-bold">₹{gc.amount.toFixed(2)}</td>
                    <td className="p-3 text-slate-400">{gc.claimed_count} / {gc.max_claims || 100}</td>
                    <td className="p-3">
                      <button
                        onClick={() => handleDeleteGiftCode(gc.code)}
                        className="px-2.5 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded transition"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab: System Settings */}
      {activeAdminTab === 'settings' && (
        <form onSubmit={handleSaveConfig} className="bg-slate-900 border border-slate-800 p-6 rounded-2xl space-y-4 text-xs">
          <h3 className="text-sm font-bold text-slate-100 border-b border-slate-800 pb-3">Bot Settings & API Keys</h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-slate-400 mb-1 font-medium">SMM Panel Provider URL</label>
              <input
                type="text"
                value={configForm.smm_panel_url}
                onChange={(e) => setConfigForm({ ...configForm, smm_panel_url: e.target.value })}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-medium">Global Markup Percentage (%)</label>
              <input
                type="number"
                value={configForm.markup_percentage}
                onChange={(e) => setConfigForm({ ...configForm, markup_percentage: parseFloat(e.target.value) || 0 })}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-medium">Referral Reward (INR ₹)</label>
              <input
                type="number"
                value={configForm.referral_reward_inr}
                onChange={(e) => setConfigForm({ ...configForm, referral_reward_inr: parseFloat(e.target.value) || 0 })}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-medium">Daily Bonus (INR ₹)</label>
              <input
                type="number"
                value={configForm.daily_bonus_inr}
                onChange={(e) => setConfigForm({ ...configForm, daily_bonus_inr: parseFloat(e.target.value) || 0 })}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-medium">Logs Channel ID / Username</label>
              <input
                type="text"
                value={configForm.logs_channel}
                onChange={(e) => setConfigForm({ ...configForm, logs_channel: e.target.value })}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-medium">Support Contact Username</label>
              <input
                type="text"
                value={configForm.payment_contact}
                onChange={(e) => setConfigForm({ ...configForm, payment_contact: e.target.value })}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
              />
            </div>
          </div>

          <div className="pt-3">
            <button
              type="submit"
              className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl transition"
            >
              Save Configuration
            </button>
          </div>
        </form>
      )}

      {/* Tab: Broadcast */}
      {activeAdminTab === 'broadcast' && (
        <form onSubmit={handleSendBroadcast} className="bg-slate-900 border border-slate-800 p-6 rounded-2xl space-y-4 text-xs">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-sky-500/10 text-sky-400 flex items-center justify-center">
              <Radio className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-100 text-sm">Broadcast Telegram Message</h3>
              <p className="text-slate-400">Send an instant announcement to all registered bot users ({usersList.length} users)</p>
            </div>
          </div>

          <textarea
            rows={5}
            value={broadcastMessage}
            onChange={(e) => setBroadcastMessage(e.target.value)}
            placeholder="Type announcement message (Supports HTML like <b>bold</b>, <code>code</code>, links)..."
            className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-slate-100 font-mono focus:outline-none focus:border-sky-500"
            required
          />

          <button
            type="submit"
            className="flex items-center space-x-2 px-5 py-2.5 bg-sky-500 hover:bg-sky-400 text-white font-bold rounded-xl transition"
          >
            <Send className="w-4 h-4" />
            <span>Send Broadcast Message</span>
          </button>
        </form>
      )}

    </div>
  );
};
