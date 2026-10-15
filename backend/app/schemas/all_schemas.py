from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=30)
    full_name: str = Field(..., min_length=2, max_length=60)
    password: str = Field(..., min_length=8, max_length=128)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class UserProfileResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    is_active: bool = True

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=60)
    avatar_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = Field(None, max_length=280)

class AccountDeleteRequest(BaseModel):
    password: str = Field(..., min_length=1)


SUPPORTED_LANGUAGES = {
    "en", "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks",
    "kok", "mai", "ml", "mni", "mr", "ne", "or", "pa",
    "sa", "sat", "sd", "ta", "te", "ur"
}

class PreferencesModel(BaseModel):
    theme: str = "midnight-glass"
    appearanceMode: str = "system"
    language: str = "en"
    accentColor: str = "#8b5cf6"
    reducedMotion: bool = False
    fontSize: str = "normal"
    compactSidebar: bool = False
    currency: str = "INR"
    aiMemoryEnabled: bool = True
    pinnedModules: List[str] = ["home", "ai-assistant", "search", "chat", "food", "payments"]
    hiddenModules: List[str] = []
    onboardingCompleted: bool = True

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        clean = (v or "").strip().lower()
        if clean not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language code '{v}'. Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}")
        return clean

class ConversationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    model: str = "SUPER Multilingual (Indic-v2)"

class MessageItem(BaseModel):
    id: str
    sender: str
    text: str
    timestamp: str

class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    model: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageItem] = []

class NotificationResponse(BaseModel):
    id: str
    user_id: str
    category: str  # "chat", "social", "food", "shopping", "system"
    event_type: str  # e.g. "chat_message", "social_like", "social_comment", "social_follow", "food_order_status", "shopping_order_status"
    title: str
    desc: str
    time: str
    read: bool
    read_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

class NotificationListResponse(BaseModel):
    total: int
    unread_count: int
    page: int
    limit: int
    has_more: bool
    notifications: List[NotificationResponse]

class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


# P2P Real-time Chat Schemas
class UserPublicSummary(BaseModel):
    id: str
    username: str
    full_name: str
    avatar_url: Optional[str] = None

class ChatConversationCreate(BaseModel):
    recipient_id: str

class ChatMessageCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)

class ChatMessageUpdate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)

class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_username: str
    sender_full_name: str
    sender_avatar: Optional[str] = None
    text: str
    created_at: datetime
    updated_at: datetime
    is_edited: bool = False
    is_deleted: bool = False
    read_by: List[str] = []

class LastMessageSummary(BaseModel):
    id: str
    sender_id: str
    text: str
    created_at: datetime

class ChatConversationResponse(BaseModel):
    id: str
    type: str = "direct"
    participants: List[str]
    participant_meta: dict[str, UserPublicSummary]
    last_message: Optional[LastMessageSummary] = None
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime

# Social Network Schemas
class SocialProfileResponse(BaseModel):
    id: str
    username: str
    full_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_following: bool = False
    is_self: bool = False

class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    image_url: Optional[str] = Field(None, max_length=500)
    media_url: Optional[str] = Field(None, max_length=500)
    media_type: Optional[str] = Field("image", pattern="^(image|video)$")

class PostUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    image_url: Optional[str] = Field(None, max_length=500)
    media_url: Optional[str] = Field(None, max_length=500)
    media_type: Optional[str] = Field(None, pattern="^(image|video)$")

class PostResponse(BaseModel):
    id: str
    author_id: str
    author_username: str
    author_full_name: str
    author_avatar: Optional[str] = None
    content: str
    image_url: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = "image"
    created_at: datetime
    updated_at: datetime
    is_edited: bool = False
    likes_count: int = 0
    comments_count: int = 0
    is_liked: bool = False
    is_owner: bool = False

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)

class CommentResponse(BaseModel):
    id: str
    post_id: str
    author_id: str
    author_username: str
    author_full_name: str
    author_avatar: Optional[str] = None
    content: str
    created_at: datetime
    is_owner: bool = False

class ReportCreate(BaseModel):
    target_type: str = Field(..., pattern="^(post|user|comment)$")
    target_id: str
    reason: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class ReportResponse(BaseModel):
    id: str
    reporter_id: str
    target_type: str
    target_id: str
    reason: str
    status: str = "pending"
    created_at: datetime

