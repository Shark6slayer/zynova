import time
from fastapi import Request, HTTPException, status
from collections import defaultdict

class InMemoryRateLimiter:
    def __init__(self, requests_limit: int = 10, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def check(self, key: str):
        now = time.time()
        # Clean older requests outside the window
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window_seconds]
        if len(self.requests[key]) >= self.requests_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication attempts. Please try again later."
            )
        self.requests[key].append(now)

# Limit to 10 requests per minute per client IP for auth endpoints
auth_rate_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60)

async def check_auth_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    auth_rate_limiter.check(client_ip)

# Limit to 60 messages per minute per user for chat sending
chat_rate_limiter = InMemoryRateLimiter(requests_limit=60, window_seconds=60)

def check_chat_user_rate_limit(user_id: str):
    chat_rate_limiter.check(user_id)

# Limit to 30 social posts per hour (or 10 per minute) per user
social_post_rate_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60)

def check_social_post_rate_limit(user_id: str):
    social_post_rate_limiter.check(user_id)

# Limit to 30 comments per minute per user
comment_rate_limiter = InMemoryRateLimiter(requests_limit=30, window_seconds=60)

def check_comment_rate_limit(user_id: str):
    comment_rate_limiter.check(user_id)

# Limit to 10 reports per 10 minutes per user
report_rate_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=600)

def check_report_rate_limit(user_id: str):
    report_rate_limiter.check(user_id)

# Limit to 60 searches per minute per IP / client
search_rate_limiter = InMemoryRateLimiter(requests_limit=60, window_seconds=60)

async def check_search_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    search_rate_limiter.check(client_ip)

# Limit to 10 video uploads per hour (or 5 per 10 minutes) per user
video_upload_rate_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=600)

def check_video_upload_rate_limit(user_id: str):
    video_upload_rate_limiter.check(user_id)

# Limit to 30 video comments per minute per user
video_comment_rate_limiter = InMemoryRateLimiter(requests_limit=30, window_seconds=60)

def check_video_comment_rate_limit(user_id: str):
    video_comment_rate_limiter.check(user_id)

# Limit to 10 orders per 5 minutes per user
food_order_rate_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=300)

def check_food_order_rate_limit(user_id: str):
    food_order_rate_limiter.check(user_id)

# Limit to 10 shopping orders per 5 minutes per user
shopping_order_rate_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=300)

def check_shopping_order_rate_limit(user_id: str):
    shopping_order_rate_limiter.check(user_id)

# Limit to 15 payment transactions per minute per user
payment_rate_limiter = InMemoryRateLimiter(requests_limit=15, window_seconds=60)

def check_payment_rate_limit(user_id: str):
    payment_rate_limiter.check(user_id)

# Limit to 10 balance enquiries per minute per user
balance_enquiry_rate_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60)

def check_balance_enquiry_rate_limit(user_id: str):
    balance_enquiry_rate_limiter.check(user_id)
