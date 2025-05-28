# app/main.py

from fastapi import (Depends, FastAPI, HTTPException, Request, Response,
                     WebSocket, status)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.game_logic.game import (get_game_status_logic, join_game_logic,
                                 start_game_logic)
from app.models import Game as ModelGame
from app.models import User as ModelUser
from app.schemas import Token
from app.schemas import User as SchemaUser
from app.schemas import UserCreate, UserLogin
from app.services.user_service import get_users
from app.utils import (create_access_token, decode_token, hash_password,
                       verify_password)
from app.websocket_handlers import websocket_endpoint

app = FastAPI(title="Battleship Game API", version="1.0.0")

# Настройка CORS
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="app/static"), name="static")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """Получение текущего пользователя по JWT."""
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


@app.get("/health")
def health():
    """Проверка работоспособности приложения."""
    return {"status": "ok", "message": "Battleship API is running"}


@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Главная страница."""
    token = None
    try:
        token = request.cookies.get("authToken")
        if not token:
            authorization_header = request.headers.get("Authorization")
            if authorization_header and authorization_header.startswith("Bearer "):
                token = authorization_header.split(" ")[1]
    except Exception as e:
        print(f"Error getting token: {e}")

    if not token:
        with open("app/static/home.html", "r", encoding="utf-8") as file:
            return HTMLResponse(content=file.read())

    payload = decode_token(token)
    if payload is None:
        with open("app/static/home.html", "r", encoding="utf-8") as file:
            return HTMLResponse(content=file.read())

    username = payload.get("sub")
    with open("app/static/authenticated_home.html", "r", encoding="utf-8") as file:
        content = file.read().replace("{{ username }}", username)
        return HTMLResponse(content=content)


@app.post("/games/start/")
def start_game(
    current_user: ModelUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Создание новой игры."""
    try:
        game = start_game_logic(current_user.id, db)
        return {
            "success": True,
            "game_id": game.id,
            "status": game.status,
            "player1_id": game.player1_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/games/join/")
def join_game(
    game_id: int,
    current_user: ModelUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Присоединение второго игрока к игре."""
    try:
        game = join_game_logic(game_id, current_user.id, db)
        return {
            "success": True,
            "game_id": game.id,
            "status": game.status,
            "player1_id": game.player1_id,
            "player2_id": game.player2_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/games/")
def list_games(
    current_user: ModelUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Получение списка игр пользователя."""
    games = (
        db.query(ModelGame)
        .filter(
            (ModelGame.player1_id == current_user.id)
            | (ModelGame.player2_id == current_user.id)
        )
        .all()
    )

    return [
        {
            "id": game.id,
            "status": game.status,
            "player1_id": game.player1_id,
            "player2_id": game.player2_id,
            "winner_id": game.winner_id,
            "turn": game.turn,
        }
        for game in games
    ]


@app.get("/games/waiting/")
def list_waiting_games(db: Session = Depends(get_db)):
    """Получение списка игр, ожидающих второго игрока."""
    games = (
        db.query(ModelGame)
        .filter(ModelGame.status == "waiting", ModelGame.player2_id.is_(None))
        .all()
    )

    return [
        {
            "id": game.id,
            "status": game.status,
            "player1_id": game.player1_id,
        }
        for game in games
    ]


@app.get("/users/", response_model=list[SchemaUser])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Получение списка пользователей."""
    return get_users(db, skip=skip, limit=limit)


@app.post("/register/", response_model=SchemaUser)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Регистрация нового пользователя."""
    # Проверяем, существует ли пользователь
    existing_user = (
        db.query(ModelUser).filter(ModelUser.username == user.username).first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = hash_password(user.password)
    new_user = ModelUser(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/token/", response_model=Token)
def login(
    response: Response, user_credentials: UserLogin, db: Session = Depends(get_db)
):
    """Аутентификация пользователя и выдача JWT."""
    user = (
        db.query(ModelUser)
        .filter(ModelUser.username == user_credentials.username)
        .first()
    )
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    response.set_cookie(key="authToken", value=access_token, httponly=True)

    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/logout")
def logout(response: Response):
    """Выход из системы."""
    response.delete_cookie(key="authToken")
    return {"message": "Logged out successfully"}


@app.get("/users/me/", response_model=SchemaUser)
def read_users_me(current_user: ModelUser = Depends(get_current_user)):
    """Получение информации о текущем пользователе."""
    return current_user


@app.get("/games/{game_id}/status/")
def get_game_status(
    game_id: int,
    current_user: ModelUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение текущего состояния игры."""
    try:
        game_status = get_game_status_logic(game_id, db)

        # Проверяем, что пользователь участвует в игре
        if current_user.id != game_status.get(
            "player1_id"
        ) and current_user.id != game_status.get("player2_id"):
            raise HTTPException(status_code=403, detail="Access denied")

        return game_status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# WebSocket endpoint
@app.websocket("/ws/{game_id}")
async def websocket_handler(websocket: WebSocket, game_id: int):
    """WebSocket endpoint для игры."""
    await websocket_endpoint(websocket, game_id)


@app.get("/auth", response_class=HTMLResponse)
async def auth_page():
    """Страница авторизации."""
    with open("app/static/auth.html", "r", encoding="utf-8") as file:
        return HTMLResponse(content=file.read())


@app.get("/game", response_class=HTMLResponse)
async def game_page():
    """Главная страница игры."""
    with open("app/static/index.html", "r", encoding="utf-8") as file:
        return HTMLResponse(content=file.read())


@app.get("/game/{game_id}", response_class=HTMLResponse)
async def game_room_page(game_id: int):
    """Страница конкретной игры."""
    with open("app/static/game_room.html", "r", encoding="utf-8") as file:
        content = file.read().replace("{{ game_id }}", str(game_id))
        return HTMLResponse(content=content)
