"""ANSI frame composer.

Builds the whole screen as one string per frame. Nothing is ever cleared
mid-frame: the cursor goes home, each line is written and terminated with
an erase-to-end-of-line, which keeps the picture from flickering.

Nothing on the playfield animates: the board is drawn exactly as the engine
holds it. The only thing measured against `game.elapsed` is how long the
clear banner stays up.
"""
from __future__ import annotations

from . import engine, pieces
from .board import HIDDEN, VISIBLE, WIDTH
from .terminal import CLEAR_LINE, HOME, RESET

CELL_WIDTH = 2
BOARD_INNER = WIDTH * CELL_WIDTH
PANEL_INNER = 8
LEFT_WIDTH = PANEL_INNER + 4
MIN_COLS = LEFT_WIDTH + (BOARD_INNER + 2) + 2 + (PANEL_INNER + 2)
MIN_ROWS = VISIBLE + 4

DIM = "\x1b[38;5;238m"
LABEL = "\x1b[38;5;245m"
BRIGHT = "\x1b[38;5;255m"
GOLD = "\x1b[38;5;220m"
CYAN = "\x1b[38;5;51m"
MAGENTA = "\x1b[38;5;207m"
YELLOW = "\x1b[38;5;226m"
BANNER_TIME = 2.0

METER_CELLS = 5

# Two spaces between hints, so a key and its action stay one visual unit.
HINT_GAP = "  "
MAX_HINT_LINES = 3


UNICODE_CHARS = {
    "filled": "██",
    "ghost": "▒▒",
    "empty": "· ",
    "meter_on": "▓",
    "meter_off": "░",
    "tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│",
    "controls": (
        ("←→/AD", "hareket"), ("↓/S", "soft"), ("SPACE/W", "hard"),
        ("↑/X", "don"), ("Z", "ters"), ("F", "180"), ("C", "hold"),
        ("P", "duraklat"), ("R", "yeniden"), ("Q", "cikis"),
    ),
}

ASCII_CHARS = {
    "filled": "[]",
    "ghost": "::",
    "empty": " .",
    "meter_on": "#",
    "meter_off": ".",
    "tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|",
    "controls": (
        ("Ok/AD", "hareket"), ("S", "soft"), ("SPACE/W", "hard"),
        ("X", "don"), ("Z", "ters"), ("F", "180"), ("C", "hold"),
        ("P", "duraklat"), ("R", "yeniden"), ("Q", "cikis"),
    ),
}


