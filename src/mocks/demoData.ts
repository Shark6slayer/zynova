export interface UserProfile {
  id: string;
  name: string;
  handle: string;
  avatar: string;
  verified: boolean;
  location: string;
  bio: string;
  followersCount: number;
}

export interface DemoChatMessage {
  id: string;
  sender: 'user' | 'assistant' | 'contact';
  senderName: string;
  text: string;
  timestamp: string;
  read?: boolean;
}

export interface RestaurantItem {
  id: string;
  name: string;
  cuisine: string;
  rating: number;
  timeMins: number;
  priceForTwo: number;
  isVeg: boolean;
  image: string;
  popularDish: string;
}

export interface ProductItem {
  id: string;
  title: string;
  brand: string;
  category: string;
  price: number;
  originalPrice: number;
  rating: number;
  reviewsCount: number;
  image: string;
  inStock: boolean;
  fastDelivery: boolean;
}

export interface TransactionItem {
  id: string;
  title: string;
  category: 'Food' | 'Shopping' | 'Transfer' | 'Bills' | 'Entertainment';
  amount: number;
  type: 'debit' | 'credit';
  timestamp: string;
  upiId: string;
  status: 'SUCCESS' | 'PENDING';
}

export interface CloudFileItem {
  id: string;
  name: string;
  type: 'folder' | 'document' | 'spreadsheet' | 'code' | 'image' | 'pdf';
  size: string;
  updatedAt: string;
  isFavorite: boolean;
}

export interface MiniAppItem {
  id: string;
  name: string;
  category: string;
  developer: string;
  icon: string;
  rating: number;
  installed: boolean;
  description: string;
}

export const MOCK_USER: UserProfile = {
  id: 'usr_001',
  name: 'Ananya Sharma',
  handle: '@ananya_ai',
  avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
  verified: true,
  location: 'Bengaluru, India',
  bio: 'AI Product Specialist & Tech Researcher. Exploring multi-agent intelligence and Indian sovereign AI tech stacks.',
  followersCount: 14200,
};

export const MOCK_RESTAURANTS: RestaurantItem[] = [
  {
    id: 'rest_01',
    name: 'A2B - Adyar Ananda Bhavan',
    cuisine: 'South Indian, Pure Veg',
    rating: 4.6,
    timeMins: 22,
    priceForTwo: 350,
    isVeg: true,
    image: 'https://images.unsplash.com/photo-1610192244261-3f33de3f55e4?w=600&auto=format&fit=crop&q=80',
    popularDish: 'Ghee Roast Dosa & Filter Coffee',
  },
  {
    id: 'rest_02',
    name: 'Meghana Foods',
    cuisine: 'Andhra, Biryani',
    rating: 4.8,
    timeMins: 30,
    priceForTwo: 650,
    isVeg: false,
    image: 'https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=600&auto=format&fit=crop&q=80',
    popularDish: 'Special Chicken Boneless Biryani',
  },
  {
    id: 'rest_03',
    name: 'Truffles Bistro',
    cuisine: 'Burgers, American, Desserts',
    rating: 4.5,
    timeMins: 28,
    priceForTwo: 550,
    isVeg: false,
    image: 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600&auto=format&fit=crop&q=80',
    popularDish: 'All American Cheese Burger',
  },
  {
    id: 'rest_04',
    name: 'The Rameshwaram Cafe',
    cuisine: 'Authentic South Indian',
    rating: 4.9,
    timeMins: 25,
    priceForTwo: 300,
    isVeg: true,
    image: 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=600&auto=format&fit=crop&q=80',
    popularDish: 'Podi Thatte Idli with Ghee',
  },
];

