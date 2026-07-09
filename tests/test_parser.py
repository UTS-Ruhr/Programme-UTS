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


# Nachgebauter OCR-Text einer echten Speditions-Sammelrechnung (DACHSER-Layout):
# Betraege stehen in Tabellenspalten statt in "Label: Wert"-Zeilen, und es gibt
# zwei IBANs (SEPA-Lastschrift-Mandat + tatsaechliche Bankverbindung).
TABLE_INVOICE = """
DACHSER SE
Logistikzentrum Hamburg

Umformtechnik Stade GmbH
Ohle Kamp 12
21684 Stade

SUMMENRECHNUNG NATIONAL EINGANG
Datum: 01.07.2026 Rechnungs-Nr.: 0040495258 Kunden-Nr.: 47156531

Zeilennr Datum Anzahl Sendungen Gew.(kg) Netto EUR Steuer
001 29.06.2026 1 220 108,96 A
220 108,96

Steuer Netto EUR % USt Steuercode Steuerbetrag EUR Brutto EUR
A 108,96 19,000 DE 20,70 129,66
129,66

Rechnungen sind sofort fällig.

Der Rechnungsbetrag wird am 15.07.2026 von Ihrem Konto eingezogen.
IBAN: DE82241510051210234298
BIC: NOLADE21STS

Bankverbindung: HypoVereinsbank Hamburg, Konto 4402699
IBAN: DE41 2003 0000 0004 4026 99 BIC: HYVEDEMM300
"""


def test_table_style_invoice_extracts_amounts_and_correct_iban():
    data = parse_invoice_text(TABLE_INVOICE, filename="dachser.pdf")

    assert data["Unternehmensname"] == "DACHSER SE"
    assert data["Rechnungsnummer"] == "0040495258"
    assert data["Rechnungsdatum"] == date(2026, 7, 1)
    assert data["Bruttobetrag"] == 129.66
    assert data["Nettobetrag"] == 108.96
    assert data["MwSt-Betrag"] == 20.70
    assert data["IBAN"] == "DE41 2003 0000 0004 4026 99"
    assert data["BIC"] == "HYVEDEMM300"
    assert data["Zahlungsziel"] == date(2026, 7, 1)


# Nachgebauter OCR-Text einer echten Lieferantenrechnung (VETTER-Layout):
# eigener Firmenname (Empfaenger) erscheint im Anschriftenfeld ebenfalls mit
# Rechtsform und darf nicht mit dem Rechnungssteller verwechselt werden;
# Betraege stehen als "GESAMT Netto/Brutto"/"Steuer" statt Standardlabels;
# Zahlungsziel steht unter "Zahlungsbedingung"; Bankdaten ohne "IBAN:"/"BIC:"-
# Label in einer reinen Banktabelle.
VETTER_INVOICE = """
VETTER Stahlhandel GmbH
D-27612 Loxstedt - Fon +49.471.97988.0
Amtsgericht Tostedt - HRB 204086 - GF: Carsten Vetter
USt-IdNr.: DE 151 090 109 - Steuer-Nr.: 49 200 10515

Vetter Stahlhandel GmbH - Postfach 10 10 47 - 27510 Bremerhaven

Umformtechnik Stade GmbH
Ohle Kamp 12
21684 Stade

Rechnung
Rechnungs-Nr. : 4334066
Datum : 30.06.2026
Kunden-Nr. : 13314

Pos Bezeichnung Anzahl Gewicht Preis Gesamtpreis
1 Edelstahlblech 1 STK 80,000 KG 3,20 € 256,00 €
2 Transportschutz 1 STK 20,00 € 10,00 €

Zahlungsbedingung
13.09.2026 ohne Abzug

GESAMT Netto 266,00 €
+ 19,00% Steuer 50,54 €
GESAMT Brutto 316,54 €

Weser-Elbe Sparkasse BRLADE21BRS DE27 2925 0000 0100 0170 37
Stadtsparkasse Cuxhaven BRLADE21CUX DE19 2415 0001 0000 1008 91
"""


def test_recipient_own_company_not_mistaken_for_vendor():
    data = parse_invoice_text(VETTER_INVOICE, filename="vetter.pdf")

    assert data["Unternehmensname"] == "VETTER Stahlhandel GmbH"
    assert data["Rechnungsnummer"] == "4334066"
    assert data["Rechnungsdatum"] == date(2026, 6, 30)
    assert data["Zahlungsziel"] == date(2026, 9, 13)
    assert data["Nettobetrag"] == 266.00
    assert data["MwSt-Betrag"] == 50.54
    assert data["Bruttobetrag"] == 316.54
    assert data["IBAN"] == "DE27 2925 0000 0100 0170 37"
    assert data["BIC"] == "BRLADE21BRS"
