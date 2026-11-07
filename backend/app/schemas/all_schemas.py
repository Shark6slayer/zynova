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

class UserProfileResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    is_active: bool = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str
    user: Optional[UserProfileResponse] = None

class TokenRefreshRequest(BaseModel):
    refresh_token: str

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
    text: Optional[str] = Field(None, max_length=2000)
    media_url: Optional[str] = Field(None, max_length=500)
    media_type: Optional[str] = Field("text", pattern="^(text|image|video|audio|voice|document)$")
    file_name: Optional[str] = Field(None, max_length=255)
    file_size_bytes: Optional[int] = None
    reply_to_id: Optional[str] = None
    forward_from_id: Optional[str] = None
    client_message_id: Optional[str] = None

class ChatMessageUpdate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)

class MessageReactionPayload(BaseModel):
    emoji: str = Field(..., min_length=1, max_length=16)

class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_username: str
    sender_full_name: str
    sender_avatar: Optional[str] = None
    text: str
    media_url: Optional[str] = None
    media_type: str = "text"
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    reply_to_id: Optional[str] = None
    forward_from_id: Optional[str] = None
    client_message_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_edited: bool = False
    is_deleted: bool = False
    is_pinned: bool = False
    delivery_status: str = "sent"  # "sent", "delivered", "read"
    delivered_to: List[str] = []
    read_by: List[str] = []
    reactions: Dict[str, str] = {}  # user_id -> emoji

class LastMessageSummary(BaseModel):
    id: str
    sender_id: str
    text: str
    media_type: Optional[str] = "text"
    delivery_status: Optional[str] = "sent"
    created_at: datetime

class ChatConversationResponse(BaseModel):
    id: str
    type: str = "direct"  # "direct", "group"
    name: Optional[str] = None
    description: Optional[str] = None
    picture_url: Optional[str] = None
    participants: List[str]
    participant_meta: dict[str, UserPublicSummary]
    admin_ids: List[str] = []
    community_id: Optional[str] = None
    is_archived: bool = False
    is_locked: bool = False
    pinned_message_id: Optional[str] = None
    last_message: Optional[LastMessageSummary] = None
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime

# Connect Extended Schemas (Phase 26)
class GroupCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    picture_url: Optional[str] = Field(None, max_length=500)
    participant_ids: List[str] = Field(..., min_length=1)
    community_id: Optional[str] = None

class GroupUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    picture_url: Optional[str] = Field(None, max_length=500)

class GroupMemberActionPayload(BaseModel):
    user_id: str

class CommunityCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    picture_url: Optional[str] = Field(None, max_length=500)
    group_ids: Optional[List[str]] = None

class CommunityResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    picture_url: Optional[str] = None
    creator_id: str
    admin_ids: List[str]
    group_ids: List[str]
    announcement_group_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ConnectStatusCreatePayload(BaseModel):
    media_url: Optional[str] = Field(None, max_length=500)
    media_type: str = Field("text", pattern="^(text|image|video)$")
    caption: Optional[str] = Field(None, max_length=500)
    bg_color: Optional[str] = Field(None, max_length=30)
    font_style: Optional[str] = Field(None, max_length=30)
    privacy: str = Field("contacts", pattern="^(contacts|close_friends|public)$")

class ConnectStatusResponse(BaseModel):
    id: str
    user_id: str
    user_username: str
    user_full_name: str
    user_avatar: Optional[str] = None
    media_url: Optional[str] = None
    media_type: str = "text"
    caption: Optional[str] = None
    bg_color: Optional[str] = None
    font_style: Optional[str] = None
    privacy: str = "contacts"
    viewers_count: int = 0
    created_at: datetime
    expires_at: datetime
    has_viewed: bool = False

class LockChatPayload(BaseModel):
    pin: str = Field(..., min_length=4, max_length=32)

class UnlockChatPayload(BaseModel):
    pin: str = Field(..., min_length=4, max_length=32)

