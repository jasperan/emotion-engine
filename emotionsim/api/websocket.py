"""WebSocket handler for real-time updates"""
import json
import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from emotionsim.auth.deps import ensure_visible, resolve_scope
from emotionsim.core import database
from emotionsim.models.run import Run
from emotionsim.simulation import SimulationManager

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections per run"""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, run_id: str) -> None:
        """Accept a WebSocket connection for a run"""
        await websocket.accept()

        if run_id not in self._connections:
            self._connections[run_id] = []
        self._connections[run_id].append(websocket)

    def disconnect(self, websocket: WebSocket, run_id: str) -> None:
        """Remove a WebSocket connection"""
        if run_id in self._connections:
            try:
                self._connections[run_id].remove(websocket)
            except ValueError:
                pass

            if not self._connections[run_id]:
                del self._connections[run_id]

    async def broadcast(self, run_id: str, message: dict[str, Any]) -> None:
        """Broadcast a message to all connections for a run"""
        if run_id not in self._connections:
            return

        message_json = json.dumps(message, default=str)
        dead_connections = []

        for websocket in self._connections[run_id]:
            try:
                await websocket.send_text(message_json)
            except Exception:
                dead_connections.append(websocket)

        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws, run_id)


# Global connection manager
connection_manager = ConnectionManager()


@router.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for run updates.

    Ownership is checked before the handshake is accepted. Private runs need
    the owner's API key, sent as an ``X-API-Key`` header or (for browsers,
    which cannot set headers on a WebSocket) an ``api_key`` query parameter.
    Public runs stay open to anonymous clients.
    """
    api_key = websocket.headers.get("x-api-key") or websocket.query_params.get("api_key")
    try:
        # Short-lived session: the socket itself can stay open for hours.
        async with database.async_session_maker() as db:
            scope = await resolve_scope(api_key, db)
            ensure_visible(await db.get(Run, run_id), scope, "Run")
    except HTTPException:
        await websocket.close(code=1008)  # policy violation; rejected pre-accept
        return

    await connection_manager.connect(websocket, run_id)

    # Set up event handler for this connection
    manager = SimulationManager.get_instance()

    def event_handler(event_type: str, data: dict[str, Any]) -> None:
        """Handle simulation events and queue for sending"""
        asyncio.create_task(
            connection_manager.broadcast(run_id, {
                "event": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        )

    # Subscribe to simulation events
    manager.subscribe(run_id, event_handler)

    try:
        # Send initial status
        status = manager.get_run_status(run_id)
        await websocket.send_json({
            "event": "connected",
            "data": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (commands)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Ping every 30 seconds
                )

                # Parse and handle client commands
                try:
                    command = json.loads(data)
                    cmd_type = command.get("type")

                    if cmd_type == "ping":
                        await websocket.send_json({
                            "event": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    elif cmd_type == "get_status":
                        status = manager.get_run_status(run_id)
                        await websocket.send_json({
                            "event": "status",
                            "data": status,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({
                        "event": "ping",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup
        manager.unsubscribe(run_id, event_handler)
        connection_manager.disconnect(websocket, run_id)
