# app/game_logic/game.py

from sqlalchemy.orm import Session

from app.game_logic.board import generate_board
from app.game_logic.utils import deserialize_board, serialize_board
from app.models import Game


def start_game_logic(player1_id: int, db: Session):
    """Создание новой игры."""
    new_game = Game(player1_id=player1_id, status="waiting")
    db.add(new_game)
    db.commit()
    db.refresh(new_game)
    return new_game


def join_game_logic(game_id: int, player2_id: int, db: Session):
    """Присоединение второго игрока к игре."""
    game = db.query(Game).filter(Game.id == game_id, Game.player2_id == None).first()
    if not game:
        raise ValueError("Game not found or already has two players")

    game.player2_id = player2_id
    game.status = "setup"  # Изменяем на setup для фазы расстановки кораблей
    game.turn = game.player1_id  # Первый игрок начинает

    db.commit()
    db.refresh(game)
    return game


def get_game_status_logic(game_id: int, db: Session):
    """Получение текущего состояния игры."""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise ValueError("Game not found")

    return {
        "game_id": game.id,
        "status": game.status,
        "player1_id": game.player1_id,
        "player2_id": game.player2_id,
        "winner_id": game.winner_id,
        "turn": game.turn,
        "board_player1": (
            deserialize_board(game.board_player1) if game.board_player1 else None
        ),
        "board_player2": (
            deserialize_board(game.board_player2) if game.board_player2 else None
        ),
    }


def initialize_player_board(game: Game, player_id: int, db: Session):
    """Инициализация игрового поля игрока."""
    board = generate_board()
    serialized_board = serialize_board(board)

    if player_id == game.player1_id:
        game.board_player1 = serialized_board
    elif player_id == game.player2_id:
        game.board_player2 = serialized_board

    db.commit()
    return board
