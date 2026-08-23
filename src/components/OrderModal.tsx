import React, { useState } from 'react';
import { SMMService, UserAccount } from '../types.ts';
import { X, ShoppingCart, AlertCircle, CheckCircle2, ShieldCheck, Link2, Zap } from 'lucide-react';

interface OrderModalProps {
  service: SMMService | null;
  currentUser: UserAccount;
  onClose: () => void;
  onPlaceOrder: (serviceId: string, link: string, quantity: number) => Promise<boolean>;
  onOpenAddFunds: () => void;
}

export const OrderModal: React.FC<OrderModalProps> = ({
  service,
  currentUser,
  onClose,
  onPlaceOrder,
  onOpenAddFunds
}) => {
  if (!service) return null;

  const [link, setLink] = useState('');
  const [quantity, setQuantity] = useState<number>(service.min);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calculateCharge = (qty: number) => {
    return Math.round(((qty / 1000.0) * service.selling_price) * 100) / 100;
  };

  const currentCharge = calculateCharge(quantity);
  const hasSufficientBalance = currentUser.balance >= currentCharge;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!link.trim()) {
      setError('Please provide a valid URL/link (profile, post, channel or video link).');
      return;
    }

    if (quantity < service.min || quantity > service.max) {
      setError(`Quantity must be between ${service.min} and ${service.max.toLocaleString()}.`);
      return;
    }

    if (!hasSufficientBalance) {
      setError(`Insufficient wallet balance. Required: ₹${currentCharge.toFixed(2)}, Available: ₹${currentUser.balance.toFixed(2)}.`);
      return;
    }

    setSubmitting(true);
    try {
      const success = await onPlaceOrder(service._id, link.trim(), quantity);
      if (success) {
        onClose();
      }
    } catch (err: any) {
      setError(err.message || 'Failed to place order.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-850">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
              <ShoppingCart className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-100 text-base">Place SMM Order</h3>
              <p className="text-xs text-slate-400">{service.platform} • {service.category}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          
          {/* Service Banner */}
          <div className="p-3.5 bg-slate-800/80 border border-slate-700/80 rounded-xl">
            <div className="font-medium text-sm text-slate-200">{service.display_name}</div>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-700/60 text-xs">
              <span className="text-slate-400">Rate per 1,000:</span>
              <span className="font-mono font-bold text-sky-400">₹{service.selling_price.toFixed(2)}</span>
            </div>
            <div className="flex items-center justify-between text-xs mt-1">
              <span className="text-slate-400">Limits (Min / Max):</span>
              <span className="text-slate-300">{service.min.toLocaleString()} - {service.max.toLocaleString()}</span>
            </div>
          </div>

          {/* Link Input */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Target Link / URL <span className="text-rose-400">*</span>
            </label>
            <div className="relative">
              <input
                type="text"
                value={link}
                onChange={(e) => setLink(e.target.value)}
                placeholder="https://instagram.com/p/... or https://t.me/..."
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 pl-9 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition"
                required
              />
              <Link2 className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
            </div>
            <p className="text-[11px] text-slate-500">Ensure profile or channel is public during processing.</p>
          </div>

          {/* Quantity Input with Quick Presets */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Quantity <span className="text-rose-400">*</span>
              </label>
              <span className="text-xs text-slate-400">
                Min: {service.min} | Max: {service.max.toLocaleString()}
              </span>
            </div>

            <input
              type="number"
              min={service.min}
              max={service.max}
              value={quantity}
              onChange={(e) => setQuantity(Math.max(0, parseInt(e.target.value) || 0))}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 font-mono font-medium focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition"
              required
            />

            {/* Presets */}
            <div className="flex items-center space-x-2 pt-1">
              {[100, 500, 1000, 2500, 5000].map((preset) => {
                if (preset >= service.min && preset <= service.max) {
                  return (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setQuantity(preset)}
                      className={`px-2.5 py-1 text-xs rounded-lg border transition ${
                        quantity === preset
                          ? 'bg-sky-500/20 border-sky-500 text-sky-400 font-semibold'
                          : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {preset.toLocaleString()}
                    </button>
                  );
                }
                return null;
              })}
            </div>
          </div>

          {/* Pricing & Balance Calculation */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">Order Total:</span>
              <span className="font-mono text-base font-bold text-emerald-400">
                ₹{currentCharge.toFixed(2)}
              </span>
            </div>
            
            <div className="flex items-center justify-between text-xs pt-2 border-t border-slate-800">
              <span className="text-slate-400">Your Wallet Balance:</span>
              <span className={`font-mono font-semibold ${hasSufficientBalance ? 'text-slate-200' : 'text-rose-400'}`}>
                ₹{currentUser.balance.toFixed(2)}
              </span>
            </div>

            {!hasSufficientBalance && (
              <div className="flex items-center justify-between pt-1">
                <span className="text-xs text-rose-400 font-medium">⚠️ Needs ₹{(currentCharge - currentUser.balance).toFixed(2)} more</span>
                <button
                  type="button"
                  onClick={onOpenAddFunds}
                  className="text-xs text-sky-400 hover:text-sky-300 underline font-semibold"
                >
                  Recharge Wallet Now
                </button>
              </div>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="flex items-start space-x-2 p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center space-x-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 px-4 rounded-xl border border-slate-700 text-slate-300 text-sm font-medium hover:bg-slate-800 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !hasSufficientBalance}
              className="flex-1 flex items-center justify-center space-x-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold shadow-lg shadow-sky-500/20 transition"
            >
              <Zap className="w-4 h-4" />
              <span>{submitting ? 'Submitting...' : 'Confirm Order'}</span>
            </button>
          </div>

        </form>

      </div>
    </div>
  );
};
