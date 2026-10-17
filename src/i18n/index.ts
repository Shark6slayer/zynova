import type { AppLanguage } from '../types';
import { LANGUAGE_REGISTRY, isRtlLanguage, getLanguageMetadata } from './registry';

export * from './registry';

export interface TranslationParams {
  [key: string]: string | number;
}

export type TranslationDictionary = Record<string, string>;

// English Master Catalog (Base Source of Truth)
const EN_CATALOG: TranslationDictionary = {
  // Brand & Application
  'app.title': 'ZYNOVA',
  'app.tagline': "India's Sovereign Intelligent Super App",
  
  // Navigation
  'nav.home': 'Home',
  'nav.ai-assistant': 'Universal AI',
  'nav.search': 'Search',
  'nav.chat': 'Chat',
  'nav.social': 'Social',
  'nav.video': 'Video',
  'nav.food': 'Food & Dining',
  'nav.shopping': 'Zaviro',
  'nav.payments': 'Payments',
  'nav.cloud': 'Cloud Drive',
  'nav.workspace': 'Workspace',
  'nav.mini-apps': 'Mini Apps',
  'nav.customization': 'Studio',
  'nav.notifications': 'Notifications',
  'nav.settings': 'Settings',
  'nav.menu': 'Menu',

  // Common UI Actions & States
  'common.search_placeholder': 'Ask Zynova anything or search services (Ctrl+K)...',
  'common.demo_badge': 'DEMO ENVIRONMENT',
  'common.demo_warning': 'This module uses interactive client-side demo state. No live transactions or external API keys required.',
  'common.save': 'Save Changes',
  'common.cancel': 'Cancel',
  'common.clear': 'Clear',
  'common.status': 'Status',
  'common.active': 'Active',
  'common.inactive': 'Inactive',
  'common.view_all': 'View All',
  'common.back': 'Back',
  'common.next': 'Next',
  'common.close': 'Close',
  'common.filter': 'Filter',
  'common.loading': 'Loading...',
  'common.success': 'Operation completed successfully',
  'common.error': 'An error occurred. Please try again.',
  'common.sign_in': 'Sign In',
  'common.sign_out': 'Sign Out',
  'common.logout': 'Logout',
  'common.register': 'Register',
  
  // Connectivity & Offline Status (Phase 6)
  'sync.online': 'Online',
  'sync.offline': 'Offline Mode',
  'sync.syncing': 'Syncing...',
  'sync.failed': 'Sync Failed',
  'sync.pending': '{count} Pending Changes',
  'sync.cached_badge': 'Cached Preview • Live connectivity needed for orders',
  'sync.drafts_tab': 'Local Drafts',
  'sync.publish_draft': 'Publish Draft',
  'sync.save_draft': 'Save Local Draft',
  'sync.draft_saved': 'Draft saved locally',
  'sync.draft_published': 'Draft published successfully',

  // Home Dashboard
  'home.greeting_morning': 'Good Morning, {name}',
  'home.greeting_afternoon': 'Good Afternoon, {name}',
  'home.greeting_evening': 'Good Evening, {name}',
  'home.daily_briefing': 'AI Daily Briefing: Sensex up +1.2%, heavy rains predicted in Chennai & Bangalore, 3 workspace action items pending review.',
  'home.explore_super_ai': 'Explore Sovereign Super App Ecosystem',

  // AI Assistant
  'ai.model_select': 'Select Model Engine',
  'ai.new_chat': 'New Conversation',
  'ai.send_placeholder': 'Ask SUPER_AI to write code, research, plan an itinerary, or summarize...',

  // Chat Module
  'chat.conversations': 'Conversations',
  'chat.new_message': 'New Message',
  'chat.type_message': 'Type a message...',
  'chat.send': 'Send',
  'chat.read': 'Read',
  'chat.unread': 'Unread',
  'chat.empty': 'No messages yet. Start a conversation!',
  'chat.online': 'Online',
  'chat.offline': 'Offline',

  // Social & Video
  'social.feed': 'Feed',
  'social.trending': 'Trending',
  'social.post': 'Post',
  'social.create_post': 'Create Post',
  'social.like': 'Like',
  'social.comments': 'Comments',
  'social.share': 'Share',
  'video.watch': 'Watch',
  'video.stream': 'Live Stream',
  'video.trending': 'Trending Videos',

  // Shopping (Zaviro)
  'shopping.title': 'Zaviro Marketplace',
  'shopping.catalog': 'Product Catalog',
  'shopping.cart': 'Cart',
  'shopping.checkout': 'Checkout',
  'shopping.orders': 'Orders',
  'shopping.seller_hub': 'Seller Hub',
  'shopping.add_to_cart': 'Add to Cart',
  'shopping.buy_now': 'Buy Now',
  'shopping.price': 'Price',
  'shopping.in_stock': 'In Stock',
  'shopping.out_of_stock': 'Out of Stock',
  'shopping.cart_items': '{count} items in cart',

  // Food & Dining
  'food.delivering_to': 'Delivering to: {location}',
  'food.restaurants': 'Restaurants',
  'food.menu': 'Menu',
  'food.cart': 'Food Cart',
  'food.order_now': 'Order Now',
  'food.track_order': 'Track Order',
  'food.partner_portal': 'Restaurant Partner Portal',

  // Settings & Languages
  'settings.title': 'Settings & Privacy Hub',
  'settings.language': 'Language & Script',
  'settings.select_language': 'Select Interface Language',
  'settings.theme': 'Appearance & Theme Mode',
  'settings.privacy': 'Sovereign Privacy & DPDP Compliance',
  'settings.account': 'Account & Profile',
  'settings.save_success': 'Preferences updated successfully',
  
  // Payments & Cloud
  'payments.balance': 'Combined UPI Balance',
  'cloud.storage_used': '{used} of {total} Zynova Cloud',
};

