import type { UserPreferences } from '../types';

// Dynamic Mobile & Web Base URL Resolver
export const getApiBaseUrl = (): string => {
  // If explicitly provided via Vite environment variable and not a placeholder, prioritize it
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && !envUrl.includes('YOUR-BACKEND-DOMAIN') && !envUrl.includes('<verified-production-api-host>')) {
    return envUrl.replace(/\/+$/, '');
  }

  // Detect Capacitor Android webview or emulator
  const isCapacitor = typeof (window as any)?.Capacitor !== 'undefined';
  const isLocalhostOrigin = window.location.hostname === 'localhost' || window.location.origin.includes('localhost');
  const isAndroidUA = navigator.userAgent.includes('Android');

  if (isCapacitor || (isLocalhostOrigin && isAndroidUA)) {
    // Android emulator loopback alias to host machine
    return 'http://10.0.2.2:8000/api/v1';
  }

  // Local development fallback
  if (import.meta.env.DEV || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'http://127.0.0.1:8000/api/v1';
  }

  // In production on a public domain, if VITE_API_BASE_URL is missing, we must NOT fall back to loopback.
  // We point to relative API path or surface a configuration notice.
  return '/api/v1';
};

export const API_BASE_URL = getApiBaseUrl();

export interface HealthCheckResponse {
  status: 'healthy' | 'unhealthy';
  service: string;
  environment: string;
}

export interface ReadinessResponse {
  status: 'ready' | 'not_ready';
  database: string;
  dependencies: {
    mongodb: string;
  };
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  refresh_token: string;
}

export interface UserProfileResponse {
  id: string;
  email: string;
  username: string;
  full_name: string;
  avatar_url?: string | null;
  bio?: string | null;
  created_at: string;
  is_active: boolean;
}

