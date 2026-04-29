# daten_beispiel.py
# ==================
# Kopiere zu daten/<projektname>.py und trag deine eigenen Werte ein.
# Die daten/-Dateien stehen in .gitignore → kommen NICHT auf GitHub.
#
#   cp daten/daten_beispiel.py daten/daten_meinprojekt.py

# ── Projektdaten ───────────────────────────────────────────────────────────────
PROJEKT = {
    "auftraggeber":  "Max Mustermann",
    "adresse":       "Musterstraße 1, 12345 Musterstadt",
    "foerderung":    "KfW 458 – Bundesförderung Heizungstausch",
    "nachweis":      "VdZ-Formular Hydraul. Abgleich Einzelmaßnahme Verfahren B",
    "normen":        "DIN EN 12831-1 (Heizlast) + EN 442 (HK-Korrektur)",
    "datum":         "Mai 2026",
}

# ── Klimaparameter ─────────────────────────────────────────────────────────────
PARAMETER = {
    # Klimadaten
    "theta_e":       -12,      # Norm-Außentemperatur °C  ← Standort aus DIN EN 12831 Anhang
    "h_kg":          2.50,     # Raumhöhe Keller m        ← messen
    "h_eg":          2.50,     # Raumhöhe EG m            ← messen

    # Lüftung EN 12831 (normale Dichtheit – in der Regel nicht ändern)
    "rcp_luft":      0.340,    # ρ·cp Luft Wh/(m³K)  – Konstante
    "n_wohn":        0.50,     # Luftwechsel Wohnräume h⁻¹
    "n_feucht":      1.50,     # Luftwechsel Bad/WC/Dusche h⁻¹

    # Wärmepumpen-Auslegungstemperaturen ← EINGABE (Anlagenplanung)
    "vl":            55,       # Vorlauftemperatur °C
    "rl":            45,       # Rücklauftemperatur °C

    # Heizkörper-Normtemperatur EN 442 (Katalogbedingungen – nicht ändern)
    "vl_norm":       75,
    "rl_norm":       65,
    "ti_norm":       20,

    # EN 442 Exponenten nach Heizkörpertyp (nicht ändern)
    "n_typ10":       1.26,     # 1 Platte, 0 Rippen
    "n_typ11":       1.28,     # 1 Platte, 1 Rippe  (Standard)
    "n_typ21":       1.30,     # 2 Platten, 1 Rippe
    "n_typ22":       1.33,     # 2 Platten, 2 Rippenlagen

    # Wandheizung Hypoplan
    "q_hypo":        250,      # W/m² bei tm=50°C, Ti=20°C  ← aus Herstellerdiagramm
    "hypo_rohrabstand": 18,    # cm

    # Hydraulik
    "rcp_wasser":    1.163,    # ρ·cp Wasser Wh/(l·K)
}

# ── Räume ──────────────────────────────────────────────────────────────────────
#
# BAUTEILE pro Raum – das ist die Basis der EN 12831 Berechnung:
#
#   HT = Σ (A_netto × U × fx)      [W/K]
#
#   Bauteil-Felder:
#     typ       Kürzel: "AW"=Außenwand, "FE"=Fenster, "DE"=Decke,
#                       "FB"=Fußboden, "IW"=Innenwand (kein Verlust)
#     name      Freitext z.B. "Außenwand Nord", "Fenster Süd"
#     a_netto   m²  Nettofläche (Fenster etc. bereits abgezogen)
#                   → bei Fenstern: direkte Fensterfläche eintragen
#                   → bei Wänden: Wandfläche OHNE Fenster
#     u_wert    W/(m²K)  ← aus Bauteilaufbau oder Ubakus.de
#     fx        Temperaturkorrekturfaktor:
#                 1.0 = grenzt an Außenluft
#                 0.5 = grenzt an unbeheizten Raum (Keller, Garage)
#                 0.8 = grenzt an Erdreich (Bodenplatte)
#                 0.0 = Innenwand zu beheiztem Raum (kein Verlust)
#
#   U-WERTE Richtwerte nach Baujahr (falls unbekannt):
#     Außenwand  vor 1960: ~1.4   1960-1980: ~0.8   1980-2000: ~0.5   nach 2000: ~0.3
#     Fenster    Einfach:  ~5.0   Doppelt:   ~2.8   Wärmeschutz: ~1.1  3-fach: ~0.7
#     Dach/Decke vor 1980: ~1.0   gedämmt:   ~0.3   gut gedämmt: ~0.15
#     Bodenplatte          ~0.5   gedämmt:   ~0.25
#
#   HEIZKÖRPER-Felder:
#     hk_typ      "Typ10", "Typ11", "Typ21", "Typ22", None (mitgeheizt)
#     hk_breite   mm  (aus Katalog)
#     hk_hoehe    mm  (aus Katalog)
#     hk_q_norm   W bei 75/65/20  (aus Katalog)  ← EINGABE, None bis Katalog vorliegt
#     wand_fl     m²  Wandheizfläche (nur bei Wandheizung, sonst 0)
#     mehrere_hk  Liste von HK-Dicts falls mehrere HK im Raum, sonst None
#                 Format: [{"hk_typ": "Typ11", "hk_breite": 1800,
#                           "hk_hoehe": 600, "hk_q_norm": None}, ...]
#
#   HYDRAULIK-Felder (hydraulischer Abgleich):
#     ve          Voreinstellwert Thermostatventil  ← EINGABE nach Rohrnetzberechnung
#                 None bis Rohrnetzberechnung vorliegt
#     dp          Druckverlust des Kreises [mbar]   ← EINGABE nach Rohrnetzberechnung
#                 None bis Rohrnetzberechnung vorliegt
#     v_soll      Soll-Volumenstrom [l/h]           ← wird vom Script berechnet
#                 (= q_ausl / rcp_wasser / spreizung), hier immer None lassen
#
#     bemerkung   Freitext

