# app/websocket_handlers.py

import asyncio
import json
from typing import List

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.game_logic.board import generate_board, place_ships, check_ship_placement
from app.game_logic.utils import make_move, check_winner
from app.models import Game as ModelGame
from app.db.session import SessionLocal
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
    db: Session = SessionLocal()

    # Получаем игру из базы данных
    game = db.query(ModelGame).filter(ModelGame.id == game_id).first()
    if not game:
        print(f"Game not found: {game_id}")
        await websocket.close(code=1008, reason="Game not found")
        return

    # Проверяем, является ли пользователь участником игры
    player_id = None
    if game.player1.username == username:
        player_id = game.player1_id
    elif game.player2.username == username:
        player_id = game.player2_id
    else:
        await websocket.close(reason="You are not a participant of this game")
        return

    # Инициализируем игровое поле, если оно еще не создано
    if player_id == game.player1_id and not game.board_player1:
        game.board_player1 = generate_board()
    elif player_id == game.player2_id and not game.board_player2:
        game.board_player2 = generate_board()

    db.commit()

    # Определяем поле текущего игрока и поля противника
    current_board = (
        game.board_player1 if player_id == game.player1_id else game.board_player2
    )
    opponent_board = (
        game.board_player2 if player_id == game.player1_id else game.board_player1
    )

    await manager.connect(websocket)
    try:
        while True:
            # Проверяем статус игры
            if game.status == "waiting" or game.status.endswith("_ready"):
                # Этап расстановки кораблей
                data = await websocket.receive_text()
                message = json.loads(data)

                action = message.get("action")

                if action == "place_ship":
                    print(1)
                    # Расстановка корабля
                    x, y = message.get("x"), message.get("y")
                    size = message.get("size")
                    orientation = message.get("orientation")

                    # Проверяем, можно ли разместить корабль
                    if not check_ship_placement(current_board, x, y, size, orientation):
                        await manager.send_personal_message(
                            json.dumps(
                                {"status": "error", "message": "Invalid ship placement"}
                            ),
                            websocket,
                        )
                        continue

                    # Размещаем корабль
                    current_board = place_ships(
                        current_board, [(size, orientation, x, y)]
                    )

                    # Обновляем поле в базе данных
                    if player_id == game.player1_id:
                        game.board_player1 = current_board
                    else:
                        game.board_player2 = current_board

                    db.commit()

                    # Отправляем подтверждение клиенту
                    await manager.send_personal_message(
                        json.dumps(
                            {
                                "status": "success",
                                "message": f"Ship placed at ({x}, {y})",
                            }
                        ),
                        websocket,
                    )

                elif action == "finish_placement":
                    # Завершение расстановки
                    if player_id == game.player1_id:
                        game.status = "player1_ready"
                    else:
                        game.status = "player2_ready"

                    db.commit()

                    # Проверяем, готовы ли оба игрока
                    if (
                        game.status == "player1_ready"
                        and game.status == "player2_ready"
                    ):
                        game.status = "in_progress"

                    db.commit()

                    # Уведомляем обоих игроков
                    await manager.broadcast(json.dumps({"status": "game_started"}))

            elif game.status == "in_progress":
                # Боевая фаза
                if game.turn != player_id:
                    await manager.send_personal_message(
                        json.dumps({"status": "wait", "message": "Not your turn"}),
                        websocket,
                    )
                    continue

                # Устанавливаем таймер на ход
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                except asyncio.TimeoutError:
                    # Если время вышло, передаем ход противнику
                    game.turn = (
                        game.player2_id
                        if game.turn == game.player1_id
                        else game.player1_id
                    )
                    db.commit()
                    await manager.broadcast(
                        json.dumps(
                            {"status": "timeout", "message": "Time's up! Turn passed"}
                        )
                    )
                    continue

                # Обрабатываем ход
                message = json.loads(data)
                x, y = message.get("x"), message.get("y")

                result = make_move(opponent_board, x, y)

                # Обновляем поле противника в базе данных
                if player_id == game.player1_id:
                    game.board_player2 = opponent_board
                else:
                    game.board_player1 = opponent_board

                db.commit()

                # Проверяем победителя
                winner = None
                if check_winner(opponent_board):
                    game.status = "finished"
                    game.winner_id = player_id
                    db.commit()
                    winner = game.winner.username

                # Отправляем результат всем участникам
                response = {
                    "result": result,
                    "status": game.status,
                    "winner": winner,
                    "move": {"x": x, "y": y},
                    "player": username,
                }
                await manager.broadcast(json.dumps(response))

                # Передаем ход, если игрок промахнулся
                if result == "miss":
                    game.turn = (
                        game.player2_id
                        if game.turn == game.player1_id
                        else game.player1_id
                    )
                    db.commit()

            elif game.status == "finished":
                # Игра завершена
                await manager.send_personal_message(
                    json.dumps({"status": "finished", "message": "Game over"}),
                    websocket,
                )
                break

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        db.close()
