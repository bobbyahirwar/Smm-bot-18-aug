import React, { useState } from 'react';
import { SMMOrder } from '../types.ts';
import { 
  Clock, 
  Search, 
  CheckCircle2, 
  Loader2, 
  ExternalLink, 
  RefreshCw, 
  AlertCircle,
  Package,
  Layers
} from 'lucide-react';

interface MyOrdersProps {
  orders: SMMOrder[];
  onRefresh: () => void;
}

export const MyOrders: React.FC<MyOrdersProps> = ({ orders, onRefresh }) => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const filteredOrders = orders.filter(o => {
    const matchesStatus = statusFilter === 'all' || o.status === statusFilter;
    const matchesSearch = !search.trim() || 
      o.id.toLowerCase().includes(search.toLowerCase()) ||
      o.service_name.toLowerCase().includes(search.toLowerCase()) ||
      o.link.toLowerCase().includes(search.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Completed</span>
          </span>
        );
      case 'processing':
      case 'in_progress':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>Processing</span>
          </span>
        );
      case 'partial':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Partial</span>
          </span>
        );
      case 'canceled':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Canceled</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300">
            <Clock className="w-3.5 h-3.5" />
            <span>Pending</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900/90 border border-slate-800 p-5 rounded-2xl">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
            <Package className="w-5 h-5 text-sky-400" />
            <span>Order History & Tracking</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real-time status updates from provider SMM servers
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={onRefresh}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs font-semibold transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter and Search */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-slate-900/60 border border-slate-800 p-3.5 rounded-2xl">
        <div className="relative w-full sm:w-80">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by Order ID, link, or service..."
            className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 pl-9 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
          />
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
        </div>

        {/* Status Filter */}
        <div className="flex items-center space-x-1 overflow-x-auto w-full sm:w-auto text-xs">
          {['all', 'processing', 'completed', 'partial', 'canceled'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-lg capitalize font-medium transition ${
                statusFilter === st
                  ? 'bg-sky-500 text-white shadow-sm'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Orders List */}
      {filteredOrders.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-800 text-slate-500 mx-auto flex items-center justify-center">
            <Layers className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-slate-200">No Orders Found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            You haven't placed any orders yet or no orders match your search criteria.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredOrders.map(order => (
            <div
              key={order.id}
              className="bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 transition space-y-4 shadow-sm"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                <div className="flex items-center space-x-2.5">
                  <span className="font-mono font-bold text-sky-400 text-sm">{order.id}</span>
                  <span className="text-xs text-slate-500">•</span>
                  <span className="text-xs text-slate-400">
                    {new Date(order.created_at).toLocaleString()}
                  </span>
                  {order.provider_order_id && (
                    <span className="hidden sm:inline-block text-[11px] font-mono bg-slate-950 text-slate-400 px-2 py-0.5 rounded border border-slate-800">
                      Prov ID: {order.provider_order_id}
                    </span>
                  )}
                </div>

                <div>
                  {getStatusBadge(order.status)}
                </div>
              </div>

              {/* Order Info */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div className="space-y-1 sm:col-span-2">
                  <div className="text-slate-400 font-medium">Service</div>
                  <div className="text-slate-100 font-semibold text-sm">{order.service_name}</div>
                  
                  <div className="flex items-center space-x-1 pt-1 text-slate-400 truncate">
                    <span className="text-slate-500">Target Link:</span>
                    <a
                      href={order.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sky-400 hover:underline flex items-center space-x-1 truncate max-w-xs"
                    >
                      <span className="truncate">{order.link}</span>
                      <ExternalLink className="w-3 h-3 shrink-0" />
                    </a>
                  </div>
                </div>

                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80 flex flex-col justify-between space-y-1">
                  <div className="flex justify-between items-center text-slate-400">
                    <span>Quantity:</span>
                    <span className="font-bold text-slate-200">{order.quantity.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center text-slate-400">
                    <span>Total Charge:</span>
                    <span className="font-mono font-bold text-emerald-400 text-sm">₹{order.charge.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between items-center text-slate-500 text-[10px] pt-1 border-t border-slate-800">
                    <span>Est Delivery:</span>
                    <span>{order.estimated_time || '1-3 hours'}</span>
                  </div>
                </div>
              </div>

            </div>
          ))}
        </div>
      )}

    </div>
  );
};
