"""
generate_optimize.py – WP-limitierter Min-Max-Optimierer
==========================================================
Wärmepumpe kann nur 8800 W (±10%) liefern, ΦHL Gebäude liegt bei ~16 kW.
Es gibt also ein systemisches Defizit. Dieser Optimierer verteilt es
"min-max-fair": kein Raum ist viel schlechter dran als andere.

Verwendung:
    python3 generate_optimize.py <projektname>

Erwartet:  daten/daten_<projektname>.py mit
             PARAMETER["wp_leistung_max"]    z.B. 8800
             PARAMETER["wp_leistung_tol"]    optional, default 0.10 (= ±10%)

Ausgabe:   output/<projektname>/    Norm- und _moh-Variante (HTML)


Algorithmus (zwei Stufen, pro Variante):

  STUFE 1 — VL pro Kreis suchen:
    Probiere alle Kombinationen (vl_hk, vl_wand) im sinnvollen Bereich
    (30..vl_orig in 1°C-Schritten). Für jede Kombination:
      - berechne alle Räume
      - prüfe: Q_WP_gesamt ∈ [wp_min, wp_max]
      - bewerte: max_defizit_pct = max((φhl - q_ausl) / φhl)
    Wähle Kombination mit kleinstem max_defizit_pct.
    Sekundärkriterium bei Gleichstand: niedrigste Σ(VL) (besserer COP).

  STUFE 2 — Ventil-Kappung für überversorgte HK-Räume:
    Räume mit Reserve > 200 W bekommen v_soll_vorgabe + ve_max gesetzt:
      - simuliere reduzierte Volumenströme
      - finde V_soll, bei dem Reserve nahe +200 W
      - setze raum["v_soll_vorgabe"] und raum["ve_max"]
    HINWEIS: Kappung wirkt im Modell schwach (f_flow-Exponent 0.1),
    in der Praxis aber stark, weil Thermostate schließen wenn θi
    erreicht. Die Kappung ist also primär dokumentarisch:
    "dieser Raum darf nicht mehr als Stufe X bekommen".

WANDHEIZUNG: wird über VL mitoptimiert (kein Ventil-Eingriff,
weil Wandheizung kein typisches HK-Thermostat hat).

BÄDER: keine Sonderbehandlung — alle Räume gleich.

FBH (zukünftig): wenn FBH-Kreis hinzukommt, in KREIS_REIHENFOLGE
unten ergänzen und prüfen, ob f_flow-Logik in iteriere_tm passt
(FBH ist Flächensystem, dort gilt f_flow ≈ 1).
"""

import sys
import math
import importlib
import copy
from itertools import product
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# ── Argumente und Daten laden ──────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Verwendung:  python3 generate_optimize.py <projektname>")
    sys.exit(1)

projektname = sys.argv[1].lower()
sys.path.insert(0, str(Path(__file__).parent / "daten"))
sys.path.insert(0, str(Path(__file__).parent))

try:
    modul     = importlib.import_module(f"daten_{projektname}")
    PROJEKT   = modul.PROJEKT
    PARAMETER = modul.PARAMETER
    RAEUME    = modul.RAEUME
except ModuleNotFoundError:
    print(f"FEHLER: daten/daten_{projektname}.py nicht gefunden.")
    sys.exit(1)

gen = importlib.import_module("generate")


# ── Konfiguration ──────────────────────────────────────────────────────────────

KREIS_REIHENFOLGE = ["wand", "hk"]   # FBH ergänzen wenn verbaut
RESERVE_KAP_W     = 200              # Räume mit Reserve > 200 W kappen
KAP_ZIEL_W        = 200              # Reserve nach Kappung ≈ +200 W
VL_SCHRITT        = 1                # °C
VL_MIN_BAD_OFFSET = 5                # tm muss ≥ θi + 5 K sein


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def kreis_eines_raums(raum):
    hk = raum.get("heizkoerper") or []
    if hk:                       return hk[0].get("kreis", "hk")
    if raum.get("wand_fl"):      return raum.get("wand_kreis", "wand")
    if raum.get("fbh_fl"):       return raum.get("fbh_kreis", "fbh")
    return None


