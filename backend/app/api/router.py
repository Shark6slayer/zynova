from fastapi import APIRouter
from app.api.routes import health, auth, users, preferences, conversations, notifications, chat, social, search, videos, food, shopping, payments, ledger, devices

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(preferences.router)
api_router.include_router(conversations.router)
api_router.include_router(notifications.router)
api_router.include_router(chat.router)
api_router.include_router(social.router)
api_router.include_router(search.router)
api_router.include_router(videos.router)
api_router.include_router(food.router)
api_router.include_router(shopping.router)
api_router.include_router(payments.router)
api_router.include_router(ledger.router)
api_router.include_router(devices.router)