export interface RegisterPayload {
  email: string;
  username: string;
  full_name: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface UpdateProfilePayload {
  full_name?: string;
  avatar_url?: string;
  bio?: string;
}

export interface UserPublicSummary {
  id: string;
  username: string;
  full_name: string;
  avatar_url?: string | null;
}

export interface LastMessageSummary {
  id: string;
  sender_id: string;
  text: string;
  created_at: string;
}

export interface ChatConversationResponse {
  id: string;
  type: string;
  participants: string[];
  participant_meta: Record<string, UserPublicSummary>;
  last_message?: LastMessageSummary | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageResponse {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_username: string;
  sender_full_name: string;
  sender_avatar?: string | null;
  text: string;
  created_at: string;
  updated_at: string;
  is_edited: boolean;
  is_deleted: boolean;
  read_by: string[];
}

// Social Network Interfaces
export interface SocialProfileResponse {
  id: string;
  username: string;
  full_name: string;
  avatar_url?: string | null;
  bio?: string | null;
  created_at: string;
  followers_count: number;
  following_count: number;
  posts_count: number;
  is_following: boolean;
  is_self: boolean;
}

export interface PostCreatePayload {
  content: string;
  image_url?: string | null;
  media_url?: string | null;
  media_type?: 'image' | 'video' | null;
}

export interface PostResponse {
  id: string;
  author_id: string;
  author_username: string;
  author_full_name: string;
  author_avatar?: string | null;
  content: string;
  image_url?: string | null;
  media_url?: string | null;
  media_type?: 'image' | 'video' | null;
  created_at: string;
  updated_at: string;
  is_edited: boolean;
  likes_count: number;
  comments_count: number;
  is_liked: boolean;
  is_owner: boolean;
}

export interface CommentResponse {
  id: string;
  post_id: string;
  author_id: string;
  author_username: string;
  author_full_name: string;
  author_avatar?: string | null;
  content: string;
  created_at: string;
  is_owner: boolean;
}

export interface ReportPayload {
  target_type: 'post' | 'user' | 'comment';
  target_id: string;
  reason: string;
  description?: string;
}

export interface ReportResponse {
  id: string;
  reporter_id: string;
  target_type: string;
  target_id: string;
  reason: string;
  status: string;
  created_at: string;
}

// Platform Search Engine Interfaces
export interface SearchResultItem {
  id: string;
  result_type: 'person' | 'post';
  title: string;
  subtitle?: string | null;
  excerpt: string;
  avatar_url?: string | null;
  image_url?: string | null;
  timestamp?: string | null;
  navigation_target: string;
  metadata?: Record<string, any>;
}

export interface SearchResponse {
  query: string;
  filter_type: string;
  total_count: number;
  has_more: boolean;
  results: SearchResultItem[];
}

// Video Platform Interfaces
export interface VideoResponse {
  id: string;
  owner_id: string;
  owner_username: string;
  owner_full_name: string;
  owner_avatar?: string | null;
  title: string;
  description?: string | null;
  storage_key: string;
  mime_type: string;
  file_size_bytes: number;
  duration_seconds?: number | null;
  thumbnail_url?: string | null;
  visibility: 'public' | 'private';
  status: string;
  view_count: number;
  likes_count: number;
  comments_count: number;
  is_liked: boolean;
  is_owner: boolean;
  created_at: string;
  updated_at: string;
}

export interface VideoCommentResponse {
  id: string;
  video_id: string;
  author_id: string;
  author_username: string;
  author_full_name: string;
  author_avatar?: string | null;
  content: string;
  created_at: string;
  is_owner: boolean;
}

// Food Discovery & Ordering Interfaces
export interface MenuItemResponse {
  id: string;
  restaurant_id: string;
  name: string;
  description?: string | null;
  price_paise: number;
  price_inr: number;
  is_veg: boolean;
  is_available: boolean;
  category: string;
  image_url?: string | null;
}

export interface RestaurantResponse {
  id: string;
  name: string;
  description?: string | null;
  service_area: string;
  address: string;
  cuisine: string;
  rating: number;
  time_mins: number;
  price_for_two_inr: number;
  is_veg: boolean;
  image_url?: string | null;
  is_open: boolean;
  owner_id?: string | null;
  menu?: MenuItemResponse[] | null;
}

export interface OrderItemInput {
  item_id: string;
  quantity: number;
}

export interface CreateOrderPayload {
  restaurant_id: string;
  items: OrderItemInput[];
  delivery_address: string;
  payment_method: 'cod' | 'test_mode_upi' | 'test_mode_card';
}

export interface OrderItemSnapshot {
  item_id: string;
  name: string;
  unit_price_paise: number;
  quantity: number;
  total_price_paise: number;
}

export interface FoodOrderResponse {
  id: string;
  customer_id: string;
  customer_name: string;
  customer_email: string;
  restaurant_id: string;
  restaurant_name: string;
  items: OrderItemSnapshot[];
  item_count: number;
  delivery_address: string;
  subtotal_paise: number;
  delivery_fee_paise: number;
  taxes_paise: number;
  total_paise: number;
  total_inr: number;
  payment_method: string;
  payment_status: string;
  order_status: 'placed' | 'confirmed' | 'preparing' | 'out_for_delivery' | 'delivered' | 'cancelled';
  created_at: string;
  updated_at: string;
}

// Shopping & E-Commerce Interfaces (Phase 4I)
export interface ProductResponse {
  id: string;
  name: string;
  brand: string;
  sku: string;
  category: string;
  description: string;
  price_paise: number;
  price_inr: number;
  mrp_paise?: number | null;
  mrp_inr?: number | null;
  rating: number;
  reviews_count: number;
  stock: number;
  is_available: boolean;
  is_published: boolean;
  is_seed_data: boolean;
  seller_id?: string | null;
  seller_name?: string | null;
  images: string[];
  features: string[];
  created_at: string;
  updated_at: string;
}

export interface ShoppingCartItemInput {
  product_id: string;
  quantity: number;
}

export interface ShoppingOrderItemSnapshot {
  product_id: string;
  name: string;
  sku: string;
  brand: string;
  unit_price_paise: number;
  quantity: number;
  total_price_paise: number;
  image_url?: string | null;
  seller_id?: string | null;
}

export interface CreateShoppingOrderPayload {
  items: ShoppingCartItemInput[];
  shipping_full_name: string;
  shipping_phone: string;
  shipping_address: string;
  shipping_city: string;
  shipping_postal_code: string;
  payment_method: 'cod' | 'test_mode_upi' | 'test_mode_card';
  idempotency_key?: string;
}

export interface ShoppingOrderResponse {
  id: string;
  customer_id: string;
  customer_name: string;
  customer_email: string;
  shipping_full_name: string;
  shipping_phone: string;
  shipping_address: string;
  shipping_city: string;
  shipping_postal_code: string;
  items: ShoppingOrderItemSnapshot[];
  total_items_count: number;
  subtotal_paise: number;
  shipping_paise: number;
  taxes_paise: number;
  discount_paise: number;
  total_paise: number;
  total_inr: number;
  payment_method: string;
  payment_status: string;
  order_status: 'placed' | 'confirmed' | 'processing' | 'shipped' | 'delivered' | 'cancelled';
  idempotency_key?: string | null;
  created_at: string;
  updated_at: string;
}

// Phase 4: Seller & Restaurant Operation Interfaces
export interface SellerRegisterPayload {
  business_name: string;
  business_category: string;
  contact_phone: string;
  business_address: string;
  city: string;
  state: string;
  pincode: string;
  gstin_or_pan?: string;
}

export interface SellerResponse {
  id: string;
  user_id: string;
  business_name: string;
  business_category: string;
  contact_phone: string;
  business_address: string;
  city: string;
  state: string;
  pincode: string;
  gstin_or_pan?: string | null;
  status: 'pending' | 'approved' | 'rejected' | 'suspended';
  created_at: string;
  updated_at: string;
}

export interface SellerDashboardResponse {
  seller_id: string;
  business_name: string;
  status: string;
  active_products: number;
  low_stock_products: number;
  pending_orders: number;
  fulfilled_orders: number;
  gross_sales_paise: number;
  gross_sales_inr: number;
}

export interface ProductCreatePayload {
  name: string;
  brand: string;
  category: string;
  description: string;
  price_paise: number;
  mrp_paise?: number;
  stock: number;
  sku?: string;
  images?: string[];
  features?: string[];
  is_available?: boolean;
  is_published?: boolean;
}

export interface ProductUpdatePayload {
  name?: string;
  brand?: string;
  category?: string;
  description?: string;
  price_paise?: number;
  mrp_paise?: number;
  stock?: number;
  images?: string[];
  features?: string[];
  is_available?: boolean;
  is_published?: boolean;
}

export interface RestaurantRegisterPayload {
  name: string;
  description?: string;
  service_area: string;
  address: string;
  cuisine: string;
  price_for_two_inr: number;
  is_veg?: boolean;
  image_url?: string;
  is_open?: boolean;
}

export interface RestaurantUpdatePayload {
  name?: string;
  description?: string;
  service_area?: string;
  address?: string;
  cuisine?: string;
  price_for_two_inr?: number;
  is_veg?: boolean;
  image_url?: string;
  is_open?: boolean;
}

export interface MenuItemCreatePayload {
  name: string;
  category: string;
  price_paise: number;
  description?: string;
  is_veg?: boolean;
  is_available?: boolean;
  image_url?: string;
}

export interface MenuItemUpdatePayload {
  name?: string;
  category?: string;
  price_paise?: number;
  description?: string;
  is_veg?: boolean;
  is_available?: boolean;
  image_url?: string;
}

// Notification & Activity Center Interfaces (Phase 4K)
export interface NotificationResponse {
  id: string;
  user_id: string;
  category: 'chat' | 'social' | 'food' | 'shopping' | 'system';
  event_type: string;
  title: string;
  desc: string;
  time: string;
  read: boolean;
  read_at?: string | null;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface NotificationListResponse {
  total: number;
  unread_count: number;
  page: number;
  limit: number;
  has_more: boolean;
  notifications: NotificationResponse[];
}

export interface NotificationUnreadCountResponse {
  unread_count: number;
}

// UPI, Banking & Payments Interfaces (Phase 4J)
export interface BankAccountResponse {
  id: string;
  user_id: string;
  bank_name: string;
  ifsc_code: string;
  masked_account_number: string;
  account_type: 'savings' | 'current';
  nickname?: string | null;
  is_default: boolean;
  balance_paise?: number | null;
  balance_inr?: number | null;
  last_balance_enquiry?: string | null;
  provider_status: string;
  is_seed_account: boolean;
  created_at: string;
}

export interface BankAccountCreatePayload {
  bank_name: string;
  ifsc_code: string;
  account_number: string;
  account_type?: 'savings' | 'current';
  nickname?: string;
}

export interface RuPayCardResponse {
  id: string;
  user_id: string;
  issuing_bank: string;
  last_four_digits: string;
  nickname?: string | null;
  network: string;
  is_credit_on_upi_eligible: boolean;
  provider_status: string;
  created_at: string;
}

export interface RuPayCardCreatePayload {
  issuing_bank: string;
  last_four_digits: string;
  expiry_month: number;
  expiry_year: number;
  nickname?: string;
}

export interface SendPaymentPayload {
  recipient_type: 'upi_id' | 'phone' | 'contact' | 'merchant';
  recipient_identifier: string;
  recipient_name?: string;
  amount_paise: number;
  source_type: 'bank_account' | 'rupay_credit_card';
  source_id: string;
  note?: string;
  idempotency_key: string;
}

export interface PaymentTransactionResponse {
  id: string;
  user_id: string;
  transaction_ref: string;
  npci_ref?: string | null;
  recipient_type: string;
  recipient_identifier: string;
  recipient_name: string;
  amount_paise: number;
  amount_inr: number;
  fee_paise: number;
  source_type: string;
  source_id: string;
  source_title: string;
  category: string;
  status: 'success' | 'pending' | 'failed' | 'reversed';
  failure_reason?: string | null;
  note?: string | null;
  idempotency_key: string;
  created_at: string;
  updated_at: string;
}

export interface BillerResponse {
  id: string;
  category: string;
  name: string;
  operator_code: string;
  icon_name: string;
  sample_identifier_label: string;
}

export interface BillDetailResponse {
  biller_id: string;
  biller_name: string;
  category: string;
  customer_identifier: string;
  customer_name: string;
  bill_number: string;
  bill_date: string;
  due_date: string;
  amount_paise: number;
  amount_inr: number;
  is_test_fixture: boolean;
}

class ApiClient {
  private baseUrl: string;


  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  public getApiBaseUrl(): string {
    return getApiBaseUrl();
  }

