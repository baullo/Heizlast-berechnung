# daten_beispiel.py
#
# Template für neue Heizlast-/Hydraulikabgleich-Projekte.
# Kopieren als daten_<nachname>.py, dann alle <PLATZHALTER> ersetzen.
#
# Konventionen:
#   Bauteil-Typen:  AW=Außenwand  FE=Fenster  DE=Decke  FB=Fußboden  IW=Innenwand
#   fx:  1.0 = grenzt an Außenluft
#        0.8 = grenzt an Erdreich
#        0.5 = grenzt an unbeheizten Raum (Dachboden, Nachbar)
#        0.0 = grenzt an beheizten Raum (= kein Wärmestrom, nur zur Info)
#   theta_i:  20 = Wohnen   22 = Küche/Essen   24 = Bad   18 = Flur/Treppe
#   Nr-Konvention:  EG = 0.00x   OG = 1.00x   KG = -1.00x   DG = 2.00x

# ── Projektdaten ───────────────────────────────────────────────────────────────
PROJEKT = {
    "auftraggeber":  "<VORNAME NACHNAME>",
    "adresse":       "<STRASSE NR, PLZ ORT>",
    "foerderung":    "KfW 458 – Bundesförderung Heizungstausch",
    "nachweis":      "VdZ-Formular Hydraul. Abgleich Einzelmaßnahme Verfahren B",
    "normen":        "DIN EN 12831-1 (Heizlast) + EN 442 (HK-Korrektur)",
    "datum":         "<MONAT JAHR>",
}

# ── Klimaparameter & Auslegung ─────────────────────────────────────────────────
PARAMETER = {
    # Standort-Klimadaten (DIN/TRY-Tabellen oder lokale Vorgabe)
    "theta_e":         -12,     # Norm-Außentemperatur °C  (z.B. Saarland -12, Berlin -14)
    "theta_e_moh":      -7,     # Bivalenzpunkt (ohne Heizstab)

    # Raumhöhen pro Geschoss in m
    "h_kg":            2.50,    # Keller   – ggf. ungenutzt lassen
    "h_eg":            2.50,    # Erdgeschoss
    # "h_og":          2.50,   # ggf. ergänzen
    # "h_dg":          2.30,   # ggf. ergänzen

    # Lüftung EN 12831-1 Anhang B
    "rcp_luft":        0.34,    # ρ·cp Luft Wh/(m³K) – Konstante, nicht ändern
    "n_wohn":          0.5,     # h⁻¹  Luftwechsel Wohnräume
    "n_feucht":        0.5,     # h⁻¹  Bad/Küche  (1.5 = DIN 1946-6, hier nicht)

    # ── Heizkreise ─────────────────────────────────────────────────────────────
    # Spreizung (vl − rl) bestimmt V_soll je HK:
    #   V_soll_hk = Q_WP_HK / (ρcp × ΔT_spreiz)
    #
    # v_max Richtwerte:
    #   hk   = 0.5–1.0 m/s  (Heizkörper Ø15 Cu, di=13 mm → max ~477 l/h bei 1 m/s)
    #   wand = 0.5 m/s      (Wandheizung Hypoplan)
    #   fbh  = 0.5 m/s      (Fußbodenheizung EN 1264, di an Rohr-Innen-Ø anpassen)
    "kreise": {
        "hk": {
            "vl":              50,    # °C  Vorlauf Heizkörper
            "rl":              45,    # °C  Rücklauf → Spreizung = vl − rl
            "v_max_ms":       0.5,    # m/s
            "di_anschluss_mm": 13,    # mm  Ø15 Cu → di=13 mm
        },
        "wand": {
            "vl":              50,    # °C  Vorlauf Wandheizung
            "rl":              45,    # °C  Rücklauf → Spreizung 5 K
            "v_max_ms":       0.5,    # m/s
            "di_anschluss_mm":  8,    # mm  Ø10 Cu → di=8 mm
        },
        # Fußbodenheizung – Bauteilvorlage:
        # "fbh": {
        #     "vl":              33,
        #     "rl":              28,    # → Spreizung 5 K
        #     "v_max_ms":       0.5,
        #     "di_anschluss_mm": 10,    # auf tatsächlichen Rohr-Innen-Ø setzen
        # },
    },
    "wp_leistung_max": 8800,    # W  Auslegungsobergrenze der Wärmepumpe

    # Heizkörper-Normtemperatur EN 442 (NICHT ÄNDERN)
    "vl_norm":   75,
    "rl_norm":   65,
    "ti_norm":   20,

    # EN 442 Exponenten (NICHT ÄNDERN)
    "n_typ10":  1.26,
    "n_typ11":  1.28,
    "n_typ21":  1.30,
    "n_typ22":  1.33,

    # Wandheizung Hypoplan
    "q_hypo":            250,    # W/m² bei tm=50°C, Ti=20°C (Referenz)
    "hypo_steig":       13.0,    # W/(m²·K) – direkt aus Hypoplan-Diagramm
    "hypo_rohrabstand":   18,    # cm

    # FBH (für zukünftige Projekte)
    "q_fbh_steig":       8.0,    # W/(m²·K) – besser aus Herstellerangabe

    # Wasser
    "rcp_wasser":     1.163,     # Wh/(l·K) – Konstante

    # ── Rohrnetz ───────────────────────────────────────────────────────────────
    "rohr_d_haupt":   28,        # mm Hauptstrang Cu Außen-Ø
    "rohr_d_zweig":   22,        # mm Zweigstrang
    "rohr_d_hk":      15,        # mm letzter Abschnitt zum HK
    "rohr_l_hk":       8.0,      # m  geschätzte Länge (Hin = Rücklauf)
    "rohr_zuschlag":   1.3,      # Faktor für Bögen/Fittings

    # ── Pumpe & Ventil ─────────────────────────────────────────────────────────
    "dp_pumpe":       400,       # mbar  verfügbarer Differenzdruck
    "dp_hk_intern":    80,       # mbar  HK-Innenwiderstand
    "ventil_stufen":    6,
    "ventil_kv": [0.04, 0.10, 0.19, 0.32, 0.50, 0.82],

    # ── Statischer Anlagen-Vordruck ────────────────────────────────────────────
    # p_0 = h_statisch / 10 + 0.2  [bar]
    "hoehe_statisch_m":    4,    # m  vertikal Pumpe → höchster HK

    # ── Wärmeerzeuger ──────────────────────────────────────────────────────────
    "waermeerzeuger": {
        "hersteller":    "<HERSTELLER>",
        "modell":        "<MODELL>",
        "heizleistung":  "<X kW bei -10°C / Y-Z kW modulierend>",
        "kaeltemittel":  "<z.B. R290 (Propan)>",
        "scop_55":       "<SCOP bei 55°C VL>",
    },

    # ── Heizungspumpe ──────────────────────────────────────────────────────────
    "pumpe": {
        "fabrikat":      "<z.B. Wilo Para 25/6>",
        "modus":         "<z.B. Differenzdruck variabel Δp-v>",
        "stufe":         "<z.B. I (von I/II/III)>",
    },
}

