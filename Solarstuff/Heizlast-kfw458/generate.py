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

  HT  = Σ (A_netto × U × fx)         [W/K]
  HV  = ρcp_L × n_min × V            [W/K]
  ΦHL = (HT + HV) × (θi − θe)        [W]

  EN 442 iterative tm/RL-Berechnung:
    Gegeben: VL (fest), V_soll (aus v_max × Querschnitt oder Vorgabe)
    Iteration bis |Δtm| < 0.01 K:
      tm       = (VL + RL) / 2
      ΔT_neu   = tm − θi
      f_flow_i = (V_soll/n_hk / V_norm_i)^0.1   EN442-Durchflusskorrekturfaktor
      Q_WP_HK  = Σ Q_Norm_i × (ΔT_neu/ΔT_norm)^n_i × f_flow_i
      Q_abgabe = min(Q_WP_HK + Q_WP_Wand, ΦHL)
      ΔT_real  = Q_abgabe / (V_soll × ρcp)
      RL_real  = VL − ΔT_real
      tm_neu   = (VL + RL_real) / 2

    ANNAHME PARALLELSCHALTUNG: Mehrere HK pro Raum werden als parallel
    angenommen → V_soll wird gleichmäßig aufgeteilt (V_soll / n_hk).
    HINWEIS REIHENSCHALTUNG: Falls HK in Reihe geschaltet sind (selten),
    muss V_soll_hk = V_soll (ungeteilt) verwendet werden und RL_zwischen
    stufenweise berechnet werden. Kennzeichnung im Raum-Dict mit
    "hk_schaltung": "reihe" vorbereiten.

    f_flow Exponent 0.1 (empirisch EN 442 Anhang):
    Halbierung des Durchflusses → ~7% Leistungsverlust.
    Bereich begrenzt auf [0.5, 2.0] für Plausibilität.

  Wandheizung: kein f_flow (Flächensystem, Durchfluss unkritisch)

  FBH: analog Wandheizung, aber eigener Kreis mit v_max=0.5 m/s (EN 1264).
    HINWEIS FBH: Bei ersten FBH-Projekten prüfen ob iteriere_tm() korrekt
    anwendbar ist. Ggf. eigene Funktion mit FBH-spezifischer Steigung bauen.

  v_max pro Kreis:
    hk   = 1.0 m/s  (Heizkörper Ø15 Cu, Standardwert)
    wand = 2.0 m/s  (Wandheizung Hypoplan verträgt höhere Geschwindigkeiten)
    fbh  = 0.5 m/s  (Fußbodenheizung EN 1264 — beim ersten FBH-Projekt prüfen!)
    V_max_lh = v_max × π × (di/2)² × 3.6e6

  Rohrnetz-Druckverlust: Blasius, Cu-Rohr, Hin + Rücklauf
  Ventil: kv_ben = (V/1000) / √(dp/100), kleinste Stufe mit kv ≥ kv_ben