  public getToken(): string | null {
    return localStorage.getItem('super_ai_access_token');
  }

  public setToken(token: string): void {
    localStorage.setItem('super_ai_access_token', token);
  }

  public getRefreshToken(): string | null {
    return localStorage.getItem('super_ai_refresh_token');
  }

  public setRefreshToken(token: string): void {
    localStorage.setItem('super_ai_refresh_token', token);
  }

  public clearTokens(): void {
    localStorage.removeItem('super_ai_access_token');
    localStorage.removeItem('super_ai_refresh_token');
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const currentBaseUrl = getApiBaseUrl();
    let response: Response;
    try {
      response = await fetch(`${currentBaseUrl}${endpoint}`, {
        ...options,
        headers,
      });
    } catch (networkErr: any) {
      console.warn(`[Zynova Network Error] Failed to reach API at ${currentBaseUrl}${endpoint}:`, networkErr);
      throw new Error(
        `Unable to connect to server. Please check your internet connection or verify backend configuration. (${networkErr.message || 'NetworkError'})`
      );
    }

    // If access token expired, try to refresh once automatically
    if (response.status === 401 && this.getRefreshToken()) {
      try {
        const refreshed = await this.refreshToken();
        if (refreshed) {
          headers['Authorization'] = `Bearer ${refreshed.access_token}`;
          response = await fetch(`${currentBaseUrl}${endpoint}`, {
            ...options,
            headers,
          });
        }
      } catch {
        this.clearTokens();
      }
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorBody.detail || `Request failed with status ${response.status}`);
    }