class Renderer:
    def __init__(self, color: bool = True, unicode: bool = True) -> None:
        self.color = color
        self.chars = UNICODE_CHARS if unicode else ASCII_CHARS

    # ---- cell painting -------------------------------------------------
    def filled(self, color: int) -> str:
        block = self.chars["filled"]
        if not self.color:
            return block
        return f"\x1b[38;5;{color}m{block}{RESET}"

    def ghost(self, color: int) -> str:
        block = self.chars["ghost"]
        if not self.color:
            return block
        return f"\x1b[2;38;5;{color}m{block}{RESET}"

    def empty(self) -> str:
        cell = self.chars["empty"]
        if not self.color:
            return cell
        return f"{DIM}{cell}{RESET}"

    def _tint(self, text: str, code: str) -> str:
        return f"{code}{text}{RESET}" if self.color else text

    # ---- panels --------------------------------------------------------
    def _piece_preview(self, kind: str | None) -> list[str]:
        rows = [self.empty() * 4 for _ in range(2)]
        if kind is None:
            return rows
        cells = pieces.cells(kind, 0)
        min_x = min(x for x, _ in cells)
        min_y = min(y for _, y in cells)
        width = max(x for x, _ in cells) - min_x + 1
        offset = (4 - width) // 2
        grid = [[None] * 4 for _ in range(2)]
        for x, y in cells:
            gx, gy = x - min_x + offset, y - min_y
            if 0 <= gx < 4 and 0 <= gy < 2:
                grid[gy][gx] = pieces.COLORS[kind]
        return [
            "".join(self.filled(c) if c else self.empty() for c in row)
            for row in grid
        ]

    def _box(self, title: str, body: list[str]) -> list[str]:
        c = self.chars
        header = f" {title} ".ljust(PANEL_INNER, c["h"])
        top = c["tl"] + header + c["tr"]
        bottom = c["bl"] + c["h"] * PANEL_INNER + c["br"]
        lines = [top]
        lines += [c["v"] + row + c["v"] for row in body]
        lines.append(bottom)
        return lines

    def _stat(self, label: str, value: str, code: str = BRIGHT) -> list[str]:
        return [self._tint(f" {label}", LABEL), self._tint(f" {value}", code)]

    def _meter(self, combo: int) -> str:
        """Combo bar: one cell per chained clear, capped at the bar width."""
        c = self.chars
        filled = min(max(combo, 0), METER_CELLS)
        bar = c["meter_on"] * filled + c["meter_off"] * (METER_CELLS - filled)
        return f"x{combo} {bar}" if combo > 0 else f"-  {bar}"

    def _left_panel(self, game: engine.Game, records=None) -> list[str]:
        minutes, seconds = divmod(int(game.elapsed), 60)
        best = records.score if records else 0
        # A run that already passed the stored best is worth shouting about.
        best_code = GOLD if best and game.score > best else BRIGHT
        combo_code = YELLOW if game.combo > 0 else DIM

        lines = self._box("HOLD", self._piece_preview(game.hold))
        lines.append("")
        lines += self._stat("SCORE", f"{game.score}")
        lines.append("")
        lines += self._stat("BEST", f"{max(best, game.score)}", best_code)
        lines.append("")
        lines += self._stat("LEVEL", f"{game.level}")
        lines.append("")
        lines += self._stat("LINES", f"{game.lines}")
        lines.append("")
        lines += self._stat("COMBO", self._meter(game.combo), combo_code)
        lines.append("")
        lines += self._stat("TIME", f"{minutes:02d}:{seconds:02d}")
        return lines

    def _right_panel(self, game: engine.Game) -> list[str]:
        body: list[str] = []
        blank = self.empty() * 4
        for kind in game.queue[: engine.NEXT_COUNT]:
            if body:
                body.append(blank)
            body += self._piece_preview(kind)
        return self._box("NEXT", body)

    # ---- board ---------------------------------------------------------
    def _board_rows(self, game: engine.Game) -> list[list[str]]:
        rows = [[self.empty() for _ in range(WIDTH)] for _ in range(VISIBLE)]
        for y, line in enumerate(game.board.visible_rows()):
            for x, value in enumerate(line):
                if value:
                    rows[y][x] = self.filled(value)

        piece = game.piece
        if piece is not None and game.phase != engine.GAME_OVER:
            color = pieces.COLORS[piece.kind]
            for cx, cy in piece.cells:
                gy = game.ghost_y() + cy - HIDDEN
                gx = piece.x + cx
                if 0 <= gy < VISIBLE and 0 <= gx < WIDTH:
                    rows[gy][gx] = self.ghost(color)
            for cx, cy in piece.cells:
                py = piece.y + cy - HIDDEN
                px = piece.x + cx
                if 0 <= py < VISIBLE and 0 <= px < WIDTH:
                    rows[py][px] = self.filled(color)
        return rows

    def _overlay(self, rows: list[list[str]], title: str, subtitle: str) -> None:
        """Stamp centered text over the playfield, keeping cell alignment."""
        for offset, text in ((-1, title), (1, subtitle)):
            if not text:
                continue
            text = text[:BOARD_INNER]
            padded = text.center(BOARD_INNER)
            y = VISIBLE // 2 + offset
            for x in range(WIDTH):
                chunk = padded[x * CELL_WIDTH : (x + 1) * CELL_WIDTH]
                rows[y][x] = self._tint(chunk, BRIGHT)

    def _board_lines(self, game: engine.Game, records=None) -> list[str]:
        rows = self._board_rows(game)
        if game.phase == engine.PAUSED:
            self._overlay(rows, "PAUSED", "P ile devam")
        elif game.phase == engine.GAME_OVER:
            broken = records.beats(game) if records else []
            subtitle = "YENI REKOR!" if broken else "R yeniden  Q cikis"
            self._overlay(rows, "OYUN BITTI", subtitle)
        c = self.chars
        top = c["tl"] + c["h"] * BOARD_INNER + c["tr"]
        bottom = c["bl"] + c["h"] * BOARD_INNER + c["br"]
        side = c["v"]
        return [top] + [side + "".join(row) + side for row in rows] + [bottom]

    # ---- controls ------------------------------------------------------
    def _pack(self, hints: list[str], cols: int, allowed: int) -> list[str] | None:
        """Lay hints out over at most `allowed` lines, or None if they spill."""
        lines: list[str] = []
        current = ""
        for hint in hints:
            candidate = current + HINT_GAP + hint if current else " " + hint
            if len(candidate) <= cols:
                current = candidate
                continue
            if len(lines) + 1 == allowed or len(" " + hint) > cols:
                return None
            lines.append(current)
            current = " " + hint
        lines.append(current)
        return lines

    def _control_lines(self, cols: int, allowed: int) -> list[str]:
        """Every key hint, packed into as few lines as the width allows.

        The hints used to live on one clipped line, which quietly swallowed
        whatever did not fit - Z, C and Q among them. A narrow window drops
        the labels rather than the keys.
        """
        pairs = self.chars["controls"]
        full = [f"{key} {action}" for key, action in pairs]
        lines = self._pack(full, cols, allowed)
        if lines is None:
            lines = self._pack([key for key, _ in pairs], cols, allowed)
        if lines is None:
            lines = [" " + HINT_GAP.join(full)]
        return [line[:cols] for line in lines]

    # ---- banner --------------------------------------------------------
    def _banner(self, game: engine.Game) -> str:
        """The last clear, announced with its points, then faded out."""
        info = game.last_clear
        text = info.label
        if not text:
            return ""
        if not 0 <= game.elapsed - game.last_clear_at <= BANNER_TIME:
            return ""
        if info.combo:
            text += f"  x{info.combo} COMBO"
        if info.back_to_back:
            text = "B2B " + text
        if info.points:
            text += f"  +{info.points}"
        return text

    def _banner_code(self, game: engine.Game) -> str:
        info = game.last_clear
        if info.tspin:
            return MAGENTA
        if info.lines == 4:
            return CYAN
        if info.combo >= 2:
            return YELLOW
        return BRIGHT

    # ---- frame ---------------------------------------------------------
    def frame(
        self, game: engine.Game, cols: int, rows_available: int, records=None
    ) -> str:
        if cols < MIN_COLS or rows_available < MIN_ROWS:
            message = f"Terminal cok kucuk: {cols}x{rows_available}, "
            message += f"gereken {MIN_COLS}x{MIN_ROWS}"
            return HOME + message + CLEAR_LINE + "\n"

        left = self._left_panel(game, records)
        board = self._board_lines(game, records)
        right = self._right_panel(game)
        height = max(len(left), len(board), len(right))

        out: list[str] = []
        for i in range(height):
            left_cell = left[i] if i < len(left) else ""
            board_cell = board[i] if i < len(board) else ""
            right_cell = right[i] if i < len(right) else ""
            pad = " " * max(0, LEFT_WIDTH - _visible_len(left_cell))
            line = left_cell + pad + board_cell
            if right_cell:
                line += "  " + right_cell
            out.append(line + CLEAR_LINE)

        # The status lines are the only ones that can outgrow the board, and
        # a wrapped line would scroll the whole frame, so they get clipped.
        banner = (" " + self._banner(game))[:cols]
        out.append(self._tint(banner, self._banner_code(game)) + CLEAR_LINE)
        # A taller terminal gets the hints on more lines instead of losing
        # the tail of the list to clipping.
        spare = max(0, rows_available - MIN_ROWS)
        allowed = min(1 + spare, MAX_HINT_LINES)
        for line in self._control_lines(cols, allowed):
            out.append(self._tint(line, LABEL) + CLEAR_LINE)
        return HOME + "\n".join(out)


def _visible_len(text: str) -> int:
    """Length ignoring ANSI escape sequences."""
    length = 0
    i = 0
    while i < len(text):
        if text[i] == "\x1b":
            end = text.find("m", i)
            if end == -1:
                break
            i = end + 1
            continue
        length += 1
        i += 1
    return length