def aktive_kreise(raeume, parameter):
    """Welche Kreise sind in Räumen verbaut UND in PARAMETER definiert?"""
    benutzt = set()
    for r in raeume:
        k = kreis_eines_raums(r)
        if k: benutzt.add(k)
    return [k for k in KREIS_REIHENFOLGE
            if k in benutzt and k in parameter.get("kreise", {})]


def defizit_pct(raum):
    """Defizit eines Raumes in % von φhl. Mitgeheizte Räume: 0%."""
    if raum["status"] == "○ mitgeheizt":   return 0.0
    if raum["phi_hl"] <= 0:                return 0.0
    fehlmenge = max(0, raum["phi_hl"] - raum["q_wp_gesamt"])
    return round(100 * fehlmenge / raum["phi_hl"], 1)


def bewerte_konfiguration(raeume_calc, summen, wp_min, wp_max):
    """
    Liefert ein Bewertungs-Tupel zum Sortieren (kleiner = besser):
      (wp_verletzung, max_defizit_pct, mittel_defizit_pct)
    """
    q_wp = summen["gesamt"]["q_wp_gesamt"]
    if q_wp < wp_min:
        wp_verletzung = wp_min - q_wp
    elif q_wp > wp_max:
        wp_verletzung = q_wp - wp_max
    else:
        wp_verletzung = 0

    defs = [defizit_pct(r) for r in raeume_calc
            if r["status"] != "○ mitgeheizt" and r["phi_hl"] > 0]
    if defs:
        max_def    = max(defs)
        mittel_def = sum(defs) / len(defs)
    else:
        max_def = mittel_def = 0.0

    return (wp_verletzung, max_def, round(mittel_def, 2))


# ── STUFE 1: VL pro Kreis suchen ──────────────────────────────────────────────

def suche_beste_vl(raeume, parameter):
    """
    Brute-Force-Suche im Produkt aller (vl_hk, vl_wand)-Kombinationen.
    Bei zwei Kreisen mit je ~15 Werten = ~225 Berechnungen, das ist OK.
    """
    p_orig    = copy.deepcopy(parameter)
    wp_max_w  = p_orig.get("wp_leistung_max", 9999999)
    wp_tol    = p_orig.get("wp_leistung_tol", 0.10)
    wp_lo     = wp_max_w * (1 - wp_tol)
    wp_hi     = wp_max_w * (1 + wp_tol)

    kreise = aktive_kreise(raeume, p_orig)

    # VL-Bereich pro Kreis
    vl_min_global = max(int(max(r["theta_i"] for r in raeume) + VL_MIN_BAD_OFFSET), 30)
    vl_bereiche = {}
    for k in kreise:
        vl_orig = p_orig["kreise"][k]["vl"]
        vl_bereiche[k] = list(range(vl_min_global, vl_orig + 1, VL_SCHRITT))

    # Cartesisches Produkt aller VL-Kombinationen
    namen = list(vl_bereiche.keys())
    kombis = list(product(*[vl_bereiche[k] for k in namen]))

    print(f"  WP-Fenster:    [{wp_lo:.0f} .. {wp_hi:.0f}] W")
    print(f"  Kreise:        {namen}")
    print(f"  VL-Bereiche:   "
          f"{dict((k, (v[0], v[-1])) for k,v in vl_bereiche.items())}")
    print(f"  Teste {len(kombis)} VL-Kombinationen ...", end=" ")

    beste_score = None
    beste_combo = None
    beste_data  = None

    for combo in kombis:
        p_test = copy.deepcopy(p_orig)
        for k, vl in zip(namen, combo):
            p_test["kreise"][k]["vl"] = vl
        try:
            raeume_calc, summen, _, _ = gen.berechne_alle(raeume, p_test)
        except Exception:
            continue
        score = bewerte_konfiguration(raeume_calc, summen, wp_lo, wp_hi)
        # Sekundär: niedrige VL bevorzugen (besserer COP)
        score_full = score + (sum(combo),)
        if beste_score is None or score_full < beste_score:
            beste_score = score_full
            beste_combo = combo
            beste_data  = (raeume_calc, summen, p_test)

    print("fertig.")
    if beste_combo is None:
        print("  ⚠ keine zulässige Kombination gefunden")
        return p_orig, None

    p_opt = beste_data[2]
    print(f"  Beste VL-Kombi:  ", end="")
    for k, vl in zip(namen, beste_combo):
        vl_orig = p_orig["kreise"][k]["vl"]
        delta = vl - vl_orig
        print(f"{k}={vl}°C ({delta:+d} K)  ", end="")
    print()
    wp_verl, max_def, mittel_def = beste_score[:3]
    print(f"  Q_WP gesamt:     {beste_data[1]['gesamt']['q_wp_gesamt']:.0f} W "
          f"(Verletzung: {wp_verl:.0f} W)")
    print(f"  max Defizit:     {max_def:.1f} %")
    print(f"  Ø  Defizit:      {mittel_def:.1f} %")

    return p_opt, beste_data


