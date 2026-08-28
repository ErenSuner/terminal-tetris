"""Game rules: gravity, lock delay, 7-bag, hold, scoring, T-spins.

Knows nothing about terminals or drawing, so tests drive it directly.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from . import pieces
from .board import HIDDEN, Board

PLAYING = "playing"
PAUSED = "paused"
GAME_OVER = "game_over"

SPAWN_X = 3
SPAWN_Y = HIDDEN  # first visible row
NEXT_COUNT = 5
LOCK_DELAY = 0.5
MAX_LOCK_RESETS = 15
LINES_PER_LEVEL = 10

LINE_SCORES = {1: 100, 2: 300, 3: 500, 4: 800}
TSPIN_SCORES = {0: 400, 1: 800, 2: 1200, 3: 1600}
TSPIN_MINI_SCORES = {0: 100, 1: 200, 2: 400}

# T corners in box coordinates, and which two are "front" per rotation.
_T_CORNERS = ((0, 0), (2, 0), (0, 2), (2, 2))
_T_FRONT = {0: (0, 1), 1: (1, 3), 2: (2, 3), 3: (0, 2)}


@dataclass
class Piece:
    kind: str
    rotation: int = 0
    x: int = SPAWN_X
    y: int = SPAWN_Y

    @property
    def cells(self):
        return pieces.cells(self.kind, self.rotation)


@dataclass
class ClearInfo:
    """What the last lock produced, for the render layer to announce."""

    lines: int = 0
    tspin: str = ""  # "", "mini" or "full"
    back_to_back: bool = False
    combo: int = 0
    points: int = 0

    @property
    def label(self) -> str:
        if self.tspin:
            base = "T-SPIN" + (" MINI" if self.tspin == "mini" else "")
            names = {0: "", 1: " SINGLE", 2: " DOUBLE", 3: " TRIPLE"}
            return base + names.get(self.lines, "")
        return {1: "SINGLE", 2: "DOUBLE", 3: "TRIPLE", 4: "TETRIS"}.get(self.lines, "")


class Game:
    def __init__(self, level: int = 1, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.start_level = max(1, level)
        self.reset()

    # ---- lifecycle -----------------------------------------------------
    def reset(self) -> None:
        self.board = Board()
        self.bag: list[str] = []
        self.queue: list[str] = []
        self._refill_queue()
        self.hold: str | None = None
        self.hold_used = False
        self.score = 0
        self.lines = 0
        self.level = self.start_level
        self.combo = -1
        self.back_to_back = False
        self.phase = PLAYING
        self.gravity_acc = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.lowest_y = -1
        self.elapsed = 0.0
        self.last_clear = ClearInfo()
        self.max_combo = 0
        # When the last clear happened, so the banner can time itself out.
        self.last_clear_at = -99.0
        self.last_move_was_rotation = False
        self.last_kick_index = 0
        self.piece = None
        self._spawn()

    def _refill_queue(self) -> None:
        while len(self.queue) <= NEXT_COUNT:
            if not self.bag:
                self.bag = list(pieces.TYPES)
                self.rng.shuffle(self.bag)
            self.queue.append(self.bag.pop())

    def _spawn(self, kind: str | None = None) -> None:
        if kind is None:
            kind = self.queue.pop(0)
            self._refill_queue()
        self.piece = Piece(kind)
        self.hold_used = False
        self.gravity_acc = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.lowest_y = self.piece.y
        self.last_move_was_rotation = False
        if not self.board.fits(self.piece.cells, self.piece.x, self.piece.y):
            self.phase = GAME_OVER

    # ---- timing --------------------------------------------------------
    @property
    def gravity_interval(self) -> float:
        """Guideline fall speed: seconds per row at the current level."""
        level = min(self.level, 20)
        return max((0.8 - (level - 1) * 0.007) ** (level - 1), 0.001)

    # ---- movement ------------------------------------------------------
    def _try_move(self, dx: int, dy: int) -> bool:
        p = self.piece
        if not self.board.fits(p.cells, p.x + dx, p.y + dy):
            return False
        p.x += dx
        p.y += dy
        self.last_move_was_rotation = False
        self._touch_lock_timer(moved_down=dy > 0)
        return True

    def _try_rotate(self, turn: int) -> bool:
        p = self.piece
        target = (p.rotation + turn) % 4
        cells = pieces.cells(p.kind, target)
        for index, (dx, dy) in enumerate(pieces.kicks(p.kind, p.rotation, target)):
            if self.board.fits(cells, p.x + dx, p.y + dy):
                p.rotation = target
                p.x += dx
                p.y += dy
                self.last_move_was_rotation = True
                self.last_kick_index = index
                self._touch_lock_timer(moved_down=dy > 0)
                return True
        return False

    def _touch_lock_timer(self, moved_down: bool) -> None:
        if moved_down and self.piece.y > self.lowest_y:
            self.lowest_y = self.piece.y
            self.lock_resets = 0
            self.lock_timer = 0.0
        elif self._grounded() and self.lock_resets < MAX_LOCK_RESETS:
            self.lock_resets += 1
            self.lock_timer = 0.0

    def _grounded(self) -> bool:
        p = self.piece
        return not self.board.fits(p.cells, p.x, p.y + 1)

    def hold_piece(self) -> None:
        if self.hold_used:
            return
        current = self.piece.kind
        if self.hold is None:
            self.hold = current
            self._spawn()
        else:
            self.hold, kind = current, self.hold
            self._spawn(kind)
        self.hold_used = True

    def hard_drop(self) -> None:
        p = self.piece
        distance = self.board.drop_distance(p.cells, p.x, p.y)
        p.y += distance
        self.score += 2 * distance
        if distance:
            self.last_move_was_rotation = False
        self._lock_piece()

    # ---- locking and scoring -------------------------------------------
    def _detect_tspin(self) -> str:
        p = self.piece
        if p.kind != "T" or not self.last_move_was_rotation:
            return ""
        filled = [self.board.at(p.x + cx, p.y + cy) != 0 for cx, cy in _T_CORNERS]
        front_a, front_b = _T_FRONT[p.rotation]
        front = filled[front_a] + filled[front_b]
        if sum(filled) < 3:
            return ""
        if front == 2:
            return "full"
        # A last-resort kick promotes a mini into a full T-spin.
        return "full" if self.last_kick_index == 4 else "mini"

    def _lock_piece(self) -> None:
        p = self.piece
        tspin = self._detect_tspin()
        self.board.lock(p.cells, p.x, p.y, pieces.COLORS[p.kind])
        cleared = len(self.board.clear_lines())

        if cleared:
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.last_clear_at = self.elapsed
        else:
            self.combo = -1

        if tspin:
            table = TSPIN_MINI_SCORES if tspin == "mini" else TSPIN_SCORES
            points = table.get(cleared, TSPIN_SCORES[3]) * self.level
        elif cleared:
            points = LINE_SCORES[cleared] * self.level
        else:
            points = 0

        chained = False
        difficult = bool(tspin) or cleared == 4
        if cleared and difficult:
            chained = self.back_to_back
            if chained:
                points = int(points * 1.5)
            self.back_to_back = True
        elif cleared:
            self.back_to_back = False

        if self.combo > 0:
            points += 50 * self.combo * self.level

        self.score += points
        self.lines += cleared
        self.level = self.start_level + self.lines // LINES_PER_LEVEL
        self.last_clear = ClearInfo(
            lines=cleared,
            tspin=tspin,
            back_to_back=chained,
            combo=max(self.combo, 0),
            points=points,
        )

        # Lock out: the piece came to rest entirely in the hidden rows.
        if all(p.y + cy < HIDDEN for _, cy in p.cells):
            self.phase = GAME_OVER
            return
        self._spawn()

    # ---- main step -----------------------------------------------------
    def update(self, dt: float, actions: list[str]) -> None:
        for action in actions:
            if action == "pause":
                if self.phase == PLAYING:
                    self.phase = PAUSED
                elif self.phase == PAUSED:
                    self.phase = PLAYING
            elif action == "restart":
                self.reset()

        if self.phase != PLAYING:
            return

        self.elapsed += dt
        for action in actions:
            if action == "left":
                self._try_move(-1, 0)
            elif action == "right":
                self._try_move(1, 0)
            elif action == "soft":
                if self._try_move(0, 1):
                    self.score += 1
                    self.gravity_acc = 0.0
            elif action == "hard":
                self.hard_drop()
                return
            elif action == "cw":
                self._try_rotate(1)
            elif action == "ccw":
                self._try_rotate(-1)
            elif action == "flip":
                self._try_rotate(2)
            elif action == "hold":
                self.hold_piece()
            if self.phase != PLAYING:
                return

        self.gravity_acc += dt
        interval = self.gravity_interval
        while self.gravity_acc >= interval:
            self.gravity_acc -= interval
            if not self._try_move(0, 1):
                break

        if self._grounded():
            self.lock_timer += dt
            if self.lock_timer >= LOCK_DELAY:
                self._lock_piece()
        else:
            self.lock_timer = 0.0

    # ---- view helpers --------------------------------------------------
    def ghost_y(self) -> int:
        p = self.piece
        return p.y + self.board.drop_distance(p.cells, p.x, p.y)
