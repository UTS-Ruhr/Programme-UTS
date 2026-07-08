"""Extrahiert strukturierte Rechnungsdaten (Datum, Betrag, IBAN, usw.) aus OCR-Rohtext.

Die Erkennung basiert auf Schlüsselwörtern und Mustern, wie sie auf deutschen
Rechnungen üblich sind. Da OCR nie fehlerfrei ist, dient das Ergebnis als
Vorschlag, der vom Anwender in der Kontrollmaske geprüft/korrigiert wird.
"""

import re
from datetime import date, timedelta

# Reihenfolge = Spaltenreihenfolge in der Excel-Datei.
FIELDS = [
    "Dateiname",
    "Unternehmensname",
    "Rechnungsnummer",
    "Rechnungsdatum",
    "Zahlungsziel",
    "Nettobetrag",
    "MwSt-Betrag",
    "Bruttobetrag",
    "Waehrung",
    "IBAN",
    "BIC",
    "USt-IdNr / Steuernummer",
    "Verarbeitet am",
]

_AMOUNT = r"(\d{1,3}(?:[.\s]\d{3})*,\d{2})"
_DATE = r"(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{2,4})"

_LEGAL_FORMS = (
    r"GmbH & Co\. ?KG|GmbH|AG|KG|OHG|UG|e\.\s?K\.|GbR|mbH|SE"
)


def _to_amount(raw: str) -> float | None:
    if not raw:
        return None
    try:
        return float(raw.replace(".", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _to_date(day: str, month: str, year: str) -> date | None:
    try:
        d, m, y = int(day), int(month), int(year)
        if y < 100:
            y += 2000 if y < 50 else 1900
        return date(y, m, d)
    except ValueError:
        return None


def _find_labeled(text: str, labels: list[str], value_pattern: str, flags=re.IGNORECASE):
    for label in labels:
        match = re.search(rf"{label}\s*[:.\-]?\s*{value_pattern}", text, flags)
        if match:
            return match
    return None


def extract_invoice_number(text: str) -> str:
    match = _find_labeled(
        text,
        [r"Rechnungs(?:-)?nummer", r"Rechnungs(?:-)?nr\.?", r"Rechnung\s*Nr\.?",
         r"Beleg(?:-)?nummer", r"Invoice\s*(?:No|Number)"],
        r"([A-Z0-9][A-Z0-9\-/\.]{2,20})",
    )
    return match.group(1).strip() if match else ""


def extract_invoice_date(text: str) -> date | None:
    match = _find_labeled(
        text,
        [r"Rechnungsdatum", r"Rechnungs-?Datum", r"Beleg(?:-)?datum", r"Datum"],
        _DATE,
    )
    if not match:
        match = re.search(_DATE, text)
    if match:
        return _to_date(*match.groups())
    return None


def extract_due_date(text: str, invoice_date: date | None) -> date | None:
    match = _find_labeled(
        text,
        [r"Zahlungsziel", r"F[äa]llig(?:keitsdatum)?(?:\s*am)?", r"zahlbar\s*bis"],
        _DATE,
    )
    if match:
        return _to_date(*match.groups())

    days_match = re.search(
        r"(?:Zahlungsziel|zahlbar\s*innerhalb|netto)\D{0,15}?(\d{1,3})\s*Tage",
        text,
        re.IGNORECASE,
    )
    if days_match and invoice_date:
        return invoice_date + timedelta(days=int(days_match.group(1)))
    return None


def extract_amounts(text: str) -> dict:
    net = _find_labeled(
        text, [r"Netto(?:betrag)?", r"Zwischensumme", r"Summe\s*netto"], _AMOUNT
    )
    vat = _find_labeled(
        text, [r"(?:MwSt|USt|Umsatzsteuer)\.?\s*(?:\d{1,2}\s*%)?", r"Steuerbetrag"],
        _AMOUNT,
    )
    gross = _find_labeled(
        text,
        [r"Gesamtbetrag", r"Rechnungsbetrag", r"Gesamtsumme", r"Endbetrag",
         r"Bruttobetrag", r"Summe\s*brutto", r"Zu\s*zahlen"],
        _AMOUNT,
    )

    currency = "EUR" if re.search(r"€|EUR", text) else ""

    return {
        "net": _to_amount(net.group(1)) if net else None,
        "vat": _to_amount(vat.group(1)) if vat else None,
        "gross": _to_amount(gross.group(1)) if gross else None,
        "currency": currency,
    }


def extract_iban(text: str) -> str:
    match = re.search(r"\bIBAN\b\s*[:.\-]?\s*([A-Z]{2}[ ]?\d{2}(?:[ ]?[A-Z0-9]{2,4}){2,7})", text, re.IGNORECASE)
    if not match:
        match = re.search(r"\b([A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7})\b", text)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip().upper()
    return ""


def extract_bic(text: str) -> str:
    match = re.search(r"\bBIC\b\s*[:.\-]?\s*([A-Z0-9]{8}(?:[A-Z0-9]{3})?)\b", text, re.IGNORECASE)
    return match.group(1).upper() if match else ""


def extract_tax_id(text: str) -> str:
    match = _find_labeled(
        text,
        [r"USt(?:\.|-)?\s*Id(?:ent)?(?:-)?Nr\.?", r"USt(?:\.|-)?ID", r"Steuernummer",
         r"St\.?-?Nr\.?"],
        r"([A-Z]{0,2}\s?[\d\s/]{7,15})",
    )
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def extract_company_name(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:15]:
        if re.search(_LEGAL_FORMS, line):
            return line
    return lines[0] if lines else ""


def parse_invoice_text(text: str, filename: str = "") -> dict:
    """Erkennt alle relevanten Felder in einem OCR-Rohtext und liefert sie als dict."""
    invoice_date = extract_invoice_date(text)
    amounts = extract_amounts(text)

    return {
        "Dateiname": filename,
        "Unternehmensname": extract_company_name(text),
        "Rechnungsnummer": extract_invoice_number(text),
        "Rechnungsdatum": invoice_date,
        "Zahlungsziel": extract_due_date(text, invoice_date),
        "Nettobetrag": amounts["net"],
        "MwSt-Betrag": amounts["vat"],
        "Bruttobetrag": amounts["gross"],
        "Waehrung": amounts["currency"],
        "IBAN": extract_iban(text),
        "BIC": extract_bic(text),
        "USt-IdNr / Steuernummer": extract_tax_id(text),
        "Verarbeitet am": date.today(),
    }
