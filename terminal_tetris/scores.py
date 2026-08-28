"""Kişisel rekorların diske yazılması.

Tek iş: JSON oku/yaz. Motoru ve terminali tanımaz, hiçbir zaman istisna
sızdırmaz — bozuk ya da yazılamayan bir rekor dosyası oyunu durdurmamalı.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

APP_DIR = "terminal-tetris"
FILE_NAME = "records.json"
VERSION = 1

TRACKED = ("score", "lines", "level", "combo", "time")
LABELS = {
    "score": "SKOR",
    "lines": "SATIR",
    "level": "SEVIYE",
    "combo": "COMBO",
    "time": "SURE",
}


@dataclass
class Records:
    score: int = 0
    lines: int = 0
    # The first level is where everyone starts, so it is not an achievement.
    level: int = 1
    combo: int = 0
    time: float = 0.0
    date: str = ""

    def beats(self, game) -> list[str]:
        """Bu oyunun kırdığı rekor alanlarının adları."""
        current = from_game(game)
        return [
            name
            for name in TRACKED
            if getattr(current, name) > getattr(self, name)
        ]

    def merged(self, game) -> "Records":
        """Her alanın en iyisini alan yeni bir kayıt."""
        current = from_game(game)
        broken = self.beats(game)
        values = {
            name: max(getattr(self, name), getattr(current, name))
            for name in TRACKED
        }
        date = datetime.now().strftime("%Y-%m-%d") if broken else self.date
        return replace(self, date=date, **values)


def from_game(game) -> Records:
    """Motorun anlık durumunu rekor biçimine çevirir."""
    return Records(
        score=game.score,
        lines=game.lines,
        level=game.level,
        combo=max(game.max_combo, 0),
        time=game.elapsed,
    )


def records_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or Path.home()
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_DIR / FILE_NAME


def load(path: Path | None = None) -> Records:
    """Dosya yoksa, bozuksa ya da okunamıyorsa boş bir kayıt döner."""
    path = Path(path) if path else records_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Records()
    best = data.get("best") if isinstance(data, dict) else None
    if not isinstance(best, dict):
        return Records()
    records = Records()
    for name in TRACKED:
        value = best.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        setattr(records, name, float(value) if name == "time" else int(value))
    date = best.get("date")
    if isinstance(date, str):
        records.date = date
    return records


def save(records: Records, path: Path | None = None) -> bool:
    """Geçici dosya + os.replace ile atomik yazar. Başarısızsa False."""
    path = Path(path) if path else records_path()
    payload = {
        "version": VERSION,
        "best": {name: getattr(records, name) for name in TRACKED},
    }
    payload["best"]["date"] = records.date
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2)
            os.replace(temp, path)
        except BaseException:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise
    except (OSError, ValueError):
        return False
    return True


def clear(path: Path | None = None) -> bool:
    """Rekor dosyasını siler. Zaten yoksa da True."""
    path = Path(path) if path else records_path()
    try:
        path.unlink()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True