export const MOCK_PRODUCTS: ProductItem[] = [
  {
    id: 'prod_1',
    title: 'Titan Connected Smart Edge Ultra X',
    brand: 'Titan',
    category: 'Wearables',
    price: 8999,
    originalPrice: 12999,
    rating: 4.7,
    reviewsCount: 1840,
    image: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80',
    inStock: true,
    fastDelivery: true,
  },
  {
    id: 'prod_2',
    title: 'boAt Airdopes Nirvana Pro ANC Earbuds',
    brand: 'boAt',
    category: 'Audio',
    price: 3499,
    originalPrice: 6999,
    rating: 4.4,
    reviewsCount: 3200,
    image: 'https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=600&auto=format&fit=crop&q=80',
    inStock: true,
    fastDelivery: true,
  },
  {
    id: 'prod_3',
    title: 'Minimalist 10% Niacinamide Serum 30ml',
    brand: 'Be Minimalist',
    category: 'Personal Care',
    price: 599,
    originalPrice: 699,
    rating: 4.8,
    reviewsCount: 9400,
    image: 'https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=600&auto=format&fit=crop&q=80',
    inStock: true,
    fastDelivery: false,
  },
  {
    id: 'prod_4',
    title: 'Handloom Pure Mulberry Silk Saree',
    brand: 'Kancheepuram Weaves',
    category: 'Apparel',
    price: 14500,
    originalPrice: 18500,
    rating: 4.9,
    reviewsCount: 420,
    image: 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=600&auto=format&fit=crop&q=80',
    inStock: true,
    fastDelivery: true,
  },
];

export const MOCK_TRANSACTIONS: TransactionItem[] = [
  {
    id: 'tx_981',
    title: 'Swiggy Instamart Order',
    category: 'Food',
    amount: 482,
    type: 'debit',
    timestamp: 'Today, 10:14 AM',
    upiId: 'swiggy@icici',
    status: 'SUCCESS',
  },
  {
    id: 'tx_980',
    title: 'Client Consulting Remittance',
    category: 'Transfer',
    amount: 45000,
    type: 'credit',
    timestamp: 'Yesterday, 4:30 PM',
    upiId: 'deeptechlabs@hdfcbank',
    status: 'SUCCESS',
  },
  {
    id: 'tx_979',
    title: 'BESCOM Electricity Bill',
    category: 'Bills',
    amount: 1850,
    type: 'debit',
    timestamp: '12 Oct, 11:20 AM',
    upiId: 'bescom@sbi',
    status: 'SUCCESS',
  },
  {
    id: 'tx_978',
    title: 'BookMyShow Bangalore Film Festival',
    category: 'Entertainment',
    amount: 900,
    type: 'debit',
    timestamp: '10 Oct, 8:15 PM',
    upiId: 'bookmyshow@axisbank',
    status: 'SUCCESS',
  },
];

export const MOCK_MINI_APPS: MiniAppItem[] = [
  {
    id: 'app_irctc',
    name: 'RailConnect Pro',
    category: 'Travel & Mobility',
    developer: 'Indian Transit Labs',
    icon: 'Train',
    rating: 4.7,
    installed: true,
    description: 'Instant PNR status prediction, tatkal booking assistant, and live train tracker.',
  },
  {
    id: 'app_digilocker',
    name: 'Secure Vault Locker',
    category: 'Identity & Legal',
    developer: 'National Sovereign Tech',
    icon: 'ShieldCheck',
    rating: 4.9,
    installed: true,
    description: 'Cryptographically verified Aadhaar, PAN, and driving license stored locally.',
  },
  {
    id: 'app_zerodha',
    name: 'Kite Market Radar',
    category: 'Finance & Wealth',
    developer: 'FinTech Pulse',
    icon: 'TrendingUp',
    rating: 4.8,
    installed: false,
    description: 'Real-time NSE/BSE stock screener with multilingual AI sentiment breakdown.',
  },
  {
    id: 'app_health',
    name: 'Ayush TeleHealth',
    category: 'Wellness & Health',
    developer: 'CareBharat Health',
    icon: 'Activity',
    rating: 4.6,
    installed: false,
    description: 'Connect with certified doctors and Ayurvedic consultants across 10 Indian languages.',
  },
];
