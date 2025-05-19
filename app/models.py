# app/models.py

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    player1_id = Column(Integer, ForeignKey("users.id"))
    player2_id = Column(Integer, ForeignKey("users.id"))
    board_player1 = Column(String)  # JSON-строка для игрового поля первого игрока
    board_player2 = Column(String)  # JSON-строка для игрового поля второго игрока
    status = Column(String, default="waiting")  # Статус игры
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    player1 = relationship("User", foreign_keys=[player1_id])
    player2 = relationship("User", foreign_keys=[player2_id])
    winner = relationship("User", foreign_keys=[winner_id])
