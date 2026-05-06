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

  Rohrnetz-Druckverlust (Kupfer, Parallelstrang):
    di     = rohr_d_hk − 2.0              [mm]  Innendurchmesser (Wandstärke ~1mm)
    v_str  = v_soll / (900 × π × (di/2000)²)    [m/s]  Strömungsgeschwindigkeit
    R      = 0.025 × (v_str² × 1000) / di       [mbar/m]  Rohrreibung (vereinfacht)
    dp_rohr = 2 × R × rohr_l_hk × rohr_zuschlag [mbar]  Hin + Rücklauf

  Ventil-Voreinstellung:
    dp_ventil = dp_pumpe − dp_rohr − dp_hk_intern   [mbar]
    kv_ben    = (v_soll / 1000) / √(dp_ventil / 100) [m³/h]
    ve        = kleinste Stufe mit ventil_kv[stufe] ≥ kv_ben
    Fallback  = dp_pumpe × 0.5 falls dp_ventil ≤ 0
"""

import sys
import math
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


# ── Rohrnetz-Druckverlust ──────────────────────────────────────────────────────

def berechne_dp_rohr(v_soll_lh, p):
    """
    Druckverlust im Ø15-Abschnitt (letztes Stück zum HK), Hin + Rücklauf.
    Kupfer: Wandstärke ~1mm → di = d_außen − 2mm
    Vereinfachte Rohrreibungsformel (Blasius-Näherung für turbulente Strömung).
    Gibt dp_rohr [mbar] zurück.
    """
    d_aussen  = p.get("rohr_d_hk", 15)          # mm
    l_hk      = p.get("rohr_l_hk", 5.0)         # m
    zuschlag  = p.get("rohr_zuschlag", 1.3)      # Bögen/Fittings

    di_mm = d_aussen - 2.0                       # Innendurchmesser mm (Cu Wandstärke ~1mm)
    di_m  = di_mm / 1000.0

    if v_soll_lh <= 0 or di_m <= 0:
        return 0.0

    # Volumenstrom m³/s
    q_m3s = v_soll_lh / 1000.0 / 3600.0
    # Querschnitt m²
    A = math.pi * (di_m / 2) ** 2
    # Strömungsgeschwindigkeit m/s
    v_str = q_m3s / A

    # Rohrreibungszahl λ (Blasius, turbulent, glatte Rohre)
    Re = v_str * di_m / 1e-6          # kinematische Viskosität Wasser ~1e-6 m²/s bei 50°C
    if Re < 1:
        return 0.0
    lam = 0.316 / Re**0.25 if Re > 2300 else 64 / Re

    # Druckgradient Pa/m → mbar/m
    R_pa = lam * (1.0 / di_m) * (985 * v_str**2 / 2)   # ρ Wasser ~985 kg/m³ bei 55°C
    R_mbar = R_pa / 100.0

    # Hin + Rücklauf × Zuschlag
    dp = round(2 * R_mbar * l_hk * zuschlag, 1)
    return dp


# ── Ventil-Voreinstellung ──────────────────────────────────────────────────────

def berechne_ve(v_soll_lh, dp_ventil, kv_tabelle, max_stufe):
    """
    Gibt Voreinstellstufe zurück (1 … max_stufe).
    kv_tabelle : Liste von kv-Werten [m³/h], Index 0 = Stufe 1
    dp_ventil  : verfügbarer Differenzdruck am Ventil [mbar]
    Gibt None zurück wenn dp ≤ 0 oder v_soll = 0.
    """
    if not dp_ventil or dp_ventil <= 0 or not v_soll_lh or v_soll_lh <= 0:
        return None
    kv_ben = (v_soll_lh / 1000.0) / math.sqrt(dp_ventil / 100.0)
    for stufe, kv in enumerate(kv_tabelle, start=1):
        if kv >= kv_ben:
            return stufe
    return max_stufe   # v_soll > was Ventil schafft → voll auf


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

    hk_liste = raum.get("heizkoerper") or []

    hk_liste_calc = []
    for hk in hk_liste:
        n_exp_hk = n_exponent(hk["typ"], p)
        q_norm   = hk.get("hk_q_norm") or hk.get("q_norm")
        q_hk = 0.0
        if hk["typ"] in ("Typ10", "Typ11", "Typ21", "Typ22") and q_norm and n_exp_hk:
            q_hk = round(q_norm * (dt_neu / p["dt_norm"]) ** n_exp_hk, 2)
            q_wp_hk += q_hk
        hk_liste_calc.append({**hk, "q_wp": q_hk, "n_exp": n_exp_hk})

    q_wp_hk = round(q_wp_hk, 2)
    if hk_liste_calc:
        exps = set(hk["n_exp"] for hk in hk_liste_calc if hk["n_exp"])
        n_exp = hk_liste_calc[0]["n_exp"] if len(exps) == 1 else "gem."
    else:
        n_exp = None

    # ── Wandheizung ───────────────────────────────────────
    q_wp_wand = 0.0
    if raum.get("wand_fl") and raum["wand_fl"] > 0:
        q_wp_wand = round(raum["wand_fl"] * p["hypo_steig"] * dt_neu, 2)

    # ── Gesamt & Reserve ──────────────────────────────────
    q_wp_gesamt = round(q_wp_hk + q_wp_wand, 2)
    reserve     = round(q_wp_gesamt - phi_hl, 2)

    if not hk_liste and not raum.get("wand_fl"):
        status = "○ mitgeheizt"
    elif reserve >= 0:
        status = "✓ OK"
    elif reserve >= -100:
        status = "~ Grenz"
    else:
        status = "✗ zu klein"

    # ── Volumenstrom ──────────────────────────────────────
    q_ausl = round(min(q_wp_gesamt, phi_hl) if phi_hl > 0 else q_wp_gesamt, 2)
    v_soll = round(q_ausl / p["div_vol"], 2) if p["div_vol"] > 0 else 0.0

    # ── Hydraulischer Abgleich ────────────────────────────
    # Rohrverlust aus physikalischen Parametern berechnen
    dp_rohr = berechne_dp_rohr(v_soll, p)

    # dp_ventil: explizit im Raum überschreibbar, sonst aus Parametern
    if raum.get("dp") is not None:
        dp_ventil = raum["dp"]
    else:
        dp_pumpe    = p.get("dp_pumpe",    400)
        dp_hk_int   = p.get("dp_hk_intern", 80)
        dp_ventil   = dp_pumpe - dp_rohr - dp_hk_int
        # Fallback falls Rohrverlust zu groß berechnet (unplausibel)
        if dp_ventil <= 0:
            dp_ventil = dp_pumpe * 0.5

    dp_ventil = round(dp_ventil, 1)

    # Ventil-Kennlinie aus PARAMETER lesen
    kv_tab    = p.get("ventil_kv",     [0.04, 0.10, 0.19, 0.32, 0.50, 0.82])
    max_stufe = p.get("ventil_stufen", 6)

    ve = berechne_ve(v_soll, dp_ventil, kv_tab, max_stufe)

    return {
        **raum,
        "bauteile_calc":    bauteile_calc,
        "heizkoerper_calc": hk_liste_calc,
        "h": h, "vol": vol, "n_min": n_min,
        "ht": ht, "hv": hv,
        "phi_hl": phi_hl,
        "dt_neu": dt_neu, "n_exp": n_exp,
        "q_wp_hk": q_wp_hk, "q_wp_wand": q_wp_wand,
        "q_wp_gesamt": q_wp_gesamt, "reserve": reserve,
        "status": status,
        "q_ausl":    q_ausl,
        "v_soll":    v_soll,
        "dp_rohr":   dp_rohr,       # berechneter Rohrverlust [mbar]
        "dp_ventil": dp_ventil,     # verfügbarer Druck am Ventil [mbar]
        "ve":        ve,            # Voreinstellstufe
        "massenstrom": v_soll,      # Rückwärtskompatibilität
    }


def berechne_alle(raeume, parameter):
    p        = abgeleitete_parameter(parameter)
    ergebnis = [berechne_raum(r, p) for r in raeume]

    geschosse = sorted(set(r["gs"] for r in ergebnis))

    def summe(key, gs=None):
        subset = [r for r in ergebnis if gs is None or r["gs"] == gs]
        return round(sum(r[key] for r in subset
                         if isinstance(r.get(key), (int, float))), 2)

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
