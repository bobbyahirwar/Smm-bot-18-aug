import React, { useState, useEffect, useRef } from 'react';
import { UserAccount, SMMService, BotConfig } from '../types.ts';
import { 
  Bot, 
  Send, 
  User, 
  Check, 
  CheckCircle2, 
  ExternalLink, 
  RefreshCw, 
  ArrowLeft, 
  ShoppingBag,
  Sparkles,
  ShieldAlert
} from 'lucide-react';

interface TelegramBotSimulatorProps {
  currentUser: UserAccount;
  services: SMMService[];
  config: BotConfig | null;
  onPlaceOrder: (serviceId: string, link: string, quantity: number) => Promise<boolean>;
  onOpenAddFunds: () => void;
  onClaimBonus: () => Promise<{ success: boolean; message: string }>;
  onRedeemGiftCode: (code: string) => Promise<{ success: boolean; message: string }>;
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  photoUrl?: string;
  buttons?: { text: string; callback: string; url?: string }[][];
  timestamp: string;
}

export const TelegramBotSimulator: React.FC<TelegramBotSimulatorProps> = ({
  currentUser,
  services,
  config,
  onPlaceOrder,
  onOpenAddFunds,
  onClaimBonus,
  onRedeemGiftCode
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [fsmState, setFsmState] = useState<{ step: string; serviceId?: string; quantity?: number; link?: string } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initial Bot Welcome Message
  useEffect(() => {
    if (messages.length === 0) {
      sendBotWelcome();
    }
  }, []);

  const sendBotWelcome = () => {
    const welcomeMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      sender: 'bot',
      text: `👋 Welcome, <b>${currentUser.first_name}</b>!\n\n🚀 <b>Bobby SMM Panel</b>\n━━━━━━━━━━━━━━━━━━\n💰 Wallet Balance: <b>₹${currentUser.balance.toFixed(2)}</b>\n⚡ Fast Delivery • Best Rates • 24/7 Support\n━━━━━━━━━━━━━━━━━━\n\n🛍️ Choose an option below:`,
      buttons: [
        [
          { text: '🛒 ORDER SERVICES', callback: 'catalog_home' },
          { text: '📦 MY ORDERS', callback: 'my_orders' }
        ],
        [
          { text: '💳 ADD FUNDS', callback: 'add_funds' },
          { text: '💰 WALLET', callback: 'check_balance' }
        ],
        [
          { text: '👥 REFER & EARN', callback: 'refer_earn' },
          { text: '🎁 DAILY BONUS', callback: 'claim_bonus' }
        ],
        [
          { text: '📞 SUPPORT', callback: 'support' },
          { text: 'ℹ️ HELP', callback: 'help' }
        ]
      ],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages([welcomeMsg]);
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputText.trim()) return;

    const userText = inputText.trim();
    setInputText('');

    // Append user message
    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      sender: 'user',
      text: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages(prev => [...prev, userMsg]);

    // Handle FSM State if waiting for input
    if (fsmState) {
      if (fsmState.step === 'wait_link') {
        const service = services.find(s => s._id === fsmState.serviceId);
        if (!service) {
          setFsmState(null);
          return;
        }
        setFsmState({ ...fsmState, step: 'wait_qty', link: userText });
        setTimeout(() => {
          setMessages(prev => [
            ...prev,
            {
              id: `bot_${Date.now()}`,
              sender: 'bot',
              text: `🔢 <b>Enter Quantity</b>\n\nService: <b>${service.display_name}</b>\nMin: <code>${service.min}</code> | Max: <code>${service.max.toLocaleString()}</code>\nPrice: <b>₹${service.selling_price.toFixed(2)}/1K</b>\n\n<i>Send the number of units you want to order:</i>`,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }
          ]);
        }, 400);
        return;
      }

      if (fsmState.step === 'wait_qty') {
        const qty = parseInt(userText);
        const service = services.find(s => s._id === fsmState.serviceId);
        if (!service || isNaN(qty) || qty < service.min || qty > service.max) {
          setTimeout(() => {
            setMessages(prev => [
              ...prev,
              {
                id: `bot_${Date.now()}`,
                sender: 'bot',
                text: `❌ Invalid quantity. Please enter a number between <b>${service?.min || 10}</b> and <b>${service?.max.toLocaleString() || 100000}</b>.`,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              }
            ]);
          }, 400);
          return;
        }

        const charge = ((qty / 1000.0) * service.selling_price);
        const link = fsmState.link!;
        setFsmState(null);

        // Place order
        setTimeout(async () => {
          try {
            const ok = await onPlaceOrder(service._id, link, qty);
            if (ok) {
              setMessages(prev => [
                ...prev,
                {
                  id: `bot_${Date.now()}`,
                  sender: 'bot',
                  text: `✅ <b>ORDER PLACED 🦋</b>\n\nService: <b>${service.display_name}</b>\nQuantity: <b>${qty.toLocaleString()}</b>\nCharge: <b>₹${charge.toFixed(2)}</b>\nTarget Link: <code>${link}</code>\nStatus: <b>Processing</b>\nEstimated delivery: <b>1-3 hours</b>`,
                  buttons: [
                    [
                      { text: '📦 View in My Orders', callback: 'my_orders' },
                      { text: '🏠 Main Menu', callback: 'main_menu' }
                    ]
                  ],
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                }
              ]);
            }
          } catch (err: any) {
            setMessages(prev => [
              ...prev,
              {
                id: `bot_${Date.now()}`,
                sender: 'bot',
                text: `❌ Order failed: <b>${err.message || 'Insufficient balance'}</b>`,
                buttons: [
                  [{ text: '💳 Add Funds', callback: 'add_funds' }],
                  [{ text: '🏠 Main Menu', callback: 'main_menu' }]
                ],
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              }
            ]);
          }
        }, 500);
        return;
      }
    }

    // Default Command Dispatcher
    setTimeout(() => {
      handleBotCommand(userText.toLowerCase());
    }, 400);
  };

  const handleBotCommand = (cmd: string) => {
    if (cmd === '/start' || cmd.includes('start')) {
      sendBotWelcome();
    } else if (cmd === '/admin') {
      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `👑 <b>ADMIN CONTROL PANEL</b>\n\nWelcome back Admin! Select an action:`,
          buttons: [
            [
              { text: '📊 Stats', callback: 'admin_stats' },
              { text: '🧰 Manage Services', callback: 'admin_services' }
            ],
            [
              { text: '🎁 Create GiftCode', callback: 'admin_giftcode' },
              { text: '💰 Edit Prices', callback: 'admin_prices' }
            ],
            [
              { text: '🔙 Exit to Main Menu', callback: 'main_menu' }
            ]
          ],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } else if (cmd.includes('balance') || cmd.includes('wallet')) {
      handleCallback('check_balance');
    } else if (cmd.includes('bonus')) {
      handleCallback('claim_bonus');
    } else if (cmd.includes('order')) {
      handleCallback('catalog_home');
    } else {
      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `🤖 Command not recognized. Use the menu buttons below or type /start.`,
          buttons: [[{ text: '🏠 Main Menu', callback: 'main_menu' }]],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    }
  };

  const handleCallback = async (callback: string) => {
    if (callback === 'main_menu') {
      setFsmState(null);
      sendBotWelcome();
      return;
    }

    if (callback === 'catalog_home') {
      const platforms = ['Instagram', 'Telegram', 'YouTube', 'Facebook', 'Twitter/X', 'TikTok'];
      const buttons = platforms.map(p => ([{ text: `📁 ${p}`, callback: `catalog_platform:${p}` }]));
      buttons.push([{ text: '🔙 Back to Menu', callback: 'main_menu' }]);

      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `🛍 <b>Order Services</b>\n\n📂 <b>Select Platform Category:</b>`,
          buttons,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      return;
    }

    if (callback.startsWith('catalog_platform:')) {
      const platform = callback.split(':')[1];
      const platformServices = services.filter(s => s.platform.toLowerCase() === platform.toLowerCase() && s.enabled);
      
      if (platformServices.length === 0) {
        setMessages(prev => [
          ...prev,
          {
            id: `bot_${Date.now()}`,
            sender: 'bot',
            text: `No active services currently in ${platform}.`,
            buttons: [[{ text: '🔙 Back', callback: 'catalog_home' }]],
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
        return;
      }

      const buttons = platformServices.map(s => ([
        { text: `${s.display_name.substring(0, 32)}... (₹${s.selling_price}/1k)`, callback: `catalog_select:${s._id}` }
      ]));
      buttons.push([{ text: '🔙 Back', callback: 'catalog_home' }]);

      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `📱 <b>${platform} Services</b>\n\nChoose a package to order:`,
          buttons,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      return;
    }

    if (callback.startsWith('catalog_select:')) {
      const serviceId = callback.split(':')[1];
      const service = services.find(s => s._id === serviceId);
      if (!service) return;

      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `🛍 <b>${service.display_name}</b>\n\n━━━━━━━━━━━━━━━━━━\n💰 Price: <b>₹${service.selling_price.toFixed(2)}</b> per 1,000\n📊 Min / Max: <b>${service.min}</b> - <b>${service.max.toLocaleString()}</b>\n⚡ Delivery: <b>Instant Automated</b>\n━━━━━━━━━━━━━━━━━━\n\nReady to place order?`,
          buttons: [
            [{ text: '🛒 Order Now', callback: `catalog_order_start:${service._id}` }],
            [{ text: '🔙 Back', callback: `catalog_platform:${service.platform}` }]
          ],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      return;
    }

    if (callback.startsWith('catalog_order_start:')) {
      const serviceId = callback.split(':')[1];
      const service = services.find(s => s._id === serviceId);
      if (!service) return;

      setFsmState({ step: 'wait_link', serviceId });
      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `🔗 <b>Send Target Link</b>\n\nService: <b>${service.display_name}</b>\n\n<i>Please type or paste the profile / post / channel URL:</i>`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      return;
    }

    if (callback === 'check_balance') {
      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `💰 <b>Wallet Balance</b>\n\nAccount: <code>${currentUser.user_id}</code>\nCurrent Balance: <b>₹${currentUser.balance.toFixed(2)}</b>\nTotal Orders: <b>${currentUser.orders_count}</b>\nReferral Bonus: <b>₹${(currentUser.referral_earnings || 0).toFixed(2)}</b>`,
          buttons: [
            [
              { text: '💳 Add Funds', callback: 'add_funds' },
              { text: '🎁 Claim Bonus', callback: 'claim_bonus' }
            ],
            [{ text: '🏠 Main Menu', callback: 'main_menu' }]
          ],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      return;
    }

    if (callback === 'claim_bonus') {
      try {
        const res = await onClaimBonus();
        setMessages(prev => [
          ...prev,
          {
            id: `bot_${Date.now()}`,
            sender: 'bot',
            text: res.message,
            buttons: [[{ text: '🏠 Main Menu', callback: 'main_menu' }]],
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
      } catch (err: any) {
        setMessages(prev => [
          ...prev,
          {
            id: `bot_${Date.now()}`,
            sender: 'bot',
            text: `⚠️ ${err.message || 'You have already claimed your daily bonus today.'}`,
            buttons: [[{ text: '🏠 Main Menu', callback: 'main_menu' }]],
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
      }
      return;
    }

    if (callback === 'add_funds') {
      onOpenAddFunds();
      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `💳 <b>Add Funds Modal Opened</b>\n\nScan the UPI QR code or pay to <code>bobbyahirwar@upi</code>.\n\nSupport contact: <b>${config?.payment_contact || '@BOBBY_2606'}</b>`,
          buttons: [[{ text: '🏠 Main Menu', callback: 'main_menu' }]],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      return;
    }

    if (callback === 'refer_earn') {
      const refLink = `https://t.me/${config?.bot_username || 'BobbySMM_bot'}?start=${currentUser.user_id}`;
      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `👥 <b>REFER & EARN ₹${config?.referral_reward_inr || 25}</b>\n\nInvite your friends to use this bot and receive ₹${config?.referral_reward_inr || 25} for each active user!\n\nYour Referral Link:\n<code>${refLink}</code>`,
          buttons: [[{ text: '🏠 Main Menu', callback: 'main_menu' }]],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      return;
    }

    if (callback === 'support') {
      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `📞 <b>Support & Assistance</b>\n\nFor payment verification, custom high-volume discounts, or order support, contact: <b>${config?.payment_contact || '@BOBBY_2606'}</b>`,
          buttons: [[{ text: '🏠 Main Menu', callback: 'main_menu' }]],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      return;
    }

    if (callback === 'help') {
      setMessages(prev => [
        ...prev,
        {
          id: `bot_${Date.now()}`,
          sender: 'bot',
          text: `ℹ️ <b>How to Use Bobby SMM Bot</b>\n\n1. Check your balance or use 💳 Add Funds to top up via UPI.\n2. Tap 🛒 ORDER SERVICES to browse platforms.\n3. Paste the target post or profile URL and specify quantity.\n4. Watch the progress in 📦 MY ORDERS.`,
          buttons: [[{ text: '🏠 Main Menu', callback: 'main_menu' }]],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      return;
    }
  };

  return (
    <div className="max-w-2xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col h-[680px]">
      
      {/* Telegram App Header Bar */}
      <div className="bg-slate-850 px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-white font-bold shadow">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-bold text-sm text-slate-100">{config?.bot_username || 'Bobby SMM Bot'}</span>
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            </div>
            <p className="text-[11px] text-slate-400">bot • automated 24/7 service</p>
          </div>
        </div>

        <button
          onClick={() => {
            setMessages([]);
            setFsmState(null);
            sendBotWelcome();
          }}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-white transition"
          title="Restart Bot Session (/start)"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Telegram Chat Message History */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-950/70">
        
        <div className="text-center my-2">
          <span className="text-[10px] uppercase font-semibold tracking-wider text-slate-400 bg-slate-900/90 border border-slate-800/80 px-2.5 py-1 rounded-full">
            Telegram Bot Live Web Interface
          </span>
        </div>

        {messages.map((msg) => {
          const isBot = msg.sender === 'bot';
          return (
            <div
              key={msg.id}
              className={`flex ${isBot ? 'justify-start' : 'justify-end'} animate-in fade-in duration-200`}
            >
              <div className={`max-w-[85%] space-y-2`}>
                
                {/* Bubble */}
                <div
                  className={`p-3.5 rounded-2xl text-xs sm:text-sm leading-relaxed shadow-sm ${
                    isBot
                      ? 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-sm'
                      : 'bg-sky-600 text-white rounded-tr-sm'
                  }`}
                >
                  <div
                    dangerouslySetInnerHTML={{ __html: msg.text.replace(/\n/g, '<br/>') }}
                  />
                  <div className={`text-[10px] mt-1.5 text-right ${isBot ? 'text-slate-500' : 'text-sky-200'}`}>
                    {msg.timestamp}
                  </div>
                </div>

                {/* Inline Buttons Grid */}
                {isBot && msg.buttons && msg.buttons.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    {msg.buttons.map((row, rIdx) => (
                      <div key={rIdx} className="grid grid-flow-col auto-cols-fr gap-1.5">
                        {row.map((btn, bIdx) => (
                          <button
                            key={bIdx}
                            onClick={() => handleCallback(btn.callback)}
                            className="bg-slate-800/90 hover:bg-slate-750 active:bg-sky-600 border border-slate-700/80 text-sky-300 hover:text-white font-semibold text-xs py-2 px-2.5 rounded-xl text-center truncate transition shadow-sm"
                          >
                            {btn.text}
                          </button>
                        ))}
                      </div>
                    ))}
                  </div>
                )}

              </div>
            </div>
          );
        })}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={handleSendMessage} className="p-3 bg-slate-900 border-t border-slate-800 flex items-center space-x-2">
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={fsmState ? "Type your response..." : "Send a command (e.g., /start, /admin, or tap buttons)..."}
          className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
        />
        <button
          type="submit"
          disabled={!inputText.trim()}
          className="p-2.5 bg-sky-500 hover:bg-sky-400 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl shadow-md transition"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>

    </div>
  );
};
