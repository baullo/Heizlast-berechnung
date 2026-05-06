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

# ── Seiten-Konfiguration ───────────────────────────────────────────────────────
# @page size/orientation kommt aus dem CSS der jeweiligen HTML-Datei –
# WeasyPrint liest das direkt, hier nur die Dateinamen definieren.
pages = [
    ("deckblatt.html", "tmp_deckblatt.pdf"),
    ("heizlast.html",  "tmp_heizlast.pdf"),
    ("hydraulik.html", "tmp_hydraulik.pdf"),
]

# ── PDFs erzeugen ──────────────────────────────────────────────────────────────
tmp_files = []

for html_name, pdf_name in pages:
    html_path = out / html_name
    pdf_path  = out / pdf_name

    if not html_path.exists():
        print(f"WARNUNG: {html_path} nicht gefunden – übersprungen.")
        continue

    print(f"  Konvertiere {html_name} ...", end=" ")
    try:
        weasyprint.HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        tmp_files.append(pdf_path)
        print("✓")
    except Exception as e:
        print(f"FEHLER: {e}")
        sys.exit(1)

# ── PDFs zusammenfügen ─────────────────────────────────────────────────────────
output_pdf = out / f"{projektname}_heizlast.pdf"

writer = PdfWriter()
for pdf_path in tmp_files:
    reader = PdfReader(str(pdf_path))
    for page in reader.pages:
        writer.add_page(page)

with open(output_pdf, "wb") as f:
    writer.write(f)

print(f"\n✓ PDF erstellt: {output_pdf}")
print(f"  Seiten: {sum(len(PdfReader(str(p)).pages) for p in tmp_files)}")

# ── Temporäre Einzeldateien aufräumen ──────────────────────────────────────────
for pdf_path in tmp_files:
    pdf_path.unlink(missing_ok=True)

print("  Temporäre Dateien gelöscht.")
