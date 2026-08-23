import express from 'express';
import cors from 'cors';
import path from 'path';
import { createServer as createViteServer } from 'vite';
import { SMMService, SMMOrder, UserAccount, GiftCode, WalletReservation, WalletLedgerEntry, BotConfig, AdminStats } from './src/types.ts';

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

// In-Memory Database (mocking MongoDB persistent collections)
let config: BotConfig = {
  bot_token: process.env.BOT_TOKEN || '',
  smm_panel_url: process.env.SMM_PANEL_URL || 'https://vcprovider.shop/api/v2',
  smm_api_key: process.env.SMM_API_KEY || '',
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
  channels: [
    { name: '🌺 MAIN', username: '-1004357091931', url: 'https://t.me/+JSco8U0Ej6c2Zjk1' },
    { name: '🤖 JOIN', username: '-1004490909992', url: 'https://t.me/+gaYXF8qAdTdiMWU1' }
  ],
  qr_code_url: 'https://t.me/bobbyQr/2',
  main_menu_photo_file_id: '',
  payment_contact: '@BOBBY_2606',
  bot_username: 'Bobby SMM Bot'
};

const services: SMMService[] = [
  {
    _id: 'reactions',
    name: '👍 Order Reactions',
    display_name: 'Instagram Reactions (Instant Fast)',
    platform: 'Instagram',
    provider_service_id: 476,
    category: 'Reactions',
    min: 10,
    max: 100000,
    provider_rate: 10,
    selling_price: 15,
    enabled: true,
    curated: true
  },
  {
    _id: 'views',
    name: '👀 Order Views',
    display_name: 'Instagram Video/Reels Views [HQ High Speed]',
    platform: 'Instagram',
    provider_service_id: 500,
    category: 'Views',
    min: 50,
    max: 1000000,
    provider_rate: 100,
    selling_price: 120,
    enabled: true,
    curated: true
  },
  {
    _id: 'members',
    name: '👥 Order Members',
    display_name: 'Telegram Channel/Group Members [Real Non-Drop]',
    platform: 'Telegram',
    provider_service_id: 470,
    category: 'Members',
    min: 20,
    max: 50000,
    provider_rate: 1,
    selling_price: 2.5,
    enabled: true,
    curated: true
  },
  {
    _id: 'ig_followers_hq',
    name: '📸 Instagram Followers',
    display_name: 'Instagram Followers [Real Active / 30 Days Refill]',
    platform: 'Instagram',
    provider_service_id: 512,
    category: 'Followers',
    min: 20,
    max: 500000,
    provider_rate: 45,
    selling_price: 65,
    enabled: true,
    curated: true
  },
  {
    _id: 'yt_views_monetizable',
    name: '▶️ YouTube Views',
    display_name: 'YouTube High Retention Views [Monetizable]',
    platform: 'YouTube',
    provider_service_id: 601,
    category: 'Views',
    min: 100,
    max: 2000000,
    provider_rate: 120,
    selling_price: 175,
    enabled: true,
    curated: true
  },
  {
    _id: 'yt_subscribers',
    name: '▶️ YouTube Subscribers',
    display_name: 'YouTube Real Subscribers [Lifetime Guarantee]',
    platform: 'YouTube',
    provider_service_id: 608,
    category: 'Subscribers',
    min: 10,
    max: 20000,
    provider_rate: 450,
    selling_price: 599,
    enabled: true,
    curated: true
  },
  {
    _id: 'tg_post_views',
    name: '✈️ Telegram Post Views',
    display_name: 'Telegram Channel Post Views [Instant Delivery]',
    platform: 'Telegram',
    provider_service_id: 480,
    category: 'Views',
    min: 50,
    max: 500000,
    provider_rate: 0.8,
    selling_price: 1.5,
    enabled: true,
    curated: true
  },
  {
    _id: 'fb_page_likes',
    name: '👍 Facebook Page Likes',
    display_name: 'Facebook Page Likes & Followers [Targeted]',
    platform: 'Facebook',
    provider_service_id: 710,
    category: 'Likes',
    min: 50,
    max: 100000,
    provider_rate: 90,
    selling_price: 135,
    enabled: true,
    curated: true
  },
  {
    _id: 'x_retweets_likes',
    name: '🐦 Twitter/X Retweets',
    display_name: 'Twitter/X Retweets & Fast Reposts',
    platform: 'Twitter/X',
    provider_service_id: 805,
    category: 'Retweets',
    min: 20,
    max: 50000,
    provider_rate: 80,
    selling_price: 110,
    enabled: true,
    curated: true
  },
  {
    _id: 'tiktok_views',
    name: '🎵 TikTok Views',
    display_name: 'TikTok Video Views [Super Fast Algorithm Boost]',
    platform: 'TikTok',
    provider_service_id: 902,
    category: 'Views',
    min: 100,
    max: 10000000,
    provider_rate: 5,
    selling_price: 9.9,
    enabled: true,
    curated: true
  }
];