class CallInitiatePayload(BaseModel):
    conversation_id: str
    call_type: str = Field("voice", pattern="^(voice|video)$")
    recipient_id: Optional[str] = None  # None for group calls

class CallSignalPayload(BaseModel):
    call_id: str
    signal_type: str = Field(..., pattern="^(offer|answer|candidate|reject|end|mute)$")
    payload: Dict[str, Any]

class CallHistoryResponse(BaseModel):
    id: str
    conversation_id: str
    caller_id: str
    caller_name: str
    caller_avatar: Optional[str] = None
    participants: List[str]
    call_type: str  # "voice" or "video"
    status: str     # "missed", "completed", "rejected", "busy"
    duration_seconds: int = 0
    created_at: datetime
    ended_at: Optional[datetime] = None

class E2EEPrekeyBundlePayload(BaseModel):
    identity_key_pub: str
    signed_prekey_pub: str
    signed_prekey_sig: Optional[str] = None
    one_time_prekeys: List[Dict[str, Any]]

class E2EEPrekeyBundleResponse(BaseModel):
    user_id: str
    device_id: Optional[str] = None
    identity_key_pub: str
    signed_prekey_pub: str
    signed_prekey_sig: Optional[str] = None
    one_time_prekey: Optional[Dict[str, Any]] = None

# Social Network Schemas
class SocialProfileResponse(BaseModel):
    id: str
    username: str
    full_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    website: Optional[str] = None
    is_private: bool = False
    is_verified: bool = False
    created_at: datetime
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_following: bool = False
    has_pending_follow_request: bool = False
    is_self: bool = False

class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    image_url: Optional[str] = Field(None, max_length=500)
    media_url: Optional[str] = Field(None, max_length=500)
    media_type: Optional[str] = Field("image", pattern="^(image|video)$")
    media_assets: Optional[List[str]] = Field(None, max_length=10) # Multi-image/carousel asset IDs
    tags: Optional[List[str]] = Field(None, max_length=30)
    location: Optional[str] = Field(None, max_length=100)

class PostUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    image_url: Optional[str] = Field(None, max_length=500)
    media_url: Optional[str] = Field(None, max_length=500)
    media_type: Optional[str] = Field(None, pattern="^(image|video)$")
    tags: Optional[List[str]] = Field(None, max_length=30)
    location: Optional[str] = Field(None, max_length=100)

class PostResponse(BaseModel):
    id: str
    author_id: str
    author_username: str
    author_full_name: str
    author_avatar: Optional[str] = None
    author_is_verified: bool = False
    content: str
    image_url: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = "image"
    media_assets: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    location: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_edited: bool = False
    likes_count: int = 0
    comments_count: int = 0
    is_liked: bool = False
    is_bookmarked: bool = False
    is_owner: bool = False

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    parent_comment_id: Optional[str] = None

class CommentResponse(BaseModel):
    id: str
    post_id: str
    author_id: str
    author_username: str
    author_full_name: str
    author_avatar: Optional[str] = None
    content: str
    parent_comment_id: Optional[str] = None
    created_at: datetime
    is_owner: bool = False

class StoryCreate(BaseModel):
    media_url: str = Field(..., min_length=1, max_length=500)
    media_type: str = Field("image", pattern="^(image|video)$")
    caption: Optional[str] = Field(None, max_length=280)
    is_close_friends_only: bool = False

class StoryReactionCreate(BaseModel):
    reaction: str = Field(..., min_length=1, max_length=10) # Emoji reaction

class StoryItemResponse(BaseModel):
    id: str
    media_url: str
    media_type: str = "image"
    caption: Optional[str] = None
    is_close_friends_only: bool = False
    created_at: datetime
    expires_at: datetime
    views_count: int = 0
    is_seen: bool = False

class StoryGroupResponse(BaseModel):
    author_id: str
    author_username: str
    author_full_name: str
    author_avatar: Optional[str] = None
    has_unseen: bool = False
    stories: List[StoryItemResponse]

class StoryHighlightCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=30)
    cover_image_url: Optional[str] = None
    story_ids: List[str] = Field(..., min_length=1)

