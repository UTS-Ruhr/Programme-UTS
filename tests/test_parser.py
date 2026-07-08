from datetime import date

from rechnungsscanner.parser import parse_invoice_text

SAMPLE_INVOICE = """
Mustermann GmbH
Musterstraße 1
12345 Musterstadt

Rechnung

Rechnungsnummer: RE-2026-00123
Rechnungsdatum: 01.07.2026
Kundennummer: K-4711

Leistungsbeschreibung ...

Nettobetrag: 1.000,00 €
MwSt. 19%: 190,00 €
Gesamtbetrag: 1.190,00 €

Zahlungsziel: 14 Tage netto

Bankverbindung:
IBAN: DE89 3704 0044 0532 0130 00
BIC: COBADEFFXXX
USt-IdNr: DE123456789
"""


def test_parse_invoice_extracts_all_fields():
    data = parse_invoice_text(SAMPLE_INVOICE, filename="rechnung1.pdf")

    assert data["Dateiname"] == "rechnung1.pdf"
    assert data["Unternehmensname"] == "Mustermann GmbH"
    assert data["Rechnungsnummer"] == "RE-2026-00123"
    assert data["Rechnungsdatum"] == date(2026, 7, 1)
    assert data["Zahlungsziel"] == date(2026, 7, 15)
    assert data["Nettobetrag"] == 1000.00
    assert data["MwSt-Betrag"] == 190.00
    assert data["Bruttobetrag"] == 1190.00
    assert data["Waehrung"] == "EUR"
    assert data["IBAN"] == "DE89 3704 0044 0532 0130 00"
    assert data["BIC"] == "COBADEFFXXX"
    assert data["USt-IdNr / Steuernummer"] == "DE123456789"


def test_due_date_from_explicit_date():
    text = "Rechnungsdatum: 01.07.2026\nZahlungsziel: 20.07.2026\nGesamtbetrag: 50,00 €"
    data = parse_invoice_text(text)
    assert data["Zahlungsziel"] == date(2026, 7, 20)


def test_company_name_fallback_to_first_line():
    text = "Beispielhandel\nRechnungsdatum: 01.07.2026\n"
    data = parse_invoice_text(text)
    assert data["Unternehmensname"] == "Beispielhandel"


def test_missing_fields_are_none_or_empty():
    data = parse_invoice_text("Ein Text ohne jegliche Rechnungsdaten.")
    assert data["IBAN"] == ""
    assert data["Nettobetrag"] is None
    assert data["Rechnungsdatum"] is None
