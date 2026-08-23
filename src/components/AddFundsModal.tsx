import React, { useState } from 'react';
import { UserAccount, BotConfig } from '../types.ts';
import { X, QrCode, CreditCard, Copy, Check, ShieldCheck, Sparkles } from 'lucide-react';

interface AddFundsModalProps {
  currentUser: UserAccount;
  config: BotConfig | null;
  onClose: () => void;
  onDeposit: (amount: number, utr: string) => Promise<boolean>;
}

export const AddFundsModal: React.FC<AddFundsModalProps> = ({
  currentUser,
  config,
  onClose,
  onDeposit
}) => {
  const [amount, setAmount] = useState<number>(100);
  const [utr, setUtr] = useState('');
  const [copied, setCopied] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const paymentContact = config?.payment_contact || '@BOBBY_2606';
  const qrUrl = config?.qr_code_url || 'https://t.me/bobbyQr/2';

  const handleCopyUPI = () => {
    navigator.clipboard.writeText('bobbyahirwar@upi');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDepositSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!amount || amount <= 0) {
      setError('Please enter a valid amount.');
      return;
    }

    setSubmitting(true);
    try {
      const ok = await onDeposit(amount, utr.trim());
      if (ok) {
        setSuccessMsg(`₹${amount} has been added directly to your wallet!`);
        setTimeout(() => {
          onClose();
        }, 1500);
      }
    } catch (err: any) {
      setError(err.message || 'Deposit failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
        
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-850">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <CreditCard className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-100 text-base">Add Wallet Funds</h3>
              <p className="text-xs text-slate-400">UPI / QR Instant Auto Recharge</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-5">

          {/* QR Code & Payment Instructions */}
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col items-center text-center space-y-3">
            <div className="w-36 h-36 bg-white p-2 rounded-xl shadow-md flex items-center justify-center relative">
              <QrCode className="w-28 h-28 text-slate-900" />
              <div className="absolute inset-0 flex items-center justify-center bg-slate-900/5 backdrop-blur-[0.5px]">
                <div className="bg-emerald-600 text-white text-[9px] font-bold px-2 py-0.5 rounded shadow">
                  BHIM UPI
                </div>
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-xs font-semibold text-slate-300">Scan QR or Pay via UPI ID</div>
              <div className="flex items-center justify-center space-x-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg">
                <span className="font-mono text-xs text-sky-400 font-medium">bobbyahirwar@upi</span>
                <button
                  type="button"
                  onClick={handleCopyUPI}
                  className="text-slate-400 hover:text-white transition"
                  title="Copy UPI ID"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
              <p className="text-[11px] text-slate-500 pt-1">
                Support contact: <span className="text-slate-300 font-mono">{paymentContact}</span>
              </p>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleDepositSubmit} className="space-y-4">
            {/* Amount Selection */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Select or Enter Amount (INR ₹)
              </label>

              <div className="grid grid-cols-4 gap-2">
                {[50, 100, 250, 500].map((amt) => (
                  <button
                    key={amt}
                    type="button"
                    onClick={() => setAmount(amt)}
                    className={`py-2 text-xs font-mono font-semibold rounded-lg border transition ${
                      amount === amt
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400'
                        : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-750'
                    }`}
                  >
                    ₹{amt}
                  </button>
                ))}
              </div>

              <input
                type="number"
                min="10"
                value={amount}
                onChange={(e) => setAmount(Math.max(1, parseInt(e.target.value) || 0))}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 font-mono font-medium focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                placeholder="Custom Amount"
                required
              />
            </div>

            {/* UTR / Transaction Ref */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                UTR / Reference Number (12 Digits)
              </label>
              <input
                type="text"
                value={utr}
                onChange={(e) => setUtr(e.target.value)}
                placeholder="e.g. 423981293812"
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-slate-100 font-mono placeholder-slate-600 focus:outline-none focus:border-emerald-500"
              />
            </div>

            {error && (
              <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 p-2.5 rounded-lg">
                {error}
              </div>
            )}

            {successMsg && (
              <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 p-2.5 rounded-lg font-medium flex items-center space-x-2">
                <Check className="w-4 h-4" />
                <span>{successMsg}</span>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-semibold text-sm shadow-lg shadow-emerald-500/20 transition flex items-center justify-center space-x-2"
            >
              <Sparkles className="w-4 h-4" />
              <span>{submitting ? 'Verifying...' : `Add ₹${amount} To Wallet`}</span>
            </button>
          </form>

        </div>

      </div>
    </div>
  );
};