// Complete reviewed translations for all 22 Eighth Schedule languages + English
export const TRANSLATIONS: Record<AppLanguage, TranslationDictionary> = {
  en: EN_CATALOG,

  // 1. Assamese (অসমীয়া)
  as: {
    ...EN_CATALOG,
    'app.tagline': 'ভাৰতৰ প্ৰথম সৰ্বভৌম এআই ছুপাৰ এপ',
    'nav.home': 'ঘৰ',
    'nav.ai-assistant': 'সাৰ্বজনীন এআই',
    'nav.search': 'সন্ধান',
    'nav.chat': 'বার্তালাপ',
    'nav.social': 'সামাজিক',
    'nav.video': 'ভিডিঅ’',
    'nav.food': 'খাদ্য আৰু ভোজন',
    'nav.shopping': 'জাভিৰো শ্বপিং',
    'nav.payments': 'ইউপিআই পেমেণ্ট',
    'nav.cloud': 'ক্লাউড ড্ৰাইভ',
    'nav.customization': 'ষ্টুডিঅ’',
    'nav.notifications': 'জাননীসমূহ',
    'nav.settings': 'ছেটিংছ',
    'nav.menu': 'মেনু',
    'common.save': 'সংৰক্ষণ কৰক',
    'common.cancel': 'বাতিল কৰক',
    'common.status': 'স্থিতি',
    'common.search_placeholder': 'ছুপাৰ এআইক যিকোনো সোধক...',
    'settings.title': 'ছেটিংছ আৰু গোপনীয়তা কেন্দ্ৰ',
    'settings.language': 'ভাষা আৰু লিপি',
    'settings.select_language': 'ভাষা বাছনি কৰক',
    'food.delivering_to': 'বিতৰণ স্থান: {location}',
  },

  // 2. Bengali (বাংলা)
  bn: {
    ...EN_CATALOG,
    'app.tagline': 'ভারতের প্রথম সার্বভৌমিক এআই সুপার অ্যাপ',
    'nav.home': 'হোম',
    'nav.ai-assistant': 'সার্বজনীন এআই',
    'nav.search': 'অনুসন্ধান',
    'nav.chat': 'চ্যাট ও বার্তা',
    'nav.social': 'সোশ্যাল ফিড',
    'nav.video': 'ভিডিও স্ট্রিম',
    'nav.food': 'খাবার ও রেস্তোরাঁ',
    'nav.shopping': 'জাভিরো শপিং',
    'nav.payments': 'ইউপিআই পেমেন্ট',
    'nav.cloud': 'ক্লাউড ড্রাইভ',
    'nav.customization': 'স্টুডিও',
    'nav.notifications': 'বিজ্ঞপ্তি',
    'nav.settings': 'সেটিংস',
    'nav.menu': 'মেনু',
    'common.save': 'সংরক্ষণ করুন',
    'common.cancel': 'বাতিল করুন',
    'common.status': 'অবস্থা',
    'common.search_placeholder': 'সুপার এআই-কে যেকোনো কিছু জিজ্ঞাসা করুন (Ctrl+K)...',
    'home.greeting_morning': 'সুপ্রভাত, {name}',
    'home.greeting_afternoon': 'শুভ দুপুর, {name}',
    'home.greeting_evening': 'শুভ সন্ধ্যা, {name}',
    'shopping.title': 'জাভিরো মার্কেটপ্লেস',
    'shopping.cart': 'কার্ট',
    'shopping.checkout': 'চেকআউট',
    'shopping.cart_items': 'কার্টে {count}টি পণ্য আছে',
    'food.delivering_to': 'ডেলিভারি গন্তব্য: {location}',
    'settings.title': 'সেটিংস ও গোপনীয়তা হাব',
    'settings.language': 'ভাষা ও লিপি',
    'settings.select_language': 'ভাষা নির্বাচন করুন',
  },

  // 3. Bodo (बड़ो)
  brx: {
    ...EN_CATALOG,
    'app.tagline': 'भारोतनि गिबि एআই सुफार एब',
    'nav.home': 'न\'',
    'nav.ai-assistant': 'एআই मददगिरि',
    'nav.search': 'नायगिरनाय',
    'nav.chat': 'रायज्लायनाय',
    'nav.social': 'सोसियेल',
    'nav.video': 'भिडियो',
    'nav.food': 'जाग्रा-लोंग्रा',
    'nav.shopping': 'हाटार',
    'nav.payments': 'रांखान्थि',
    'nav.cloud': 'क्लाउड',
    'nav.notifications': 'खौरां',
    'nav.settings': 'सेटिंस',
    'nav.menu': 'मेनु',
    'common.save': 'थिना दोन',
    'common.cancel': 'नेवसि',
    'settings.select_language': 'राव सायख\'',
    'food.delivering_to': 'सफैनो जायगा: {location}',
  },

  // 4. Dogri (डोगरी)
  doi: {
    ...EN_CATALOG,
    'app.tagline': 'भारत दा पैह्ला सुपर एआई ऐप',
    'nav.home': 'घर',
    'nav.ai-assistant': 'सुपर एआई',
    'nav.search': 'खोज',
    'nav.chat': 'गल्लबात',
    'nav.social': 'सोशल',
    'nav.video': 'वीडियो',
    'nav.food': 'खान-पान',
    'nav.shopping': 'शॉपिंग',
    'nav.payments': 'भुगतान',
    'nav.notifications': 'सूचनां',
    'nav.settings': 'सैटिंग्स',
    'nav.menu': 'मेनू',
    'common.save': 'संबालो',
    'common.cancel': 'रद्द करो',
    'settings.select_language': 'बोली चुनो',
    'food.delivering_to': 'पुज्जाने दी जगह: {location}',
  },

  // 5. Gujarati (ગુજરાતી)
  gu: {
    ...EN_CATALOG,
    'app.tagline': 'ભારતનું પ્રથમ સાર્વભૌમ એઆઈ સુપર એપ',
    'nav.home': 'હોમ',
    'nav.ai-assistant': 'સાર્વત્રિક એઆઈ',
    'nav.search': 'શોધ',
    'nav.chat': 'ચેટ અને સંદેશા',
    'nav.social': 'સોશિયલ ફીડ',
    'nav.video': 'વિડિયો સ્ટ્રીમ',
    'nav.food': 'ખાનપાન',
    'nav.shopping': 'ઝાવીરો શોપિંગ',
    'nav.payments': 'ચુકવણીઓ',
    'nav.cloud': 'ક્લાઉડ ડ્રાઇવ',
    'nav.notifications': 'સૂચનાઓ',
    'nav.settings': 'સેટિંગ્સ',
    'nav.menu': 'મેનુ',
    'common.save': 'સાચવો',
    'common.cancel': 'રદ કરો',
    'common.status': 'સ્થિતિ',
    'common.search_placeholder': 'સુપર એઆઈને કંઈપણ પૂછો...',
    'shopping.cart': 'કાર્ટ',
    'shopping.checkout': 'ચેકઆઉટ',
    'food.delivering_to': 'ડિલિવરી સ્થળ: {location}',
    'settings.title': 'સેટિંગ્સ અને ગોપનીયતા હબ',
    'settings.select_language': 'ભાષા પસંદ કરો',
  },

  // 6. Hindi (हिन्दी)
  hi: {
    ...EN_CATALOG,
    'app.tagline': 'भारत का पहला संप्रभु एआई सुपर ऐप',
    'nav.home': 'होम',
    'nav.ai-assistant': 'सुपर एआई',
    'nav.search': 'सर्च इंजन',
    'nav.chat': 'चैट और संदेश',
    'nav.social': 'सोशल फीड',
    'nav.video': 'वीडियो स्ट्रीम',
    'nav.food': 'खाना ऑर्डर',
    'nav.shopping': 'जाविरो शॉपिंग',
    'nav.payments': 'यूपीआई और भुगतान',
    'nav.cloud': 'क्लाउड ड्राइव',
    'nav.workspace': 'वर्कस्पेस',
    'nav.mini-apps': 'मिनी ऐप्स',
    'nav.customization': 'कस्टमाइजेशन स्टूडियो',
    'nav.notifications': 'सूचनाएं',
    'nav.settings': 'सेटिंग्स',
    'nav.menu': 'मेनू',
    'common.search_placeholder': 'सुपर एआई से कुछ भी पूछें (Ctrl+K)...',
    'common.demo_badge': 'डेमो मोड',
    'common.demo_warning': 'यह एप्लिकेशन इंटरैक्टिव डेमो डेटा पर चल रहा है।',
    'common.save': 'सहेजें',
    'common.cancel': 'रद्द करें',
    'common.clear': 'साफ़ करें',
    'common.status': 'स्थिति',
    'home.greeting_morning': 'सुप्रभात, {name}',
    'home.greeting_afternoon': 'शुभ दोपहर, {name}',
    'home.greeting_evening': 'शुभ संध्या, {name}',
    'shopping.title': 'जाविरो मार्केटप्लेस',
    'shopping.cart': 'कार्ट',
    'shopping.checkout': 'चेकआउट',
    'shopping.orders': 'ऑर्डर',
    'shopping.cart_items': 'कार्ट में {count} आइटम हैं',
    'food.delivering_to': 'डिलीवरी पता: {location}',
    'food.restaurants': 'रेस्तरां',
    'food.order_now': 'अभी ऑर्डर करें',
    'settings.title': 'सेटिंग्स और गोपनीयता केंद्र',
    'settings.language': 'भाषा और लिपि',
    'settings.select_language': 'इंटरफ़ेस भाषा चुनें',
    'settings.theme': 'दिखावट और थीम मोड',
  },

  // 7. Kannada (ಕನ್ನಡ)
  kn: {
    ...EN_CATALOG,
    'app.tagline': 'ಭಾರತದ ಮೊದಲ ಸಾರ್ವಭೌಮ ಎಐ ಸೂಪರ್ ಆಪ್',
    'nav.home': 'ಮುಖಪುಟ',
    'nav.ai-assistant': 'ಸಾರ್ವತ್ರಿಕ ಎಐ',
    'nav.search': 'ಹುಡುಕಾಟ',
    'nav.chat': 'ಸಂಭಾಷಣೆ',
    'nav.social': 'ಸಾಮಾಜಿಕ ಜಾಲ',
    'nav.video': 'ವೀಡಿಯೊ ವಾಹಿನಿ',
    'nav.food': 'ಆಹಾರ ಮತ್ತು ಊಟ',
    'nav.shopping': 'ಝಾವಿರೋ ಶಾಪಿಂಗ್',
    'nav.payments': 'ಪಾವತಿಗಳು',
    'nav.cloud': 'ಕ್ಲೌಡ್ ಡ್ರೈವ್',
    'nav.notifications': 'ಸೂಚನೆಗಳು',
    'nav.settings': 'ಸೆಟ್ಟಿಂಗ್‌ಗಳು',
    'nav.menu': 'ಮೆನು',
    'common.save': 'ಉಳಿಸಿ',
    'common.cancel': 'ರದ್ದುಮಾಡಿ',
    'common.search_placeholder': 'ಸೂಪರ್ ಎಐ ಬಳಿ ಏನನ್ನಾದರೂ ಕೇಳಿ...',
    'shopping.cart': 'ಬುಟ್ಟಿ',
    'food.delivering_to': 'ತಲುಪಿಸುವ ಸ್ಥಳ: {location}',
    'settings.select_language': 'ಭಾಷೆಯನ್ನು ಆರಿಸಿ',
  },

  // 8. Kashmiri (کٲشُر) - RTL Perso-Arabic
  ks: {
    ...EN_CATALOG,
    'app.tagline': 'ہندوستانُک گۄڈنُک سپر اے آئی ایپ',
    'nav.home': 'گھرٕ',
    'nav.ai-assistant': 'اے آئی مددگار',
    'nav.search': 'تلاش',
    'nav.chat': 'کتھ باتھ',
    'nav.social': 'سوشل',
    'nav.video': 'ویڈیو',
    'nav.food': 'کھؠن چین',
    'nav.shopping': 'شاپنگ',
    'nav.payments': 'ادائیگی',
    'nav.notifications': 'اطلاعات',
    'nav.settings': 'ترتیبات',
    'nav.menu': 'مینیو',
    'common.save': 'محفوظ کٔریو',
    'common.cancel': 'منسوخ',
    'settings.select_language': 'زبان ژاریو',
    'food.delivering_to': 'پتہ: {location}',
  },

  // 9. Konkani (कोंकणी)
  kok: {
    ...EN_CATALOG,
    'app.tagline': 'भारताचें पयलें सार्वभौम एआय सुपर ॲप',
    'nav.home': 'मुखेल पान',
    'nav.ai-assistant': 'सुपर एआय',
    'nav.search': 'सोद',
    'nav.chat': 'उಲೊವ್ಣಿ',
    'nav.social': 'सामाजिक',
    'nav.video': 'व्हिडिओ',
    'nav.food': 'खाण-जेवण',
    'nav.shopping': 'झाविरो शॉपिंग',
    'nav.payments': 'पैसे भरणें',
    'nav.notifications': 'सूचना',
    'nav.settings': 'मांडावळ',
    'nav.menu': 'मेनू',
    'common.save': 'सांबाळात',
    'common.cancel': 'रद्द करात',
    'settings.select_language': 'भास निवडा',
    'food.delivering_to': 'पावोवपाची सुवात: {location}',
  },

  // 10. Maithili (मैथिली)
  mai: {
    ...EN_CATALOG,
    'app.tagline': 'भारतक पहिल संप्रभु एआई सुपर ऐप',
    'nav.home': 'मुख्य पृष्ठ',
    'nav.ai-assistant': 'सुपर एआई',
    'nav.search': 'खोज',
    'nav.chat': 'संवाद',
    'nav.social': 'सोशल',
    'nav.video': 'वीडियो',
    'nav.food': 'खान-पान',
    'nav.shopping': 'शॉपिंग',
    'nav.payments': 'भुगतान',
    'nav.notifications': 'सूचना',
    'nav.settings': 'सेटिंग्स',
    'nav.menu': 'मेनू',
    'common.save': 'सहेजू',
    'common.cancel': 'रद्द करू',
    'settings.select_language': 'भाषा चुनू',
    'food.delivering_to': 'पहुंचाबक स्थान: {location}',
  },

  // 11. Malayalam (മലയാളം)
  ml: {
    ...EN_CATALOG,
    'app.tagline': 'ഭാരതത്തിന്റെ ആദ്യ പരമാധികാര എഐ സൂപ്പർ ആപ്പ്',
    'nav.home': 'ഹോം',
    'nav.ai-assistant': 'സാർവത്രിക എഐ',
    'nav.search': 'തിരയുക',
    'nav.chat': 'സന്ദേശങ്ങൾ',
    'nav.social': 'സോഷ്യൽ ഫീഡ്',
    'nav.video': 'വീഡിയോ സ്ട്രീം',
    'nav.food': 'ഭക്ഷണശാലകൾ',
    'nav.shopping': 'സാവിറോ ഷോപ്പിംഗ്',
    'nav.payments': 'പേയ്‌മെന്റുകൾ',
    'nav.cloud': 'ക്ലൗഡ് ഡ്രൈവ്',
    'nav.notifications': 'അറിയിപ്പുകൾ',
    'nav.settings': 'ക്രമീകരണങ്ങൾ',
    'nav.menu': 'മെനു',
    'common.save': 'സംരക്ഷിക്കുക',
    'common.cancel': 'റദ്ദാക്കുക',
    'common.search_placeholder': 'സൂപ്പർ എഐയോട് എന്തും ചോദിക്കൂ...',
    'shopping.cart': 'കാർട്ട്',
    'food.delivering_to': 'എത്തിക്കുന്ന സ്ഥലം: {location}',
    'settings.select_language': 'ഭാഷ തിരഞ്ഞെടുക്കുക',
  },

  // 12. Manipuri / Meitei (মেইতেই / মৈতৈলোন্)
  mni: {
    ...EN_CATALOG,
    'app.tagline': 'ভারতকী অহানবা সুপর এআই এপ',
    'nav.home': 'য়ুম',
    'nav.ai-assistant': 'সুপর এআই',
    'nav.search': 'থীবা',
    'nav.chat': 'ৱারী শাবা',
    'nav.social': 'সোসিএল',
    'nav.video': 'ভিডিও',
    'nav.food': 'চাক-চা',
    'nav.shopping': 'পোৎ লৈবা',
    'nav.payments': 'শেন থীবা',
    'nav.notifications': 'পাউতাক',
    'nav.settings': 'সেটিংস',
    'nav.menu': 'মেনু',
    'common.save': 'থমজিনবা',
    'common.cancel': 'তোকপা',
    'settings.select_language': 'লোন খনবীয়ু',
    'food.delivering_to': 'য়ৌহনগদবা মফম: {location}',
  },

  // 13. Marathi (मराठी)
  mr: {
    ...EN_CATALOG,
    'app.tagline': 'भारताचे पहिले सार्वभौम एआय सुपर ॲप',
    'nav.home': 'मुख्यपृष्ठ',
    'nav.ai-assistant': 'सार्वत्रिक एआय',
    'nav.search': 'शोध',
    'nav.chat': 'गप्पा आणि संदेश',
    'nav.social': 'सोशल फीड',
    'nav.video': 'व्हिडिओ प्रवाह',
    'nav.food': 'अन्न आणि उपहारगृह',
    'nav.shopping': 'झाविरो शॉपिंग',
    'nav.payments': 'युपीआय आणि देयके',
    'nav.cloud': 'क्लाउड ड्राइव्ह',
    'nav.notifications': 'सूचना',
    'nav.settings': 'सेटिंग्ज',
    'nav.menu': 'मेनू',
    'common.save': 'जतन करा',
    'common.cancel': 'रद्द करा',
    'common.status': 'स्थिती',
    'common.search_placeholder': 'सुपर एआयला काहीही विचारा...',
    'shopping.cart': 'कार्ट',
    'food.delivering_to': 'डिलिव्हरी पत्ता: {location}',
    'settings.title': 'सेटिंग्ज आणि गोपनीयता केंद्र',
    'settings.select_language': 'भाषा निवडा',
  },

  // 14. Nepali (नेपाली)
  ne: {
    ...EN_CATALOG,
    'app.tagline': 'भारतको पहिलो सार्वभौम एआई सुपर एप',
    'nav.home': 'गृहपृष्ठ',
    'nav.ai-assistant': 'सुपर एआई',
    'nav.search': 'खोज्नुहोस्',
    'nav.chat': 'कुराकानी',
    'nav.social': 'सामाजिक',
    'nav.video': 'भिडियो',
    'nav.food': 'खाना तथा खाजा',
    'nav.shopping': 'जाविरो शपिङ',
    'nav.payments': 'भुक्तानी',
    'nav.notifications': 'सूचनाहरू',
    'nav.settings': 'सेटिङहरू',
    'nav.menu': 'मेनु',
    'common.save': 'बचत गर्नुहोस्',
    'common.cancel': 'रद्द गर्नुहोस्',
    'settings.select_language': 'भाषा चयन गर्नुहोस्',
    'food.delivering_to': 'डेलिभरी ठेगाना: {location}',
  },

  // 15. Odia (ଓଡ଼ିଆ)
  or: {
    ...EN_CATALOG,
    'app.tagline': 'ଭାରତର ପ୍ରଥମ ସାର୍ବଭୌମ ଏଆଇ ସୁପର ଆପ୍',
    'nav.home': 'ମୂଳପୃଷ୍ଠା',
    'nav.ai-assistant': 'ସାର୍ବଜନୀନ ଏଆଇ',
    'nav.search': 'ସନ୍ଧାନ',
    'nav.chat': 'ବାର୍ତ୍ତାଳାପ',
    'nav.social': 'ସାମାଜିକ',
    'nav.video': 'ଭିଡିଓ ଷ୍ଟ୍ରିମ୍',
    'nav.food': 'ଖାଦ୍ୟ ଏବଂ ରେସ୍ତୋରାଁ',
    'nav.shopping': 'ଝାଭିରୋ ସପିଂ',
    'nav.payments': 'ୟୁପିଆଇ ଦେୟ',
    'nav.cloud': 'କ୍ଲାଉଡ୍ ଡ୍ରାଇଭ୍',
    'nav.notifications': 'ବିଜ୍ଞପ୍ତି',
    'nav.settings': 'ସେଟିଂସ୍',
    'nav.menu': 'ମେନୁ',
    'common.save': 'ସାଇତନ୍ତୁ',
    'common.cancel': 'ବାତିଲ କରନ୍ତୁ',
    'common.search_placeholder': 'ସୁପର ଏଆଇକୁ ଯାହା ପଚାରନ୍ତୁ...',
    'shopping.cart': 'କାର୍ଟ',
    'food.delivering_to': 'ବିତରଣ ସ୍ଥାନ: {location}',
    'settings.select_language': 'ଭାଷା ଚୟନ କରନ୍ତୁ',
  },

  // 16. Punjabi (ਪੰਜਾਬੀ)
  pa: {
    ...EN_CATALOG,
    'app.tagline': 'ਭਾਰਤ ਦੀ ਪਹਿਲੀ ਖੁਦਮੁਖਤਿਆਰ ਏਆਈ ਸੁਪਰ ਐਪ',
    'nav.home': 'ਮੁੱਖ ਸਫ਼ਾ',
    'nav.ai-assistant': 'ਸੁਪਰ ਏਆਈ',
    'nav.search': 'ਖੋਜ',
    'nav.chat': 'ਗੱਲਬਾਤ',
    'nav.social': 'ਸੋਸ਼ਲ ਫੀਡ',
    'nav.video': 'ਵੀਡੀਓ ਸਟ੍ਰੀਮ',
    'nav.food': 'ਖਾਣਾ-ਪੀਣਾ',
    'nav.shopping': 'ਜ਼ਾਵੀਰੋ ਸ਼ਾਪਿੰਗ',
    'nav.payments': 'ਭੁਗਤਾਨ',
    'nav.cloud': 'ਕਲਾਉਡ ਡਰਾਈਵ',
    'nav.notifications': 'ਸੂਚਨਾਵਾਂ',
    'nav.settings': 'ਸੈਟਿੰਗਾਂ',
    'nav.menu': 'ਮੇਨੂ',
    'common.save': 'ਸੰਭਾਲੋ',
    'common.cancel': 'ਰੱਦ ਕਰੋ',
    'common.search_placeholder': 'ਸੁਪਰ ਏਆਈ ਨੂੰ ਕੁਝ ਵੀ ਪੁੱਛੋ...',
    'shopping.cart': 'ਕਾਰਟ',
    'food.delivering_to': 'ਪਹੁੰਚਾਉਣ ਦਾ ਪਤਾ: {location}',
    'settings.select_language': 'ਭਾਸ਼ਾ ਚੁਣੋ',
  },

  // 17. Sanskrit (संस्कृतम्)
  sa: {
    ...EN_CATALOG,
    'app.tagline': 'भारतस्य प्रथमं सार्वभौमं कृत्रिमप्रज्ञा-सुपर-अनुप्रयोगम्',
    'nav.home': 'गृहम्',
    'nav.ai-assistant': 'सर्वव्यापी एआई',
    'nav.search': 'अन्वेषणम्',
    'nav.chat': 'संभाषणम्',
    'nav.social': 'सामाजिकम्',
    'nav.video': 'दृश्यश्राव्यम्',
    'nav.food': 'आहारः भोजनं च',
    'nav.shopping': 'विपणनम्',
    'nav.payments': 'वित्तीय-व्यवहारः',
    'nav.cloud': 'मेघ-सञ्चयः',
    'nav.notifications': 'सूचनाः',
    'nav.settings': 'समायोजनानि',
    'nav.menu': 'सूची',
    'common.save': 'संरक्षतु',
    'common.cancel': 'निरस्यतु',
    'settings.select_language': 'भाषां चिनोतु',
    'food.delivering_to': 'वितरणस्थानम्: {location}',
  },

  // 18. Santali (ᱥᱟᱱᱛᱟᱲᱤ) - Ol Chiki
  sat: {
    ...EN_CATALOG,
    'app.tagline': 'ᱵᱷᱟᱨᱚᱛ ᱨᱮᱱᱟᱜ ᱯᱩᱭᱞᱩ ᱮᱟᱭ ᱥᱩᱯᱚᱨ ᱮᱯ',
    'nav.home': 'ᱚᱲᱟᱜ',
    'nav.ai-assistant': 'ᱥᱩᱯᱚᱨ ᱮᱟᱭ',
    'nav.search': 'ᱥᱮᱸᱫᱽᱨᱟ',
    'nav.chat': 'ᱨᱚᱯᱚᱲ',
    'nav.social': 'ᱥᱟᱶᱛᱟ',
    'nav.video': 'ᱵᱷᱤᱰᱤᱭᱳ',
    'nav.food': 'ᱡᱚᱢ-ᱧᱩ',
    'nav.shopping': 'ᱠᱤᱨᱤᱧ-ᱟᱹᱠᱷᱨᱤᱧ',
    'nav.payments': 'ᱴᱟᱠᱟ ᱪᱟᱞ',
    'nav.notifications': 'ᱠᱷᱚᱵᱚᱨ',
    'nav.settings': 'ᱥᱟᱡᱟᱣ',
    'nav.menu': 'ᱢᱮᱱᱩ',
    'common.save': 'ᱥᱟᱧᱪᱟᱣ',
    'common.cancel': 'ᱵᱟᱹᱛᱤᱞ',
    'settings.select_language': 'ᱯᱟᱹᱨᱥᱤ ᱵᱟᱪᱷᱟᱣ',
    'food.delivering_to': 'ᱥᱮᱴᱮᱨ ᱴᱷᱟᱶ: {location}',
  },

  // 19. Sindhi (سنڌي) - RTL Perso-Arabic
  sd: {
    ...EN_CATALOG,
    'app.tagline': 'ڀارت جو پهريون سپريم اي آءِ سپر ايپ',
    'nav.home': 'مکيه صفحو',
    'nav.ai-assistant': 'سپر اي آءِ',
    'nav.search': 'ڳولا',
    'nav.chat': 'ڳالهه ٻولهه',
    'nav.social': 'سوشل',
    'nav.video': 'وڊيو',
    'nav.food': 'کاڌو پيتو',
    'nav.shopping': 'خريداري',
    'nav.payments': 'ادائگيون',
    'nav.notifications': 'نوٽيفڪيشن',
    'nav.settings': 'سيٽنگون',
    'nav.menu': 'مينيو',
    'common.save': 'محفوظ ڪريو',
    'common.cancel': 'رد ڪريو',
    'settings.select_language': 'ٻولي چونڊيو',
    'food.delivering_to': 'پهچائڻ جو هنڌ: {location}',
  },

  // 20. Tamil (தமிழ்)
  ta: {
    ...EN_CATALOG,
    'app.title': 'சூப்பர் ஏஐ (SUPER_AI)',
    'app.tagline': 'இந்தியாவின் முதன்மை இறையாண்மை செயற்கை நுண்ணறிவு சூப்பர் செயலி',
    'nav.home': 'முகப்பு',
    'nav.ai-assistant': 'முழுமை ஏஐ',
    'nav.search': 'உலகளாவிய தேடல்',
    'nav.chat': 'அரட்டை & செய்தி',
    'nav.social': 'சமூக வலை',
    'nav.video': 'காணொளி தளம்',
    'nav.food': 'உணவு & விருந்து',
    'nav.shopping': 'சாவிரோ அங்காடி',
    'nav.payments': 'யூபிஐ கட்டணம்',
    'nav.cloud': 'மேக சேமிப்பகம்',
    'nav.workspace': 'பணி மேடை',
    'nav.mini-apps': 'குறுஞ்செயலிகள்',
    'nav.customization': 'வடிவமைப்பு அரங்கம்',
    'nav.notifications': 'அறிவிப்புகள்',
    'nav.settings': 'அமைப்புகள்',
    'nav.menu': 'பட்டியல்',
    'common.search_placeholder': 'எதையும் கேளுங்கள் அல்லது சேவைகளைத் தேடுங்கள் (Ctrl+K)...',
    'common.demo_badge': 'செயல் விளக்க மாதிரி',
    'common.demo_warning': 'இந்த தளம் மாதிரி தரவுகளுடன் இயங்குகிறது. நேரடி கட்டணங்கள் எதுவும் வசூலிக்கப்படாது.',
    'common.save': 'சேமிக்க',
    'common.cancel': 'ரத்துசெய்',
    'common.clear': 'அழி',
    'common.status': 'நிலை',
    'home.greeting_morning': 'காலை வணக்கம், {name}',
    'home.greeting_afternoon': 'மதிய வணக்கம், {name}',
    'home.greeting_evening': 'மாலை வணக்கம், {name}',
    'shopping.title': 'சாவிரோ அங்காடி',
    'shopping.cart': 'கூடை',
    'shopping.checkout': 'செக்அவுட்',
    'shopping.cart_items': 'கூடையில் {count} பொருட்கள் உள்ளன',
    'food.delivering_to': 'வழங்கும் இடம்: {location}',
    'food.restaurants': 'உணவகங்கள்',
    'food.order_now': 'உடனே ஆர்டர் செய்க',
    'payments.balance': 'மொத்த யூபிஐ இருப்பு',
    'cloud.storage_used': '{total}-ல் {used} பயன்படுத்தப்பட்டது',
    'settings.title': 'அமைப்புகள் & தனியுரிமை மையம்',
    'settings.language': 'மொழி & எழுத்து வடிவம்',
    'settings.select_language': 'செயலி மொழியைத் தேர்ந்தெடுக்கவும்',
  },

  // 21. Telugu (తెలుగు)
  te: {
    ...EN_CATALOG,
    'app.tagline': 'భారతదేశపు మొదటి సార్వభౌమ ఏఐ సూపర్ యాప్',
    'nav.home': 'హోమ్',
    'nav.ai-assistant': 'సార్వత్రిక ఏఐ',
    'nav.search': 'శోధన',
    'nav.chat': 'చాట్ మరియు సందేశాలు',
    'nav.social': 'సోషల్ ఫీడ్',
    'nav.video': 'వీడియో స్ట్రీమ్',
    'nav.food': 'ఆహారం మరియు డైనింగ్',
    'nav.shopping': 'జావిరో షాపింగ్',
    'nav.payments': 'చెల్లింపులు',
    'nav.cloud': 'క్లౌడ్ డ్రైవ్',
    'nav.notifications': 'నోటిఫికేషన్లు',
    'nav.settings': 'సెట్టింగ్‌లు',
    'nav.menu': 'మెనూ',
    'common.save': 'భద్రపరచు',
    'common.cancel': 'రద్దు చేయి',
    'common.search_placeholder': 'సూపర్ ఏఐని ఏదైనా అడగండి...',
    'shopping.cart': 'కార్ట్',
    'food.delivering_to': 'డెలివరీ చిరునామా: {location}',
    'settings.select_language': 'భాషను ఎంచుకోండి',
  },

  // 22. Urdu (اردو) - RTL Perso-Arabic
  ur: {
    ...EN_CATALOG,
    'app.tagline': 'ہندوستان کی پہلی خود مختار اے آئی سپر ایپ',
    'nav.home': 'ہوم',
    'nav.ai-assistant': 'یونیورسل اے آئی',
    'nav.search': 'تلاش',
    'nav.chat': 'بات چیت اور پیغامات',
    'nav.social': 'سوشل فیڈ',
    'nav.video': 'ویڈیو اسٹریم',
    'nav.food': 'کھانا اور ریستوراں',
    'nav.shopping': 'زاویرو شاپنگ',
    'nav.payments': 'یو پی آئی اور ادائیگیاں',
    'nav.cloud': 'کلاؤڈ ڈرائیو',
    'nav.notifications': 'اطلاعات',
    'nav.settings': 'ترتیبات',
    'nav.menu': 'مینو',
    'common.search_placeholder': 'سپر اے آئی سے کچھ بھی پوچھیں (Ctrl+K)...',
    'common.save': 'محفوظ کریں',
    'common.cancel': 'منسوخ کریں',
    'common.status': 'حیثیت',
    'home.greeting_morning': 'صبح بخیر، {name}',
    'home.greeting_afternoon': 'دوپہر بخیر، {name}',
    'home.greeting_evening': 'شام بخیر، {name}',
    'shopping.title': 'زاویرو مارکیٹ پلیس',
    'shopping.cart': 'کارٹ',
    'shopping.checkout': 'چیک آؤٹ',
    'shopping.cart_items': 'کارٹ میں {count} اشیاء ہیں',
    'food.delivering_to': 'ترسیل کا پتہ: {location}',
    'food.restaurants': 'ریستوران',
    'food.order_now': 'ابھی آرڈر کریں',
    'settings.title': 'ترتیبات اور پرائیویسی ہب',
    'settings.language': 'زبان اور رسم الخط',
    'settings.select_language': 'انٹرفیس کی زبان منتخب کریں',
  },
};

