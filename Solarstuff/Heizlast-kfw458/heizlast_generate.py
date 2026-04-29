"""
Heizlastberechnung PDF-Generator
=================================
Lernziel: Jinja2-Templates + Datenstrukturen + PDF-Erzeugung

Datenstruktur:  Python-Dictionary (später: aus Excel oder Ubakus.de-Export)
Template:       Jinja2 HTML-Template (raumblatt.html)
PDF-Ausgabe:    ReportLab über platypus (oder direkt HTML speichern)

Dieses Skript zeigt:
  1. Wie Daten als Python-Dict strukturiert werden
  2. Wie Jinja2 ein Template mit Daten befüllt
  3. Wie man das Ergebnis als HTML speichert (und mit WeasyPrint zu PDF)
"""

from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import json

# ──────────────────────────────────────────────
# 1. STAMMDATEN (Projekt & Firma)
#    → Hier trägst du deine eigenen Daten ein
# ──────────────────────────────────────────────

FIRMA = {
    "name":         "MH Heizung & Baddesign",
    "strasse":      "Bahnhofstraße 4",
    "ort":          "66424 Homburg-Jägersburg",
    "logo_kuerzel": "MH",
    "logo_zusatz":  "HEIZUNG & BADDESIGN",
}

PROJEKT = {
    "bezeichnung":  "3-in-2-Familienhaus",
    "datum":        "30.11.2025",
    "bauvorhaben":  "Kerstin Fels und Michael Bauer",
    "bauort":       "D66333 Völklingen",
}

# ──────────────────────────────────────────────
# 2. RAUMDATEN
#    Jeder Raum ist ein Dictionary.
#    "bauteile" ist eine Liste von Bauteilen.
#
#    Bauteile-Kürzel:
#      Aw = Außenwand
#      Af = Fenster (in Aw)
#      De = Decke
#      Fb = Fußboden
#
#    fx = Temperaturkorrekturfaktor
#      1.0 = grenzt an Außenluft
#      0.5 = grenzt an unbeheizten Raum (z.B. Keller)
#      0.0 = Innenwand (kein Verlust)
# ──────────────────────────────────────────────