    return response.json();
  }

  // Authentication endpoints
  async register(payload: RegisterPayload): Promise<UserProfileResponse> {
    return this.request<UserProfileResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async login(payload: LoginPayload): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    this.setToken(res.access_token);
    this.setRefreshToken(res.refresh_token);
    return res;
  }

  async refreshToken(): Promise<AuthResponse | null> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return null;

    const res = await fetch(`${this.baseUrl}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      this.clearTokens();
      return null;
    }

    const data: AuthResponse = await res.json();
    this.setToken(data.access_token);
    this.setRefreshToken(data.refresh_token);
    return data;
  }

  async logout(): Promise<void> {
    try {
      await this.request('/auth/logout', { method: 'POST' });
    } catch (err) {
      console.warn('Logout endpoint warning:', err);
    } finally {
      this.clearTokens();
    }
  }

  // User details
  async getMe(): Promise<UserProfileResponse> {
    return this.request<UserProfileResponse>('/auth/me');
  }

  async updateProfile(payload: UpdateProfilePayload): Promise<UserProfileResponse> {
    return this.request<UserProfileResponse>('/users/me', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async deleteAccount(password: string): Promise<{ status: string; detail: string }> {
    const res = await this.request<{ status: string; detail: string }>('/users/me', {
      method: 'DELETE',
      body: JSON.stringify({ password }),
    });
    this.clearTokens();
    return res;
  }

  // System & Health
  async checkHealth(): Promise<HealthCheckResponse> {
    return this.request<HealthCheckResponse>('/health');
  }

  async checkReadiness(): Promise<ReadinessResponse> {
    return this.request<ReadinessResponse>('/ready');
  }

  // Preferences
  async getPreferences(): Promise<UserPreferences> {
    return this.request<UserPreferences>('/preferences');
  }

  async updatePreferences(preferences: UserPreferences): Promise<UserPreferences> {
    return this.request<UserPreferences>('/preferences', {
      method: 'PUT',
      body: JSON.stringify(preferences),
    });
  }

  // Chat Methods

  async searchUsers(query: string): Promise<UserPublicSummary[]> {
    return this.request<UserPublicSummary[]>(`/chat/users/search?q=${encodeURIComponent(query)}`);
  }

  async getOrCreateConversation(recipientId: string): Promise<ChatConversationResponse> {
    return this.request<ChatConversationResponse>('/chat/conversations', {
      method: 'POST',
      body: JSON.stringify({ recipient_id: recipientId }),
    });
  }

  async listConversations(limit: number = 50): Promise<ChatConversationResponse[]> {
    return this.request<ChatConversationResponse[]>(`/chat/conversations?limit=${limit}`);
  }

  async getChatMessages(conversationId: string, limit: number = 40, before?: string): Promise<ChatMessageResponse[]> {
    let url = `/chat/conversations/${conversationId}/messages?limit=${limit}`;
    if (before) {
      url += `&before=${encodeURIComponent(before)}`;
    }
    return this.request<ChatMessageResponse[]>(url);
  }

  async sendChatMessage(conversationId: string, text: string): Promise<ChatMessageResponse> {
    return this.request<ChatMessageResponse>(`/chat/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  }