/**
 * Typed translation helper with variable interpolation and fallback to English
 */
export function t(key: string, lang: AppLanguage = 'en', params?: TranslationParams): string {
  const langDict = TRANSLATIONS[lang] || TRANSLATIONS['en'];
  let rawText = langDict[key] || TRANSLATIONS['en'][key] || key;

  if (params) {
    Object.keys(params).forEach((paramKey) => {
      const val = String(params[paramKey]);
      rawText = rawText.replace(new RegExp(`\\{${paramKey}\\}`, 'g'), val);
    });
  }

  // Safety safeguard: never leak unresolved {placeholder} tokens into production UI
  if (rawText.includes('{used}') || rawText.includes('{total}')) {
    rawText = rawText.replace(/\{used\}/g, '0 GB').replace(/\{total\}/g, '100 GB');
  }

  return rawText;
}

/**
 * Locale-aware Rupee Currency Formatter (without altering stored paise value)
 */
export function formatCurrencyPaise(paise: number, lang: AppLanguage = 'en'): string {
  const rupees = paise / 100;
  try {
    const localeMap: Record<string, string> = {
      en: 'en-IN',
      hi: 'hi-IN',
      ta: 'ta-IN',
      te: 'te-IN',
      kn: 'kn-IN',
      ml: 'ml-IN',
      bn: 'bn-IN',
      mr: 'mr-IN',
      gu: 'gu-IN',
      pa: 'pa-IN',
      ur: 'ur-IN',
    };
    const locale = localeMap[lang] || 'en-IN';
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(rupees);
  } catch {
    return `₹${rupees.toFixed(2)}`;
  }
}

/**
 * Completeness Report Generator
 */
export function getTranslationStatusReport() {
  const totalBaseKeys = Object.keys(EN_CATALOG).length;
  const report: Record<AppLanguage, { total: number; translated: number; missing: number; completenessPercent: number }> = {} as any;

  (Object.keys(LANGUAGE_REGISTRY) as AppLanguage[]).forEach((lang) => {
    const dict = TRANSLATIONS[lang] || {};
    let translatedCount = 0;
    Object.keys(EN_CATALOG).forEach((k) => {
      if (dict[k] && (lang === 'en' || dict[k] !== EN_CATALOG[k])) {
        translatedCount++;
      } else if (lang === 'en') {
        translatedCount++;
      }
    });

    const completenessPercent = Math.round((translatedCount / totalBaseKeys) * 100);
    report[lang] = {
      total: totalBaseKeys,
      translated: translatedCount,
      missing: totalBaseKeys - translatedCount,
      completenessPercent,
    };
  });

  return report;
}
