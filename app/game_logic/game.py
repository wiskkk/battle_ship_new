# app/game_logic/game.py

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Game, User


def start_game(player1_id: int, db: Session):
    """Создание новой игры."""
    new_game = Game(player1_id=player1_id, status="waiting")
    db.add(new_game)
    db.commit()
    db.refresh(new_game)
    return {"game_id": new_game.id, "status": "waiting"}


def join_game(game_id: int, player2_id: int, db: Session):
    """Присоединение второго игрока к игре."""
    game = db.query(Game).filter(Game.id == game_id, Game.player2_id == None).first()
    if not game:
        return {"error": "Game not found or already has two players"}
    game.player2_id = player2_id
    game.status = "in_progress"
    db.commit()
    db.refresh(game)
    return {"game_id": game.id, "status": "in_progress"}


def get_game_status(game_id: int, db: Session):
    """Получение текущего состояния игры."""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {"error": "Game not found"}
    return {
        "game_id": game.id,
        "status": game.status,
        "player1_id": game.player1_id,
        "player2_id": game.player2_id,
        "winner_id": game.winner_id,
    }