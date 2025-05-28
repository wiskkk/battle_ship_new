# app/models.py

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String,
                        Text)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    games_as_player1 = relationship("Game", foreign_keys="Game.player1_id", back_populates="player1")
    games_as_player2 = relationship("Game", foreign_keys="Game.player2_id", back_populates="player2")
    won_games = relationship("Game", foreign_keys="Game.winner_id", back_populates="winner")


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    player1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    player2_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    board_player1 = Column(Text, nullable=True)  # JSON-строка для игрового поля первого игрока
    board_player2 = Column(Text, nullable=True)  # JSON-строка для игрового поля второго игрока
    status = Column(String, default="waiting", nullable=False)  # waiting, setup, player1_ready, player2_ready, both_ready, in_progress, finished
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    turn = Column(Integer, ForeignKey("users.id"), nullable=True)  # Чей ход
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Связи
    player1 = relationship("User", foreign_keys=[player1_id], back_populates="games_as_player1")
    player2 = relationship("User", foreign_keys=[player2_id], back_populates="games_as_player2")
    winner = relationship("User", foreign_keys=[winner_id], back_populates="won_games")
    
    def __repr__(self):
        return f"<Game(id={self.id}, status={self.status}, player1_id={self.player1_id}, player2_id={self.player2_id})>"