class StoryHighlightResponse(BaseModel):
    id: str
    author_id: str
    title: str
    cover_image_url: Optional[str] = None
    stories_count: int
    created_at: datetime

class SocialNoteCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=60)
    music_title: Optional[str] = Field(None, max_length=60)
    music_artist: Optional[str] = Field(None, max_length=60)

class SocialNoteResponse(BaseModel):
    id: str
    user_id: str
    username: str
    full_name: str
    avatar_url: Optional[str] = None
    text: str
    music_title: Optional[str] = None
    music_artist: Optional[str] = None
    created_at: datetime
    expires_at: datetime

class VerificationApplicationCreate(BaseModel):
    full_legal_name: str = Field(..., min_length=2, max_length=100)
    document_type: str = Field(..., pattern="^(passport|national_id|drivers_license|business_doc)$")
    evidence_urls: List[str] = Field(..., min_length=1, max_length=5)
    category: str = Field(..., pattern="^(news_media|sports|entertainment|creator|business|government)$")
    reason: str = Field(..., min_length=10, max_length=1000)

class VerificationApplicationResponse(BaseModel):
    id: str
    user_id: str
    full_legal_name: str
    document_type: str
    category: str
    status: str # "pending", "approved", "rejected"
    reviewer_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

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
    result_type: str  # "person", "post", "reel", "video", "short", "channel", "community", "hashtag"
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

class SearchHistoryItem(BaseModel):
    id: str
    query: str
    category: str
    created_at: datetime

# Platform Share Schemas (Phase 28 Cross-Platform Sharing)
class ShareMetadataResponse(BaseModel):
    share_url: str
    content_type: str  # "post", "reel", "story", "video", "short", "channel", "profile", "community"
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    deep_link: str
    is_public: bool
    author_name: Optional[str] = None

# Unified Notification Preferences (Phase 28)
class NotificationPreferencesModel(BaseModel):
    social_likes: bool = True
    social_comments: bool = True
    social_follows: bool = True
    social_mentions: bool = True
    connect_messages: bool = True
    connect_group_activity: bool = True
    connect_calls: bool = True
    video_subscriptions: bool = True
    video_uploads: bool = True
    video_comments: bool = True
    security_alerts: bool = True
    preview_privacy: str = "full"  # "full", "sender_only", "hidden"


# Video Platform Schemas (Phase 27 Extended)
class ChannelCreatePayload(BaseModel):
    handle: str = Field(..., min_length=3, max_length=30, pattern="^[a-zA-Z0-9_]+$")
    name: str = Field(..., min_length=2, max_length=60)
    description: Optional[str] = Field(None, max_length=1000)
    avatar_url: Optional[str] = Field(None, max_length=500)
    banner_url: Optional[str] = Field(None, max_length=500)

class ChannelUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=60)
    description: Optional[str] = Field(None, max_length=1000)
    avatar_url: Optional[str] = Field(None, max_length=500)
    banner_url: Optional[str] = Field(None, max_length=500)

class ChannelResponse(BaseModel):
    id: str
    owner_id: str
    handle: str
    name: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    subscriber_count: int = 0
    video_count: int = 0
    shorts_count: int = 0
    is_subscribed: bool = False
    is_owner: bool = False
    created_at: datetime
    updated_at: datetime

class VideoCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    thumbnail_url: Optional[str] = Field(None, max_length=500)
    visibility: str = Field("public", pattern="^(public|unlisted|private)$")
    category: str = Field("General", max_length=50)
    channel_id: Optional[str] = None
    is_short: bool = False
    audio_title: Optional[str] = Field(None, max_length=100)
    audio_artist: Optional[str] = Field(None, max_length=100)

class VideoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    thumbnail_url: Optional[str] = Field(None, max_length=500)
    visibility: Optional[str] = Field(None, pattern="^(public|unlisted|private)$")
    category: Optional[str] = Field(None, max_length=50)

class VideoCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    parent_comment_id: Optional[str] = None