# Platform Search Engine Schemas
class SearchResultItem(BaseModel):
    id: str
    result_type: str  # "person" or "post"
    title: str
    subtitle: Optional[str] = None
    excerpt: str
    avatar_url: Optional[str] = None
    image_url: Optional[str] = None
    timestamp: Optional[datetime] = None
    navigation_target: str
    metadata: Optional[Dict[str, Any]] = None

class SearchResponse(BaseModel):
    query: str
    filter_type: str
    total_count: int
    has_more: bool
    results: List[SearchResultItem]

# Video Platform Schemas
class VideoCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    thumbnail_url: Optional[str] = Field(None, max_length=500)
    visibility: str = Field("public", pattern="^(public|private)$")

class VideoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    thumbnail_url: Optional[str] = Field(None, max_length=500)
    visibility: Optional[str] = Field(None, pattern="^(public|private)$")

class VideoCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)

class VideoCommentResponse(BaseModel):
    id: str
    video_id: str
    author_id: str
    author_username: str
    author_full_name: str
    author_avatar: Optional[str] = None
    content: str
    created_at: datetime
    is_owner: bool = False

class VideoResponse(BaseModel):
    id: str
    owner_id: str
    owner_username: str
    owner_full_name: str
    owner_avatar: Optional[str] = None
    title: str
    description: Optional[str] = None
    storage_key: str
    mime_type: str
    file_size_bytes: int
    duration_seconds: Optional[float] = None
    thumbnail_url: Optional[str] = None
    visibility: str
    status: str
    view_count: int = 0
    likes_count: int = 0
    comments_count: int = 0
    is_liked: bool = False
    is_owner: bool = False
    created_at: datetime
    updated_at: datetime

# Food Discovery and Ordering Schemas
class MenuItemResponse(BaseModel):
    id: str
    restaurant_id: str
    name: str
    description: Optional[str] = None
    price_paise: int
    price_inr: float
    is_veg: bool = True
    is_available: bool = True
    category: str
    image_url: Optional[str] = None

class RestaurantResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    service_area: str
    address: str
    cuisine: str
    rating: float
    time_mins: int
    price_for_two_inr: int
    is_veg: bool
    image_url: Optional[str] = None
    is_open: bool = True
    owner_id: Optional[str] = None
    menu: Optional[List[MenuItemResponse]] = None

class OrderItemInput(BaseModel):
    item_id: str
    quantity: int = Field(..., ge=1, le=20)

class CreateOrderPayload(BaseModel):
    restaurant_id: str
    items: List[OrderItemInput] = Field(..., min_length=1)
    delivery_address: str = Field(..., min_length=5, max_length=300)
    payment_method: str = Field("cod", pattern="^(cod|test_mode_upi|test_mode_card)$")

class OrderItemSnapshot(BaseModel):
    item_id: str
    name: str
    unit_price_paise: int
    quantity: int
    total_price_paise: int

class OrderResponse(BaseModel):
    id: str
    customer_id: str
    customer_name: str
    customer_email: str
    restaurant_id: str
    restaurant_name: str
    items: List[OrderItemSnapshot]
    item_count: int
    delivery_address: str
    subtotal_paise: int
    delivery_fee_paise: int
    taxes_paise: int
    total_paise: int
    total_inr: float
    payment_method: str
    payment_status: str  # "pending", "simulated_paid", "failed"
    order_status: str    # "placed", "confirmed", "preparing", "out_for_delivery", "delivered", "cancelled"
    created_at: datetime
    updated_at: datetime

# Shopping & E-Commerce Schemas (Phase 4I)
class ProductResponse(BaseModel):
    id: str
    name: str
    brand: str
    sku: str
    category: str
    description: str
    price_paise: int
    price_inr: float
    mrp_paise: Optional[int] = None
    mrp_inr: Optional[float] = None
    rating: float = 4.5
    reviews_count: int = 0
    stock: int
    is_available: bool = True
    is_published: bool = True
    is_seed_data: bool = True
    seller_id: Optional[str] = None
    seller_name: Optional[str] = None
    images: List[str]
    features: List[str] = []
    created_at: datetime
    updated_at: datetime

class ShoppingCartItemInput(BaseModel):
    product_id: str
    quantity: int = Field(..., ge=1, le=10)

class ShoppingOrderItemSnapshot(BaseModel):
    product_id: str
    name: str
    sku: str
    brand: str
    unit_price_paise: int
    quantity: int
    total_price_paise: int
    image_url: Optional[str] = None
    seller_id: Optional[str] = None

