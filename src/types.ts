export interface SMMService {
  _id: string;
  name: string;
  display_name: string;
  platform: string;
  provider_service_id: number;
  category: string;
  min: number;
  max: number;
  price?: number;
  provider_rate: number;
  selling_price: number;
  enabled: boolean;
  curated: boolean;
}

export interface SMMOrder {
  id: string;
  user_id: number;
  user_name?: string;
  service_id: string;
  service_name: string;
  platform: string;
  link: string;
  quantity: number;
  charge: number;
  status: 'pending' | 'processing' | 'completed' | 'partial' | 'canceled';
  provider_order_id?: number | string;
  reservation_id?: string;
  created_at: string;
  estimated_time?: string;
}

export interface UserAccount {
  user_id: number;
  username: string;
  first_name: string;
  balance: number;
  last_bonus?: string | null;
  referral?: {
    referrer: number | null;
    rewarded: boolean;
  };
  referral_count: number;
  referral_earnings: number;
  redeemed_codes: string[];
  banned: boolean;
  joined_at: string;
  orders_count: number;
}

export interface GiftCode {
  code: string;
  amount: number;
  created_at: string;
  claimed_count: number;
  max_claims?: number;
}

export interface WalletReservation {
  reservation_id: string;
  user_id: number;
  amount: number;
  order_id?: string;
  status: 'pending' | 'settled' | 'released';
  provider_request_id?: string;
  provider_state?: string;
  pending_reason?: string;
  created_at: string;
  updated_at: string;
}

export interface WalletLedgerEntry {
  id: string;
  reservation_id?: string;
  order_id?: string;
  user_id: number;
  event: 'hold' | 'settle' | 'release' | 'bonus' | 'deposit' | 'referral' | 'admin_add' | 'admin_rem' | 'giftcode';
  amount: number;
  description: string;
  created_at: string;
}

export interface ForceJoinChannel {
  name: string;
  username: string;
  url: string;
}

export interface BotConfig {
  bot_token?: string;
  smm_panel_url: string;
  smm_api_key?: string;
  provider_rate_reactions: number;
  provider_rate_views: number;
  provider_rate_members: number;
  markup_percentage: number;
  referral_reward_inr: number;
  daily_bonus_inr: number;
  service_id_reactions: number;
  service_id_views: number;
  service_id_members: number;
  logs_channel: string;
  channels: ForceJoinChannel[];
  qr_code_url: string;
  main_menu_photo_file_id?: string;
  payment_contact: string;
  bot_username: string;
}

export interface AdminStats {
  total_users: number;
  banned_users: number;
  active_gift_codes: number;
  total_orders: number;
  total_inr_held: number;
  total_services: number;
  pending_reservations: number;
  provider_connected: boolean;
}
