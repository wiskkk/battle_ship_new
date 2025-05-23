# app/main.py

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.game_logic.game import get_game_status as get_game_status_logic
from app.game_logic.game import join_game as join_game_logic
from app.game_logic.game import start_game_logic
from app.game_logic.utils import check_winner, make_move
from app.models import Game as ModelGame
from app.models import User as ModelUser
from app.schemas import Token
from app.schemas import User as SchemaUser
from app.schemas import UserCreate, UserLogin
from app.services.user_service import get_users
from app.utils import create_access_token, decode_token, hash_password, verify_password
from app.websocket_handlers import websocket_endpoint

app = FastAPI()

# Настройка CORS
origins = [
    "http://localhost",
    "http://localhost:8000",  # Убедитесь, что это соответствует порту вашего клиента
    "http://localhost:8001",
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
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Главная страница."""
    # Проверяем, есть ли токен в cookies или заголовках
    token = None
    try:
        # Получаем токен из cookies
        token = request.cookies.get("authToken")
        if not token:
            # Если токена нет в cookies, пробуем получить его из заголовков
            authorization_header = request.headers.get("Authorization")
            if authorization_header and authorization_header.startswith("Bearer "):
                token = authorization_header.split(" ")[1]
    except Exception as e:
        print(f"Error - {e}")

    if not token:
        # Если токен отсутствует, показываем страницу для неавторизованных пользователей
        with open("app/static/home.html", "r", encoding="utf-8") as file:
            return HTMLResponse(content=file.read())

    # Если токен есть, проверяем его валидность
    payload = decode_token(token)
    if payload is None:
        # Если токен недействителен, также показываем страницу для неавторизованных пользователей
        with open("app/static/home.html", "r", encoding="utf-8") as file:
            return HTMLResponse(content=file.read())

    # Если токен действителен, показываем страницу для авторизованных пользователей
    username = payload.get("sub")
    with open("app/static/authenticated_home.html", "r", encoding="utf-8") as file:
        content = file.read().replace("{{ username }}", username)
        return HTMLResponse(content=content)


@app.post("/games/start/")
def start_game(
    current_user: ModelUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Создание новой игры."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    game = start_game_logic(current_user.id, db)
    return {"game_id": game.id}


@app.post("/games/join/")
def join_game(
    game_id: int,
    current_user: ModelUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Присоединение второго игрока к игре."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    game = join_game_logic(game_id, current_user.id, db)
    return {"game_id": game.id}


@app.get("/users/", response_model=list[SchemaUser])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Получение списка пользователей."""
    return get_users(db, skip=skip, limit=limit)


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

    # Сохраняем токен в cookies
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
def get_game_status(game_id: int, db: Session = Depends(get_db)):
    """Получение текущего состояния игры."""
    return get_game_status_logic(game_id, db)


@app.post("/games/{game_id}/move/")
def make_move_endpoint(game_id: int, move_data: dict, db: Session = Depends(get_db)):
    """Обработка хода игрока."""
    game = db.query(ModelGame).filter(ModelGame.id == game_id).first()
    if not game:
        print("Game not found def make_move_point")
        raise HTTPException(status_code=404, detail="Game not found")

    player_id = move_data.get("player_id")
    x, y = move_data.get("x"), move_data.get("y")

    # Определяем поле противника
    if player_id == game.player1_id:
        board = game.board_player2
    elif player_id == game.player2_id:
        board = game.board_player1
    else:
        raise HTTPException(status_code=403, detail="Not your turn")

    # Обрабатываем ход
    result = make_move(board, x, y)

    # Обновляем поле противника в базе данных
    if player_id == game.player1_id:
        game.board_player2 = board
    else:
        game.board_player1 = board

    db.commit()

    # Проверяем победителя
    if check_winner(board):
        game.status = "finished"
        game.winner_id = player_id

    return {"result": result, "status": game.status}


@app.websocket("/ws/{game_id}")
async def websocket_handler(websocket: WebSocket, game_id: int):
    try:
        # Получаем токен
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008, reason="Token is required")
            return

        # Проверяем токен
        payload = decode_token(token)
        if payload is None:
            print(f"Invalid token: {token}")
            await websocket.close(code=1008, reason="Invalid token")
            return

        # Получаем пользователя
        username = payload.get("sub")

        # Подключаемся к базе данных
        db: Session = SessionLocal()

        # Получаем игру
        game = db.query(ModelGame).filter(ModelGame.id == game_id).first()
        if not game:
            print(f"Game not found for ID: {game_id}")
            await websocket.close(code=1008, reason="Game not found")
            return

        # Если игра найдена, принимаем соединение
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Message text was: {data}, from client")
        except WebSocketDisconnect:
            pass

    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason=str(e))


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
