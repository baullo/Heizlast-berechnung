# daten_beispiel.py
# ==================
# Kopiere zu daten.py und trag deine eigenen Werte ein.
# daten.py steht in .gitignore → kommt NICHT auf GitHub.
#
#   cp daten_beispiel.py daten.py
#
# Alle Werte mit  ← EINGABE  müssen von dir befüllt werden.
# Der Rest wird automatisch berechnet (generate.py).

# ── Projektdaten ───────────────────────────────────────────
PROJEKT = {
    "auftraggeber":  "Max Mustermann",           # ← EINGABE
    "adresse":       "Musterstraße 1, 12345 Ort",# ← EINGABE
    "foerderung":    "KfW 458 – Bundesförderung Heizungstausch",
    "nachweis":      "VdZ-Formular Hydraul. Abgleich Einzelmaßnahme Verfahren B",
    "normen":        "DIN EN 12831-1 (Heizlast) + EN 442 (HK-Korrektur)",
    "datum":         "Mai 2026",                 # ← EINGABE
}

# ── Klimaparameter ─────────────────────────────────────────
PARAMETER = {
    # Klimadaten
    "theta_e":       -12,      # Norm-Außentemperatur °C  ← EINGABE (DIN EN 12831, Standort)
    "h_kg":          2.89,     # Raumhöhe Keller m        ← EINGABE (messen)
    "h_eg":          2.85,     # Raumhöhe EG m            ← EINGABE (messen)

    # Lüftung (EN 12831 – in der Regel nicht ändern)
    "rcp_luft":      0.340,    # ρ·cp Luft Wh/(m³K)
    "n_wohn":        0.50,     # Luftwechsel Wohnräume h⁻¹
    "n_feucht":      1.50,     # Luftwechsel Feuchträume h⁻¹ (Bad/WC/Dusche)

    # Wärmepumpen-Auslegungstemperaturen  ← EINGABE (Anlagenplanung)
    "vl":            55,       # Vorlauftemperatur °C
    "rl":            45,       # Rücklauftemperatur °C

    # Heizkörper-Normtemperatur EN 442 (Katalogbedingungen – nicht ändern)
    "vl_norm":       75,       # Norm-Vorlauf °C
    "rl_norm":       65,       # Norm-Rücklauf °C
    "ti_norm":       20,       # Norm-Raumtemperatur °C

    # EN 442 Exponenten nach Heizkörpertyp (nicht ändern)
    "n_typ10":       1.26,     # 1 Platte, 0 Rippen
    "n_typ11":       1.28,     # 1 Platte, 1 Rippe  (Standard)
    "n_typ21":       1.30,     # 2 Platten, 1 Rippe

    # Wandheizung Hypoplan (aus Herstellerdiagramm)
    "q_hypo":        250,      # Leistung bei tm=50°C, Ti=20°C  W/m²  ← EINGABE falls vorhanden
    "hypo_rohrabstand": 18,    # Rohrabstand cm

    # Hydraulik
    "rcp_wasser":    1.163,    # ρ·cp Wasser Wh/(l·K) – Konstante ~50°C
}

# ── Räume ──────────────────────────────────────────────────
# Felder pro Raum:
#   nr          Raumnummer (z.B. -1.001 = Keller, 0.001 = EG)
#   name        Raumbezeichnung
#   gs          Geschoss: "KG" oder "EG"
#   flaeche     m²   ← EINGABE (messen oder aus Grundriss)
#   theta_i     Innentemperatur °C  (20 Wohn, 22 Küche/Essen, 24 Bad, 18 Flur)
#   qt_1995     Transmissionswärmeverlust W aus DIN 4701/1995 (falls vorhanden, sonst None)
#   ql_1995     Lüftungswärmeverlust W aus DIN 4701/1995 (falls vorhanden, sonst None)
#   hk_typ      Heizkörper-Typ: "Typ10", "Typ11", "Typ21", "Wand", None
#   hk_breite   Heizkörper Breite mm (bei HK-Typen)
#   hk_hoehe    Heizkörper Höhe mm  (bei HK-Typen)
#   hk_q_norm   Nennleistung W bei 75/65/20 (aus Katalog)  ← EINGABE
#   wand_fl     Wandheizfläche m² (nur bei Wandheizung, sonst 0)
#   mehrere_hk  Beschreibung falls mehrere HK z.B. "2× Typ10"
#   bemerkung   Freitext
#
# qt_1995 / ql_1995: Alte DIN 4701 Werte falls vorhanden.
# Werden für Vergleich angezeigt, aber NICHT für die Berechnung verwendet.

