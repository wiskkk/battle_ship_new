# app/websocket_handlers.py

import json
from typing import Dict, List

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.game_logic.board import generate_board, place_ship_manual
from app.game_logic.utils import (check_winner, deserialize_board, make_move,
                                  serialize_board)
from app.models import Game as ModelGame
from app.models import User as ModelUser
from app.utils import decode_token


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = (
            {}
        )  # game_id -> list of websockets
        self.user_connections: Dict[int, Dict[int, WebSocket]] = (
            {}
        )  # game_id -> {user_id: websocket}

    async def connect(self, websocket: WebSocket, game_id: int, user_id: int):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
            self.user_connections[game_id] = {}

        self.active_connections[game_id].append(websocket)
        self.user_connections[game_id][user_id] = websocket

    def disconnect(self, websocket: WebSocket, game_id: int, user_id: int):
        if game_id in self.active_connections:
            if websocket in self.active_connections[game_id]:
                self.active_connections[game_id].remove(websocket)

            if (
                game_id in self.user_connections
                and user_id in self.user_connections[game_id]
            ):
                del self.user_connections[game_id][user_id]

            if not self.active_connections[game_id]:
                del self.active_connections[game_id]
                if game_id in self.user_connections:
                    del self.user_connections[game_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")

    async def send_to_user(self, message: str, game_id: int, user_id: int):
        if (
            game_id in self.user_connections
            and user_id in self.user_connections[game_id]
        ):
            websocket = self.user_connections[game_id][user_id]
            try:
                await websocket.send_text(message)
            except Exception as e:
                print(f"Error sending message to user {user_id}: {e}")

    async def broadcast_to_game(
        self, message: str, game_id: int, exclude_user: int = None
    ):
        if game_id in self.active_connections:
            disconnected = []
            for user_id, connection in self.user_connections.get(game_id, {}).items():
                if exclude_user and user_id == exclude_user:
                    continue
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Error broadcasting to user {user_id}: {e}")
                    disconnected.append(connection)

            # Удаляем отключенные соединения
            for conn in disconnected:
                if conn in self.active_connections[game_id]:
                    self.active_connections[game_id].remove(conn)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, game_id: int):
    """Обработка WebSocket-соединений с проверкой JWT."""
    # Получаем токен из query параметров
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Token is required")
        return

    payload = decode_token(token)
    if payload is None:
        await websocket.close(code=1008, reason="Invalid token")
        return

    username = payload.get("sub")
    db: Session = SessionLocal()

    try:
        # Получаем игру из базы данных
        game = db.query(ModelGame).filter(ModelGame.id == game_id).first()
        if not game:
            await websocket.close(code=1008, reason="Game not found")
            return

        # Получаем пользователя
        user = db.query(ModelUser).filter(ModelUser.username == username).first()
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return

        # Проверяем, является ли пользователь участником игры
        if game.player1_id != user.id and game.player2_id != user.id:
            await websocket.close(
                code=1008, reason="You are not a participant of this game"
            )
            return

        await manager.connect(websocket, game_id, user.id)

        # Инициализируем игровые поля если они не созданы
        if not game.board_player1:
            game.board_player1 = serialize_board(generate_board())
        if not game.board_player2:
            game.board_player2 = serialize_board(generate_board())

        # Инициализируем статусы готовности
        if not hasattr(game, "player1_ready"):
            game.player1_ready = False
        if not hasattr(game, "player2_ready"):
            game.player2_ready = False

        db.commit()

        # Отправляем текущее состояние игры
        await send_game_state(websocket, game, user.id)

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                action = message.get("action")

                # Обновляем состояние игры из БД
                db.refresh(game)

                if action == "place_ship":
                    await handle_place_ship(websocket, game, user.id, message, db)
                elif action == "ready":
                    await handle_player_ready(websocket, game, user.id, db)
                elif action == "make_move":
                    await handle_make_move(websocket, game, user.id, message, db)
                elif action == "get_state":
                    await send_game_state(websocket, game, user.id)
                else:
                    await manager.send_personal_message(
                        json.dumps(
                            {"status": "error", "message": f"Unknown action: {action}"}
                        ),
                        websocket,
                    )

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await manager.send_personal_message(
                    json.dumps({"status": "error", "message": "Invalid JSON"}),
                    websocket,
                )
            except Exception as e:
                print(f"WebSocket error: {e}")
                await manager.send_personal_message(
                    json.dumps({"status": "error", "message": str(e)}), websocket
                )

    except Exception as e:
        print(f"WebSocket connection error: {e}")
    finally:
        manager.disconnect(websocket, game_id, user.id)
        db.close()