class VideoCommentResponse(BaseModel):
    id: str
    video_id: str
    author_id: str
    author_username: str
    author_full_name: str
    author_avatar: Optional[str] = None
    content: str
    parent_comment_id: Optional[str] = None
    created_at: datetime
    is_pinned: bool = False
    is_owner: bool = False

class VideoResponse(BaseModel):
    id: str
    owner_id: str
    owner_username: str
    owner_full_name: str
    owner_avatar: Optional[str] = None
    channel_id: Optional[str] = None
    channel_handle: Optional[str] = None
    channel_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    storage_key: str
    mime_type: str
    file_size_bytes: int
    duration_seconds: Optional[float] = None
    thumbnail_url: Optional[str] = None
    visibility: str = "public"  # public, unlisted, private
    status: str = "published"    # draft, processing, published
    category: str = "General"
    is_short: bool = False
    aspect_ratio: Optional[str] = "16:9"
    audio_title: Optional[str] = None
    audio_artist: Optional[str] = None
    view_count: int = 0
    likes_count: int = 0
    dislikes_count: int = 0
    comments_count: int = 0
    is_liked: bool = False
    is_saved: bool = False
    is_owner: bool = False
    created_at: datetime
    updated_at: datetime

class PlaylistCreatePayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    visibility: str = Field("public", pattern="^(public|unlisted|private)$")
    video_ids: Optional[List[str]] = None

class PlaylistResponse(BaseModel):
    id: str
    owner_id: str
    owner_username: str
    title: str
    description: Optional[str] = None
    visibility: str
    video_ids: List[str]
    videos_count: int = 0
    created_at: datetime
    updated_at: datetime

class WatchProgressPayload(BaseModel):
    playback_position_seconds: float = Field(..., ge=0)
    duration_seconds: float = Field(..., ge=0)
    completed: bool = False

class WatchHistoryResponse(BaseModel):
    video: VideoResponse
    playback_position_seconds: float
    last_watched_at: datetime
    completed: bool

class CreatorAnalyticsResponse(BaseModel):
    channel_id: str
    total_views: int
    total_watch_time_seconds: float
    average_view_duration_seconds: float
    total_subscribers: int
    total_videos: int
    total_shorts: int
    total_likes: int
    total_comments: int
    top_videos: List[Dict[str, Any]]

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

# Phase 12: Device Identity & Verifiable Security Action Schemas
class SessionInfoResponse(BaseModel):
    id: str
    user_id: str
    device_label: str
    client_ip_masked: str
    user_agent_summary: str
    created_at: datetime
    last_activity: datetime
    is_current: bool = False

class DeviceRegisterPayload(BaseModel):
    device_label: str = Field(..., min_length=2, max_length=60)
    public_key_hex: str = Field(..., pattern="^[a-fA-F0-9]{64}$", description="32-byte Ed25519 public key in hex")
    platform: str = Field("web", pattern="^(android|ios|web|desktop)$")
    hardware_backed: bool = False

class DeviceResponse(BaseModel):
    id: str
    user_id: str
    device_label: str
    public_key_hex: str
    platform: str
    hardware_backed: bool
    status: str = "active"  # "active", "revoked"
    registered_at: datetime
    last_used_at: Optional[datetime] = None

class ChallengeRequestPayload(BaseModel):
    action_type: str = Field(..., pattern="^(password_change|revoke_all_sessions|admin_role_change|seller_approval|account_recovery)$")
    resource_id: Optional[str] = None

class ChallengeResponse(BaseModel):
    challenge_id: str
    nonce: str
    action_type: str
    resource_id: Optional[str] = None
    expires_at: datetime
    issued_at: datetime

class ChallengeVerifyPayload(BaseModel):
    challenge_id: str
    device_id: str
    signature_hex: str = Field(..., description="Ed25519 signature over canonical challenge payload")
    password: Optional[str] = Field(None, description="Recent password reauthentication (if required)")

class SensitiveActionResponse(BaseModel):
    status: str = "verified"
    action_type: str
    executed_at: datetime
    audit_sequence: Optional[int] = None