RAEUME = [
    {
        "bezeichnung":   "Arbeiten 2",
        "t_aussen":      -9.1,
        "t_innen":       20,
        "delta_t":       29.1,
        "raumhoehe":     2.50,
        "flaeche":       11.03,
        "volumen":       27.57,
        "luftwechsel":   0.50,
        "bauteile": [
            # Außenwand (Aw Summe) – Bruttofläche inkl. Fenster
            {"name": "Aw 1",    "breite": 3.90, "hoehe": 2.50, "f_flaeche": 1.25,
             "a_brutto": 12.19, "a_abzug": 2.48, "a_netto": 9.71,
             "u_wert": 0.32, "fx": 1.0, "phi_t": 90.4},
            # Fenster (Abzugsfläche aus Aw)
            {"name": "Af (in Aw)", "breite": "", "hoehe": "", "f_flaeche": 1.00,
             "a_brutto": 2.48, "a_abzug": "", "a_netto": 2.48,
             "u_wert": 0.90, "fx": 1.0, "phi_t": 65.0},
            # Decke
            {"name": "De 1",    "breite": "", "hoehe": "", "f_flaeche": 1.00,
             "a_brutto": 11.03, "a_abzug": "", "a_netto": 11.03,
             "u_wert": 0.24, "fx": 1.0, "phi_t": ""},
            # Fußboden (grenzt an unbeheizten Keller → fx=0.5)
            {"name": "Fb 1",    "breite": "", "hoehe": "", "f_flaeche": 1.00,
             "a_brutto": 11.03, "a_abzug": "", "a_netto": 11.03,
             "u_wert": 0.30, "fx": 0.5, "phi_t": 48.1},
        ],
        "phi_t_gesamt":  203,
        "phi_v":         136,
        "phi_hl":        340,
        "spez_flaeche":  31,
        "spez_volumen":  12,
    },
    {
        "bezeichnung":   "Gäste-WC",
        "t_aussen":      -9.1,
        "t_innen":       20,
        "delta_t":       29.1,
        "raumhoehe":     2.50,
        "flaeche":       4.16,
        "volumen":       10.40,
        "luftwechsel":   0.50,
        "bauteile": [
            {"name": "Aw 1",       "breite": 1.60, "hoehe": 2.50, "f_flaeche": 1.25,
             "a_brutto": 5.00, "a_abzug": 1.20, "a_netto": 3.80,
             "u_wert": 0.32, "fx": 1.0, "phi_t": 35.4},
            {"name": "Af (in Aw)", "breite": "",   "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 1.20, "a_abzug": "", "a_netto": 1.20,
             "u_wert": 0.90, "fx": 1.0, "phi_t": 31.4},
            {"name": "De 1",       "breite": "",   "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 4.16, "a_abzug": "", "a_netto": 4.16,
             "u_wert": 0.24, "fx": 1.0, "phi_t": ""},
            {"name": "Fb 1",       "breite": "",   "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 4.16, "a_abzug": "", "a_netto": 4.16,
             "u_wert": 0.30, "fx": 0.5, "phi_t": 18.2},
        ],
        "phi_t_gesamt":  85,
        "phi_v":         51,
        "phi_hl":        136,
        "spez_flaeche":  33,
        "spez_volumen":  13,
    },
    {
        "bezeichnung":   "Wohnen/Essen/Kochen",
        "t_aussen":      -9.1,
        "t_innen":       20,
        "delta_t":       29.1,
        "raumhoehe":     2.50,
        "flaeche":       49.37,
        "volumen":       123.42,
        "luftwechsel":   0.50,
        "bauteile": [
            {"name": "Aw 1",       "breite": 23.80, "hoehe": 2.50, "f_flaeche": 1.25,
             "a_brutto": 74.38, "a_abzug": 21.96, "a_netto": 52.41,
             "u_wert": 0.32, "fx": 1.0, "phi_t": 488.1},
            {"name": "Af (in Aw)", "breite": "",    "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 21.96, "a_abzug": "", "a_netto": 21.96,
             "u_wert": 0.90, "fx": 1.0, "phi_t": 575.1},
            {"name": "De 1",       "breite": "",    "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 49.37, "a_abzug": "", "a_netto": 49.37,
             "u_wert": 0.24, "fx": 1.0, "phi_t": ""},
            {"name": "Fb 1",       "breite": "",    "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 49.37, "a_abzug": "", "a_netto": 49.37,
             "u_wert": 0.30, "fx": 0.5, "phi_t": 215.5},
        ],
        "phi_t_gesamt":  1279,
        "phi_v":         611,
        "phi_hl":        1889,
        "spez_flaeche":  38,
        "spez_volumen":  15,
    },
    {
        "bezeichnung":   "Ankleide/HWR",
        "t_aussen":      -9.1,
        "t_innen":       20,
        "delta_t":       29.1,
        "raumhoehe":     2.50,
        "flaeche":       10.97,
        "volumen":       27.43,
        "luftwechsel":   0.50,
        "bauteile": [
            {"name": "Aw 1",       "breite": 7.50, "hoehe": 2.50, "f_flaeche": 1.25,
             "a_brutto": 23.44, "a_abzug": 2.83, "a_netto": 20.61,
             "u_wert": 0.32, "fx": 1.0, "phi_t": 191.9},
            {"name": "Af (in Aw)", "breite": "",   "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 2.83, "a_abzug": "", "a_netto": 2.83,
             "u_wert": 0.90, "fx": 0.5, "phi_t": 38.3},
            {"name": "De 1",       "breite": "",   "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 10.97, "a_abzug": "", "a_netto": 10.97,
             "u_wert": 0.24, "fx": 1.0, "phi_t": ""},
            {"name": "Fb 1",       "breite": "",   "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 10.97, "a_abzug": "", "a_netto": 10.97,
             "u_wert": 0.30, "fx": 0.5, "phi_t": ""},
        ],
        "phi_t_gesamt":  304,
        "phi_v":         136,
        "phi_hl":        440,
        "spez_flaeche":  40,
        "spez_volumen":  16,
    },
    {
        "bezeichnung":   "Bad",
        "t_aussen":      -9.1,
        "t_innen":       24,   # ← Bad hat 24°C!
        "delta_t":       33.1,
        "raumhoehe":     2.50,
        "flaeche":       8.69,
        "volumen":       21.72,
        "luftwechsel":   0.50,
        "bauteile": [
            {"name": "Aw 1",       "breite": 3.40, "hoehe": 2.50, "f_flaeche": 1.25,
             "a_brutto": 10.63, "a_abzug": 2.40, "a_netto": 8.23,
             "u_wert": 0.32, "fx": 1.0, "phi_t": 87.1},
            {"name": "Af (in Aw)", "breite": "",   "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 2.40, "a_abzug": "", "a_netto": 2.40,
             "u_wert": 0.90, "fx": 1.0, "phi_t": 71.5},
            {"name": "De 1",       "breite": "",   "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 8.69, "a_abzug": "", "a_netto": 8.69,
             "u_wert": 0.24, "fx": 0.5, "phi_t": 34.5},
            {"name": "Fb 1",       "breite": "",   "hoehe": "",   "f_flaeche": 1.00,
             "a_brutto": 8.69, "a_abzug": "", "a_netto": 8.69,
             "u_wert": 0.30, "fx": 0.5, "phi_t": ""},
        ],
        "phi_t_gesamt":  193,
        "phi_v":         122,
        "phi_hl":        315,
        "spez_flaeche":  36,
        "spez_volumen":  15,
    },
]