"""

import sys
import math
import importlib
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

if len(sys.argv) < 2:
    print("Verwendung:  python3 generate.py <projektname>")
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
    tm_norm    = (p["vl_norm"] + p["rl_norm"]) / 2
    dt_norm    = tm_norm - p["ti_norm"]
    hypo_steig = p.get("hypo_steig") or p["q_hypo"] / dt_norm

    kreise_roh = p.get("kreise", {
        "hk":   {"vl": p.get("vl", 57)},
        "wand": {"vl": p.get("vl", 57)},
    })

    kreise = {}
    for name, k in kreise_roh.items():
        vl             = k["vl"]
        rl_start       = k.get("rl", vl - 5)      # Startwert; wird iterativ überschrieben
        tm             = (vl + rl_start) / 2
        spreiz         = vl - rl_start
        div_vol        = p["rcp_wasser"] * spreiz if spreiz > 0 else 1
        v_max_ms       = k.get("v_max_ms", 1.0)
        di_mm          = k.get("di_anschluss_mm", 13)
        di_m           = di_mm / 1000.0
        A              = math.pi * (di_m / 2) ** 2
        v_max_lh       = round(v_max_ms * A * 3.6e6, 1)
        kreise[name]   = {
            **k,
            "rl":              rl_start,
            "tm":              tm,
            "spreiz":          spreiz,
            "div_vol":         div_vol,
            "v_max_ms":        v_max_ms,
            "di_anschluss_mm": di_mm,
            "v_max_lh":        v_max_lh,
        }

    k_hk      = kreise.get("hk", next(iter(kreise.values())))
    vl_g      = k_hk["vl"]
    rl_g      = k_hk["rl"]
    dt_spreiz = vl_g - rl_g
    div_vol   = p["rcp_wasser"] * dt_spreiz if dt_spreiz > 0 else 1

    return {**p,
            "tm":         (vl_g + rl_g) / 2,
            "tm_norm":    tm_norm,
            "dt_norm":    dt_norm,
            "dt_spreiz":  dt_spreiz,
            "div_vol":    div_vol,
            "hypo_steig": hypo_steig,
            "kreise":     kreise}


def get_kreis(p, name):
    k = p.get("kreise", {})
    if name in k: return k[name]
    if k: return next(iter(k.values()))
    return {"vl": p["tm"] + p["dt_spreiz"]/2, "rl": p["tm"] - p["dt_spreiz"]/2,
            "tm": p["tm"], "spreiz": p["dt_spreiz"], "div_vol": p["div_vol"],
            "v_max_lh": 477.0, "di_anschluss_mm": 13}


# ── Rohrnetz-Druckverlust ──────────────────────────────────────────────────────

def berechne_dp_rohr(v_soll_lh, p):
    di_mm = p.get("rohr_d_hk", 15) - 2.0
    di_m  = di_mm / 1000.0
    l_hk  = p.get("rohr_l_hk", 5.0)
    zuschl = p.get("rohr_zuschlag", 1.3)
    if v_soll_lh <= 0 or di_m <= 0: return 0.0
    q     = v_soll_lh / 3.6e6
    A     = math.pi * (di_m / 2) ** 2
    v     = q / A
    Re    = v * di_m / 1e-6
    if Re < 1: return 0.0
    lam   = 0.316 / Re**0.25 if Re > 2300 else 64 / Re
    R_pa  = lam * (1 / di_m) * (985 * v**2 / 2)
    return round(2 * (R_pa / 100) * l_hk * zuschl, 1)


def berechne_ve(v_lh, dp_mbar, kv_tab, max_s):
    """
    Ventil-Voreinstellung aus benötigtem kv-Wert.
    kv-Definition (DIN EN 60534-2-3): kv = V[m³/h] / sqrt(Δp[bar])
      v_lh    [l/h]   → /1000 → m³/h
      dp_mbar [mbar]  → /1000 → bar
    Wählt kleinste Ventilstufe mit kv ≥ kv_benötigt.
    """
    if not dp_mbar or dp_mbar <= 0 or not v_lh or v_lh <= 0: return None
    kv = (v_lh / 1000) / math.sqrt(dp_mbar / 1000)
    for s, k in enumerate(kv_tab, 1):
        if k >= kv: return s
    return max_s


# ── Iterative tm/RL-Berechnung ────────────────────────────────────────────────

def iteriere_tm(vl, ti, phi_hl, hk_liste, wand_fl, hypo_steig,
                dt_norm, dt_spreiz, rcp_wasser, n_exp_fn, v_max_lh,
                vl_wand=None, iters=8):
    """
    Konvergiert VL-fest → tm, RL, V_soll je HK durch iterative Energiebilanz.

    Verfahren B (bedarfsgerecht):
      V_soll_hk = Q_WP_HK / (ρcp × ΔT_spreiz)     ← bedarfsgerecht
      Iteration: tm bestimmt Q_WP_HK, Q_WP_HK bestimmt V_soll_hk,
                 V_soll_hk bestimmt f_flow, f_flow bestimmt Q_WP_HK → fixpunkt

    Parallelschaltung: jeder HK hat eigenen V_soll, eigenes Ventil.
    Clamping: V_soll_hk ≤ v_max_lh (Anschlussleitung).

    WICHTIG vl_wand:
      Wandheizung hängt am EIGENEN Kreis (z.B. VL=40°C). vl_wand muss
      übergeben werden, sonst wird tm_wand fälschlich aus dem HK-Kreis
      abgeleitet (gemischte Räume liefern dann ~doppelte Wand-Leistung).

    Rückgabe:
      (tm, rl_real_raum, q_hk_total, q_wand_total, hk_results,
       tm_wand, dt_neu_wand)
      hk_results = [{"q_wp": ..., "v_soll": ..., "dt_real": ..., "rl_real": ...}]
      tm_wand    = mittlere Wand-Heizmedientemperatur (None falls keine Wandhz.)
      dt_neu_wand = tm_wand − θi (für Anzeige in Hydraulik-Tabelle)
    """
    n_hk = len(hk_liste)
    tm   = vl - dt_norm / 2
    scale = 1.0   # Initialisierung vor Schleife (sonst NameError bei iters=0)
    tm_wand = None
    dt_neu_wand = 0.0

    # Initialisierung: V_soll je HK aus Q_Norm-Anteil als Startschätzung
    v_soll_hk = []
    for hk in hk_liste:
        q_n = hk.get("hk_q_norm") or hk.get("q_norm") or 0
        v_n = q_n / (rcp_wasser * dt_norm) if dt_norm > 0 and q_n else 0
        v_soll_hk.append(min(v_n, v_max_lh) if v_n > 0 else v_max_lh)

    q_hk_each = [0.0] * n_hk

    for _ in range(iters):
        dt_neu = max(tm - ti, 0.1)

        # Q je HK bei aktuellem tm und aktuellem V_soll_hk
        q_hk_each = []
        for i, hk in enumerate(hk_liste):
            q_n = hk.get("hk_q_norm") or hk.get("q_norm") or 0
            n_e = n_exp_fn(hk["typ"])
            if not q_n or not n_e:
                q_hk_each.append(0.0)
                continue
            v_n  = q_n / (rcp_wasser * dt_norm) if dt_norm > 0 else 1
            v_hk = v_soll_hk[i]
            ff   = max(0.5, min((v_hk / v_n) ** 0.1 if v_n > 0 and v_hk > 0 else 1.0, 2.0))
            q_hk_each.append(q_n * (dt_neu / dt_norm) ** n_e * ff)

        q_hk_total = sum(q_hk_each)

        # Wandheizung (eigener Kreis, fester tm_wand aus Wand-VL)
        # WICHTIG: Wandheizung hängt am Wand-Kreis (vl_wand), NICHT am HK-Kreis (vl).
        # vl_wand muss vom Aufrufer übergeben werden, sonst rechnen wir mit HK-VL
        # (das wäre physikalisch falsch).
        if wand_fl > 0:
            if vl_wand is not None:
                # Wand-tm aus Wand-VL minus halber Wand-Spreizung (Schätzung 2.5K)
                tm_wand = vl_wand - 2.5
            else:
                # Fallback: nur wenn kein Wand-Kreis übergeben — sollte nicht vorkommen
                tm_wand = tm
            dt_neu_wand = max(tm_wand - ti, 0.1)
            q_wand_total = wand_fl * hypo_steig * dt_neu_wand
        else:
            tm_wand = None
            dt_neu_wand = 0.0
            q_wand_total = 0.0

        # V_soll_hk: bedarfsgerecht aus Q_WP_HK / (ρcp × ΔT)
        # KEINE Deckelung auf ΦHL hier — das verfälscht die Reserve-Anzeige
        # und macht aus überdimensionierten HK künstlich „passende" HK.
        # Die HK liefern bei tm physikalisch ihre volle Leistung; ob das mehr
        # ist als ΦHL braucht, regelt im Realbetrieb das Thermostatventil.
        # Für die Auslegung (Verfahren B) zählt die theoretisch verfügbare
        # Leistung — Reserve = Q_WP − ΦHL ist die zentrale Auslegungsgröße.
        q_abgabe = q_hk_total + q_wand_total
        scale = 1.0   # behalten als Variable für Rückwärtskompatibilität,
                      # immer 1.0 → keine Skalierung

        v_soll_hk_neu = []
        for i in range(n_hk):
            q_eff = q_hk_each[i]   # ungedeckelt
            v_b   = q_eff / (rcp_wasser * dt_spreiz) if dt_spreiz > 0 else 0
            v_soll_hk_neu.append(min(v_b, v_max_lh) if v_b > 0 else 0.0)

        # Konvergenz: tm aus Energiebilanz Raumkreis (V_soll_raum = Σ V_soll_hk)
        # WICHTIG: q_abgabe hier ungedeckelt — repräsentiert die echte
        # HK-Leistung bei tm. dt_real_raum spiegelt damit die tatsächliche
        # Auskühlung, nicht eine auf ΦHL skalierte.
        v_soll_raum = sum(v_soll_hk_neu)
        if v_soll_raum > 0:
            dt_real_raum = q_hk_total / (v_soll_raum * rcp_wasser)
        else:
            dt_real_raum = 0
        tm_neu = vl - dt_real_raum / 2

        v_soll_hk = v_soll_hk_neu
        if abs(tm_neu - tm) < 0.01:
            tm = tm_neu
            break
        tm = tm_neu

    # Finale Werte je HK (alle bei VL gespeist → eigenes ΔT_real, eigenes RL)
    hk_results = []
    for i in range(n_hk):
        v = v_soll_hk[i]
        q = q_hk_each[i]
        # Bei phi_hl-Begrenzung Q skalieren (scale ist garantiert definiert, s.o.)
        q_final = q * scale
        dt_r = q_final / (v * rcp_wasser) if v > 0 else 0
        hk_results.append({
            "q_wp":    round(q_final, 2),
            "v_soll":  round(v, 1),
            "dt_real": round(dt_r, 2),
            "rl_real": round(vl - dt_r, 2),
        })

    q_hk_final   = sum(h["q_wp"] for h in hk_results)
    q_wand_final = q_wand_total

    return (round(tm, 2), round(vl - dt_real_raum, 2),
            round(q_hk_final, 2), round(q_wand_final, 2),
            hk_results,
            round(tm_wand, 2) if tm_wand is not None else None,
            round(dt_neu_wand, 2))


# ── Raumberechnung ─────────────────────────────────────────────────────────────

def n_exponent(hk_typ, p):
    return {"Typ10": p["n_typ10"], "Typ11": p["n_typ11"],
            "Typ21": p["n_typ21"], "Typ22": p["n_typ22"]}.get(hk_typ)


def berechne_raum(raum, p):
    gs   = raum["gs"]
    h    = p["h_kg"] if gs == "KG" else p["h_eg"]
    ti   = raum["theta_i"]
    dt_i = ti - p["theta_e"]
    vol  = round(raum["flaeche"] * h, 4)

    nl   = raum["name"].lower()
    n_min = p["n_feucht"] if (ti >= 24 or "bad" in nl
            or "dusche" in nl or "wc" in nl) else p["n_wohn"]

    bauteile_calc, ht = [], 0.0
    for bt in raum.get("bauteile", []):
        phi_t = round(bt["a_netto"] * bt["u_wert"] * bt["fx"] * dt_i, 2)
        ht   += bt["a_netto"] * bt["u_wert"] * bt["fx"]
        bauteile_calc.append({**bt, "phi_t": phi_t})
    ht     = round(ht, 6)
    hv     = round(p["rcp_luft"] * n_min * vol, 4)
    phi_v  = round(hv * dt_i, 2)
    phi_hl = round((ht + hv) * dt_i, 2)

    hk_liste = raum.get("heizkoerper") or []

    # Dominanter Kreis
    if hk_liste:       kreis_name = hk_liste[0].get("kreis", "hk")
    elif raum.get("wand_fl"): kreis_name = raum.get("wand_kreis", "wand")
    elif raum.get("fbh_fl"):  kreis_name = raum.get("fbh_kreis", "fbh")
    else:              kreis_name = "hk"

    k    = get_kreis(p, kreis_name)
    vl   = k["vl"]
    wand_fl = raum.get("wand_fl") or 0
    v_max_lh = k["v_max_lh"]
    dt_spreiz_kreis = k["spreiz"]

    # Wand-Kreis-Parameter unabhängig vom dominanten Kreis vorhalten,
    # damit Wandheizung in gemischten Räumen am richtigen VL hängt.
    k_wand = get_kreis(p, "wand") if wand_fl > 0 else None
    vl_wand = k_wand["vl"] if k_wand else None
    dt_spreiz_wand = k_wand["spreiz"] if k_wand else dt_spreiz_kreis

    if hk_liste or wand_fl > 0:
        tm_real, rl_real, q_wp_hk, q_wp_wand, hk_iter, tm_wand, dt_neu_wand = iteriere_tm(
            vl=vl, ti=ti, phi_hl=phi_hl,
            hk_liste=hk_liste, wand_fl=wand_fl,
            hypo_steig=p["hypo_steig"], dt_norm=p["dt_norm"],
            dt_spreiz=dt_spreiz_kreis, rcp_wasser=p["rcp_wasser"],
            n_exp_fn=lambda typ: n_exponent(typ, p), v_max_lh=v_max_lh,
            vl_wand=vl_wand,
        )
    else:
        tm_real   = k["tm"]
        rl_real   = k["rl"]
        q_wp_hk   = 0.0
        q_wp_wand = 0.0
        hk_iter   = []
        tm_wand   = None
        dt_neu_wand = 0.0

    # V_soll-Vorgabe pro HK respektieren (überschreibt iterativen Wert)
    for i, hk in enumerate(hk_liste):
        if hk.get("v_soll_vorgabe") is not None and i < len(hk_iter):
            v_neu = float(hk["v_soll_vorgabe"])
            hk_iter[i]["v_soll"] = round(v_neu, 1)
            if v_neu > 0:
                hk_iter[i]["dt_real"] = round(hk_iter[i]["q_wp"] / (v_neu * p["rcp_wasser"]), 2)
                hk_iter[i]["rl_real"] = round(vl - hk_iter[i]["dt_real"], 2)

    # Raum-Aggregat:
    # V_soll_HK   = Σ V_soll je HK (HK-Kreis, eigene Spreizung)
    # V_soll_Wand = Q_Wand / (ρcp × ΔT_Wand-Kreis)  (eigener Kreis!)
    # V_soll      = V_soll_HK + V_soll_Wand
    v_soll_hk_sum = round(sum(h["v_soll"] for h in hk_iter), 1) if hk_iter else 0.0

    if wand_fl > 0 and q_wp_wand > 0 and dt_spreiz_wand > 0:
        v_soll_wand = round(q_wp_wand / (p["rcp_wasser"] * dt_spreiz_wand), 1)
    else:
        v_soll_wand = 0.0

    v_soll = round(v_soll_hk_sum + v_soll_wand, 1)

    dt_real = round(vl - rl_real, 2)
    dt_neu  = round(tm_real - ti, 1)

    # FBH — kein iteriere_tm (Flächensystem, RL aus Kreis)
    # HINWEIS: Bei FBH-Projekten prüfen, ggf. anpassen
    q_wp_fbh = 0.0
    if raum.get("fbh_fl") and raum["fbh_fl"] > 0:
        k_fbh    = get_kreis(p, raum.get("fbh_kreis", "fbh"))
        q_wp_fbh = round(raum["fbh_fl"] * p.get("q_fbh_steig", 8.0)
                         * (k_fbh["tm"] - ti), 2)

    # HK-Liste für Template — pro HK ve, dp, v_ms
    hk_liste_calc = []
    di_m = k.get("di_anschluss_mm", 13) / 1000
    A_q  = math.pi * (di_m / 2) ** 2 if di_m > 0 else 0
    for i, hk in enumerate(hk_liste):
        n_e   = n_exponent(hk["typ"], p)
        it    = hk_iter[i] if i < len(hk_iter) else {}
        v_hk  = it.get("v_soll", 0.0)
        q_hk  = it.get("q_wp", 0.0)
        dt_hk = it.get("dt_real", 0.0)
        rl_hk = it.get("rl_real", vl)
        v_ms_hk = round((v_hk / 3.6e6) / A_q, 2) if A_q > 0 else 0.0

        dp_rohr_hk   = berechne_dp_rohr(v_hk, p)
        dp_ventil_hk = hk.get("dp")
        if dp_ventil_hk is None:
            dp_ventil_hk = max(p.get("dp_pumpe", 400) * 0.5,
                               p.get("dp_pumpe", 400) - dp_rohr_hk - p.get("dp_hk_intern", 80))
        dp_ventil_hk = round(dp_ventil_hk, 1)
        ve_hk = berechne_ve(v_hk, dp_ventil_hk,
                            p.get("ventil_kv", [0.04,0.10,0.19,0.32,0.50,0.82]),
                            p.get("ventil_stufen", 6))

        hk_liste_calc.append({**hk, "kreis": hk.get("kreis","hk"),
                               "tm": tm_real, "dt_neu": dt_neu,
                               "q_wp": q_hk, "n_exp": n_e,
                               "v_soll":  v_hk,
                               "dt_real": dt_hk,
                               "rl_real": rl_hk,
                               "v_ms":    v_ms_hk,
                               "dp_rohr": dp_rohr_hk,
                               "dp":      dp_ventil_hk,
                               "ve":      ve_hk})

    if hk_liste_calc:
        exps  = set(h["n_exp"] for h in hk_liste_calc if h["n_exp"])
        n_exp = hk_liste_calc[0]["n_exp"] if len(exps) == 1 else "gem."
    else:
        n_exp = None

    q_wp_gesamt = round(q_wp_hk + q_wp_wand + q_wp_fbh, 2)
    reserve     = round(q_wp_gesamt - phi_hl, 2)

    if not hk_liste and not wand_fl and not raum.get("fbh_fl"):
        status = "○ mitgeheizt"
    elif reserve >= 0:   status = "✓ OK"
    elif reserve >= -100: status = "~ Grenz"
    else:                status = "✗ zu klein"

    q_ausl    = round(min(q_wp_gesamt, phi_hl) if phi_hl > 0 else q_wp_gesamt, 2)

    # Raum-Aggregat für Summenzeile / Übersicht
    # ve, dp, dp_rohr, v_ms sind jetzt pro HK (siehe heizkoerper_calc).
    # Raum-Werte: max v_ms, Σ dp_rohr (für Pumpenauslegung-Übersicht)
    if hk_liste_calc:
        v_ms_max   = max(h["v_ms"] for h in hk_liste_calc)
        dp_rohr_sum = sum(h["dp_rohr"] for h in hk_liste_calc)
        # Raum-ve/dp zeigt nichts Sinnvolles mehr → None (Template macht "–")
        ve_raum, dp_raum = None, None
    else:
        v_ms_max, dp_rohr_sum = 0.0, 0.0
        ve_raum, dp_raum = None, None

    return {
        **raum,
        "bauteile_calc":    bauteile_calc,
        "heizkoerper_calc": hk_liste_calc,
        "h": h, "vol": vol, "n_min": n_min,
        "ht": ht, "hv": hv, "phi_v": phi_v, "phi_hl": phi_hl,
        "dt_neu": dt_neu, "n_exp": n_exp,
        "tm_real": tm_real, "rl_real": rl_real, "dt_real": dt_real,
        "tm_wand": tm_wand, "dt_neu_wand": dt_neu_wand,
        "v_ms": v_ms_max,
        "q_wp_hk": q_wp_hk, "q_wp_wand": q_wp_wand, "q_wp_fbh": q_wp_fbh,
        "q_wp_gesamt": q_wp_gesamt, "reserve": reserve, "status": status,
        "q_ausl": q_ausl, "v_soll": v_soll,
        "v_soll_hk": v_soll_hk_sum, "v_soll_wand": v_soll_wand,
        "dp_rohr": dp_rohr_sum, "dp_ventil": dp_raum, "ve": ve_raum,
        "massenstrom": v_soll,
    }


def anlagenvordruck(parameter):
    """
    Berechnet den statischen Anlagen-Vordruck (Manometer-Sollwert kalt):

      p_0 = h_statisch / 10 + 0.2   [bar]

    h_statisch = vertikale Differenz Pumpe → höchster Heizkörper [m]
    Sicherheitszuschlag 0.2 bar nach Faustregel.
    """
    h_stat = parameter.get("hoehe_statisch_m", 0)
    vordruck_bar = h_stat / 10.0 + 0.2

    return {
        "h_statisch_m": h_stat,
        "vordruck_bar": round(vordruck_bar, 2),
    }


def berechne_alle(raeume, parameter):
    p         = abgeleitete_parameter(parameter)
    ergebnis  = [berechne_raum(r, p) for r in raeume]
    geschosse = sorted(set(r["gs"] for r in ergebnis))

    def summe(key, gs=None):
        s = [r for r in ergebnis if gs is None or r["gs"] == gs]
        return round(sum(r[key] for r in s if isinstance(r.get(key), (int, float))), 2)

    keys   = ["flaeche","vol","ht","hv","phi_hl","q_wp_gesamt","q_ausl","v_soll","massenstrom"]
    summen = {"gesamt": {k: summe(k) for k in keys}}
    for gs in geschosse:
        summen[gs] = {k: summe(k, gs) for k in keys}

    return ergebnis, summen, p, geschosse


def render(template_name, **ctx):
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                      autoescape=False)
    return env.get_template(template_name).render(**ctx)


if __name__ == "__main__":
    out = Path("output") / projektname
    out.mkdir(parents=True, exist_ok=True)

    # ── Variante 1: Normauslegung (θe = theta_e) ─────────────────────────────
    raeume_calc, summen, p, geschosse = berechne_alle(RAEUME, PARAMETER)
    vordruck = anlagenvordruck(PARAMETER)
    waermeerzeuger = PARAMETER.get("waermeerzeuger", {})
    pumpe_info = PARAMETER.get("pumpe", {})
    ctx = dict(projekt=PROJEKT, parameter=p, raeume=raeume_calc,
               summen=summen, geschosse=geschosse,
               vordruck=vordruck, waermeerzeuger=waermeerzeuger,
               pumpe=pumpe_info)
    (out/"deckblatt.html").write_text(render("deckblatt.html", **ctx), encoding="utf-8")
    (out/"heizlast.html").write_text( render("heizlast.html",  **ctx), encoding="utf-8")
    (out/"hydraulik.html").write_text(render("hydraulik.html", **ctx), encoding="utf-8")

    print(f"✓ output/{projektname}/deckblatt.html")
    print(f"✓ output/{projektname}/heizlast.html")
    print(f"✓ output/{projektname}/hydraulik.html")
    print()
    print(f"  Variante 1 (θe = {PARAMETER['theta_e']} °C):")
    print(f"  Gesamtheizlast ΦHL:  {summen['gesamt']['phi_hl']:>8.0f} W")
    print(f"  Q_WP gesamt:         {summen['gesamt']['q_wp_gesamt']:>8.0f} W")
    print(f"  V_soll gesamt:       {summen['gesamt']['v_soll']:>8.1f} l/h")
    print(f"  Anlagen-Vordruck:    {vordruck['vordruck_bar']:>8.2f} bar  "
          f"(h_statisch {vordruck['h_statisch_m']} m)")
    if "kreise" in p:
        print()
        print("  Kreise:")
        for name, k in p["kreise"].items():
            print(f"    {name:6s}  VL={k['vl']}°C  "
                  f"v_max={k['v_max_ms']}m/s → {k['v_max_lh']:.0f} l/h  "
                  f"di={k['di_anschluss_mm']}mm")

    # ── Variante 2: WP-Auslegung (θe = theta_e_moh) ──────────────────────────
    if "theta_e_moh" in PARAMETER:
        PARAMETER_MOH = {**PARAMETER, "theta_e": PARAMETER["theta_e_moh"]}
        raeume_calc_m, summen_m, p_m, geschosse_m = berechne_alle(RAEUME, PARAMETER_MOH)
        ctx_m = dict(projekt=PROJEKT, parameter=p_m, raeume=raeume_calc_m,
                     summen=summen_m, geschosse=geschosse_m,
                     vordruck=vordruck, waermeerzeuger=waermeerzeuger,
                     pumpe=pumpe_info)
        (out/"deckblatt_moh.html").write_text(render("deckblatt.html", **ctx_m), encoding="utf-8")
        (out/"heizlast_moh.html").write_text( render("heizlast.html",  **ctx_m), encoding="utf-8")
        (out/"hydraulik_moh.html").write_text(render("hydraulik.html", **ctx_m), encoding="utf-8")

        print()
        print(f"✓ output/{projektname}/deckblatt_moh.html")
        print(f"✓ output/{projektname}/heizlast_moh.html")
        print(f"✓ output/{projektname}/hydraulik_moh.html")
        print()
        print(f"  Variante 2 (θe_moh = {PARAMETER['theta_e_moh']} °C):")
        print(f"  Gesamtheizlast ΦHL:  {summen_m['gesamt']['phi_hl']:>8.0f} W")
        print(f"  Q_WP gesamt:         {summen_m['gesamt']['q_wp_gesamt']:>8.0f} W")
        print(f"  V_soll gesamt:       {summen_m['gesamt']['v_soll']:>8.1f} l/h")
