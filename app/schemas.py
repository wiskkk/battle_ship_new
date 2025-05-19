from pydantic import BaseModel


# Схема для создания пользователя
class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


# Схема для ответа с данными пользователя
class User(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True  # Автоматическое преобразование из SQLAlchemy модели


# Схема для создания игры
class GameCreate(BaseModel):
    player1_id: int
    player2_id: int


# Схема для ответа с данными игры
class Game(BaseModel):
    id: int
    player1_id: int
    player2_id: int

    class Config:
        from_attributes = True  # Автоматическое преобразование из SQLAlchemy модели