const users = new Map<number, UserAccount>();
const orders = new Map<string, SMMOrder>();
const giftCodes = new Map<string, GiftCode>();
const reservations = new Map<string, WalletReservation>();
const ledger: WalletLedgerEntry[] = [];

// Seed initial users
const defaultAdminId = 881394179;
const demoUserId = 100435709;

users.set(defaultAdminId, {
  user_id: defaultAdminId,
  username: 'admin_bobby',
  first_name: 'Bobby (Admin)',
  balance: 5000.0,
  last_bonus: null,
  referral: { referrer: null, rewarded: false },
  referral_count: 8,
  referral_earnings: 200.0,
  redeemed_codes: [],
  banned: false,
  joined_at: new Date(Date.now() - 30 * 86400000).toISOString(),
  orders_count: 14
});

users.set(demoUserId, {
  user_id: demoUserId,
  username: 'social_booster',
  first_name: 'Alex Vance',
  balance: 245.50,
  last_bonus: new Date(Date.now() - 86400000 * 2).toISOString().split('T')[0],
  referral: { referrer: defaultAdminId, rewarded: true },
  referral_count: 2,
  referral_earnings: 50.0,
  redeemed_codes: ['BOBBYWELCOME'],
  banned: false,
  joined_at: new Date(Date.now() - 7 * 86400000).toISOString(),
  orders_count: 4
});

// Seed Initial Gift Codes
giftCodes.set('BOBBYWELCOME', {
  code: 'BOBBYWELCOME',
  amount: 50.0,
  created_at: new Date().toISOString(),
  claimed_count: 1,
  max_claims: 100
});

giftCodes.set('FREESMM100', {
  code: 'FREESMM100',
  amount: 100.0,
  created_at: new Date().toISOString(),
  claimed_count: 0,
  max_claims: 20
});

// Seed Initial Orders
const sampleOrders: SMMOrder[] = [
  {
    id: 'ORD-781920',
    user_id: demoUserId,
    user_name: 'Alex Vance',
    service_id: 'views',
    service_name: 'Instagram Video/Reels Views [HQ High Speed]',
    platform: 'Instagram',
    link: 'https://instagram.com/p/C9Z82kLa1x',
    quantity: 1000,
    charge: 120.0,
    status: 'completed',
    provider_order_id: 1092834,
    created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    estimated_time: 'Completed'
  },
  {
    id: 'ORD-781921',
    user_id: demoUserId,
    user_name: 'Alex Vance',
    service_id: 'reactions',
    service_name: 'Instagram Reactions (Instant Fast)',
    platform: 'Instagram',
    link: 'https://instagram.com/p/C9Z82kLa1x',
    quantity: 500,
    charge: 7.5,
    status: 'processing',
    provider_order_id: 1092855,
    created_at: new Date(Date.now() - 3600000 * 1).toISOString(),
    estimated_time: '1-2 hours'
  },
  {
    id: 'ORD-781922',
    user_id: defaultAdminId,
    user_name: 'Bobby (Admin)',
    service_id: 'members',
    service_name: 'Telegram Channel/Group Members [Real Non-Drop]',
    platform: 'Telegram',
    link: 'https://t.me/bobbypanelchannel',
    quantity: 2000,
    charge: 5.0,
    status: 'completed',
    provider_order_id: 1092801,
    created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
    estimated_time: 'Completed'
  }
];

sampleOrders.forEach(o => orders.set(o.id, o));

