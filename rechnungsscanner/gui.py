"""Tkinter-Oberfläche: Rechnungen auswählen, OCR-Ergebnis kontrollieren, nach Excel exportieren."""

import tkinter as tk
import traceback
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import config as cfg
from . import excel_export, ocr
from .parser import FIELDS, parse_invoice_text

FILE_TYPES = [
    ("Rechnungen (PDF/Bild)", "*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp"),
    ("Alle Dateien", "*.*"),
]

DATE_FIELDS = {"Rechnungsdatum", "Zahlungsziel", "Verarbeitet am"}
AMOUNT_FIELDS = {"Nettobetrag", "MwSt-Betrag", "Bruttobetrag"}


def _format_value(field: str, value) -> str:
    if value is None:
        return ""
    if field in DATE_FIELDS and isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if field in AMOUNT_FIELDS and isinstance(value, (int, float)):
        return f"{value:.2f}".replace(".", ",")
    return str(value)


def _parse_value(field: str, text: str):
    text = text.strip()
    if not text:
        return None
    if field in DATE_FIELDS:
        for fmt in ("%d.%m.%Y", "%d.%m.%y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"'{text}' ist kein gültiges Datum (Format: TT.MM.JJJJ)")
    if field in AMOUNT_FIELDS:
        try:
            return float(text.replace(".", "").replace(",", "."))
        except ValueError:
            raise ValueError(f"'{text}' ist kein gültiger Betrag")
    return text


class ReviewDialog(tk.Toplevel):
    """Zeigt die erkannten Felder einer Rechnung zur Kontrolle/Korrektur an."""

    def __init__(self, parent, filename: str, raw_text: str, data: dict):
        super().__init__(parent)
        self.title(f"Rechnung prüfen – {filename}")
        self.geometry("820x600")
        self.transient(parent)
        self.grab_set()

        self.result: str | None = None  # "accept", "skip" oder "cancel_all"
        self.entries: dict[str, tk.Entry] = {}

        container = ttk.Frame(self, padding=10)
        container.pack(side="left", fill="y")

        ttk.Label(container, text=f"Datei: {filename}", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        for i, field in enumerate(FIELDS, start=1):
            if field == "Dateiname":
                continue
            ttk.Label(container, text=field + ":").grid(row=i, column=0, sticky="w", pady=3)
            entry = ttk.Entry(container, width=32)
            entry.insert(0, _format_value(field, data.get(field)))
            entry.grid(row=i, column=1, sticky="w", pady=3, padx=(6, 0))
            self.entries[field] = entry

        button_frame = ttk.Frame(container)
        button_frame.grid(row=len(FIELDS) + 1, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(button_frame, text="In Excel übernehmen", command=self._accept).pack(
            side="left", padx=4
        )
        ttk.Button(button_frame, text="Überspringen", command=self._skip).pack(side="left", padx=4)
        ttk.Button(button_frame, text="Rest abbrechen", command=self._cancel_all).pack(
            side="left", padx=4
        )

        text_frame = ttk.Frame(self, padding=10)
        text_frame.pack(side="right", fill="both", expand=True)
        ttk.Label(text_frame, text="Erkannter Text (OCR):").pack(anchor="w")
        text_widget = tk.Text(text_frame, wrap="word")
        text_widget.insert("1.0", raw_text)
        text_widget.configure(state="disabled")
        text_widget.pack(fill="both", expand=True)

        self.data = dict(data)
        self.protocol("WM_DELETE_WINDOW", self._skip)

    def _accept(self):
        try:
            for field, entry in self.entries.items():
                self.data[field] = _parse_value(field, entry.get())
        except ValueError as exc:
            messagebox.showerror("Ungültiger Wert", str(exc), parent=self)
            return
        self.result = "accept"
        self.destroy()

    def _skip(self):
        self.result = "skip"
        self.destroy()

    def _cancel_all(self):
        self.result = "cancel_all"
        self.destroy()


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, config: dict, on_save):
        super().__init__(parent)
        self.title("Einstellungen")
        self.geometry("560x200")
        self.transient(parent)
        self.grab_set()
        self.on_save = on_save

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Pfad zu tesseract.exe:").grid(row=0, column=0, sticky="w")
        self.tesseract_var = tk.StringVar(value=config.get("tesseract_path", ""))
        ttk.Entry(frame, textvariable=self.tesseract_var, width=55).grid(row=1, column=0, pady=(2, 10))
        ttk.Button(frame, text="Durchsuchen...", command=self._browse_tesseract).grid(
            row=1, column=1, padx=6
        )

        ttk.Label(frame, text="Excel-Datei:").grid(row=2, column=0, sticky="w")
        self.excel_var = tk.StringVar(value=config.get("excel_path", ""))
        ttk.Entry(frame, textvariable=self.excel_var, width=55).grid(row=3, column=0, pady=(2, 10))
        ttk.Button(frame, text="Durchsuchen...", command=self._browse_excel).grid(
            row=3, column=1, padx=6
        )

        ttk.Button(frame, text="Speichern", command=self._save).grid(row=4, column=0, pady=(10, 0))

    def _browse_tesseract(self):
        path = filedialog.askopenfilename(
            title="tesseract.exe auswählen", filetypes=[("Programm", "tesseract.exe")]
        )
        if path:
            self.tesseract_var.set(path)

    def _browse_excel(self):
        path = filedialog.asksaveasfilename(
            title="Excel-Datei wählen", defaultextension=".xlsx",
            filetypes=[("Excel-Datei", "*.xlsx")],
        )
        if path:
            self.excel_var.set(path)

    def _save(self):
        self.on_save(self.tesseract_var.get().strip(), self.excel_var.get().strip())
        self.destroy()


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rechnungsscanner")
        self.geometry("700x460")

        self.config_data = cfg.load_config()
        self.files: list[str] = []

        self._build_menu()
        self._build_widgets()
        self._update_status_labels()

    def _build_menu(self):
        menu = tk.Menu(self)
        settings_menu = tk.Menu(menu, tearoff=0)
        settings_menu.add_command(label="Einstellungen...", command=self._open_settings)
        menu.add_cascade(label="Datei", menu=settings_menu)
        self.config(menu=menu)

    def _build_widgets(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Button(top, text="Rechnungen auswählen...", command=self._select_files).pack(side="left")
        ttk.Button(top, text="Liste leeren", command=self._clear_files).pack(side="left", padx=6)
        ttk.Button(
            top, text="Verarbeiten und nach Excel übertragen", command=self._process_files
        ).pack(side="right")

        self.listbox = tk.Listbox(self, selectmode="extended")
        self.listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        status_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        status_frame.pack(fill="x")
        self.tesseract_label = ttk.Label(status_frame)
        self.tesseract_label.pack(anchor="w")
        self.excel_label = ttk.Label(status_frame)
        self.excel_label.pack(anchor="w")

        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=(0, 10))

    def _update_status_labels(self):
        tpath = self.config_data.get("tesseract_path") or "(nicht gesetzt)"
        self.tesseract_label.config(text=f"Tesseract: {tpath}")
        self.excel_label.config(text=f"Excel-Datei: {self.config_data.get('excel_path')}")

    def _open_settings(self):
        def on_save(tesseract_path, excel_path):
            self.config_data["tesseract_path"] = tesseract_path
            self.config_data["excel_path"] = excel_path
            cfg.save_config(self.config_data)
            self._update_status_labels()

        SettingsDialog(self, self.config_data, on_save)

    def _select_files(self):
        paths = filedialog.askopenfilenames(title="Gescannte Rechnungen auswählen", filetypes=FILE_TYPES)
        for path in paths:
            if path not in self.files:
                self.files.append(path)
                self.listbox.insert("end", Path(path).name)

    def _clear_files(self):
        self.files.clear()
        self.listbox.delete(0, "end")

    def _process_files(self):
        if not self.files:
            messagebox.showinfo("Keine Dateien", "Bitte zuerst Rechnungen auswählen.")
            return
        if not self.config_data.get("tesseract_path"):
            messagebox.showwarning(
                "Tesseract fehlt",
                "Bitte in den Einstellungen den Pfad zu tesseract.exe hinterlegen.",
            )
            return

        ocr.configure_tesseract(self.config_data["tesseract_path"])
        self.progress.configure(maximum=len(self.files), value=0)

        accepted, skipped, failed = 0, 0, 0
        remaining_files = list(self.files)

        for index, file_path in enumerate(remaining_files):
            filename = Path(file_path).name
            self.progress.configure(value=index)
            self.update_idletasks()

            try:
                raw_text = ocr.extract_text(file_path, self.config_data.get("language", "deu"))
                data = parse_invoice_text(raw_text, filename=filename)
            except Exception:
                failed += 1
                messagebox.showerror(
                    "Fehler bei der Texterkennung",
                    f"{filename}:\n{traceback.format_exc(limit=1)}",
                )
                continue

            dialog = ReviewDialog(self, filename, raw_text, data)
            self.wait_window(dialog)

            if dialog.result == "accept":
                try:
                    excel_export.append_invoice(self.config_data["excel_path"], dialog.data)
                    accepted += 1
                except PermissionError as exc:
                    messagebox.showerror("Excel-Datei gesperrt", str(exc))
                    failed += 1
            elif dialog.result == "skip":
                skipped += 1
            else:  # cancel_all
                break

        self.progress.configure(value=len(remaining_files))
        messagebox.showinfo(
            "Fertig",
            f"Übernommen: {accepted}\nÜbersprungen: {skipped}\nFehler: {failed}",
        )
        self._clear_files()


def run():
    app = MainWindow()
    app.mainloop()