# ── STUFE 2: Ventil-Kappung ────────────────────────────────────────────────────

def kappe_ventile(raeume, parameter, raeume_calc):
    """
    Räume mit Reserve > RESERVE_KAP_W bekommen v_soll_vorgabe + ve_max gesetzt.
    Mutiert die raeume-Liste in-place. Gibt Anzahl gekappter Räume zurück.
    """
    p_calc = gen.abgeleitete_parameter(parameter)
    n_kap = 0
    raum_by_nr = {r["nr"]: r for r in raeume}

    for rcalc in raeume_calc:
        if rcalc["status"] == "○ mitgeheizt":   continue
        if rcalc["reserve"] <= RESERVE_KAP_W:   continue
        if not rcalc.get("heizkoerper_calc"):   continue   # nur HK-Räume

        v_orig = rcalc["v_soll"]
        gef_v  = None
        v_test = v_orig
        for faktor in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.25, 0.2]:
            v_test = round(v_orig * faktor, 1)
            r_in = raum_by_nr[rcalc["nr"]]
            test_raum = {**r_in, "v_soll_vorgabe": v_test}
            r_neu = gen.berechne_raum(test_raum, p_calc)
            if r_neu["reserve"] < KAP_ZIEL_W:
                gef_v = v_test
                break
        if gef_v is None:
            gef_v = v_test

        # ve_max berechnen
        dp_schaetz = max(parameter.get("dp_pumpe", 400) * 0.5,
                         parameter.get("dp_pumpe", 400) - 80)
        kv = (gef_v / 1000) / math.sqrt(dp_schaetz / 100) if dp_schaetz > 0 else 0.0
        kv_tab = parameter.get("ventil_kv", [0.04,0.10,0.19,0.32,0.50,0.82])
        ve_max = parameter.get("ventil_stufen", 6)
        for s, k in enumerate(kv_tab, 1):
            if k >= kv:
                ve_max = s
                break

        raum_orig = raum_by_nr[rcalc["nr"]]
        raum_orig["v_soll_vorgabe"] = gef_v
        raum_orig["ve_max"]         = ve_max
        alt_bem = raum_orig.get("bemerkung") or ""
        kap_info = f"⚙ Ventil ≤ Stufe {ve_max} (V={gef_v} l/h)"
        raum_orig["bemerkung"] = (alt_bem + "; " + kap_info) if alt_bem else kap_info

        n_kap += 1

    return n_kap


# ── Render ────────────────────────────────────────────────────────────────────

def render(template_name, **ctx):
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=False,
    )
    return env.get_template(template_name).render(**ctx)