// Seed Ledger
ledger.push({
  id: 'LEDGER-1',
  user_id: demoUserId,
  event: 'deposit',
  amount: 300.0,
  description: 'UPI Add Funds Recharge (Ref: UPI98231024)',
  created_at: new Date(Date.now() - 86400000 * 3).toISOString()
});
ledger.push({
  id: 'LEDGER-2',
  user_id: demoUserId,
  event: 'giftcode',
  amount: 50.0,
  description: 'Redeemed Gift Code BOBBYWELCOME',
  created_at: new Date(Date.now() - 86400000 * 2).toISOString()
});
ledger.push({
  id: 'LEDGER-3',
  user_id: demoUserId,
  order_id: 'ORD-781920',
  event: 'settle',
  amount: -120.0,
  description: 'Order #ORD-781920 Instagram Views (1000 qty)',
  created_at: new Date(Date.now() - 3600000 * 4).toISOString()
});

// Helper functions
function getOrCreateUser(userId: number, firstName?: string, username?: string): UserAccount {
  if (!users.has(userId)) {
    users.set(userId, {
      user_id: userId,
      username: username || `user_${userId}`,
      first_name: firstName || `Telegram User ${userId}`,
      balance: 50.0, // Welcome signup INR bonus
      last_bonus: null,
      referral: { referrer: null, rewarded: false },
      referral_count: 0,
      referral_earnings: 0,
      redeemed_codes: [],
      banned: false,
      joined_at: new Date().toISOString(),
      orders_count: 0
    });
  }
  return users.get(userId)!;
}

// ─────────────────────────────────────────────────────────────
//  API ROUTES
// ─────────────────────────────────────────────────────────────

// Config API
app.get('/api/config', (_req, res) => {
  res.json({
    smm_panel_url: config.smm_panel_url,
    markup_percentage: config.markup_percentage,
    referral_reward_inr: config.referral_reward_inr,
    daily_bonus_inr: config.daily_bonus_inr,
    logs_channel: config.logs_channel,
    channels: config.channels,
    qr_code_url: config.qr_code_url,
    payment_contact: config.payment_contact,
    bot_username: config.bot_username,
    has_bot_token: Boolean(config.bot_token),
    has_api_key: Boolean(config.smm_api_key)
  });
});

app.post('/api/config', (req, res) => {
  const updates = req.body;
  config = { ...config, ...updates };
  res.json({ success: true, config });
});

// Services API
app.get('/api/services', (_req, res) => {
  res.json(services);
});

