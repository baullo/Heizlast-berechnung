"""
generate_pdf.py – HTML → PDF Konverter (WeasyPrint)
=====================================================
Nutzt WeasyPrint (reines Python, kein externer Browser) für die
PDF-Erzeugung. Rendert CSS2/CSS3 Tabellen, @page-Margins und
print-media korrekt – ohne wkhtmltopdf oder Chromium.

Verwendung:
    python3 generate_pdf.py <projektname>
    python3 generate_pdf.py köhler

Erwartet:  output/<projektname>/deckblatt.html
           output/<projektname>/heizlast.html
           output/<projektname>/hydraulik.html

Ausgabe:   output/<projektname>/<projektname>_heizlast.pdf

Installation (einmalig):
    pip install weasyprint --break-system-packages
"""

import sys
from pathlib import Path

try:
    import weasyprint
except ImportError:
    print("FEHLER: weasyprint nicht installiert.")
    print("  pip install weasyprint --break-system-packages")
    sys.exit(1)

from pypdf import PdfWriter, PdfReader

# ── Projektname ────────────────────────────────────────────────────────────────
if len(sys.argv) < 2:
    print("Verwendung:  python3 generate_pdf.py <projektname>")
    print("Beispiel:    python3 generate_pdf.py köhler")
    sys.exit(1)

projektname = sys.argv[1].lower()
out = Path("output") / projektname

if not out.exists():
    print(f"FEHLER: output/{projektname}/ nicht gefunden.")
    print(f"Bitte zuerst:  python3 generate.py {projektname}")
    sys.exit(1)

# ── Hilfsfunktion: eine Variante → PDF ───────────────────────────────────────

def variante_zu_pdf(out, suffix, output_name):
    """
    Konvertiert deckblatt{suffix}.html + heizlast{suffix}.html +
    hydraulik{suffix}.html zu einem zusammengefügten PDF.
    Gibt True zurück wenn erfolgreich, False wenn keine Dateien gefunden.
    """
    pages = [
        (f"deckblatt{suffix}.html", f"tmp_deckblatt{suffix}.pdf"),
        (f"heizlast{suffix}.html",  f"tmp_heizlast{suffix}.pdf"),
        (f"hydraulik{suffix}.html", f"tmp_hydraulik{suffix}.pdf"),
    ]

    tmp_files = []
    for html_name, pdf_name in pages:
        html_path = out / html_name
        pdf_path  = out / pdf_name
        if not html_path.exists():
            print(f"  WARNUNG: {html_path} nicht gefunden – übersprungen.")
            continue
        print(f"  Konvertiere {html_name} ...", end=" ")
        try:
            weasyprint.HTML(filename=str(html_path)).write_pdf(str(pdf_path))
            tmp_files.append(pdf_path)
            print("✓")
        except Exception as e:
            print(f"FEHLER: {e}")
            return False

    if not tmp_files:
        return False

    output_pdf = out / output_name
    writer = PdfWriter()
    for pdf_path in tmp_files:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)
    with open(output_pdf, "wb") as f:
        writer.write(f)

    seiten = sum(len(PdfReader(str(p)).pages) for p in tmp_files)
    print(f"  ✓ {output_pdf}  ({seiten} Seiten)")

    for pdf_path in tmp_files:
        pdf_path.unlink(missing_ok=True)

    return True


# ── Variante 1: Normauslegung (θe = theta_e) ──────────────────────────────────
print(f"\n── Variante 1: Normauslegung")
variante_zu_pdf(out, "", f"{projektname}_heizlast.pdf")

# ── Variante 2: WP-Auslegung (θe = theta_e_moh) ──────────────────────────────
# Nur ausgeben wenn die _moh-HTMLs existieren (wurden von generate.py erzeugt).
moh_vorhanden = (out / "heizlast_moh.html").exists()
if moh_vorhanden:
    print(f"\n── Variante 2: WP-Auslegung (θe_moh)")
    variante_zu_pdf(out, "_moh", f"{projektname}_heizlast_moh.pdf")
else:
    print(f"\nHINWEIS: heizlast_moh.html nicht gefunden – Variante 2 übersprungen.")
    print(f"  Bitte zuerst: python3 generate.py {projektname}")
