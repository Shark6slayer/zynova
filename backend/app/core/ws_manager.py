from typing import Dict, Set
from fastapi import WebSocket
import logging
import json

logger = logging.getLogger("chat_ws")

class ConnectionManager:
    def __init__(self):
        # Maps user_id -> set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected to Chat WebSocket. Total clients: {len(self.active_connections[user_id])}")

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected from Chat WebSocket.")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
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
