"""Terminal Tetris - modern guideline rules, no third-party packages.

    terminal-tetris [--no-color] [--level N] [--seed N]
"""
from __future__ import annotations

import argparse
import time

from . import engine, scores
from .render import Renderer
from .terminal import RawTerminal, supports_unicode, terminal_size

FRAME = 1.0 / 60.0
REDRAW = 1.0 / 30.0
SIZE_POLL = 0.5

KEY_ACTIONS = {
    "LEFT": "left",
    "a": "left",
    "RIGHT": "right",
    "d": "right",
    "DOWN": "soft",
    "s": "soft",
    "SPACE": "hard",
    "w": "hard",
    "UP": "cw",
    "x": "cw",
    "z": "ccw",
    "f": "flip",
    "c": "hold",
    "p": "pause",
    "r": "restart",
}
QUIT_KEYS = {"q", "CTRL_C", "ESC"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="terminal-tetris", description="Terminal Tetris"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="no escape colors"
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="plain ASCII blocks and borders (auto when the console cannot "
        "encode box drawing characters)",
    )
    parser.add_argument("--level", type=int, default=1, help="starting level (1-20)")
    parser.add_argument("--seed", type=int, default=None, help="fixed piece order")
    parser.add_argument(
        "--no-records",
        action="store_true",
        help="do not read or write the personal record file",
    )
    parser.add_argument(
        "--reset-records",
        action="store_true",
        help="delete the personal record file and quit",
    )
    parser.add_argument(
        "--keytest",
        action="store_true",
        help="print the key names this terminal delivers, then quit on Q",
    )
    return parser.parse_args(argv)


def keytest() -> int:
    """Diagnostic: show what read_keys() sees, one line per keypress."""
    print("Tuslara bas, cikis icin Q. Gordugum isimler:")
    with RawTerminal(alt_screen=False) as term:
        while True:
            for key in term.read_keys():
                action = KEY_ACTIONS.get(key, "-")
                term.write(f"  {key!r:>12}  ->  {action}\r\n")
                if key in QUIT_KEYS:
                    return 0
            time.sleep(FRAME)


def reset_records() -> int:
    path = scores.records_path()
    if scores.clear(path):
        print(f"Rekor dosyasi silindi: {path}")
        return 0
    print(f"Rekor dosyasi silinemedi: {path}")
    return 1


def run(args: argparse.Namespace) -> int:
    game = engine.Game(level=args.level, seed=args.seed)
    records = scores.Records() if args.no_records else scores.load()

    def store() -> None:
        """Fold the finished run into the records and write them out."""
        nonlocal records
        records = records.merged(game)
        if not args.no_records:
            scores.save(records)

    with RawTerminal() as term:
        # The console encoding is only final once the terminal is set up.
        use_unicode = not args.ascii and supports_unicode()
        renderer = Renderer(color=not args.no_color, unicode=use_unicode)
        cols, rows = terminal_size()
        previous = time.perf_counter()
        since_redraw = REDRAW
        since_size = 0.0

        while True:
            now = time.perf_counter()
            dt = now - previous
            previous = now

            actions: list[str] = []
            for key in term.read_keys():
                if key in QUIT_KEYS:
                    # Quitting mid-run still counts: the lines, combo and
                    # time reached so far are worth keeping.
                    store()
                    return 0
                action = KEY_ACTIONS.get(key)
                if action:
                    actions.append(action)

            was_playing = game.phase == engine.PLAYING
            game.update(dt, actions)
            if was_playing and game.phase == engine.GAME_OVER:
                store()

            since_size += dt
            if since_size >= SIZE_POLL:
                since_size = 0.0
                new_size = terminal_size()
                if new_size != (cols, rows):
                    cols, rows = new_size
                    term.write("\x1b[2J")

            since_redraw += dt
            if since_redraw >= REDRAW or actions:
                since_redraw = 0.0
                term.write(renderer.frame(game, cols, rows, records))

            slack = FRAME - (time.perf_counter() - now)
            if slack > 0:
                time.sleep(slack)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.reset_records:
        return reset_records()
    try:
        return keytest() if args.keytest else run(args)
    except KeyboardInterrupt:
        return 0

