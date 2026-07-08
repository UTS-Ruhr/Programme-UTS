# Rechnungsscanner

Windows-Anwendung, die gescannte Rechnungen (PDF, JPG, PNG) per OCR ausliest
und die erkannten Daten – nach kurzer Kontrolle durch den Anwender – als neue
Zeile in eine zentrale Excel-Datei überträgt.

Erkannte Felder: Dateiname, Unternehmensname, Rechnungsnummer, Rechnungsdatum,
Zahlungsziel, Netto-/MwSt-/Bruttobetrag, Währung, IBAN, BIC,
USt-IdNr/Steuernummer, Verarbeitungsdatum.

## Ablauf

1. Rechnungen (bereits gescannt als PDF/JPG/PNG) auswählen.
2. Die App liest jede Datei per OCR (Tesseract) aus und erkennt die Felder
   automatisch anhand typischer Schlüsselwörter auf deutschen Rechnungen.
3. Für jede Rechnung erscheint eine Kontrollmaske mit den erkannten Werten
   und dem OCR-Rohtext daneben – Werte können vor der Übernahme korrigiert
   werden (OCR ist nie zu 100 % fehlerfrei).
4. Nach Bestätigung wird die Rechnung als neue Zeile in die Excel-Datei
   geschrieben (Datei wird beim ersten Mal automatisch mit Kopfzeile angelegt).

## Fertige .exe herunterladen (kein Python, kein Tesseract-Setup nötig)

Bei jedem Push baut die GitHub-Actions-Pipeline
(`.github/workflows/build-windows.yml`) automatisch eine fertige,
in sich geschlossene Windows-Anwendung mit eingebauter Tesseract-Kopie:

1. Im GitHub-Repository auf **Actions** → Workflow **"Windows-Build
   (Rechnungsscanner .exe)"** gehen.
2. Den neuesten (grünen) Lauf öffnen.
3. Unter **Artifacts** die Datei **Rechnungsscanner-Windows** herunterladen
   und entpacken.
4. `Rechnungsscanner.exe` doppelklicken – fertig, keine weitere Installation
   nötig.

## Voraussetzungen (nur für den Start aus dem Quellcode)

- Python 3.10 oder neuer (https://www.python.org/downloads/)
- Tesseract-OCR für Windows, inkl. deutschem Sprachpaket:
  https://github.com/UB-Mannheim/tesseract/wiki
  - Beim Installieren unter "Additional language data" **Deutsch** auswählen.
  - Standardmäßig landet `tesseract.exe` unter
    `C:\Program Files\Tesseract-OCR\tesseract.exe` – die App findet den Pfad
    automatisch; alternativ lässt er sich in den Einstellungen der App setzen.

## Installation (Entwicklung / aus dem Quellcode starten)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Als eigenständige .exe bauen (manuell, ohne GitHub Actions)

```bash
pip install -r requirements-dev.txt
pyinstaller rechnungsscanner.spec
```

Die fertige Anwendung liegt danach unter `dist\Rechnungsscanner\Rechnungsscanner.exe`.
Wird der Build lokal ausgeführt (ohne den `vendor\tesseract`-Ordner, den nur
die GitHub-Actions-Pipeline anlegt), muss Tesseract-OCR auf dem Zielrechner
weiterhin separat installiert sein.

## Einstellungen

Über das Menü *Datei → Einstellungen* lassen sich Pfad zu `tesseract.exe` und
die Excel-Zieldatei ändern. Die Einstellungen werden unter
`%APPDATA%\RechnungsScanner\config.json` gespeichert.

## Hinweise zur Erkennungsgenauigkeit

Die automatische Erkennung basiert auf Schlüsselwörtern (z. B. "Rechnungsdatum",
"IBAN", "Gesamtbetrag", "Zahlungsziel") und gängigen Formaten auf deutschen
Rechnungen. Bei stark abweichenden Layouts oder schlechter Scan-Qualität
können einzelne Felder leer bleiben oder falsch erkannt werden – deshalb die
Kontrollmaske vor jeder Übernahme in Excel.
