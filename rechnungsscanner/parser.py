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

# Tausendertrennzeichen nur als Punkt (Standard-Format), kein Leerzeichen - sonst
# verschmelzen in Tabellenzeilen benachbarte Zahlen (z.B. "1 220 108,96" aus
# "Anzahl Sendungen | Gew.(kg) | Netto EUR") faelschlich zu einer einzigen Zahl.
# (?!\d) verhindert zudem, dass z.B. "19,000" (3-stellige Prozentangabe wie
# "19,000 % USt") faelschlich als Betrag "19,00" erkannt wird.
_AMOUNT = r"(\d{1,3}(?:\.\d{3})*,\d{2})(?!\d)"
_DATE = r"(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{2,4})"

_LEGAL_FORMS = (
    r"\b(?:GmbH & Co\.? ?KG|GmbH|AG|KG|OHG|UG|e\.\s?K\.|GbR|mbH|SE)\b"
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

    if invoice_date and re.search(r"sofort\s*f[äa]llig", text, re.IGNORECASE):
        return invoice_date
    return None


def _all_amounts(text: str) -> list[float]:
    """Alle im Text vorkommenden Geldbetraege, eindeutig und absteigend sortiert."""
    values = {
        amount
        for m in re.finditer(_AMOUNT, text)
        if (amount := _to_amount(m.group(1))) is not None
    }
    return sorted(values, reverse=True)


def extract_amounts(text: str) -> dict:
    net_match = _find_labeled(
        text, [r"Netto(?:betrag)?", r"Zwischensumme", r"Summe\s*netto"], _AMOUNT
    )
    vat_match = _find_labeled(
        text, [r"(?:MwSt|USt|Umsatzsteuer)\.?\s*(?:\d{1,2}\s*%)?", r"Steuerbetrag"],
        _AMOUNT,
    )
    gross_match = _find_labeled(
        text,
        [r"Gesamtbetrag", r"Rechnungsbetrag", r"Gesamtsumme", r"Endbetrag",
         r"Bruttobetrag", r"Summe\s*brutto", r"Zu\s*zahlen"],
        _AMOUNT,
    )

    net = _to_amount(net_match.group(1)) if net_match else None
    vat = _to_amount(vat_match.group(1)) if vat_match else None
    gross = _to_amount(gross_match.group(1)) if gross_match else None

    # Fallback fuer tabellarische Rechnungen (z.B. Speditions-Sammelrechnungen),
    # bei denen Betraege in Tabellenspalten stehen statt in "Label: Wert"-Zeilen:
    # der groesste Betrag im Dokument ist so gut wie immer der Bruttogesamtbetrag,
    # der naechstkleinere davon typischerweise der Nettobetrag.
    if gross is None or net is None:
        amounts = _all_amounts(text)
        if amounts:
            if gross is None:
                gross = amounts[0]
            if net is None:
                smaller = [a for a in amounts if a < gross]
                if smaller:
                    net = smaller[0]

    if vat is None and gross is not None and net is not None:
        difference = round(gross - net, 2)
        if difference > 0:
            vat = difference

    currency = "EUR" if re.search(r"€|EUR", text) else ""

    return {
        "net": net,
        "vat": vat,
        "gross": gross,
        "currency": currency,
    }


_IBAN_PATTERN = r"([A-Z]{2}[ ]?\d{2}(?:[ ]?[A-Z0-9]{2,4}){2,7})"

# Offizielle IBAN-Gesamtlaenge je Land (ISO 13616) - damit die Regex (die aus
# Tabellenzeilen heraus leicht zu weit greift, z.B. bis in ein folgendes "BIC")
# zuverlaessig auf die korrekte Laenge gekappt werden kann.
_IBAN_LENGTHS = {
    "AD": 24, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24,
    "DE": 22, "DK": 18, "EE": 20, "ES": 24, "FI": 18, "FR": 27, "GB": 22,
    "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IS": 26, "IT": 27, "LI": 21,
    "LT": 20, "LU": 20, "LV": 21, "MC": 27, "MT": 31, "NL": 18, "NO": 15,
    "PL": 28, "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27,
}


def _normalize_iban(raw: str) -> str:
    compact = re.sub(r"\s+", "", raw).upper()
    length = _IBAN_LENGTHS.get(compact[:2])
    if length:
        compact = compact[:length]
    return " ".join(compact[i : i + 4] for i in range(0, len(compact), 4))


def extract_iban(text: str) -> str:
    # Manche Rechnungen (z.B. bei SEPA-Lastschrift) nennen zuerst die eigene
    # IBAN des Kunden (Mandatsreferenz) und erst danach, im Abschnitt
    # "Bankverbindung", die tatsaechliche Empfaenger-IBAN. Diese hat Vorrang.
    bankverbindung = re.search(r"Bankverbindung.{0,200}", text, re.IGNORECASE | re.DOTALL)
    if bankverbindung:
        match = re.search(rf"\bIBAN\b\s*[:.\-]?\s*{_IBAN_PATTERN}", bankverbindung.group(0), re.IGNORECASE)
        if match:
            return _normalize_iban(match.group(1))

    match = re.search(rf"\bIBAN\b\s*[:.\-]?\s*{_IBAN_PATTERN}", text, re.IGNORECASE)
    if not match:
        # Ohne "IBAN:"-Label nur echte Grossbuchstaben als Laendercode akzeptieren,
        # sonst werden zufaellige Wortenden (z.B. "Konto" -> "to") als IBAN erkannt.
        match = re.search(rf"\b{_IBAN_PATTERN}\b", text)
    if match:
        return _normalize_iban(match.group(1))
    return ""


_BIC_PATTERN = r"\bBIC\b\s*[:.\-]?\s*([A-Z0-9]{8}(?:[A-Z0-9]{3})?)\b"


def extract_bic(text: str) -> str:
    # Gleiche Vorrangregel wie bei der IBAN: die BIC im Abschnitt
    # "Bankverbindung" ist die tatsaechlich relevante, nicht eine evtl. vorher
    # genannte BIC eines SEPA-Lastschrift-Mandats.
    bankverbindung = re.search(r"Bankverbindung.{0,200}", text, re.IGNORECASE | re.DOTALL)
    if bankverbindung:
        match = re.search(_BIC_PATTERN, bankverbindung.group(0), re.IGNORECASE)
        if match:
            return match.group(1).upper()

    match = re.search(_BIC_PATTERN, text, re.IGNORECASE)
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