  async editChatMessage(messageId: string, text: string): Promise<ChatMessageResponse> {
    return this.request<ChatMessageResponse>(`/chat/messages/${messageId}`, {
      method: 'PATCH',
      body: JSON.stringify({ text }),
    });
  }

  async deleteChatMessage(messageId: string): Promise<ChatMessageResponse> {
    return this.request<ChatMessageResponse>(`/chat/messages/${messageId}`, {
      method: 'DELETE',
    });
  }

  async markConversationRead(conversationId: string): Promise<void> {
    await this.request(`/chat/conversations/${conversationId}/read`, {
      method: 'POST',
    });
  }

  async getUnreadChatCount(): Promise<number> {
    const res = await this.request<{ unread_count: number }>('/chat/unread-count');
    return res.unread_count || 0;
  }

  // --- Social Network Methods ---
  async getSocialProfile(userId: string): Promise<SocialProfileResponse> {
    return this.request<SocialProfileResponse>(`/social/profiles/${userId}`);
  }

  async followUser(userId: string): Promise<{ success: boolean; is_following: boolean }> {
    return this.request<{ success: boolean; is_following: boolean }>(`/social/profiles/${userId}/follow`, {
      method: 'POST',
    });
  }

  async unfollowUser(userId: string): Promise<{ success: boolean; is_following: boolean }> {
    return this.request<{ success: boolean; is_following: boolean }>(`/social/profiles/${userId}/follow`, {
      method: 'DELETE',
    });
  }

  async listFollowers(userId: string, limit: number = 30): Promise<UserPublicSummary[]> {
    return this.request<UserPublicSummary[]>(`/social/profiles/${userId}/followers?limit=${limit}`);
  }

  async listFollowing(userId: string, limit: number = 30): Promise<UserPublicSummary[]> {
    return this.request<UserPublicSummary[]>(`/social/profiles/${userId}/following?limit=${limit}`);
  }

