"""Platform shim: raw-mode keyboard input and ANSI screen control.

Stdlib only. Windows uses msvcrt plus a console-mode call to turn on ANSI
escape processing; POSIX uses termios + select.
"""
from __future__ import annotations

import atexit
import os
import shutil
import sys

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import ctypes
    import msvcrt
else:
    import select
    import termios
    import tty

ENTER_ALT_SCREEN = "\x1b[?1049h"
EXIT_ALT_SCREEN = "\x1b[?1049l"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
CLEAR_SCREEN = "\x1b[2J"
CLEAR_LINE = "\x1b[K"
HOME = "\x1b[H"
RESET = "\x1b[0m"

_WIN_SPECIAL = {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}
_POSIX_SPECIAL = {"A": "UP", "B": "DOWN", "D": "LEFT", "C": "RIGHT"}

_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
_STD_OUTPUT_HANDLE = -11
_UTF8_CODEPAGE = 65001


def enable_ansi() -> bool:
    """Turn on ANSI escape handling for the console. True if usable."""
    if not IS_WINDOWS:
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(
            kernel32.SetConsoleMode(
                handle, mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
            )
        )
    except Exception:
        return False


def enable_utf8() -> int | None:
    """Switch the console to UTF-8. Returns the previous code page."""
    previous = None
    if IS_WINDOWS:
        try:
            kernel32 = ctypes.windll.kernel32
            previous = kernel32.GetConsoleOutputCP()
            kernel32.SetConsoleOutputCP(_UTF8_CODEPAGE)
        except Exception:
            previous = None
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return previous


def restore_codepage(previous: int | None) -> None:
    if IS_WINDOWS and previous:
        try:
            ctypes.windll.kernel32.SetConsoleOutputCP(previous)
        except Exception:
            pass


def supports_unicode() -> bool:
    """Can the current stdout encoding carry the box-drawing characters?"""
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "┌─│└┘▒█·←→↓".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def _normalize(ch: str) -> str:
    if ch == " ":
        return "SPACE"
    if ch in ("\r", "\n"):
        return "ENTER"
    if ch == "\x1b":
        return "ESC"
    if ch == "\x03":
        return "CTRL_C"
    return ch.lower()


def terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return size.columns, size.lines


class RawTerminal:
    """Context manager owning the alternate screen and raw keyboard mode.

    Restoration runs from __exit__, atexit and on an unhandled crash, so a
    broken game never leaves the user with a hidden cursor or no echo.
    """

    def __init__(self, alt_screen: bool = True) -> None:
        self._fd = None
        self._saved = None
        self._active = False
        self._pending = ""
        self._codepage = None
        self._alt_screen = alt_screen

    def __enter__(self) -> "RawTerminal":
        enable_ansi()
        self._codepage = enable_utf8()
        if not IS_WINDOWS:
            self._fd = sys.stdin.fileno()
            try:
                self._saved = termios.tcgetattr(self._fd)
                tty.setcbreak(self._fd)
            except termios.error:
                self._saved = None
        self._active = True
        atexit.register(self.restore)
        if self._alt_screen:
            self.write(ENTER_ALT_SCREEN + HIDE_CURSOR + CLEAR_SCREEN)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.restore()
        return False

    def restore(self) -> None:
        if not self._active:
            return
        self._active = False
        if not IS_WINDOWS and self._saved is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
            except termios.error:
                pass
        self.write(RESET + SHOW_CURSOR)
        if self._alt_screen:
            self.write(EXIT_ALT_SCREEN)
        restore_codepage(self._codepage)

    def write(self, text: str) -> None:
        try:
            sys.stdout.write(text)
        except UnicodeEncodeError:
            encoding = getattr(sys.stdout, "encoding", None) or "ascii"
            sys.stdout.write(text.encode(encoding, "replace").decode(encoding))
        sys.stdout.flush()

    def read_keys(self) -> list[str]:
        """Drain the whole input queue and return normalized key names."""
        if IS_WINDOWS:
            return self._read_windows()
        return self._read_posix()

    def _read_windows(self) -> list[str]:
        keys: list[str] = []
        while msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                # The second half of a special key is always already in the
                # queue, but kbhit() does not always admit it, so read it
                # unconditionally rather than dropping the keypress.
                name = _WIN_SPECIAL.get(msvcrt.getwch())
                if name:
                    keys.append(name)
                continue
            if ch == "\x1b" and msvcrt.kbhit():
                # Some consoles deliver arrows as VT sequences instead.
                if msvcrt.getwch() == "[" and msvcrt.kbhit():
                    name = _POSIX_SPECIAL.get(msvcrt.getwch())
                    if name:
                        keys.append(name)
                    continue
                keys.append("ESC")
                continue
            keys.append(_normalize(ch))
        return keys

    def _read_posix(self) -> list[str]:
        buffer = self._pending
        while select.select([self._fd], [], [], 0)[0]:
            chunk = os.read(self._fd, 64)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", "ignore")
        keys: list[str] = []
        i = 0
        while i < len(buffer):
            ch = buffer[i]
            if ch == "\x1b" and i + 2 < len(buffer) and buffer[i + 1] == "[":
                name = _POSIX_SPECIAL.get(buffer[i + 2])
                if name:
                    keys.append(name)
                    i += 3
                    continue
            if ch == "\x1b" and i + 1 >= len(buffer):
                # Possibly a truncated escape sequence: wait for the rest.
                break
            keys.append(_normalize(ch))
            i += 1
        self._pending = buffer[i:]
        return keys
