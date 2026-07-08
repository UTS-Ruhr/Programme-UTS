"""Wandelt gescannte Rechnungen (PDF/JPG/PNG) per OCR in Text um."""

from pathlib import Path

import pytesseract
from PIL import Image

PDF_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# Rendert PDF-Seiten mit hoher Auflösung, damit die OCR auch kleine Schrift erkennt.
PDF_RENDER_ZOOM = 3.0


class OcrError(RuntimeError):
    pass


def configure_tesseract(tesseract_path: str) -> None:
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path


def extract_text(file_path: str, language: str = "deu") -> str:
    """Liest den vollständigen Text einer gescannten Rechnung (PDF oder Bild)."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in PDF_SUFFIXES:
        images = _render_pdf_pages(path)
    elif suffix in IMAGE_SUFFIXES:
        images = [Image.open(path)]
    else:
        raise OcrError(f"Nicht unterstütztes Dateiformat: {suffix}")

    try:
        texts = [pytesseract.image_to_string(image, lang=language) for image in images]
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrError(
            "Tesseract-OCR wurde nicht gefunden. Bitte den Pfad zu tesseract.exe "
            "in den Einstellungen hinterlegen."
        ) from exc

    return "\n".join(texts)


def _render_pdf_pages(path: Path) -> list:
    import fitz  # PyMuPDF

    images = []
    matrix = fitz.Matrix(PDF_RENDER_ZOOM, PDF_RENDER_ZOOM)
    with fitz.open(path) as document:
        for page in document:
            pixmap = page.get_pixmap(matrix=matrix)
            mode = "RGB" if pixmap.alpha == 0 else "RGBA"
            image = Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)
            images.append(image)
    if not images:
        raise OcrError(f"PDF enthält keine Seiten: {path.name}")
    return images
