# app/game_logic/utils.py


def make_move(board, x, y):
    """Обработка хода игрока."""
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


def make_move(board, x, y):
    """Обработка хода игрока."""
    if board[x][y] == "S":
        board[x][y] = "X"  # Попадание
        return "hit"
    elif board[x][y] == "~":
        board[x][y] = "O"  # Промах
        return "miss"
    else:
        return "already_hit"
