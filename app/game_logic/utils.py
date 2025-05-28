# app/game_logic/utils.py

import json


def make_move(board, x, y):
    """Обработка хода игрока."""
    # Проверяем границы
    if x < 0 or x >= len(board) or y < 0 or y >= len(board[0]):
        return "invalid"

    if board[x][y] == "S":
        board[x][y] = "X"  # Попадание
        return "hit"
    elif board[x][y] == "~":
        board[x][y] = "O"  # Промах
        return "miss"
    else:
        return "already_hit"


def check_winner(board):
    """Проверка, все ли корабли уничтожены."""
    return all(cell != "S" for row in board for cell in row)


def serialize_board(board):
    """Преобразование доски в JSON строку."""
    return json.dumps(board)


def deserialize_board(board_str):
    """Преобразование JSON строки в доску."""
    if not board_str:
        return None
    return json.loads(board_str)
