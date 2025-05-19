# app/main.py

from fastapi import Depends, FastAPI, HTTPException, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.game_logic.game import get_game_status as get_game_status_logic
from app.game_logic.game import join_game as join_game_logic
from app.game_logic.game import start_game as start_game_logic
from app.models import User as ModelUser
from app.schemas import Token, User as SchemaUser, UserCreate, UserLogin
from app.services.user_service import create_user, get_users
from app.utils import create_access_token, hash_password, verify_password
from app.websocket_handlers import websocket_endpoint

from app.utils import decode_token

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.get("/health")
def health():
    """Проверка работоспособности приложения."""
    return {"status": "ok"}


@app.get("/users/", response_model=list[SchemaUser])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Получение списка пользователей."""
    users = get_users(db, skip=skip, limit=limit)
    return users


@app.post("/users/", response_model=SchemaUser)
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    """Создание нового пользователя."""
    return create_user(db=db, user=user)


@app.post("/games/start/")
def start_game(player1_id: int, db: Session = Depends(get_db)):
    """
    Создание новой игры.
    Логика вынесена в game_logic.game.start_game.
    """
    return start_game_logic(player1_id, db)


@app.post("/games/join/")
def join_game(game_id: int, player2_id: int, db: Session = Depends(get_db)):
    """
    Присоединение второго игрока к игре.
    Логика вынесена в game_logic.game.join_game.
    """
    return join_game_logic(game_id, player2_id, db)


@app.get("/games/{game_id}/status/")
def get_game_status(game_id: int, db: Session = Depends(get_db)):
    """
    Получение текущего состояния игры.
    Логика вынесена в game_logic.game.get_game_status.
    """
    return get_game_status_logic(game_id, db)


@app.websocket("/ws/{game_id}")
async def websocket_handler(websocket: WebSocket, game_id: int):
    """
    Обработка WebSocket-соединений.
    Логика вынесена в websocket_handlers.websocket_endpoint.
    """
    await websocket_endpoint(websocket, game_id)


@app.post("/register/", response_model=SchemaUser)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Регистрация нового пользователя."""
    hashed_password = hash_password(user.password)
    new_user = ModelUser(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/token/", response_model=Token)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """Аутентификация пользователя и выдача JWT."""
    user = db.query(ModelUser).filter(ModelUser.username == user_credentials.username).first()
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """Получает текущего пользователя по JWT."""
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = payload.get("sub")
    user = db.query(ModelUser).filter(ModelUser.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@app.get("/users/me/", response_model=SchemaUser)
def read_users_me(current_user: ModelUser = Depends(get_current_user)):
    """Получение информации о текущем пользователе."""
    return current_user