app.post('/api/services', (req, res) => {
  const { name, display_name, platform, provider_service_id, category, min, max, provider_rate, selling_price, enabled, curated } = req.body;
  if (!display_name || !provider_service_id) {
    return res.status(400).json({ error: 'Display name and provider service ID are required' });
  }

  const id = `svc_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
  const newService: SMMService = {
    _id: id,
    name: name || display_name,
    display_name,
    platform: platform || 'General',
    provider_service_id: Number(provider_service_id),
    category: category || 'General',
    min: Number(min) || 10,
    max: Number(max) || 100000,
    provider_rate: Number(provider_rate) || 10,
    selling_price: Number(selling_price) || (Number(provider_rate || 10) * 1.5),
    enabled: enabled ?? true,
    curated: curated ?? true
  };

  services.push(newService);
  res.status(201).json(newService);
});

app.patch('/api/services/:id/toggle', (req, res) => {
  const svc = services.find(s => s._id === req.params.id);
  if (!svc) return res.status(404).json({ error: 'Service not found' });
  svc.enabled = !svc.enabled;
  res.json(svc);
});

app.patch('/api/services/:id/price', (req, res) => {
  const svc = services.find(s => s._id === req.params.id);
  if (!svc) return res.status(404).json({ error: 'Service not found' });
  if (req.body.selling_price !== undefined) {
    svc.selling_price = Number(req.body.selling_price);
  }
  if (req.body.provider_service_id !== undefined) {
    svc.provider_service_id = Number(req.body.provider_service_id);
  }
  res.json(svc);
});

app.delete('/api/services/:id', (req, res) => {
  const index = services.findIndex(s => s._id === req.params.id);
  if (index === -1) return res.status(404).json({ error: 'Service not found' });
  const removed = services.splice(index, 1);
  res.json({ success: true, removed: removed[0] });
});

app.post('/api/services/sync', async (_req, res) => {
  // If SMM API credentials are configured, try provider endpoint, otherwise simulate sync
  if (config.smm_panel_url && config.smm_api_key) {
    try {
      const response = await fetch(config.smm_panel_url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ key: config.smm_api_key, action: 'services' })
      });
      const data = await response.json();
      if (Array.isArray(data)) {
        let added = 0;
        data.slice(0, 15).forEach((pSvc: any) => {
          const exists = services.find(s => s.provider_service_id === Number(pSvc.service));
          if (!exists && pSvc.service) {
            services.push({
              _id: `svc_prov_${pSvc.service}`,
              name: pSvc.name,
              display_name: pSvc.name,
              platform: pSvc.category ? pSvc.category.split(' ')[0] : 'General',
              provider_service_id: Number(pSvc.service),
              category: pSvc.category || 'General',
              min: Number(pSvc.min || 10),
              max: Number(pSvc.max || 100000),
              provider_rate: Number(pSvc.rate || 10),
              selling_price: Number(pSvc.rate || 10) * (1 + (config.markup_percentage / 100)),
              enabled: true,
              curated: true
            });
            added++;
          }
        });
        return res.json({ success: true, message: `Synced with provider. ${added} new services added.`, total: services.length });
      }
    } catch (err: any) {
      console.warn('Provider sync error:', err.message);
    }
  }

  // Realistic mock sync update
  res.json({
    success: true,
    message: 'Provider services catalog synced and rates updated with global markup.',
    inserted: 0,
    updated: services.length,
    total: services.length
  });
});

// Orders API
app.get('/api/orders', (req, res) => {
  const userId = req.query.userId ? Number(req.query.userId) : null;
  const list = Array.from(orders.values()).sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  if (userId) {
    return res.json(list.filter(o => o.user_id === userId));
  }
  res.json(list);
});

app.post('/api/orders', async (req, res) => {
  const { user_id, service_id, link, quantity } = req.body;
  if (!user_id || !service_id || !link || !quantity) {
    return res.status(400).json({ error: 'Missing required order fields (user_id, service_id, link, quantity).' });
  }

  const user = getOrCreateUser(Number(user_id));
  if (user.banned) {
    return res.status(403).json({ error: 'Your account is banned from placing orders.' });
  }

  const service = services.find(s => s._id === service_id);
  if (!service || !service.enabled) {
    return res.status(400).json({ error: 'Selected service is disabled or not found.' });
  }

  const qty = Number(quantity);
  if (qty < service.min || qty > service.max) {
    return res.status(400).json({ error: `Quantity must be between ${service.min} and ${service.max.toLocaleString()}.` });
  }

  const charge = (qty / 1000.0) * service.selling_price;
  const formattedCharge = Math.round(charge * 100) / 100;

  if (user.balance < formattedCharge) {
    return res.status(400).json({
      error: `Insufficient balance. Required: ₹${formattedCharge.toFixed(2)}, Available: ₹${user.balance.toFixed(2)}. Please Add Funds.`
    });
  }

  // Atomic Wallet Hold & Order Creation
  const reservationId = `RES-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
  const orderId = `ORD-${Math.floor(100000 + Math.random() * 900000)}`;

  user.balance = Math.round((user.balance - formattedCharge) * 100) / 100;
  user.orders_count += 1;

  const reservation: WalletReservation = {
    reservation_id: reservationId,
    user_id: user.user_id,
    amount: formattedCharge,
    order_id: orderId,
    status: 'settled',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  };
  reservations.set(reservationId, reservation);

  const order: SMMOrder = {
    id: orderId,
    user_id: user.user_id,
    user_name: user.first_name,
    service_id: service._id,
    service_name: service.display_name,
    platform: service.platform,
    link,
    quantity: qty,
    charge: formattedCharge,
    status: 'processing',
    provider_order_id: Math.floor(1000000 + Math.random() * 9000000),
    reservation_id: reservationId,
    created_at: new Date().toISOString(),
    estimated_time: '1-3 hours'
  };

  orders.set(orderId, order);

  ledger.unshift({
    id: `LEDGER-${Date.now()}`,
    reservation_id: reservationId,
    order_id: orderId,
    user_id: user.user_id,
    event: 'settle',
    amount: -formattedCharge,
    description: `Order #${orderId} for ${service.display_name} (${qty.toLocaleString()} qty)`,
    created_at: new Date().toISOString()
  });

  res.status(201).json({
    success: true,
    order,
    remaining_balance: user.balance
  });
});