  async createSocialPost(payload: PostCreatePayload): Promise<PostResponse> {
    return this.request<PostResponse>('/social/posts', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async editSocialPost(postId: string, payload: PostCreatePayload): Promise<PostResponse> {
    return this.request<PostResponse>(`/social/posts/${postId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async deleteSocialPost(postId: string): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>(`/social/posts/${postId}`, {
      method: 'DELETE',
    });
  }

  async getSocialFeed(
    mode: 'discovery' | 'following' | 'reels' = 'discovery',
    limit: number = 20,
    before?: string
  ): Promise<PostResponse[]> {
    let url = `/social/feed?mode=${mode}&limit=${limit}`;
    if (before) {
      url += `&before=${encodeURIComponent(before)}`;
    }
    return this.request<PostResponse[]>(url);
  }

  async getUserSocialPosts(
    userId: string,
    limit: number = 20,
    before?: string,
    mediaFilter?: 'image' | 'video'
  ): Promise<PostResponse[]> {
    let url = `/social/users/${userId}/posts?limit=${limit}`;
    if (before) {
      url += `&before=${encodeURIComponent(before)}`;
    }
    if (mediaFilter) {
      url += `&media_filter=${mediaFilter}`;
    }
    return this.request<PostResponse[]>(url);
  }

  async likeSocialPost(postId: string): Promise<{ success: boolean; likes_count: number; is_liked: boolean }> {
    return this.request<{ success: boolean; likes_count: number; is_liked: boolean }>(`/social/posts/${postId}/like`, {
      method: 'POST',
    });
  }

  async unlikeSocialPost(postId: string): Promise<{ success: boolean; likes_count: number; is_liked: boolean }> {
    return this.request<{ success: boolean; likes_count: number; is_liked: boolean }>(`/social/posts/${postId}/like`, {
      method: 'DELETE',
    });
  }

  async listPostComments(postId: string, limit: number = 50): Promise<CommentResponse[]> {
    return this.request<CommentResponse[]>(`/social/posts/${postId}/comments?limit=${limit}`);
  }

  async createPostComment(postId: string, content: string): Promise<CommentResponse> {
    return this.request<CommentResponse>(`/social/posts/${postId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  async deletePostComment(commentId: string): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>(`/social/comments/${commentId}`, {
      method: 'DELETE',
    });
  }

  async reportContent(payload: ReportPayload): Promise<ReportResponse> {
    return this.request<ReportResponse>('/social/reports', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // --- Platform Search Engine Methods ---
  async searchPlatform(
    query: string,
    type: 'all' | 'people' | 'posts' = 'all',
    limit: number = 20,
    offset: number = 0,
    sort: 'recency' | 'relevance' = 'recency',
    signal?: AbortSignal
  ): Promise<SearchResponse> {
    const encodedQ = encodeURIComponent(query.trim());
    return this.request<SearchResponse>(
      `/search?q=${encodedQ}&type=${type}&limit=${limit}&offset=${offset}&sort=${sort}`,
      { signal }
    );
  }

  // --- Video Platform Methods ---
  async uploadVideo(formData: FormData): Promise<VideoResponse> {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}/videos`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorBody.detail || `Upload failed with status ${response.status}`);
    }

    return response.json();
  }

  async listVideos(limit: number = 20, offset: number = 0): Promise<VideoResponse[]> {
    return this.request<VideoResponse[]>(`/videos?limit=${limit}&offset=${offset}`);
  }

  async getVideoDetail(videoId: string): Promise<VideoResponse> {
    return this.request<VideoResponse>(`/videos/${videoId}`);
  }

  getVideoStreamUrl(videoId: string): string {
    return `${this.baseUrl}/videos/${videoId}/stream`;
  }

  async recordVideoView(videoId: string): Promise<{ recorded: boolean }> {
    return this.request<{ recorded: boolean }>(`/videos/${videoId}/view`, {
      method: 'POST',
    });
  }

  async likeVideo(videoId: string): Promise<{ success: boolean; likes_count: number; is_liked: boolean }> {
    return this.request<{ success: boolean; likes_count: number; is_liked: boolean }>(`/videos/${videoId}/like`, {
      method: 'POST',
    });
  }

  async unlikeVideo(videoId: string): Promise<{ success: boolean; likes_count: number; is_liked: boolean }> {
    return this.request<{ success: boolean; likes_count: number; is_liked: boolean }>(`/videos/${videoId}/like`, {
      method: 'DELETE',
    });
  }

  async listVideoComments(videoId: string, limit: number = 50): Promise<VideoCommentResponse[]> {
    return this.request<VideoCommentResponse[]>(`/videos/${videoId}/comments?limit=${limit}`);
  }

  async addVideoComment(videoId: string, content: string): Promise<VideoCommentResponse> {
    return this.request<VideoCommentResponse>(`/videos/${videoId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  async uploadSocialMedia(file: File): Promise<{ media_url: string; media_type: 'image' | 'video'; filename: string; size_bytes: number }> {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseUrl}/social/media`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorBody.detail || `Upload failed with status ${response.status}`);
    }

    return response.json();
  }

  async updateVideo(
    videoId: string,
    payload: { title?: string; description?: string; thumbnail_url?: string; visibility?: 'public' | 'private' }
  ): Promise<VideoResponse> {
    return this.request<VideoResponse>(`/videos/${videoId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async listUserVideos(userId: string, limit: number = 25): Promise<VideoResponse[]> {
    return this.request<VideoResponse[]>(`/videos/users/${userId}?limit=${limit}`);
  }

  async listRelatedVideos(videoId: string, limit: number = 6): Promise<VideoResponse[]> {
    return this.request<VideoResponse[]>(`/videos/${videoId}/related?limit=${limit}`);
  }

  async deleteVideo(videoId: string): Promise<{ status: string; video_id: string }> {
    return this.request<{ status: string; video_id: string }>(`/videos/${videoId}`, {
      method: 'DELETE',
    });
  }

  // --- Food Discovery & Ordering Methods ---
  async listRestaurants(vegOnly: boolean = false, search?: string, serviceArea?: string): Promise<RestaurantResponse[]> {
    let url = `/food/restaurants?veg_only=${vegOnly}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (serviceArea) url += `&service_area=${encodeURIComponent(serviceArea)}`;
    return this.request<RestaurantResponse[]>(url);
  }

  async getRestaurantDetail(restaurantId: string): Promise<RestaurantResponse> {
    return this.request<RestaurantResponse>(`/food/restaurants/${restaurantId}`);
  }

  async placeFoodOrder(payload: CreateOrderPayload): Promise<FoodOrderResponse> {
    return this.request<FoodOrderResponse>('/food/orders', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async listFoodOrders(limit: number = 20): Promise<FoodOrderResponse[]> {
    return this.request<FoodOrderResponse[]>(`/food/orders?limit=${limit}`);
  }

  async getFoodOrderDetail(orderId: string): Promise<FoodOrderResponse> {
    return this.request<FoodOrderResponse>(`/food/orders/${orderId}`);
  }

  async cancelFoodOrder(orderId: string): Promise<FoodOrderResponse> {
    return this.request<FoodOrderResponse>(`/food/orders/${orderId}/cancel`, {
      method: 'POST',
    });
  }

  // --- Shopping & E-Commerce Methods (Phase 4I) ---
  async listProducts(params?: {
    category?: string;
    search?: string;
    minPrice?: number;
    maxPrice?: number;
    sort?: 'featured' | 'price_asc' | 'price_desc' | 'rating' | 'newest';
    page?: number;
    limit?: number;
  }): Promise<ProductResponse[]> {
    const query = new URLSearchParams();
    if (params?.category) query.append('category', params.category);
    if (params?.search) query.append('search', params.search);
    if (params?.minPrice !== undefined) query.append('min_price', params.minPrice.toString());
    if (params?.maxPrice !== undefined) query.append('max_price', params.maxPrice.toString());
    if (params?.sort) query.append('sort', params.sort);
    if (params?.page) query.append('page', params.page.toString());
    if (params?.limit) query.append('limit', params.limit.toString());

    const qs = query.toString();
    const url = `/shopping/products${qs ? `?${qs}` : ''}`;
    return this.request<ProductResponse[]>(url);
  }

  async getProductDetail(productId: string): Promise<ProductResponse> {
    return this.request<ProductResponse>(`/shopping/products/${productId}`);
  }

  async placeShoppingOrder(payload: CreateShoppingOrderPayload): Promise<ShoppingOrderResponse> {
    return this.request<ShoppingOrderResponse>('/shopping/orders', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async listShoppingOrders(limit: number = 20): Promise<ShoppingOrderResponse[]> {
    return this.request<ShoppingOrderResponse[]>(`/shopping/orders?limit=${limit}`);
  }

  async getShoppingOrderDetail(orderId: string): Promise<ShoppingOrderResponse> {
    return this.request<ShoppingOrderResponse>(`/shopping/orders/${orderId}`);
  }

  async cancelShoppingOrder(orderId: string): Promise<ShoppingOrderResponse> {
    return this.request<ShoppingOrderResponse>(`/shopping/orders/${orderId}/cancel`, {
      method: 'POST',
    });
  }

  // --- Seller Operations Methods (Phase 4) ---
  async registerSeller(payload: SellerRegisterPayload): Promise<SellerResponse> {
    return this.request<SellerResponse>('/shopping/seller/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getSellerProfile(): Promise<SellerResponse> {
    return this.request<SellerResponse>('/shopping/seller/profile');
  }

  async getSellerDashboard(): Promise<SellerDashboardResponse> {
    return this.request<SellerDashboardResponse>('/shopping/seller/dashboard');
  }

  async listSellerProducts(): Promise<ProductResponse[]> {
    return this.request<ProductResponse[]>('/shopping/seller/products');
  }

  async createSellerProduct(payload: ProductCreatePayload): Promise<ProductResponse> {
    return this.request<ProductResponse>('/shopping/seller/products', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateSellerProduct(productId: string, payload: ProductUpdatePayload): Promise<ProductResponse> {
    return this.request<ProductResponse>(`/shopping/seller/products/${productId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async deleteSellerProduct(productId: string): Promise<{ status: string; product_id: string }> {
    return this.request<{ status: string; product_id: string }>(`/shopping/seller/products/${productId}`, {
      method: 'DELETE',
    });
  }

  async listSellerOrders(): Promise<ShoppingOrderResponse[]> {
    return this.request<ShoppingOrderResponse[]>('/shopping/seller/orders');
  }

  async updateSellerOrderStatus(orderId: string, status: 'processing' | 'shipped' | 'delivered'): Promise<ShoppingOrderResponse> {
    return this.request<ShoppingOrderResponse>(`/shopping/seller/orders/${orderId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }

  // --- Restaurant Partner Operations Methods (Phase 4) ---
  async registerRestaurant(payload: RestaurantRegisterPayload): Promise<RestaurantResponse> {
    return this.request<RestaurantResponse>('/food/owner/restaurant', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getOwnerRestaurant(): Promise<RestaurantResponse> {
    return this.request<RestaurantResponse>('/food/owner/restaurant');
  }

  async updateOwnerRestaurant(payload: RestaurantUpdatePayload): Promise<RestaurantResponse> {
    return this.request<RestaurantResponse>('/food/owner/restaurant', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async createMenuItem(payload: MenuItemCreatePayload): Promise<MenuItemResponse> {
    return this.request<MenuItemResponse>('/food/owner/menu', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateMenuItem(itemId: string, payload: MenuItemUpdatePayload): Promise<MenuItemResponse> {
    return this.request<MenuItemResponse>(`/food/owner/menu/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async deleteMenuItem(itemId: string): Promise<{ status: string; item_id: string }> {
    return this.request<{ status: string; item_id: string }>(`/food/owner/menu/${itemId}`, {
      method: 'DELETE',
    });
  }

  async listRestaurantOrders(): Promise<FoodOrderResponse[]> {
    return this.request<FoodOrderResponse[]>('/food/owner/orders');
  }

  async updateRestaurantOrderStatus(
    orderId: string,
    status: 'confirmed' | 'preparing' | 'out_for_delivery' | 'delivered' | 'cancelled'
  ): Promise<FoodOrderResponse> {
    return this.request<FoodOrderResponse>(`/food/owner/orders/${orderId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }

  // --- Notifications & Activity Center Methods (Phase 4K) ---
  async listNotifications(params?: {
    category?: 'all' | 'chat' | 'social' | 'food' | 'shopping' | 'system';
    unreadOnly?: boolean;
    page?: number;
    limit?: number;
  }): Promise<NotificationListResponse> {
    const query = new URLSearchParams();
    if (params?.category && params.category !== 'all') query.append('category', params.category);
    if (params?.unreadOnly) query.append('unread_only', 'true');
    if (params?.page) query.append('page', params.page.toString());
    if (params?.limit) query.append('limit', params.limit.toString());

    const qs = query.toString();
    const url = `/notifications${qs ? `?${qs}` : ''}`;
    return this.request<NotificationListResponse>(url);
  }

  async getUnreadNotificationsCount(): Promise<number> {
    const res = await this.request<NotificationUnreadCountResponse>('/notifications/unread-count');
    return res.unread_count || 0;
  }

  async markNotificationRead(notificationId: string): Promise<NotificationResponse> {
    return this.request<NotificationResponse>(`/notifications/${notificationId}/read`, {
      method: 'PATCH',
    });
  }

  async markAllNotificationsRead(): Promise<NotificationUnreadCountResponse> {
    return this.request<NotificationUnreadCountResponse>('/notifications/mark-all-read', {
      method: 'POST',
    });
  }

  async deleteNotification(notificationId: string): Promise<{ status: string; notification_id: string }> {
    return this.request<{ status: string; notification_id: string }>(`/notifications/${notificationId}`, {
      method: 'DELETE',
    });
  }

  // --- UPI, Banking & Payments Methods (Phase 4J) ---
  async listBankAccounts(): Promise<BankAccountResponse[]> {
    return this.request<BankAccountResponse[]>('/payments/accounts');
  }

  async linkBankAccount(payload: BankAccountCreatePayload): Promise<BankAccountResponse> {
    return this.request<BankAccountResponse>('/payments/accounts', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async checkAccountBalance(accountId: string): Promise<BankAccountResponse> {
    return this.request<BankAccountResponse>(`/payments/accounts/${accountId}/balance`);
  }

  async listRuPayCards(): Promise<RuPayCardResponse[]> {
    return this.request<RuPayCardResponse[]>('/payments/rupay-cards');
  }

  async linkRuPayCard(payload: RuPayCardCreatePayload): Promise<RuPayCardResponse> {
    return this.request<RuPayCardResponse>('/payments/rupay-cards', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async verifyVpa(vpa: string): Promise<{ is_valid: boolean; vpa: string; recipient_name: string; provider_verified: boolean }> {
    return this.request<{ is_valid: boolean; vpa: string; recipient_name: string; provider_verified: boolean }>(
      `/payments/vpa/verify?vpa=${encodeURIComponent(vpa)}`
    );
  }

  async sendPayment(payload: SendPaymentPayload): Promise<PaymentTransactionResponse> {
    return this.request<PaymentTransactionResponse>('/payments/send', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async listPaymentTransactions(params?: {
    category?: 'all' | 'p2p' | 'p2m' | 'bill' | 'recharge';
    status?: 'all' | 'success' | 'pending' | 'failed' | 'reversed';
    limit?: number;
  }): Promise<PaymentTransactionResponse[]> {
    const query = new URLSearchParams();
    if (params?.category && params.category !== 'all') query.append('category', params.category);
    if (params?.status && params.status !== 'all') query.append('status', params.status);
    if (params?.limit) query.append('limit', params.limit.toString());

    const qs = query.toString();
    const url = `/payments/transactions${qs ? `?${qs}` : ''}`;
    return this.request<PaymentTransactionResponse[]>(url);
  }

  async listBillers(category?: string): Promise<BillerResponse[]> {
    let url = '/payments/billers';
    if (category) url += `?category=${encodeURIComponent(category)}`;
    return this.request<BillerResponse[]>(url);
  }

  async fetchBill(payload: { category: string; biller_id: string; customer_identifier: string }): Promise<BillDetailResponse> {
    return this.request<BillDetailResponse>('/payments/billers/fetch', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}


export const apiClient = new ApiClient(API_BASE_URL);