# ──────────────────────────────────────────────
# 3. JINJA2: TEMPLATE LADEN UND RENDERN
#
#    Hier passiert die Magie:
#    Das Template bekommt die Daten als Variablen
#    und ersetzt alle {{ platzhalter }} damit.
# ──────────────────────────────────────────────

def render_html(raeume, firma, projekt, seitenoffset=5):
    """
    Rendert das Jinja2-Template mit den übergebenen Daten.
    Gibt fertiges HTML als String zurück.
    """
    # Jinja2 Environment: sagt wo Templates liegen
    env = Environment(
        loader=FileSystemLoader("/home/claude/heizlast/templates"),
        autoescape=False   # HTML darf echte Tags enthalten
    )

    # Template laden
    template = env.get_template("raumblatt.html")

    # Template rendern: alle {{ variablen }} werden ersetzt
    html = template.render(
        raeume=raeume,
        firma=firma,
        projekt=projekt,
        seitenoffset=seitenoffset,
    )
    return html


# ──────────────────────────────────────────────
# 4. ZUSAMMENFASSUNG BERECHNEN
# ──────────────────────────────────────────────

def zusammenfassung(raeume):
    gesamt_flaeche = sum(r["flaeche"] for r in raeume)
    gesamt_hl = sum(r["phi_hl"] for r in raeume)
    spez_gesamt = round(gesamt_hl / gesamt_flaeche, 1) if gesamt_flaeche > 0 else 0
    return {
        "anzahl_raeume": len(raeume),
        "gesamt_flaeche": round(gesamt_flaeche, 1),
        "gesamt_heizlast_w": gesamt_hl,
        "gesamt_heizlast_kw": round(gesamt_hl / 1000, 2),
        "spez_heizlast": spez_gesamt,
    }


# ──────────────────────────────────────────────
# 5. HAUPTPROGRAMM
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # HTML rendern
    html_output = render_html(RAEUME, FIRMA, PROJEKT, seitenoffset=5)

    # HTML speichern (kann im Browser direkt angeschaut werden)
    out_path = Path("/home/claude/heizlast/output_raumblätter.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_output, encoding="utf-8")
    print(f"✓ HTML gespeichert: {out_path}")

    # Zusammenfassung ausgeben
    zf = zusammenfassung(RAEUME)
    print("\n── Projektübersicht ──────────────────────")
    print(f"  Räume:              {zf['anzahl_raeume']}")
    print(f"  Gesamtfläche:       {zf['gesamt_flaeche']} m²")
    print(f"  Gesamtheizlast:     {zf['gesamt_heizlast_w']} W  ({zf['gesamt_heizlast_kw']} kW)")
    print(f"  Spez. Heizlast:     {zf['spez_heizlast']} W/m²")
    print("──────────────────────────────────────────")
    print("\nNächster Schritt:")
    print("  pip install weasyprint")
    print("  python generate_pdf.py  → erzeugt heizlast.pdf")