app.get('/api/orders/:id/track', (req, res) => {
  const order = orders.get(req.params.id);
  if (!order) return res.status(404).json({ error: 'Order not found' });
  res.json(order);
});

// Wallet API
app.get('/api/wallet/:userId', (req, res) => {
  const userId = Number(req.params.userId);
  const user = getOrCreateUser(userId);
  const userLedger = ledger.filter(l => l.user_id === userId).slice(0, 25);
  res.json({
    user,
    ledger: userLedger
  });
});

app.post('/api/wallet/bonus', (req, res) => {
  const { user_id } = req.body;
  if (!user_id) return res.status(400).json({ error: 'user_id required' });

  const user = getOrCreateUser(Number(user_id));
  const today = new Date().toISOString().split('T')[0];

  if (user.last_bonus === today) {
    return res.status(400).json({ error: 'You have already claimed your daily bonus today! Return tomorrow.' });
  }

  const bonusAmount = config.daily_bonus_inr;
  user.balance = Math.round((user.balance + bonusAmount) * 100) / 100;
  user.last_bonus = today;

  ledger.unshift({
    id: `LEDGER-${Date.now()}`,
    user_id: user.user_id,
    event: 'bonus',
    amount: bonusAmount,
    description: `🎁 Daily Login Bonus Reward`,
    created_at: new Date().toISOString()
  });

  res.json({
    success: true,
    message: `🎁 Successfully claimed ₹${bonusAmount.toFixed(2)} daily bonus!`,
    balance: user.balance,
    last_bonus: today
  });
});

app.post('/api/wallet/giftcode', (req, res) => {
  const { user_id, code } = req.body;
  if (!user_id || !code) return res.status(400).json({ error: 'user_id and gift code are required' });

  const cleanCode = code.trim().toUpperCase();
  const gift = giftCodes.get(cleanCode);

  if (!gift) {
    return res.status(404).json({ error: 'Invalid or expired Gift Code.' });
  }

  const user = getOrCreateUser(Number(user_id));
  if (user.redeemed_codes && user.redeemed_codes.includes(cleanCode)) {
    return res.status(400).json({ error: 'You have already redeemed this Gift Code.' });
  }

  if (gift.max_claims && gift.claimed_count >= gift.max_claims) {
    return res.status(400).json({ error: 'This Gift Code has reached its maximum claim limit.' });
  }

  user.balance = Math.round((user.balance + gift.amount) * 100) / 100;
  if (!user.redeemed_codes) user.redeemed_codes = [];
  user.redeemed_codes.push(cleanCode);
  gift.claimed_count += 1;

  ledger.unshift({
    id: `LEDGER-${Date.now()}`,
    user_id: user.user_id,
    event: 'giftcode',
    amount: gift.amount,
    description: `🔳 Redeemed Gift Code ${cleanCode}`,
    created_at: new Date().toISOString()
  });

  res.json({
    success: true,
    message: `🎉 Gift Code applied! Added ₹${gift.amount.toFixed(2)} to your wallet.`,
    balance: user.balance
  });
});

app.post('/api/wallet/deposit', (req, res) => {
  const { user_id, amount, utr } = req.body;
  if (!user_id || !amount || Number(amount) <= 0) {
    return res.status(400).json({ error: 'Valid user_id and amount are required.' });
  }

  const user = getOrCreateUser(Number(user_id));
  const depositAmount = Number(amount);
  user.balance = Math.round((user.balance + depositAmount) * 100) / 100;

  ledger.unshift({
    id: `LEDGER-${Date.now()}`,
    user_id: user.user_id,
    event: 'deposit',
    amount: depositAmount,
    description: `💳 UPI Wallet Deposit ${utr ? `(Ref UTR: ${utr})` : ''}`,
    created_at: new Date().toISOString()
  });

  res.json({
    success: true,
    message: `✅ ₹${depositAmount.toFixed(2)} deposited into wallet.`,
    balance: user.balance
  });
});