async def handle_place_ship(
    websocket: WebSocket, game: ModelGame, user_id: int, message: dict, db: Session
):
    """Обработка размещения корабля."""
    if game.status not in ["setup", "waiting"]:
        await manager.send_personal_message(
            json.dumps(
                {
                    "status": "error",
                    "message": "Cannot place ships in current game state",
                }
            ),
            websocket,
        )
        return

    x, y = message.get("x"), message.get("y")
    size = message.get("size")
    orientation = message.get("orientation")

    if None in [x, y, size, orientation]:
        await manager.send_personal_message(
            json.dumps({"status": "error", "message": "Missing required parameters"}),
            websocket,
        )
        return

    # Получаем доску игрока
    if user_id == game.player1_id:
        board = deserialize_board(game.board_player1)
    else:
        board = deserialize_board(game.board_player2)

    # Проверяем и размещаем корабль
    if place_ship_manual(board, x, y, size, orientation):
        # Сохраняем обновленную доску
        if user_id == game.player1_id:
            game.board_player1 = serialize_board(board)
        else:
            game.board_player2 = serialize_board(board)

        db.commit()

        await manager.send_personal_message(
            json.dumps(
                {
                    "status": "success",
                    "action": "ship_placed",
                    "message": f"Ship placed at ({x}, {y})",
                    "ship": {"x": x, "y": y, "size": size, "orientation": orientation},
                }
            ),
            websocket,
        )

        # Отправляем обновленное состояние
        await send_game_state(websocket, game, user_id)
    else:
        await manager.send_personal_message(
            json.dumps({"status": "error", "message": "Invalid ship placement"}),
            websocket,
        )


async def handle_player_ready(
    websocket: WebSocket, game: ModelGame, user_id: int, db: Session
):
    """Обработка готовности игрока."""
    if game.status not in ["setup", "waiting"]:
        await manager.send_personal_message(
            json.dumps(
                {"status": "error", "message": "Cannot set ready in current game state"}
            ),
            websocket,
        )
        return

    # Устанавливаем готовность игрока
    if user_id == game.player1_id:
        game.status = "player1_ready" if game.status == "setup" else "both_ready"
    elif user_id == game.player2_id:
        if game.status == "player1_ready":
            game.status = "both_ready"
        else:
            game.status = "player2_ready"

    # Если оба игрока готовы, начинаем игру
    if game.status == "both_ready":
        game.status = "in_progress"
        game.turn = game.player1_id  # Первый игрок начинает

    db.commit()

    # Уведомляем всех участников
    await manager.broadcast_to_game(
        json.dumps(
            {
                "status": "success",
                "action": "player_ready",
                "game_status": game.status,
                "turn": game.turn,
                "ready_player": user_id,
            }
        ),
        game.id,
    )


async def handle_make_move(
    websocket: WebSocket, game: ModelGame, user_id: int, message: dict, db: Session
):
    """Обработка хода игрока."""
    if game.status != "in_progress":
        await manager.send_personal_message(
            json.dumps({"status": "error", "message": "Game is not in progress"}),
            websocket,
        )
        return

    if game.turn != user_id:
        await manager.send_personal_message(
            json.dumps({"status": "error", "message": "Not your turn"}), websocket
        )
        return

    x, y = message.get("x"), message.get("y")
    if x is None or y is None:
        await manager.send_personal_message(
            json.dumps({"status": "error", "message": "Missing coordinates"}), websocket
        )
        return

    # Определяем доску противника
    if user_id == game.player1_id:
        opponent_board = deserialize_board(game.board_player2)
        opponent_id = game.player2_id
    else:
        opponent_board = deserialize_board(game.board_player1)
        opponent_id = game.player1_id

    # Делаем ход
    result = make_move(opponent_board, x, y)

    if result == "invalid":
        await manager.send_personal_message(
            json.dumps({"status": "error", "message": "Invalid move coordinates"}),
            websocket,
        )
        return

    if result == "already_hit":
        await manager.send_personal_message(
            json.dumps({"status": "error", "message": "Cell already hit"}), websocket
        )
        return

    # Сохраняем обновленную доску
    if user_id == game.player1_id:
        game.board_player2 = serialize_board(opponent_board)
    else:
        game.board_player1 = serialize_board(opponent_board)

    # Проверяем победителя
    winner = None
    if check_winner(opponent_board):
        game.status = "finished"
        game.winner_id = user_id
        winner = user_id

    # Передаем ход, если промах и игра не закончена
    if result == "miss" and game.status != "finished":
        game.turn = opponent_id

    db.commit()

    # Отправляем результат всем участникам
    response = {
        "status": "success",
        "action": "move_result",
        "result": result,
        "game_status": game.status,
        "winner": winner,
        "move": {"x": x, "y": y},
        "player": user_id,
        "turn": game.turn,
    }

    await manager.broadcast_to_game(json.dumps(response), game.id)


async def send_game_state(websocket: WebSocket, game: ModelGame, user_id: int):
    """Отправка текущего состояния игры."""
    # Получаем свою доску
    if user_id == game.player1_id:
        my_board = deserialize_board(game.board_player1)
        opponent_board = deserialize_board(game.board_player2)
        opponent_id = game.player2_id
    else:
        my_board = deserialize_board(game.board_player2)
        opponent_board = deserialize_board(game.board_player1)
        opponent_id = game.player1_id

    # Скрываем корабли противника (показываем только попадания и промахи)
    if opponent_board:
        if game.status == "finished":
            # Если игра закончена, показываем все корабли
            hidden_opponent_board = opponent_board
        else:
            # Скрываем неподбитые корабли
            hidden_opponent_board = [
                ["~" if cell == "S" else cell for cell in row] for row in opponent_board
            ]
    else:
        hidden_opponent_board = None

    state = {
        "status": "success",
        "action": "game_state",
        "game_id": game.id,
        "game_status": game.status,
        "player_id": user_id,
        "opponent_id": opponent_id,
        "turn": game.turn,
        "my_board": my_board,
        "opponent_board": hidden_opponent_board,
        "winner": game.winner_id,
        "is_my_turn": game.turn == user_id if game.turn else False,
    }

    await manager.send_personal_message(json.dumps(state), websocket)