RAEUME = [
    # ── Keller ──────────────────────────────────────────────
    {
        "nr": -1.001, "name": "Hobbyraum",       "gs": "KG",
        "flaeche": 16.4,  "theta_i": 20,
        "qt_1995": 643,   "ql_1995": 253,
        "hk_typ": "Typ11", "hk_breite": 1800, "hk_hoehe": 600, "hk_q_norm": 1480,
        "wand_fl": 0, "mehrere_hk": None, "bemerkung": "Werkstatt",
    },
    {
        "nr": -1.002, "name": "Waschen+Trocknen", "gs": "KG",
        "flaeche": 18.5,  "theta_i": 20,
        "qt_1995": 433,   "ql_1995": 285,
        "hk_typ": "Typ21", "hk_breite": 800, "hk_hoehe": 500, "hk_q_norm": 528,
        "wand_fl": 0, "mehrere_hk": None, "bemerkung": "Heizungsraum",
    },
    {
        "nr": -1.003, "name": "Kind (Keller 1)", "gs": "KG",
        "flaeche": 18.8,  "theta_i": 20,
        "qt_1995": 630,   "ql_1995": 290,
        "hk_typ": "Wand", "hk_breite": None, "hk_hoehe": None, "hk_q_norm": None,
        "wand_fl": 3.58, "mehrere_hk": None, "bemerkung": "Wandheizung Pos.1",
    },
    {
        "nr": -1.004, "name": "Dusche",          "gs": "KG",
        "flaeche": 5.1,   "theta_i": 24,
        "qt_1995": 308,   "ql_1995": 89,
        "hk_typ": "Typ11", "hk_breite": 1500, "hk_hoehe": 360, "hk_q_norm": 748,
        "wand_fl": 0, "mehrere_hk": None, "bemerkung": "Kellerdusche",
    },
    {
        "nr": -1.005, "name": "Kind (Keller 2)", "gs": "KG",
        "flaeche": 17.7,  "theta_i": 20,
        "qt_1995": 672,   "ql_1995": 273,
        "hk_typ": "Wand", "hk_breite": None, "hk_hoehe": None, "hk_q_norm": None,
        "wand_fl": 3.58, "mehrere_hk": None, "bemerkung": "Wandheizung Pos.2",
    },
    {
        "nr": -1.006, "name": "Arbeitszimmer",   "gs": "KG",
        "flaeche": 9.4,   "theta_i": 20,
        "qt_1995": 520,   "ql_1995": 145,
        "hk_typ": "Typ11", "hk_breite": 400, "hk_hoehe": 600, "hk_q_norm": 329,
        "wand_fl": 0, "mehrere_hk": None, "bemerkung": "⚠ HK zu klein",
    },
    {
        "nr": -1.007, "name": "Treppenhaus",     "gs": "KG",
        "flaeche": 30.8,  "theta_i": 18,
        "qt_1995": 625,   "ql_1995": 444,
        "hk_typ": "Typ11", "hk_breite": 2000, "hk_hoehe": 570, "hk_q_norm": 1120,
        "wand_fl": 0, "mehrere_hk": None, "bemerkung": "Schätzwert prüfen",
    },
    # ── Erdgeschoss ─────────────────────────────────────────
    {
        "nr": 0.001, "name": "Kochen",           "gs": "EG",
        "flaeche": 18.5,  "theta_i": 22,
        "qt_1995": 652,   "ql_1995": 299,
        "hk_typ": "Typ10", "hk_breite": None, "hk_hoehe": None, "hk_q_norm": 1664,
        "wand_fl": 0, "mehrere_hk": "Typ10 1600×300 + Typ10 1800×400", "bemerkung": "2 HK",
    },
    {
        "nr": 0.002, "name": "Esszimmer",        "gs": "EG",
        "flaeche": 37.1,  "theta_i": 22,
        "qt_1995": 1457,  "ql_1995": 600,
        "hk_typ": "Typ10", "hk_breite": None, "hk_hoehe": None, "hk_q_norm": 2190,
        "wand_fl": 3.02, "mehrere_hk": "2× Typ10 2600×300", "bemerkung": "2HK+Wand Pos.5+6",
    },
    {
        "nr": 0.003, "name": "Wohnzimmer",       "gs": "EG",
        "flaeche": 27.8,  "theta_i": 22,
        "qt_1995": 889,   "ql_1995": 449,
        "hk_typ": "Wand", "hk_breite": None, "hk_hoehe": None, "hk_q_norm": None,
        "wand_fl": 5.46, "mehrere_hk": None, "bemerkung": "Wand Pos.7+8",
    },
    {
        "nr": 0.004, "name": "WC",               "gs": "EG",
        "flaeche": 1.9,   "theta_i": 20,
        "qt_1995": 99,    "ql_1995": 42,
        "hk_typ": None,   "hk_breite": None, "hk_hoehe": None, "hk_q_norm": None,
        "wand_fl": 0, "mehrere_hk": None, "bemerkung": "kein HK – mitgeheizt",
    },
    {
        "nr": 0.005, "name": "Badezimmer",       "gs": "EG",
        "flaeche": 8.6,   "theta_i": 24,
        "qt_1995": 506,   "ql_1995": 148,
        "hk_typ": "Typ11", "hk_breite": 1800, "hk_hoehe": 600, "hk_q_norm": 1480,
        "wand_fl": 0, "mehrere_hk": None, "bemerkung": None,
    },
    {
        "nr": 0.006, "name": "Elternzimmer",     "gs": "EG",
        "flaeche": 15.6,  "theta_i": 20,
        "qt_1995": 504,   "ql_1995": 237,
        "hk_typ": "Wand", "hk_breite": None, "hk_hoehe": None, "hk_q_norm": None,
        "wand_fl": 3.06, "mehrere_hk": None, "bemerkung": "Wand Pos.3+4",
    },
]
