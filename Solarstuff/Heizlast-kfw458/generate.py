"""
Heizlastberechnung & Hydraulischer Abgleich – Generator
=========================================================
Norm:    DIN EN 12831-1  (Heizlast)
         EN 442          (Heizkörper-Leistungskorrektur)
Zweck:   KfW 458 / VdZ-Nachweis Verfahren B

Berechnungslogik (alle Formeln aus dem ODS-Original):

  HEIZLAST (EN 12831):
    Volumen         V   = Fläche × Raumhöhe
    Transmissionskoeff. HT = Qt_1995 / (θi − θe)        ← aus alten DIN-4701-Werten
    Lüftungskoeff.  HV  = ρcp_L × n_min × V
    Heizlast        ΦHL = (HT + HV) × (θi − θe)

  HEIZKÖRPER-KORREKTUR (EN 442):
    tm_norm = (VL_norm + RL_norm) / 2
    ΔT_norm = tm_norm − Ti_norm                          ← = 50 K bei 75/65/20
    tm      = (VL + RL) / 2                              ← Betriebspunkt
    ΔT_neu  = tm − θi
    Q_WP_HK = Q_Norm × (ΔT_neu / ΔT_norm) ^ n

  WANDHEIZUNG (Hypoplan):
    Steigung = q_hypo / (tm_ref − Ti_ref)               ← q_hypo W/m² bei tm=50, Ti=20
    Q_WP_Wand = Wandfläche × Steigung × (tm − θi)

  HYDRAULIK:
    Q_Auslegung = min(Q_WP_Gesamt, QN_1995)             ← nie mehr als Heizlast
    Volumenstrom ṁ = Q_Auslegung / (ρcp_Wasser × Spreizung)
"""

from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# ── Daten laden ────────────────────────────────────────────────────────────────
try:
    from daten import PROJEKT, PARAMETER, RAEUME
except ImportError:
    print("FEHLER: daten.py nicht gefunden.")
    print("→  cp daten_beispiel.py daten.py  und eigene Werte eintragen.")
    raise


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def abgeleitete_parameter(p):
    """Berechnet alle abgeleiteten Werte aus den PARAMETER-Eingaben."""
    tm      = (p["vl"] + p["rl"]) / 2
    tm_norm = (p["vl_norm"] + p["rl_norm"]) / 2
    dt_norm = tm_norm - p["ti_norm"]          # = 50 K bei 75/65/20
    dt_spreiz = p["vl"] - p["rl"]
    div_vol = p["rcp_wasser"] * dt_spreiz     # = 11.63 Wh/l bei ΔT=10K
    hypo_steig = p["q_hypo"] / (tm_norm - p["ti_norm"])  # W/(m²·K)
    return {
        **p,
        "tm":         tm,
        "tm_norm":    tm_norm,
        "dt_norm":    dt_norm,
        "dt_spreiz":  dt_spreiz,
        "div_vol":    div_vol,
        "hypo_steig": hypo_steig,
    }


def n_exponent(hk_typ, p):
    """Gibt den EN-442-Exponenten für den Heizkörpertyp zurück."""
    return {
        "Typ10": p["n_typ10"],
        "Typ11": p["n_typ11"],
        "Typ21": p["n_typ21"],
    }.get(hk_typ)


