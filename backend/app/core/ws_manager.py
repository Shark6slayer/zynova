from typing import Dict, Set, Optional
from fastapi import WebSocket
from datetime import datetime, timezone
import logging
import json

logger = logging.getLogger("chat_ws")

class ConnectionManager:
    def __init__(self):
        # Maps user_id -> set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Maps user_id -> last_seen UTC datetime
        self.user_last_seen: Dict[str, datetime] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        self.user_last_seen[user_id] = datetime.now(timezone.utc)
        logger.info(f"User {user_id} connected to Chat WebSocket. Total clients: {len(self.active_connections[user_id])}")

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        self.user_last_seen[user_id] = datetime.now(timezone.utc)
        logger.info(f"User {user_id} disconnected from Chat WebSocket.")

    def is_user_online(self, user_id: str) -> bool:
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    def get_user_status(self, user_id: str) -> dict:
        is_online = self.is_user_online(user_id)
        last_seen = self.user_last_seen.get(user_id)
        return {
            "user_id": user_id,
            "is_online": is_online,
            "last_seen": last_seen.isoformat() if last_seen else None
        }

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception as e:
            logger.warning(f"Failed to send personal WS message: {e}")

    async def broadcast_to_users(self, user_ids: list[str], payload: dict):
        """Sends real-time message payload to all active WebSockets of specified user IDs."""
        text_data = json.dumps(payload, default=str)
        for uid in user_ids:
            if uid in self.active_connections:
                for ws in list(self.active_connections[uid]):
                    try:
                        await ws.send_text(text_data)
                    except Exception as e:
                        logger.warning(f"Error broadcasting to user {uid}: {e}")
                        self.active_connections[uid].discard(ws)

chat_manager = ConnectionManager()
