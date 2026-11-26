from fastapi import APIRouter
from app.api.routes import health, auth, users, preferences, conversations, notifications, chat, social, search, videos, food, shopping, payments, ledger, devices, ai, delivery, legal, account, moderation
from app.api.routes import platform  # Phase 24.1: Unified Identity, Media & Blocking

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
api_router.include_router(ai.router)
api_router.include_router(delivery.router)
api_router.include_router(legal.router)
api_router.include_router(account.router)
api_router.include_router(platform.router)  # Phase 24.1: /platform/*
api_router.include_router(moderation.safety_router)  # Phase 3: /safety/*
api_router.include_router(moderation.mod_router)     # Phase 3: /moderation/*

