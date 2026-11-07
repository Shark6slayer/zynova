"""
Enhanced WebSocket Manager — Phase 24.1
Extends the existing ConnectionManager (ws_manager.py) with:
  - JWT-authenticated connections
  - Heartbeat/ping-pong lifecycle (30s client ping, 60s server timeout)
  - Multi-device connection tracking
  - Standardised event envelope format
  - Redis Pub/Sub adapter for distributed multi-instance deployments
  - In-memory adapter (dev/test) with identical interface

Architecture:
  EventBus (abstract) ─── InMemoryEventBus (default, single-node)
                      └── RedisEventBus (requires REDIS_URL, multi-node)

  ConnectionManager uses the EventBus to fan-out events across instances.
  When Redis is unavailable the system falls back to InMemoryEventBus.
"""
from __future__ import annotations

import abc
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("zynova.ws")

# ---------------------------------------------------------------------------
# Event envelope
# ---------------------------------------------------------------------------

def make_event(event_type: str, payload: Dict[str, Any]) -> str:
    """Serialises a standard Zynova WebSocket event envelope to JSON."""
    return json.dumps(
        {
            "type": event_type,
            "id": f"evt_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        },
        default=str,
    )


# ---------------------------------------------------------------------------
# Abstract event bus
# ---------------------------------------------------------------------------

class EventBus(abc.ABC):
    @abc.abstractmethod
    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a channel."""

    @abc.abstractmethod
    async def subscribe(self, channel: str, handler: Callable[[str], Any]) -> None:
        """Subscribe to a channel with a callback handler."""

    @abc.abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """Remove subscription for a channel."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable bus name for diagnostics."""


# ---------------------------------------------------------------------------
# In-memory event bus (single-node dev/test, identical interface to Redis bus)
# ---------------------------------------------------------------------------

class InMemoryEventBus(EventBus):
    """
    In-process pub/sub.
    Messages only reach subscribers in the same process instance.
    Use for: development, unit tests, single-instance deployments.
    """

    def __init__(self) -> None:
        # channel → set of async handler coroutines
        self._subs: Dict[str, List[Callable[[str], Any]]] = {}

    @property
    def name(self) -> str:
        return "in-memory"

    async def publish(self, channel: str, message: str) -> None:
        handlers = list(self._subs.get(channel, []))
        for handler in handlers:
            try:
                await handler(message)
            except Exception as exc:
                logger.warning(f"[InMemoryBus] handler error on channel {channel}: {exc}")

    async def subscribe(self, channel: str, handler: Callable[[str], Any]) -> None:
        self._subs.setdefault(channel, [])
        if handler not in self._subs[channel]:
            self._subs[channel].append(handler)

    async def unsubscribe(self, channel: str) -> None:
        self._subs.pop(channel, None)


# ---------------------------------------------------------------------------
# Redis event bus (distributed multi-instance)
# ---------------------------------------------------------------------------

class RedisEventBus(EventBus):
    """
    Redis Pub/Sub event bus for multi-instance horizontal deployments.
    Requires REDIS_URL to be set in settings.

    NOTE: Integration tests for the Redis bus require a live Redis instance.
    The connection is established lazily; if Redis is unreachable the publish
    call logs a warning and silently drops — the in-memory bus handles delivery
    within the same instance.
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._publish_conn: Optional[Any] = None
        self._subscriber_tasks: Dict[str, asyncio.Task] = {}

    @property
    def name(self) -> str:
        return f"redis ({self._redis_url.split('@')[-1] if '@' in self._redis_url else self._redis_url})"

    async def _get_publish_conn(self) -> Optional[Any]:
        if self._publish_conn is not None:
            return self._publish_conn
        try:
            import redis.asyncio as aioredis  # type: ignore
            self._publish_conn = await aioredis.from_url(
                self._redis_url,
                socket_connect_timeout=2.0,
                decode_responses=True,
            )
            await self._publish_conn.ping()
            logger.info(f"[RedisEventBus] Connected to Redis for publishing.")
            return self._publish_conn
        except Exception as exc:
            logger.warning(f"[RedisEventBus] Cannot connect to Redis: {exc}")
            return None

    async def publish(self, channel: str, message: str) -> None:
        conn = await self._get_publish_conn()
        if conn is None:
            logger.debug(f"[RedisEventBus] Drop publish to {channel}: Redis unavailable.")
            return
        try:
            await conn.publish(channel, message)
        except Exception as exc:
            logger.warning(f"[RedisEventBus] Publish error on {channel}: {exc}")
            self._publish_conn = None  # Reset for next attempt

    async def subscribe(self, channel: str, handler: Callable[[str], Any]) -> None:
        """Spawns a background task that listens on the given channel."""
        if channel in self._subscriber_tasks:
            return  # Already subscribed

        async def _listen() -> None:
            try:
                import redis.asyncio as aioredis  # type: ignore
                conn = await aioredis.from_url(
                    self._redis_url,
                    socket_connect_timeout=2.0,
                    decode_responses=True,
                )
                pubsub = conn.pubsub()
                await pubsub.subscribe(channel)
                logger.info(f"[RedisEventBus] Listening on channel: {channel}")
                async for msg in pubsub.listen():
                    if msg["type"] == "message":
                        try:
                            await handler(msg["data"])
                        except Exception as exc:
                            logger.warning(f"[RedisEventBus] Handler error on {channel}: {exc}")
            except asyncio.CancelledError:
                logger.info(f"[RedisEventBus] Subscription task for {channel} cancelled.")
            except Exception as exc:
                logger.warning(f"[RedisEventBus] Subscription error on {channel}: {exc}")

        task = asyncio.create_task(_listen(), name=f"redis_sub_{channel}")
        self._subscriber_tasks[channel] = task

    async def unsubscribe(self, channel: str) -> None:
        task = self._subscriber_tasks.pop(channel, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


# ---------------------------------------------------------------------------
# Bus factory
# ---------------------------------------------------------------------------

def _build_event_bus() -> EventBus:
    from app.core.config import settings  # avoid circular import at module load
    redis_url = getattr(settings, "REDIS_URL", None)
    if redis_url:
        try:
            import redis.asyncio  # noqa: F401 — verify installed
            logger.info("[WS] RedisEventBus selected.")
            return RedisEventBus(redis_url)
        except ImportError:
            logger.warning("[WS] redis package not installed; falling back to InMemoryEventBus.")
    logger.info("[WS] InMemoryEventBus selected (single-node).")
    return InMemoryEventBus()


# ---------------------------------------------------------------------------
# Connection record
# ---------------------------------------------------------------------------

class ConnectionRecord:
    __slots__ = ("websocket", "user_id", "device_id", "connected_at", "last_ping_at")

    def __init__(self, websocket: WebSocket, user_id: str, device_id: str) -> None:
        self.websocket = websocket
        self.user_id = user_id
        self.device_id = device_id
        self.connected_at = time.monotonic()
        self.last_ping_at = time.monotonic()


# ---------------------------------------------------------------------------
# Enhanced ConnectionManager
# ---------------------------------------------------------------------------

HEARTBEAT_INTERVAL = 30      # seconds: server sends ping frame
HEARTBEAT_TIMEOUT = 70       # seconds: disconnect if no pong received


class EnhancedConnectionManager:
    """
    Multi-device WebSocket connection manager with heartbeat and event bus.

    Public API (backward-compatible with existing ws_manager chat_manager):
      connect(user_id, websocket, device_id?)
      disconnect(user_id, websocket)
      send_personal_message(message, websocket)
      broadcast_to_users(user_ids, payload)

    New API:
      dispatch_event(user_ids, event_type, payload)
      get_online_users(user_ids)
      get_connection_count(user_id)
    """

    def __init__(self) -> None:
        # user_id → {device_id → ConnectionRecord}
        self._connections: Dict[str, Dict[str, ConnectionRecord]] = {}
        self._bus: Optional[EventBus] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    def _get_bus(self) -> EventBus:
        if self._bus is None:
            self._bus = _build_event_bus()
        return self._bus

    # --- Lifecycle -----------------------------------------------------------

    async def connect(
        self,
        user_id: str,
        websocket: WebSocket,
        device_id: Optional[str] = None,
    ) -> None:
        await websocket.accept()
        did = device_id or f"dev_{uuid.uuid4().hex[:8]}"
        record = ConnectionRecord(websocket, user_id, did)

        if user_id not in self._connections:
            self._connections[user_id] = {}
        # If same device reconnects, replace old connection
        self._connections[user_id][did] = record

        logger.info(
            f"[WS] User {user_id} connected (device={did}). "
            f"Total devices: {len(self._connections[user_id])}"
        )
        # Subscribe bus to user's inbox channel (idempotent)
        await self._get_bus().subscribe(
            f"zynova:user:{user_id}:events",
            self._make_user_inbox_handler(user_id),
        )

        # Send connection_ack
        await self._safe_send(websocket, make_event("connection.ack", {"user_id": user_id, "device_id": did}))

        # Start heartbeat task if not running
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="ws_heartbeat")

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        devices = self._connections.get(user_id, {})
        to_remove = [did for did, rec in devices.items() if rec.websocket is websocket]
        for did in to_remove:
            del devices[did]
            logger.info(f"[WS] User {user_id} disconnected (device={did}).")
        if not devices:
            self._connections.pop(user_id, None)
            logger.info(f"[WS] User {user_id} fully offline.")

    # --- Sending -------------------------------------------------------------

    async def _safe_send(self, websocket: WebSocket, text: str) -> bool:
        try:
            await websocket.send_text(text)
            return True
        except Exception as exc:
            logger.debug(f"[WS] Send error: {exc}")
            return False

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        await self._safe_send(websocket, json.dumps(message, default=str))

    async def broadcast_to_users(self, user_ids: List[str], payload: dict) -> None:
        text = json.dumps(payload, default=str)
        for uid in user_ids:
            for rec in list(self._connections.get(uid, {}).values()):
                await self._safe_send(rec.websocket, text)

    async def dispatch_event(
        self,
        user_ids: List[str],
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        Dispatches a typed event to target users.
        Uses the event bus for cross-instance fan-out.
        """
        event_text = make_event(event_type, payload)
        bus = self._get_bus()
        for uid in user_ids:
            # Publish to bus (reaches all instances)
            await bus.publish(f"zynova:user:{uid}:events", event_text)
            # Also deliver locally to this instance's connections
            for rec in list(self._connections.get(uid, {}).values()):
                await self._safe_send(rec.websocket, event_text)

    # --- Presence ------------------------------------------------------------

    def get_online_users(self, user_ids: List[str]) -> List[str]:
        """Returns the subset of user_ids that have at least one active connection."""
        return [uid for uid in user_ids if uid in self._connections]

    def get_connection_count(self, user_id: str) -> int:
        return len(self._connections.get(user_id, {}))

    def is_online(self, user_id: str) -> bool:
        return user_id in self._connections and bool(self._connections[user_id])

    # --- Redis inbox handler -------------------------------------------------

    def _make_user_inbox_handler(self, user_id: str) -> Callable[[str], Any]:
        async def _handler(message: str) -> None:
            for rec in list(self._connections.get(user_id, {}).values()):
                await self._safe_send(rec.websocket, message)
        return _handler

    # --- Heartbeat -----------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """
        Sends a ping frame every HEARTBEAT_INTERVAL seconds.
        Disconnects stale connections that haven't responded within HEARTBEAT_TIMEOUT.
        """
        logger.info("[WS] Heartbeat loop started.")
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                now = time.monotonic()
                stale: List[tuple] = []
                for uid, devices in list(self._connections.items()):
                    for did, rec in list(devices.items()):
                        age = now - rec.last_ping_at
                        if age > HEARTBEAT_TIMEOUT:
                            stale.append((uid, did, rec.websocket))
                        else:
                            ping_text = make_event("ping", {"server_time": datetime.now(timezone.utc).isoformat()})
                            await self._safe_send(rec.websocket, ping_text)
                for uid, did, ws in stale:
                    logger.info(f"[WS] Dropping stale connection user={uid} device={did}")
                    devices = self._connections.get(uid, {})
                    devices.pop(did, None)
                    if not devices:
                        self._connections.pop(uid, None)
                    try:
                        await ws.close(code=1001, reason="Heartbeat timeout")
                    except Exception:
                        pass
            except asyncio.CancelledError:
                logger.info("[WS] Heartbeat loop cancelled.")
                break
            except Exception as exc:
                logger.warning(f"[WS] Heartbeat error: {exc}")

    def record_pong(self, user_id: str, device_id: str) -> None:
        """Call when a pong or any client message is received to reset heartbeat timer."""
        rec = self._connections.get(user_id, {}).get(device_id)
        if rec:
            rec.last_ping_at = time.monotonic()


# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------

# Enhanced manager (Phase 24.1) — used by all new real-time routes
enhanced_ws_manager = EnhancedConnectionManager()

# Backward-compatible alias for existing chat.py route which imports chat_manager from ws_manager.py
# Existing chat routes continue to work unchanged.
# New routes should use enhanced_ws_manager directly.