class CreateShoppingOrderPayload(BaseModel):
    items: List[ShoppingCartItemInput] = Field(..., min_length=1)
    shipping_full_name: str = Field(..., min_length=2, max_length=100)
    shipping_phone: str = Field(..., min_length=10, max_length=15)
    shipping_address: str = Field(..., min_length=5, max_length=300)
    shipping_city: str = Field(..., min_length=2, max_length=100)
    shipping_postal_code: str = Field(..., min_length=4, max_length=10)
    payment_method: str = Field("cod", pattern="^(cod|test_mode_upi|test_mode_card)$")
    idempotency_key: Optional[str] = Field(None, max_length=100)

class ShoppingOrderResponse(BaseModel):
    id: str
    customer_id: str
    customer_name: str
    customer_email: str
    shipping_full_name: str
    shipping_phone: str
    shipping_address: str
    shipping_city: str
    shipping_postal_code: str
    items: List[ShoppingOrderItemSnapshot]
    total_items_count: int
    subtotal_paise: int
    shipping_paise: int
    taxes_paise: int
    discount_paise: int = 0
    total_paise: int
    total_inr: float
    payment_method: str
    payment_status: str  # "pending", "simulated_paid", "failed"
    order_status: str    # "placed", "confirmed", "processing", "shipped", "delivered", "cancelled"
    idempotency_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# Seller Operations Schemas (Phase 4)
class SellerRegisterPayload(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=120)
    business_category: str = Field(..., min_length=2, max_length=50)
    contact_phone: str = Field(..., min_length=10, max_length=15)
    business_address: str = Field(..., min_length=5, max_length=300)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    pincode: str = Field(..., min_length=4, max_length=10)
    gstin_or_pan: Optional[str] = Field(None, max_length=25)

class SellerResponse(BaseModel):
    id: str
    user_id: str
    business_name: str
    business_category: str
    contact_phone: str
    business_address: str
    city: str
    state: str
    pincode: str
    gstin_or_pan: Optional[str] = None
    status: str  # "pending", "approved", "rejected", "suspended"
    created_at: datetime
    updated_at: datetime

class SellerDashboardResponse(BaseModel):
    seller_id: str
    business_name: str
    status: str
    active_products: int
    low_stock_products: int
    pending_orders: int
    fulfilled_orders: int
    gross_sales_paise: int
    gross_sales_inr: float