def schreibe_variante(raeume, parameter_var, suffix, label):
    raeume_calc, summen, p, geschosse = gen.berechne_alle(raeume, parameter_var)
    ctx = dict(projekt=PROJEKT, parameter=p, raeume=raeume_calc,
               summen=summen, geschosse=geschosse)

    out = Path("output") / projektname
    out.mkdir(parents=True, exist_ok=True)

    (out / f"deckblatt{suffix}.html").write_text(
        render("deckblatt.html", **ctx), encoding="utf-8")
    (out / f"heizlast{suffix}.html").write_text(
        render("heizlast.html",  **ctx), encoding="utf-8")
    (out / f"hydraulik{suffix}.html").write_text(
        render("hydraulik.html", **ctx), encoding="utf-8")

    # Defizit-Übersicht
    defs_pro_raum = sorted(
        [(r["name"], r["gs"], defizit_pct(r),
          r["reserve"], r["phi_hl"], r["q_wp_gesamt"])
         for r in raeume_calc if r["status"] != "○ mitgeheizt"],
        key=lambda x: -x[2]
    )

    print(f"\n  ── Ergebnis {label} ──────────────────────")
    print(f"  ΦHL gesamt:        {summen['gesamt']['phi_hl']:>8.0f} W")
    print(f"  Q_WP gesamt:       {summen['gesamt']['q_wp_gesamt']:>8.0f} W   "
          f"(Limit: {parameter_var.get('wp_leistung_max', '∞')} W ±"
          f"{int(parameter_var.get('wp_leistung_tol', 0.1)*100)}%)")
    print(f"  V_soll gesamt:     {summen['gesamt']['v_soll']:>8.1f} l/h")
    print(f"  Kreise:")
    for name, k in p["kreise"].items():
        print(f"    {name:5s}  VL={k['vl']}°C  v_max={k['v_max_ms']}m/s "
              f"→ {k['v_max_lh']:.0f} l/h")
    print(f"  Defizit-Top-5 (worst first):")
    for n, gs, d, res, phi, q in defs_pro_raum[:5]:
        print(f"    {gs:3s} {n:25s}  Defizit: {d:5.1f}%  "
              f"Reserve: {res:+7.0f} W  ({q:.0f}/{phi:.0f})")

    return raeume_calc, summen


# ── Hauptprogramm ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"╭─ Optimierung Projekt: {projektname}")
    wp_max = PARAMETER.get("wp_leistung_max")
    wp_tol = PARAMETER.get("wp_leistung_tol", 0.10)
    print(f"│  WP-Limit: {wp_max} W ±{int(wp_tol*100)}%")

    # ── Variante 1: Normauslegung ────────────────────────────────────────────
    print(f"\n├─ Variante 1: Normauslegung  θe = {PARAMETER['theta_e']} °C")
    print(f"│  STUFE 1 — VL-Suche")
    raeume_v1 = copy.deepcopy(RAEUME)
    p_v1, data_v1 = suche_beste_vl(raeume_v1, PARAMETER)

    if data_v1:
        print(f"│  STUFE 2 — Ventil-Kappung (Reserve > {RESERVE_KAP_W} W)")
        n_kap = kappe_ventile(raeume_v1, p_v1, data_v1[0])
        print(f"  → {n_kap} Räume gekappt")

    schreibe_variante(raeume_v1, p_v1, "", "Variante 1 (Norm)")

    # ── Variante 2: WP-Auslegung (θe_moh) ────────────────────────────────────
    if "theta_e_moh" in PARAMETER:
        print(f"\n├─ Variante 2: WP-Auslegung  θe_moh = {PARAMETER['theta_e_moh']} °C")
        PARAMETER_MOH = {**PARAMETER, "theta_e": PARAMETER["theta_e_moh"]}
        print(f"│  STUFE 1 — VL-Suche")
        raeume_v2 = copy.deepcopy(RAEUME)
        p_v2, data_v2 = suche_beste_vl(raeume_v2, PARAMETER_MOH)

        if data_v2:
            print(f"│  STUFE 2 — Ventil-Kappung (Reserve > {RESERVE_KAP_W} W)")
            n_kap2 = kappe_ventile(raeume_v2, p_v2, data_v2[0])
            print(f"  → {n_kap2} Räume gekappt")

        schreibe_variante(raeume_v2, p_v2, "_moh", "Variante 2 (MOH)")
    else:
        print("\n├─ Variante 2 übersprungen (theta_e_moh nicht in PARAMETER)")

    print(f"\n╰─ Fertig. PDFs erzeugen mit:  python3 generate_pdf.py {projektname}")