def berechne_raum(raum, p):
    """
    Berechnet alle Kennwerte für einen Raum.
    Gibt ein neues Dict zurück mit allen Originalfeldern + berechneten Werten.
    """
    gs   = raum["gs"]
    h    = p["h_kg"] if gs == "KG" else p["h_eg"]
    ti   = raum["theta_i"]
    te   = p["theta_e"]
    dt_i = ti - te                           # Temperaturdifferenz innen–außen

    # ── Volumen ──────────────────────────────────────────────
    vol = round(raum["flaeche"] * h, 2)

    # ── Lüftung: n_min nach Raumtyp ──────────────────────────
    # Feuchträume (Bad, WC, Dusche) bekommen n=1.5
    n_min = p["n_feucht"] if ti >= 24 or "bad" in raum["name"].lower() \
            or "dusche" in raum["name"].lower() or "wc" in raum["name"].lower() \
            else p["n_wohn"]

    # ── Transmissionskoeffizient HT ──────────────────────────
    # Aus alten DIN-4701-Werten rückgerechnet (wie im ODS)
    qt = raum.get("qt_1995")
    ql = raum.get("ql_1995")
    if qt is not None and dt_i > 0:
        ht = qt / dt_i
    else:
        ht = 0.0

    # ── Lüftungskoeffizient HV ───────────────────────────────
    hv = p["rcp_luft"] * n_min * vol

    # ── Heizlast EN 12831 ────────────────────────────────────
    phi_hl = round((ht + hv) * dt_i, 4)

    # ── Vergleichswert DIN 4701/1995 ─────────────────────────
    qn_1995 = (qt or 0) + (ql or 0)

    # ── HK-Korrektur EN 442 ──────────────────────────────────
    dt_neu    = p["tm"] - ti                 # Betriebspunkt: tm − θi
    n_exp     = n_exponent(raum["hk_typ"], p)
    q_wp_hk   = 0.0
    if raum["hk_typ"] in ("Typ10", "Typ11", "Typ21") and raum["hk_q_norm"] and n_exp:
        q_wp_hk = round(raum["hk_q_norm"] * (dt_neu / p["dt_norm"]) ** n_exp, 6)

    # ── Wandheizung Hypoplan ─────────────────────────────────
    q_wp_wand = 0.0
    if raum["wand_fl"] and raum["wand_fl"] > 0:
        q_wp_wand = round(raum["wand_fl"] * p["hypo_steig"] * dt_neu, 6)

    # ── Gesamtleistung & Reserve ─────────────────────────────
    q_wp_gesamt = round(q_wp_hk + q_wp_wand, 6)
    reserve     = round(q_wp_gesamt - qn_1995, 6)

    # Status-Label
    if raum["hk_typ"] is None and raum["wand_fl"] == 0:
        status = "○ mitgeheizt"
    elif reserve >= 0:
        status = "✓ OK"
    elif reserve >= -100:
        status = "~ Grenz"
    else:
        status = "✗ zu klein"

    # ── Auslegungsvolumenstrom ───────────────────────────────
    q_ausl = min(q_wp_gesamt, qn_1995) if qn_1995 > 0 else q_wp_gesamt
    massenstrom = round(q_ausl / p["div_vol"], 6) if p["div_vol"] > 0 else 0

    return {
        **raum,
        "h":            h,
        "vol":          vol,
        "n_min":        n_min,
        "ht":           round(ht, 6),
        "hv":           round(hv, 4),
        "phi_hl":       phi_hl,
        "qn_1995":      qn_1995,
        "dt_neu":       round(dt_neu, 1),
        "n_exp":        n_exp,
        "q_wp_hk":      q_wp_hk,
        "q_wp_wand":    q_wp_wand,
        "q_wp_gesamt":  q_wp_gesamt,
        "reserve":      reserve,
        "status":       status,
        "q_ausl":       round(q_ausl, 4),
        "massenstrom":  massenstrom,
    }


def berechne_alle(raeume, parameter):
    """Berechnet alle Räume und gibt Ergebnisliste + Summen zurück."""
    p = abgeleitete_parameter(parameter)
    ergebnis = [berechne_raum(r, p) for r in raeume]

    def summe(key, gs=None):
        subset = [r for r in ergebnis if gs is None or r["gs"] == gs]
        return round(sum(r[key] for r in subset if isinstance(r.get(key), (int, float))), 4)

    summen = {
        "kg": {
            "flaeche":      summe("flaeche",    "KG"),
            "vol":          summe("vol",         "KG"),
            "phi_hl":       summe("phi_hl",      "KG"),
            "qn_1995":      summe("qn_1995",     "KG"),
            "q_wp_gesamt":  summe("q_wp_gesamt", "KG"),
            "massenstrom":  summe("massenstrom", "KG"),
        },
        "eg": {
            "flaeche":      summe("flaeche",    "EG"),
            "vol":          summe("vol",         "EG"),
            "phi_hl":       summe("phi_hl",      "EG"),
            "qn_1995":      summe("qn_1995",     "EG"),
            "q_wp_gesamt":  summe("q_wp_gesamt", "EG"),
            "massenstrom":  summe("massenstrom", "EG"),
        },
        "gesamt": {
            "flaeche":      summe("flaeche"),
            "vol":          summe("vol"),
            "phi_hl":       summe("phi_hl"),
            "qn_1995":      summe("qn_1995"),
            "q_wp_gesamt":  summe("q_wp_gesamt"),
            "massenstrom":  summe("massenstrom"),
        },
    }
    return ergebnis, summen, p


# ── Jinja2 rendern ─────────────────────────────────────────────────────────────

def render(template_name, **ctx):
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=False,
    )
    return env.get_template(template_name).render(**ctx)


# ── Hauptprogramm ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    raeume_calc, summen, p = berechne_alle(RAEUME, PARAMETER)

    # Deckblatt
    html_deck = render("deckblatt.html",
                       projekt=PROJEKT, parameter=p, summen=summen)

    # Heizlastblatt (alle Räume)
    html_hl = render("heizlast.html",
                     projekt=PROJEKT, parameter=p,
                     raeume=raeume_calc, summen=summen)

    # Hydraulischer Abgleich
    html_ha = render("hydraulik.html",
                     projekt=PROJEKT, parameter=p,
                     raeume=raeume_calc, summen=summen)

    out = Path("output")
    out.mkdir(exist_ok=True)

    (out / "deckblatt.html").write_text(html_deck, encoding="utf-8")
    (out / "heizlast.html").write_text(html_hl,   encoding="utf-8")
    (out / "hydraulik.html").write_text(html_ha,  encoding="utf-8")

    print("✓ output/deckblatt.html")
    print("✓ output/heizlast.html")
    print("✓ output/hydraulik.html")
    print()
    print(f"  Gesamtheizlast:    {summen['gesamt']['phi_hl']:,.0f} W")
    print(f"  QN 1995 gesamt:    {summen['gesamt']['qn_1995']:,.0f} W")
    print(f"  Volumenstrom ges.: {summen['gesamt']['massenstrom']:,.1f} l/h")