# ── Räume ──────────────────────────────────────────────────────────────────────
#
#   Pflichtfelder pro Raum:
#     nr          float    Raumnummer (EG: 0.00x, OG: 1.00x, KG: -1.00x, DG: 2.00x)
#     name        str
#     gs          str      "KG" | "EG" | "OG" | "DG"
#     flaeche     float    m²
#     theta_i     int      °C  (20/22/24/18 — siehe Konvention oben)
#     bauteile    list     siehe unten
#     heizkoerper list     siehe unten (leere Liste [] = kein HK)
#     wand_fl     float    m²  Wandheizfläche (0 wenn keine)
#     dp          None     Druckverlust-Override (meist None)
#     bemerkung   str|None
#
#   Optional:
#     wand_kreis  str      "hk" | "wand" | "fbh"  (Standard: "wand")
#     fbh_fl      float    m²  Fußbodenheizfläche
#     fbh_kreis   str      Standard: "fbh"
#     v_soll_vorgabe  float l/h  fester Volumenstrom (überschreibt v_max-Berechnung)
#     hk_schaltung    str  "reihe"  (Standard: parallel — siehe generate.py Docstring)
#
#   Bauteil-Dict:
#     {"typ": "AW", "name": "AW Süd", "a_netto": 8.5, "u_wert": 0.28, "fx": 1.0}
#
#   Heizkörper-Dict:
#     {"typ": "Typ11", "breite": 1800, "hoehe": 600, "q_norm": 1762, "kreis": "hk"}
#     – typ:    "Typ10" | "Typ11" | "Typ21" | "Typ22"
#     – q_norm: W bei 75/65/20 (aus Herstellerkatalog)
#     – kreis:  "hk" (Standard) | "wand" | "fbh"

