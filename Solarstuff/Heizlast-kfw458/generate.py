"""
Heizlastberechnung & Hydraulischer Abgleich – Generator
=========================================================
Norm:    DIN EN 12831-1  (Heizlast aus Bauteilen)
         EN 442          (Heizkörper-Leistungskorrektur)
Zweck:   KfW 458 / VdZ-Nachweis Verfahren B

Verwendung:
    python3 generate.py <projektname>
    python3 generate.py mustermann

Erwartet:  daten/daten_<projektname>.py
Ausgabe:   output/<projektname>/

Berechnungsformeln EN 12831:

  HT  = Σ (A_netto × U × fx)         [W/K]  Transmissionskoeffizient
  HV  = ρcp_L × n_min × V            [W/K]  Lüftungskoeffizient
  ΦHL = (HT + HV) × (θi − θe)        [W]    Heizlast

  EN 442 Heizkörperkorrektur:
    tm_norm = (VL_norm + RL_norm) / 2
    ΔT_norm = tm_norm − Ti_norm        (= 50 K bei 75/65/20)
    ΔT_neu  = tm − θi
    Q_WP_HK = Q_Norm × (ΔT_neu / ΔT_norm) ^ n

  Wandheizung Hypoplan:
    Steigung   = q_hypo / (tm_norm − Ti_norm)
    Q_WP_Wand  = A_Wand × Steigung × ΔT_neu

  Volumenstrom:
    Q_Ausl = min(Q_WP_Gesamt, ΦHL)
    ṁ      = Q_Ausl / (ρcp_Wasser × Spreizung)   [l/h]
"""

import sys
import importlib
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# ── Projektname aus Kommandozeile ──────────────────────────────────────────────
if len(sys.argv) < 2:
    print("Verwendung:  python3 generate.py <projektname>")
    print("Beispiel:    python3 generate.py mustermann")
    print("Erwartet:    daten/daten_<projektname>.py")
    sys.exit(1)

projektname = sys.argv[1].lower()

sys.path.insert(0, str(Path(__file__).parent / "daten"))
try:
    modul     = importlib.import_module(f"daten_{projektname}")
    PROJEKT   = modul.PROJEKT
    PARAMETER = modul.PARAMETER
    RAEUME    = modul.RAEUME
except ModuleNotFoundError:
    print(f"FEHLER: daten/daten_{projektname}.py nicht gefunden.")
    sys.exit(1)


# ── Abgeleitete Parameter ──────────────────────────────────────────────────────

def abgeleitete_parameter(p):
    tm         = (p["vl"] + p["rl"]) / 2
    tm_norm    = (p["vl_norm"] + p["rl_norm"]) / 2
    dt_norm    = tm_norm - p["ti_norm"]       # 50 K bei 75/65/20
    dt_spreiz  = p["vl"] - p["rl"]
    div_vol    = p["rcp_wasser"] * dt_spreiz
    hypo_steig = p["q_hypo"] / dt_norm        # W/(m²·K)
    return {**p,
            "tm": tm, "tm_norm": tm_norm, "dt_norm": dt_norm,
            "dt_spreiz": dt_spreiz, "div_vol": div_vol,
            "hypo_steig": hypo_steig}


# ── Raumberechnung ─────────────────────────────────────────────────────────────

def n_exponent(hk_typ, p):
    return {"Typ10": p["n_typ10"],
            "Typ11": p["n_typ11"],
            "Typ21": p["n_typ21"],
            "Typ22": p["n_typ22"]}.get(hk_typ)


