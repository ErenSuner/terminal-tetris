"""The playfield grid: collision, locking and line clearing.

The board is 10 x 40. Only the bottom 20 rows are drawn; the hidden rows
above give rotations and spawns room to work, as the guideline expects.
"""
from __future__ import annotations

WIDTH = 10
HEIGHT = 40
VISIBLE = 20
HIDDEN = HEIGHT - VISIBLE


class Board:
    def __init__(self) -> None:
        self.grid: list[list[int]] = [[0] * WIDTH for _ in range(HEIGHT)]

    def at(self, x: int, y: int) -> int:
        if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
            return -1  # out of bounds counts as solid
        return self.grid[y][x]

    def fits(self, cells, x: int, y: int) -> bool:
        for cx, cy in cells:
            px, py = x + cx, y + cy
            if px < 0 or px >= WIDTH or py >= HEIGHT:
                return False
            if py >= 0 and self.grid[py][px]:
                return False
        return True

    def drop_distance(self, cells, x: int, y: int) -> int:
        distance = 0
        while self.fits(cells, x, y + distance + 1):
            distance += 1
        return distance

    def lock(self, cells, x: int, y: int, color: int) -> None:
        for cx, cy in cells:
            px, py = x + cx, y + cy
            if 0 <= py < HEIGHT and 0 <= px < WIDTH:
                self.grid[py][px] = color

    def clear_lines(self) -> list[int]:
        """Remove full rows, returning their indexes (top-down order)."""
        full = [y for y in range(HEIGHT) if all(self.grid[y])]
        for y in full:
            del self.grid[y]
            self.grid.insert(0, [0] * WIDTH)
        return full

    def visible_rows(self) -> list[list[int]]:
        return self.grid[HIDDEN:]
