import React, { useState } from 'react';
import { UserAccount, WalletLedgerEntry, BotConfig } from '../types.ts';
import { 
  Wallet, 
  Gift, 
  Share2, 
  CreditCard, 
  ArrowUpRight, 
  ArrowDownLeft, 
  Check, 
  Copy, 
  Sparkles, 
  QrCode, 
  History,
  Coins
} from 'lucide-react';

interface WalletViewProps {
  currentUser: UserAccount;
  ledger: WalletLedgerEntry[];
  config: BotConfig | null;
  onOpenAddFunds: () => void;
  onClaimBonus: () => Promise<{ success: boolean; message: string }>;
  onRedeemGiftCode: (code: string) => Promise<{ success: boolean; message: string }>;
}

export const WalletView: React.FC<WalletViewProps> = ({
  currentUser,
  ledger,
  config,
  onOpenAddFunds,
  onClaimBonus,
  onRedeemGiftCode
}) => {
  const [giftCodeInput, setGiftCodeInput] = useState('');
  const [redeeming, setRedeeming] = useState(false);
  const [claimingBonus, setClaimingBonus] = useState(false);
  const [bonusStatus, setBonusStatus] = useState<string | null>(null);
  const [giftStatus, setGiftStatus] = useState<{ ok: boolean; msg: string } | null>(null);
  const [copiedReferral, setCopiedReferral] = useState(false);

  const today = new Date().toISOString().split('T')[0];
  const hasClaimedToday = currentUser.last_bonus === today;

  const referralLink = `https://t.me/${config?.bot_username || 'BobbySMM_bot'}?start=${currentUser.user_id}`;

  const handleCopyReferral = () => {
    navigator.clipboard.writeText(referralLink);
    setCopiedReferral(true);
    setTimeout(() => setCopiedReferral(false), 2000);
  };

  const handleClaimBonusClick = async () => {
    setClaimingBonus(true);
    setBonusStatus(null);
    try {
      const res = await onClaimBonus();
      setBonusStatus(res.message);
    } catch (err: any) {
      setBonusStatus(err.message || 'Could not claim bonus.');
    } finally {
      setClaimingBonus(false);
    }
  };

  const handleGiftCodeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!giftCodeInput.trim()) return;

    setRedeeming(true);
    setGiftStatus(null);
    try {
      const res = await onRedeemGiftCode(giftCodeInput.trim());
      setGiftStatus({ ok: res.success, msg: res.message });
      if (res.success) setGiftCodeInput('');
    } catch (err: any) {
      setGiftStatus({ ok: false, msg: err.message || 'Invalid gift code' });
    } finally {
      setRedeeming(false);
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Wallet Balance Hero Card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        
        {/* Main Balance Box */}
        <div className="md:col-span-2 bg-gradient-to-br from-slate-900 via-slate-900 to-sky-950/40 border border-slate-800 rounded-2xl p-6 relative overflow-hidden shadow-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shadow-inner">
                <Coins className="w-6 h-6" />
              </div>
              <div>
                <p className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Available Wallet Balance</p>
                <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-100 font-mono tracking-tight">
                  ₹{currentUser.balance.toFixed(2)}
                </h2>
              </div>
            </div>

            <button
              onClick={onOpenAddFunds}
              className="hidden sm:flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 transition"
            >
              <CreditCard className="w-4 h-4" />
              <span>Add Funds (UPI)</span>
            </button>
          </div>

          <div className="mt-6 pt-5 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
            <div className="flex items-center space-x-4">
              <div>
                <span className="text-slate-500">Account ID:</span>{' '}
                <strong className="text-slate-200 font-mono">{currentUser.user_id}</strong>
              </div>
              <div>
                <span className="text-slate-500">Status:</span>{' '}
                <span className="text-emerald-400 font-semibold">Active & Verified</span>
              </div>
            </div>

            <button
              onClick={onOpenAddFunds}
              className="sm:hidden w-full flex items-center justify-center space-x-2 py-2.5 rounded-xl bg-emerald-500 text-white font-bold text-xs"
            >
              <CreditCard className="w-4 h-4" />
              <span>Add Funds (UPI)</span>
            </button>
          </div>
        </div>

        {/* Daily Bonus Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between space-y-4">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
              <Gift className="w-5 h-5" />
            </div>
            <h3 className="font-bold text-slate-100 text-sm">Daily Login Bonus</h3>
            <p className="text-xs text-slate-400">
              Claim ₹{config?.daily_bonus_inr || 10} free INR credits every 24 hours.
            </p>
          </div>

          <div>
            {bonusStatus && (
              <p className="text-xs text-emerald-400 mb-2 font-medium">{bonusStatus}</p>
            )}
            <button
              onClick={handleClaimBonusClick}
              disabled={hasClaimedToday || claimingBonus}
              className={`w-full py-2.5 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1.5 ${
                hasClaimedToday
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50'
                  : 'bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white shadow-md shadow-amber-500/20'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{hasClaimedToday ? 'Claimed Today (Come back tomorrow)' : claimingBonus ? 'Claiming...' : 'Claim ₹10 Bonus'}</span>
            </button>
          </div>
        </div>

      </div>

      {/* Gift Codes & Referral Program */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        
        {/* Gift Code Card */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
              <Gift className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-100 text-sm">Redeem Gift Code / Voucher</h3>
              <p className="text-xs text-slate-400">Got a promo code? Enter it to get instant INR wallet top-up</p>
            </div>
          </div>

          <form onSubmit={handleGiftCodeSubmit} className="space-y-3">
            <div className="flex space-x-2">
              <input
                type="text"
                value={giftCodeInput}
                onChange={(e) => setGiftCodeInput(e.target.value.toUpperCase())}
                placeholder="e.g. BOBBYWELCOME or FREESMM100"
                className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 uppercase tracking-wider"
              />
              <button
                type="submit"
                disabled={redeeming || !giftCodeInput.trim()}
                className="px-4 py-2 bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-white text-xs font-bold rounded-xl transition"
              >
                {redeeming ? 'Checking...' : 'Apply'}
              </button>
            </div>

            {giftStatus && (
              <p className={`text-xs ${giftStatus.ok ? 'text-emerald-400' : 'text-rose-400'} font-medium`}>
                {giftStatus.msg}
              </p>
            )}

            <p className="text-[11px] text-slate-500">
              Tip: Try codes <code className="text-slate-300">FREESMM100</code> or <code className="text-slate-300">BOBBYWELCOME</code>
            </p>
          </form>
        </div>

        {/* Refer & Earn Card */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Share2 className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-100 text-sm">Refer & Earn ₹{config?.referral_reward_inr || 25}</h3>
              <p className="text-xs text-slate-400">Share your Telegram referral link with friends and channels</p>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs bg-slate-950 border border-slate-800 rounded-xl p-2.5">
              <span className="font-mono text-slate-300 truncate max-w-[240px]">{referralLink}</span>
              <button
                onClick={handleCopyReferral}
                className="flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-400 text-xs font-semibold transition shrink-0"
              >
                {copiedReferral ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedReferral ? 'Copied' : 'Copy'}</span>
              </button>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
              <span>Your Referrals: <strong className="text-slate-200">{currentUser.referral_count || 0}</strong></span>
              <span>Total Earned: <strong className="text-emerald-400 font-mono">₹{(currentUser.referral_earnings || 0).toFixed(2)}</strong></span>
            </div>
          </div>
        </div>

      </div>

      {/* Transaction History Ledger */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="font-bold text-slate-100 text-sm flex items-center space-x-2">
            <History className="w-4 h-4 text-sky-400" />
            <span>Wallet Transaction History</span>
          </h3>
          <span className="text-xs text-slate-500">Atomic ledger records</span>
        </div>

        {ledger.length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-500">
            No transactions in your ledger yet.
          </div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {ledger.map((item) => {
              const isCredit = item.amount > 0;
              return (
                <div key={item.id} className="py-3 flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-3">
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center ${
                      isCredit ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                    }`}>
                      {isCredit ? <ArrowDownLeft className="w-3.5 h-3.5" /> : <ArrowUpRight className="w-3.5 h-3.5" />}
                    </div>
                    <div>
                      <div className="font-medium text-slate-200">{item.description}</div>
                      <div className="text-[11px] text-slate-500">{new Date(item.created_at).toLocaleString()}</div>
                    </div>
                  </div>

                  <div className={`font-mono font-bold text-sm ${isCredit ? 'text-emerald-400' : 'text-slate-300'}`}>
                    {isCredit ? '+' : ''}₹{Math.abs(item.amount).toFixed(2)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
};