RAEUME = [
    # ── ERDGESCHOSS ──────────────────────────────────────────────────────────
    {
        "nr":       0.001,
        "name":     "<RAUMNAME>",
        "gs":       "EG",
        "flaeche":  0.00,
        "theta_i":  20,
        "bauteile": [
            {"typ": "AW", "name": "AW <RICHTUNG>",  "a_netto": 0.00, "u_wert": 0.00, "fx": 1.0},
            {"typ": "FE", "name": "FE <RICHTUNG>",  "a_netto": 0.00, "u_wert": 0.00, "fx": 1.0},
            {"typ": "DE", "name": "DE <BEZ>",       "a_netto": 0.00, "u_wert": 0.00, "fx": 0.5},
            {"typ": "FB", "name": "FB <BEZ>",       "a_netto": 0.00, "u_wert": 0.00, "fx": 0.8},
            # {"typ": "IW", "name": "IW1",          "a_netto": 0.00, "u_wert": 0.00, "fx": 0.0},
        ],
        "heizkoerper": [
            {"typ": "Typ11", "breite": 1800, "hoehe": 600, "q_norm": 0, "kreis": "hk"},
        ],
        "wand_fl":   0,
        "dp":        None,
        "bemerkung": None,
    },

    # Raum mit MEHREREN Heizkörpern (parallel):
    # {
    #     "nr":       0.002,
    #     "name":     "Esszimmer",
    #     "gs":       "EG",
    #     "flaeche":  0.00,
    #     "theta_i":  22,
    #     "bauteile": [ ... ],
    #     "heizkoerper": [
    #         {"typ": "Typ10", "breite": 2600, "hoehe": 300, "q_norm": 931, "kreis": "hk"},
    #         {"typ": "Typ10", "breite": 2600, "hoehe": 300, "q_norm": 931, "kreis": "hk"},
    #     ],
    #     "wand_fl":   0,
    #     "dp":        None,
    #     "bemerkung": "2× Typ10 parallel",
    # },

    # Raum NUR mit Wandheizung (kein HK):
    # {
    #     "nr":       0.003,
    #     "name":     "Wohnzimmer",
    #     "gs":       "EG",
    #     "flaeche":  0.00,
    #     "theta_i":  22,
    #     "bauteile": [ ... ],
    #     "heizkoerper": [],
    #     "wand_fl":    5.46,
    #     "wand_kreis": "wand",
    #     "dp":         None,
    #     "bemerkung":  "Wandheizung Hypoplan 5,46m²",
    # },

    # Raum mit HK + Wandheizung kombiniert:
    # {
    #     "nr":       0.004,
    #     "name":     "Bad",
    #     "gs":       "EG",
    #     "flaeche":  0.00,
    #     "theta_i":  24,
    #     "bauteile": [ ... ],
    #     "heizkoerper": [
    #         {"typ": "Typ11", "breite": 1500, "hoehe": 360, "q_norm": 712, "kreis": "hk"},
    #     ],
    #     "wand_fl":    2.50,
    #     "wand_kreis": "wand",
    #     "dp":         None,
    #     "bemerkung":  "HK + Wandheizung 2,50m²",
    # },

    # ── OBERGESCHOSS / KELLER / DACHGESCHOSS ────────────────────────────────
    # Räume hier nach gleichem Schema ergänzen.
    # Nr-Präfix:  OG = 1.00x   KG = -1.00x   DG = 2.00x

]

# ── Checkliste vor dem Generieren ──────────────────────────────────────────────
#   [ ] Alle <PLATZHALTER> ersetzt
#   [ ] θe für den Standort korrekt (DIN/TRY-Tabelle prüfen)
#   [ ] Raumhöhen pro Geschoss gesetzt
#   [ ] VL/RL je Kreis realistisch (Spreizung 5 K typisch, 2 K bei kleiner Heizlast)
#   [ ] Jede Außenwand mit fx=1.0, Erdreich fx=0.8, unbeheizt fx=0.5
#   [ ] Q_Norm je HK aus Herstellerkatalog (75/65/20) – keine Schätzwerte
#   [ ] wand_fl gesetzt wo Hypoplan/FBH vorhanden, sonst 0
#   [ ] Räume mit hoher Heizlast (Bad, Eltern) priorisiert prüfen
#   [ ] WP-Leistung > Σ ΦHL des Gebäudes
