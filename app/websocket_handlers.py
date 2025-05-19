# app/websocket_handlers.py

from typing import List

from fastapi import WebSocket, WebSocketDisconnect
from app.utils import decode_token


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, game_id: int, token: str):
    """Обработка WebSocket-соединений с проверкой JWT."""
    payload = decode_token(token)
    if payload is None:
        await websocket.close(reason="Invalid token")
        return

    username = payload.get("sub")
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Game {game_id}: Player {username} made a move: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)