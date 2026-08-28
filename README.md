# Terminal Tetris

[![PyPI](https://img.shields.io/pypi/v/tetris-tui)](https://pypi.org/project/tetris-tui/)
[![Tests](https://github.com/ErenSuner/terminal-tetris/actions/workflows/ci.yml/badge.svg)](https://github.com/ErenSuner/terminal-tetris/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/tetris-tui)](https://pypi.org/project/tetris-tui/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Modern guideline Tetris, played in your terminal. Pure Python 3 —
**no pip packages required**.

## Install

```
pip install tetris-tui        # or: pipx install tetris-tui
```

Straight from source, no PyPI needed:

```
pipx install git+https://github.com/ErenSuner/terminal-tetris
```

## Run the game:
```
terminal-tetris
```

From a clone, with nothing installed at all:

```
git clone https://github.com/ErenSuner/terminal-tetris
cd terminal-tetris
python tetris.py
```

The installed command is `terminal-tetris`; `python -m terminal_tetris` works
too. Windows, macOS and Linux terminals are all supported (Windows uses
`msvcrt` plus a console-mode call for ANSI, POSIX uses `termios` + `select`).

<img width="607" height="560" alt="normal" src="https://github.com/user-attachments/assets/ec6af562-564e-407f-acd0-b93f04596dde" />


## Controls

| Key | Action |
| --- | --- |
| ← / → or A / D | Move left / right |
| ↓ or S | Soft drop (1 point per cell) |
| Space or W | Hard drop (2 points per cell), locks instantly |
| ↑ or X | Rotate clockwise |
| Z | Rotate counter-clockwise |
| F | Rotate 180° |
| C | Hold (once per piece) |
| P | Pause / resume |
| R | Restart after a game over |
| Q or Esc | Quit |

## Flags

| Flag | What it does |
| --- | --- |
| `--level N` | Starting level (default 1; speed caps at 20) |
| `--seed N` | Fixes the piece order — repeatable games |
| `--no-color` | Draws without color escape sequences |
| `--ascii` | Plain ASCII instead of box and block characters |
| `--keytest` | Prints the key names your terminal delivers (input diagnostics) |
| `--no-records` | Neither reads nor writes the record file |
| `--reset-records` | Deletes the record file and exits |

`--ascii` turns itself on when the console code page cannot encode box drawing
characters.

But even if it can encode, I strongly recommenf to try `terminal-tetris --ascii`.

<img width="616" height="510" alt="ascii" src="https://github.com/user-attachments/assets/b2e06b1d-8021-4af0-9ba3-8c864b854e6a" />

## Rules

Follows guideline Tetris:

- **SRS rotation** with wall kick tables (the I piece uses its own table), plus
  a simple 180° kick set.
- **7-bag randomness**: all seven tetrominoes in every window of seven pieces.
- **Hold** + a five-piece next queue + ghost piece.
- **Lock delay** of 0.5 s; moves and rotations reset the timer, at most 15
  times (no infinite spin).
- **Scoring**: single 100, double 300, triple 500, tetris 800 (× level).
  T-spin 400/800/1200/1600, T-spin mini 100/200/400. Back-to-back difficult
  clears (tetris or T-spin) ×1.5. Combo is `50 × combo × level`.
- **Level** goes up every 10 lines; drop speed is
  `(0.8 - (level-1) × 0.007) ^ (level-1)` seconds per row.

## Combo and records

- **Combo meter**: the `COMBO` bar in the left panel fills while the chain
  holds (`x3 ▓▓▓░░`) and empties when it breaks. The banner also prints the
  points earned: `B2B TETRIS  x3 COMBO  +1800`.
- **Personal records**: score, lines, level, longest combo and time are each
  tracked separately. The panel shows the `BEST` score; it turns gold the
  moment you pass it in-game, and the screen prints `YENI REKOR!` on game over.
  Records are written on game over and on quit — the lines and combo of an
  unfinished run count too.
  File: `%APPDATA%\terminal-tetris\records.json` on Windows, otherwise
  `$XDG_DATA_HOME` or `~/.local/share/terminal-tetris/records.json`.
  If the file is missing or corrupt the game silently starts from zero.

There is no animation in the playfield: whatever the engine holds is what gets
drawn. Flashes, drop trails and border glows were tried and removed — they
broke the retro feel.

## Structure

```
tetris.py                     run from a clone
terminal_tetris/cli.py        entry point: flags, main loop, key mapping
terminal_tetris/terminal.py   raw mode, non-blocking key reads, alt screen, UTF-8
terminal_tetris/pieces.py     tetromino shapes, SRS rotation and kick tables
terminal_tetris/board.py      10x40 playfield: collision, locking, line clears
terminal_tetris/engine.py     gravity, lock delay, 7-bag, hold, scoring, T-spin
terminal_tetris/render.py     ANSI frame builder and panels
terminal_tetris/scores.py     atomic JSON writes for personal records
```

`board`, `pieces` and `engine` know nothing about the terminal; the tests drive
the engine directly.

## Tests

```
python -m unittest discover -s tests -t .
```

`.github/workflows/ci.yml` runs the same suite on Linux, macOS and Windows
against Python 3.9 and 3.13 for every push and pull request.

## Notes

- Terminals do not report key-up events, so real DAS/ARR tuning is impossible;
  the OS key repeat rate sets the horizontal repeat speed.
- Below 46x24 the game does not crash, it shows a warning.
- The key help on the bottom row is packed to fit the window: with room to
  spare, key + action spread over several lines; in a narrow window the labels
  drop but every key stays visible.
- Every exit path, Ctrl+C included, restores the cursor, echo and normal screen.
- Banner lifetime is measured through `game.elapsed`: the engine stamps the
  time of the last clear and the renderer looks at its age. Pausing stops that
  clock too.

## Releasing

Publishing runs on GitHub Actions via PyPI Trusted Publishing — no API token
is stored. Bump `version` in `pyproject.toml`, then:

```
git tag v1.0.0
git push origin v1.0.0
```

`.github/workflows/release.yml` runs the tests on Linux/macOS/Windows against
Python 3.9 and 3.13, checks that the tag matches the packaged version, builds
the sdist and wheel, and uploads them to PyPI.

## License

MIT — see [LICENSE](LICENSE).
