# app/game_logic/board.py

import random


def generate_board(size=10):
    """Генерация пустого игрового поля."""
    return [["~" for _ in range(size)] for _ in range(size)]


def place_ships(board, ships):
    """Размещение кораблей на поле."""
    for ship_size in ships:
        placed = False
        while not placed:
            orientation = random.choice(["horizontal", "vertical"])
            x, y = random.randint(0, len(board) - 1), random.randint(0, len(board) - 1)

            if orientation == "horizontal" and y + ship_size <= len(board):
                if all(board[x][y + i] == "~" for i in range(ship_size)):
                    for i in range(ship_size):
                        board[x][y + i] = "S"
                    placed = True

            elif orientation == "vertical" and x + ship_size <= len(board):
                if all(board[x + i][y] == "~" for i in range(ship_size)):
                    for i in range(ship_size):
                        board[x + i][y] = "S"
                    placed = True

    return board


def check_ship_placement(board, x, y, size, orientation):
    """Проверка, можно ли разместить корабль на поле."""
    if orientation == "horizontal":
        if y + size > len(board):
            return False
        for i in range(size):
            if board[x][y + i] != "~":
                return False
    elif orientation == "vertical":
        if x + size > len(board):
            return False
        for i in range(size):
            if board[x + i][y] != "~":
                return False
    return True