RAEUME = [
    # ── Erdgeschoss ─────────────────────────────────────────────────────────────
    {
        "nr": 0.001, "name": "Wohnzimmer", "gs": "EG",
        "flaeche": 25.0, "theta_i": 20,
        "bauteile": [
            # Außenwände (Nettofläche = Brutto minus Fenster)
            {"typ": "AW", "name": "AW Süd",   "a_netto": 8.5,  "u_wert": 0.28, "fx": 1.0},
            {"typ": "AW", "name": "AW West",  "a_netto": 6.0,  "u_wert": 0.28, "fx": 1.0},
            # Fenster
            {"typ": "FE", "name": "FE Süd 1", "a_netto": 2.1,  "u_wert": 1.10, "fx": 1.0},
            {"typ": "FE", "name": "FE Süd 2", "a_netto": 1.5,  "u_wert": 1.10, "fx": 1.0},
            {"typ": "FE", "name": "FE West",  "a_netto": 1.0,  "u_wert": 1.10, "fx": 1.0},
            # Decke (grenzt an Außenluft → fx=1.0; an beheiztes OG → fx=0.0)
            {"typ": "DE", "name": "Decke",    "a_netto": 25.0, "u_wert": 0.20, "fx": 1.0},
            # Boden (grenzt an unbeheizten Keller → fx=0.5; an beheizten Keller → fx=0.0)
            {"typ": "FB", "name": "Boden",    "a_netto": 25.0, "u_wert": 0.35, "fx": 0.5},
        ],
        "hk_typ":    "Typ11",
        "hk_breite": 1800,
        "hk_hoehe":  600,
        "hk_q_norm": 1480,       # W bei 75/65/20 – aus Katalog
        "wand_fl":   0,
        "mehrere_hk": None,
        "ve":        None,        # ← nach Rohrnetzberechnung eintragen
        "dp":        None,        # ← nach Rohrnetzberechnung eintragen
        "v_soll":    None,        # ← wird berechnet, hier None lassen
        "bemerkung": None,
    },
    {
        "nr": 0.002, "name": "Küche", "gs": "EG",
        "flaeche": 12.0, "theta_i": 22,
        "bauteile": [
            {"typ": "AW", "name": "AW Nord",  "a_netto": 5.5,  "u_wert": 0.28, "fx": 1.0},
            {"typ": "FE", "name": "FE Nord",  "a_netto": 1.5,  "u_wert": 1.10, "fx": 1.0},
            {"typ": "DE", "name": "Decke",    "a_netto": 12.0, "u_wert": 0.20, "fx": 1.0},
            {"typ": "FB", "name": "Boden",    "a_netto": 12.0, "u_wert": 0.35, "fx": 0.5},
        ],
        "hk_typ":    "Typ11",
        "hk_breite": 800,
        "hk_hoehe":  600,
        "hk_q_norm": 660,
        "wand_fl":   0,
        "mehrere_hk": None,
        "ve":        None,
        "dp":        None,
        "v_soll":    None,
        "bemerkung": None,
    },
    {
        "nr": 0.003, "name": "Bad", "gs": "EG",
        "flaeche": 6.0, "theta_i": 24,
        "bauteile": [
            {"typ": "AW", "name": "AW Ost",   "a_netto": 3.8,  "u_wert": 0.28, "fx": 1.0},
            {"typ": "FE", "name": "FE Ost",   "a_netto": 0.6,  "u_wert": 1.10, "fx": 1.0},
            {"typ": "DE", "name": "Decke",    "a_netto": 6.0,  "u_wert": 0.20, "fx": 1.0},
            {"typ": "FB", "name": "Boden",    "a_netto": 6.0,  "u_wert": 0.35, "fx": 0.5},
        ],
        "hk_typ":    "Typ11",
        "hk_breite": 600,
        "hk_hoehe":  600,
        "hk_q_norm": 490,
        "wand_fl":   0,
        "mehrere_hk": None,
        "ve":        None,
        "dp":        None,
        "v_soll":    None,
        "bemerkung": None,
    },
]