def berechne_raum(raum, p):
    gs   = raum["gs"]
    h    = p["h_kg"] if gs == "KG" else p["h_eg"]
    ti   = raum["theta_i"]
    te   = p["theta_e"]
    dt_i = ti - te
    vol  = round(raum["flaeche"] * h, 4)

    # Lüftungsklasse nach Raumtyp
    name_lower = raum["name"].lower()
    n_min = p["n_feucht"] if (
        ti >= 24
        or "bad" in name_lower
        or "dusche" in name_lower
        or "wc" in name_lower
    ) else p["n_wohn"]

    # ── HT aus Bauteilen ──────────────────────────────────
    bauteile_calc = []
    ht = 0.0
    for bt in raum.get("bauteile", []):
        phi_t = round(bt["a_netto"] * bt["u_wert"] * bt["fx"] * dt_i, 2)
        ht   += bt["a_netto"] * bt["u_wert"] * bt["fx"]
        bauteile_calc.append({**bt, "phi_t": phi_t})

    ht = round(ht, 6)

    # ── HV Lüftung ────────────────────────────────────────
    hv = round(p["rcp_luft"] * n_min * vol, 4)

    # ── Heizlast EN 12831 ─────────────────────────────────
    phi_hl = round((ht + hv) * dt_i, 2)

    # ── EN 442 Heizkörperkorrektur ────────────────────────
    dt_neu  = round(p["tm"] - ti, 1)
    q_wp_hk = 0.0

    # Alle HK sammeln (mehrere_hk hat Vorrang)
    hk_liste = raum.get("mehrere_hk") or []
    if not hk_liste and raum["hk_typ"] is not None:
        hk_liste = [{"hk_typ": raum["hk_typ"],
                     "hk_q_norm": raum.get("hk_q_norm")}]

    for hk in hk_liste:
        n_exp_hk = n_exponent(hk["hk_typ"], p)
        q_norm   = hk.get("hk_q_norm")
        if hk["hk_typ"] in ("Typ10", "Typ11", "Typ21", "Typ22") and q_norm and n_exp_hk:
            q_wp_hk += round(q_norm * (dt_neu / p["dt_norm"]) ** n_exp_hk, 2)

    q_wp_hk = round(q_wp_hk, 2)
    n_exp = n_exponent(raum["hk_typ"], p)  # für Template-Ausgabe (erster HK)

    # ── Wandheizung ───────────────────────────────────────
    q_wp_wand = 0.0
    if raum.get("wand_fl") and raum["wand_fl"] > 0:
        q_wp_wand = round(raum["wand_fl"] * p["hypo_steig"] * dt_neu, 2)

    # ── Gesamt & Reserve ──────────────────────────────────
    q_wp_gesamt = round(q_wp_hk + q_wp_wand, 2)
    reserve     = round(q_wp_gesamt - phi_hl, 2)

    if raum["hk_typ"] is None and not raum.get("wand_fl"):
        status = "○ mitgeheizt"
    elif reserve >= 0:
        status = "✓ OK"
    elif reserve >= -100:
        status = "~ Grenz"
    else:
        status = "✗ zu klein"

    # ── Volumenstrom (v_soll wird berechnet, ve/dp kommen aus Eingabe) ────────
    q_ausl  = round(min(q_wp_gesamt, phi_hl) if phi_hl > 0 else q_wp_gesamt, 2)
    v_soll  = round(q_ausl / p["div_vol"], 2) if p["div_vol"] > 0 else 0.0

    # ve und dp: aus Eingabe übernehmen (None bis Rohrnetzberechnung vorliegt)
    ve = raum.get("ve")   # Voreinstellwert Thermostatventil
    dp = raum.get("dp")   # Druckverlust mbar

    return {
        **raum,
        "bauteile_calc": bauteile_calc,
        "h": h, "vol": vol, "n_min": n_min,
        "ht": ht, "hv": hv,
        "phi_hl": phi_hl,
        "dt_neu": dt_neu, "n_exp": n_exp,
        "q_wp_hk": q_wp_hk, "q_wp_wand": q_wp_wand,
        "q_wp_gesamt": q_wp_gesamt, "reserve": reserve,
        "status": status,
        "q_ausl": q_ausl,
        "v_soll": v_soll,   # berechnet
        "ve":     ve,        # Eingabe
        "dp":     dp,        # Eingabe
        # Rückwärtskompatibilität: massenstrom = v_soll
        "massenstrom": v_soll,
    }


def berechne_alle(raeume, parameter):
    p        = abgeleitete_parameter(parameter)
    ergebnis = [berechne_raum(r, p) for r in raeume]

    geschosse = sorted(set(r["gs"] for r in ergebnis))

    def summe(key, gs=None):
        subset = [r for r in ergebnis if gs is None or r["gs"] == gs]
        return round(sum(r[key] for r in subset
                         if isinstance(r.get(key), (int, float))), 2)

    # Summen pro Geschoss + Gesamt
    summen = {"gesamt": {k: summe(k) for k in
                         ["flaeche", "vol", "ht", "hv", "phi_hl",
                          "q_wp_gesamt", "q_ausl", "v_soll", "massenstrom"]}}
    for gs in geschosse:
        summen[gs] = {k: summe(k, gs) for k in
                      ["flaeche", "vol", "ht", "hv", "phi_hl",
                       "q_wp_gesamt", "q_ausl", "v_soll", "massenstrom"]}

    return ergebnis, summen, p, geschosse


# ── Jinja2 ────────────────────────────────────────────────────────────────────

def render(template_name, **ctx):
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=False,
    )
    return env.get_template(template_name).render(**ctx)


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    raeume_calc, summen, p, geschosse = berechne_alle(RAEUME, PARAMETER)

    out = Path("output") / projektname
    out.mkdir(parents=True, exist_ok=True)

    ctx = dict(projekt=PROJEKT, parameter=p,
               raeume=raeume_calc, summen=summen, geschosse=geschosse)

    (out / "deckblatt.html").write_text(render("deckblatt.html", **ctx), encoding="utf-8")
    (out / "heizlast.html").write_text( render("heizlast.html",  **ctx), encoding="utf-8")
    (out / "hydraulik.html").write_text(render("hydraulik.html", **ctx), encoding="utf-8")

    print(f"✓ output/{projektname}/deckblatt.html")
    print(f"✓ output/{projektname}/heizlast.html")
    print(f"✓ output/{projektname}/hydraulik.html")
    print()
    print(f"  Gesamtheizlast ΦHL:  {summen['gesamt']['phi_hl']:>8.0f} W")
    print(f"  Q_WP gesamt:         {summen['gesamt']['q_wp_gesamt']:>8.0f} W")
    print(f"  V_soll gesamt:       {summen['gesamt']['v_soll']:>8.1f} l/h")