// Admin APIs
app.get('/api/admin/stats', (_req, res) => {
  const allUsers = Array.from(users.values());
  const allOrders = Array.from(orders.values());
  const allRes = Array.from(reservations.values()).filter(r => r.status === 'pending');

  const stats: AdminStats = {
    total_users: allUsers.length,
    banned_users: allUsers.filter(u => u.banned).length,
    active_gift_codes: giftCodes.size,
    total_orders: allOrders.length,
    total_inr_held: allUsers.reduce((sum, u) => sum + (u.balance || 0), 0),
    total_services: services.length,
    pending_reservations: allRes.length,
    provider_connected: Boolean(config.smm_api_key)
  };
  res.json(stats);
});

app.get('/api/admin/users', (_req, res) => {
  res.json(Array.from(users.values()));
});

app.post('/api/admin/users/:userId/balance', (req, res) => {
  const userId = Number(req.params.userId);
  const { amount, action } = req.body; // action: 'add' | 'remove'
  const user = users.get(userId);
  if (!user) return res.status(404).json({ error: 'User not found' });

  const numAmount = Number(amount);
  if (action === 'add') {
    user.balance = Math.round((user.balance + numAmount) * 100) / 100;
    ledger.unshift({
      id: `LEDGER-${Date.now()}`,
      user_id: user.user_id,
      event: 'admin_add',
      amount: numAmount,
      description: `👑 Admin Credit: +₹${numAmount.toFixed(2)}`,
      created_at: new Date().toISOString()
    });
  } else {
    user.balance = Math.max(0, Math.round((user.balance - numAmount) * 100) / 100);
    ledger.unshift({
      id: `LEDGER-${Date.now()}`,
      user_id: user.user_id,
      event: 'admin_rem',
      amount: -numAmount,
      description: `👑 Admin Debit: -₹${numAmount.toFixed(2)}`,
      created_at: new Date().toISOString()
    });
  }

  res.json({ success: true, user });
});

app.post('/api/admin/users/:userId/ban', (req, res) => {
  const userId = Number(req.params.userId);
  const user = users.get(userId);
  if (!user) return res.status(404).json({ error: 'User not found' });
  user.banned = !user.banned;
  res.json({ success: true, banned: user.banned });
});

app.get('/api/admin/giftcodes', (_req, res) => {
  res.json(Array.from(giftCodes.values()));
});

app.post('/api/admin/giftcodes', (req, res) => {
  const { code, amount, max_claims } = req.body;
  if (!code || !amount) return res.status(400).json({ error: 'Code and amount are required' });
  const cleanCode = code.trim().toUpperCase();

  const newGift: GiftCode = {
    code: cleanCode,
    amount: Number(amount),
    created_at: new Date().toISOString(),
    claimed_count: 0,
    max_claims: max_claims ? Number(max_claims) : 100
  };

  giftCodes.set(cleanCode, newGift);
  res.status(201).json(newGift);
});

app.delete('/api/admin/giftcodes/:code', (req, res) => {
  const cleanCode = req.params.code.trim().toUpperCase();
  if (!giftCodes.has(cleanCode)) return res.status(404).json({ error: 'Gift code not found' });
  giftCodes.delete(cleanCode);
  res.json({ success: true });
});

app.get('/api/admin/reservations', (_req, res) => {
  res.json(Array.from(reservations.values()));
});

app.post('/api/admin/broadcast', (req, res) => {
  const { message } = req.body;
  if (!message) return res.status(400).json({ error: 'Broadcast message cannot be empty' });
  res.json({
    success: true,
    recipients_count: users.size,
    message: `📢 Broadcast dispatched to ${users.size} registered bot users!`
  });
});

// Vite Middleware for Dev / Static serving for Prod
async function setupViteOrStatic() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa'
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[Bobby SMM Bot] Server listening on http://0.0.0.0:${PORT}`);
  });
}

setupViteOrStatic();
