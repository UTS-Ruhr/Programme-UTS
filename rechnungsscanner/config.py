"""Laden und Speichern der Anwendungseinstellungen (Pfade zu Tesseract und Excel-Datei)."""

import json
import os
import sys
from pathlib import Path

APP_NAME = "RechnungsScanner"

DEFAULT_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_file() -> Path:
    return _config_dir() / "config.json"


def bundled_tesseract_dir() -> Path | None:
    """Ordner mit der in die .exe eingebauten Tesseract-Kopie, falls vorhanden.

    PyInstaller entpackt Onedir-Builds neben die .exe (sys._MEIPASS zeigt dann
    auf den Programmordner, nicht auf einen temporären Ordner).
    """
    if not getattr(sys, "frozen", False):
        return None
    candidate = Path(sys._MEIPASS) / "tesseract"
    return candidate if (candidate / "tesseract.exe").exists() else None


def guess_tesseract_path() -> str:
    bundled = bundled_tesseract_dir()
    if bundled:
        return str(bundled / "tesseract.exe")
    for candidate in DEFAULT_TESSERACT_PATHS:
        if Path(candidate).exists():
            return candidate
    return ""


def load_config() -> dict:
    defaults = {
        "tesseract_path": guess_tesseract_path(),
        "excel_path": str(_config_dir() / "Rechnungen.xlsx"),
        "language": "deu",
    }
    config_file = _config_file()
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            defaults.update(data)
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def save_config(config: dict) -> None:
    _config_file().write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
