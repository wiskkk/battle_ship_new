# app/game_logic/board.py

import random


def generate_board(size=10):
    """Генерация пустого игрового поля."""
    return [["~" for _ in range(size)] for _ in range(size)]


def place_ships_auto(board, ships=[4, 3, 3, 2, 2, 2, 1, 1, 1, 1]):
    """Автоматическое размещение кораблей на поле."""
    for ship_size in ships:
        placed = False
        attempts = 0
        while not placed and attempts < 100:  # Ограничиваем количество попыток
            orientation = random.choice(["horizontal", "vertical"])
            x, y = random.randint(0, len(board) - 1), random.randint(0, len(board) - 1)

            if can_place_ship(board, x, y, ship_size, orientation):
                place_ship_on_board(board, x, y, ship_size, orientation)
                placed = True
            attempts += 1

        if not placed:
            # Если не удалось разместить корабль, возвращаем новую доску
            return place_ships_auto(generate_board())

    return board


def place_ship_manual(board, x, y, size, orientation):
    """Ручное размещение корабля на поле."""
    if can_place_ship(board, x, y, size, orientation):
        place_ship_on_board(board, x, y, size, orientation)
        return True
    return False


def can_place_ship(board, x, y, size, orientation):
    """Проверка, можно ли разместить корабль на поле."""
    board_size = len(board)

    # Проверяем границы
    if orientation == "horizontal":
        if y + size > board_size:
            return False
        cells_to_check = [(x, y + i) for i in range(size)]
    elif orientation == "vertical":
        if x + size > board_size:
            return False
        cells_to_check = [(x + i, y) for i in range(size)]
    else:
        return False

    # Проверяем, свободны ли клетки и клетки вокруг них
    for cx, cy in cells_to_check:
        # Проверяем саму клетку
        if board[cx][cy] != "~":
            return False

        # Проверяем клетки вокруг (чтобы корабли не касались)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < board_size and 0 <= ny < board_size:
                    if board[nx][ny] == "S":
                        return False

    return True


def place_ship_on_board(board, x, y, size, orientation):
    """Размещение корабля на доске."""
    if orientation == "horizontal":
        for i in range(size):
            board[x][y + i] = "S"
    elif orientation == "vertical":
        for i in range(size):
            board[x + i][y] = "S"


def check_ship_placement(board, x, y, size, orientation):
    """Проверка, можно ли разместить корабль на поле (алиас для совместимости)."""
    return can_place_ship(board, x, y, size, orientation)


def place_ships(board, ships_data):
    """Размещение списка кораблей на поле.
    ships_data: список кортежей (size, orientation, x, y)
    """
    for size, orientation, x, y in ships_data:
        if not place_ship_manual(board, x, y, size, orientation):
            return False
    return board