class ProductCreatePayload(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    brand: str = Field(..., min_length=1, max_length=80)
    category: str = Field(..., min_length=2, max_length=50)
    description: str = Field(..., min_length=5, max_length=2000)
    price_paise: int = Field(..., ge=100, le=100000000)  # Min ₹1, Max ₹10,00,000
    mrp_paise: Optional[int] = Field(None, ge=100, le=100000000)
    stock: int = Field(..., ge=0, le=100000)
    sku: Optional[str] = Field(None, max_length=50)
    images: List[str] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    is_available: bool = True
    is_published: bool = True

class ProductUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    brand: Optional[str] = Field(None, min_length=1, max_length=80)
    category: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = Field(None, min_length=5, max_length=2000)
    price_paise: Optional[int] = Field(None, ge=100, le=100000000)
    mrp_paise: Optional[int] = Field(None, ge=100, le=100000000)
    stock: Optional[int] = Field(None, ge=0, le=100000)
    images: Optional[List[str]] = None
    features: Optional[List[str]] = None
    is_available: Optional[bool] = None
    is_published: Optional[bool] = None

class SellerOrderStatusUpdatePayload(BaseModel):
    status: str = Field(..., pattern="^(processing|shipped|delivered)$")

# Restaurant Operations Schemas (Phase 4)
class RestaurantRegisterPayload(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    service_area: str = Field(..., min_length=2, max_length=100)
    address: str = Field(..., min_length=5, max_length=300)
    cuisine: str = Field(..., min_length=2, max_length=100)
    price_for_two_inr: int = Field(..., ge=50, le=20000)
    is_veg: bool = False
    image_url: Optional[str] = None
    is_open: bool = True

class RestaurantUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    service_area: Optional[str] = Field(None, min_length=2, max_length=100)
    address: Optional[str] = Field(None, min_length=5, max_length=300)
    cuisine: Optional[str] = Field(None, min_length=2, max_length=100)
    price_for_two_inr: Optional[int] = Field(None, ge=50, le=20000)
    is_veg: Optional[bool] = None
    image_url: Optional[str] = None
    is_open: Optional[bool] = None

class MenuItemCreatePayload(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    category: str = Field(..., min_length=2, max_length=50)
    price_paise: int = Field(..., ge=100, le=1000000)  # ₹1 to ₹10,000
    description: Optional[str] = Field(None, max_length=500)
    is_veg: bool = True
    is_available: bool = True
    image_url: Optional[str] = None

class MenuItemUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    category: Optional[str] = Field(None, min_length=2, max_length=50)
    price_paise: Optional[int] = Field(None, ge=100, le=1000000)
    description: Optional[str] = Field(None, max_length=500)
    is_veg: Optional[bool] = None
    is_available: Optional[bool] = None
    image_url: Optional[str] = None

class FoodOrderStatusUpdatePayload(BaseModel):
    status: str = Field(..., pattern="^(confirmed|preparing|out_for_delivery|delivered|cancelled)$")

# UPI, Banking & Bill Payments Schemas (Phase 4J)
class BankAccountCreate(BaseModel):
    bank_name: str = Field(..., min_length=2, max_length=100)
    ifsc_code: str = Field(..., min_length=11, max_length=11)
    account_number: str = Field(..., min_length=6, max_length=30)
    account_type: str = Field("savings", pattern="^(savings|current)$")
    nickname: Optional[str] = Field(None, max_length=50)

class BankAccountResponse(BaseModel):
    id: str
    user_id: str
    bank_name: str
    ifsc_code: str
    masked_account_number: str
    account_type: str
    nickname: Optional[str] = None
    is_default: bool = False
    balance_paise: Optional[int] = None
    balance_inr: Optional[float] = None
    last_balance_enquiry: Optional[datetime] = None
    provider_status: str = "connected"
    is_seed_account: bool = False
    created_at: datetime

class RuPayCardCreate(BaseModel):
    issuing_bank: str = Field(..., min_length=2, max_length=100)
    last_four_digits: str = Field(..., min_length=4, max_length=4)
    expiry_month: int = Field(..., ge=1, le=12)
    expiry_year: int = Field(..., ge=2024, le=2040)
    nickname: Optional[str] = Field(None, max_length=50)

class RuPayCardResponse(BaseModel):
    id: str
    user_id: str
    issuing_bank: str
    last_four_digits: str
    nickname: Optional[str] = None
    network: str = "RuPay"
    is_credit_on_upi_eligible: bool = True
    provider_status: str = "connected"
    created_at: datetime

class SendPaymentPayload(BaseModel):
    recipient_type: str = Field(..., pattern="^(upi_id|phone|contact|merchant)$")
    recipient_identifier: str = Field(..., min_length=3, max_length=100)
    recipient_name: Optional[str] = Field(None, max_length=100)
    amount_paise: int = Field(..., ge=100, le=10000000)  # Min ₹1, Max ₹1,00,000 per UPI limit
    source_type: str = Field("bank_account", pattern="^(bank_account|rupay_credit_card)$")
    source_id: str = Field(..., min_length=1, max_length=50)
    note: Optional[str] = Field(None, max_length=200)
    idempotency_key: str = Field(..., min_length=5, max_length=100)

class PaymentTransactionResponse(BaseModel):
    id: str
    user_id: str
    transaction_ref: str
    npci_ref: Optional[str] = None
    recipient_type: str
    recipient_identifier: str
    recipient_name: str
    amount_paise: int
    amount_inr: float
    fee_paise: int = 0
    source_type: str
    source_id: str
    source_title: str
    category: str  # "p2p", "p2m", "bill", "recharge"
    status: str    # "success", "pending", "failed", "reversed"
    failure_reason: Optional[str] = None
    note: Optional[str] = None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime

class BillFetchPayload(BaseModel):
    category: str = Field(..., pattern="^(mobile_prepaid|mobile_postpaid|electricity|water|gas|dth|broadband|fastag)$")
    biller_id: str = Field(..., min_length=2, max_length=100)
    customer_identifier: str = Field(..., min_length=3, max_length=100)

class BillerResponse(BaseModel):
    id: str
    category: str
    name: str
    operator_code: str
    icon_name: str
    sample_identifier_label: str

class BillDetailResponse(BaseModel):
    biller_id: str
    biller_name: str
    category: str
    customer_identifier: str
    customer_name: str
    bill_number: str
    bill_date: str
    due_date: str
    amount_paise: int
    amount_inr: float
    is_test_fixture: bool = True

