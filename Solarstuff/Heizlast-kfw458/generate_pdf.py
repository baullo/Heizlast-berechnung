"""
generate_pdf.py – HTML → PDF Konverter
========================================
Konvertiert die drei HTML-Ausgaben von generate.py in ein
zusammengefügtes PDF-Dokument.

Verwendung:
    python3 generate_pdf.py <projektname>
    python3 generate_pdf.py köhler

Erwartet:  output/<projektname>/deckblatt.html
           output/<projektname>/heizlast.html
           output/<projektname>/hydraulik.html

Ausgabe:   output/<projektname>/<projektname>_heizlast.pdf

Abhängigkeiten:
    pip install pdfkit
    apt install wkhtmltopdf   (oder wkhtmltopdf.org)
"""

import sys
import pdfkit
from pathlib import Path
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

# ── wkhtmltopdf Optionen ───────────────────────────────────────────────────────
options_portrait = {
    "page-size":        "A4",
    "orientation":      "Portrait",
    "margin-top":       "0mm",
    "margin-right":     "0mm",
    "margin-bottom":    "0mm",
    "margin-left":      "0mm",
    "encoding":         "UTF-8",
    "enable-local-file-access": "",
    "print-media-type": "",
    "quiet":            "",
}

options_landscape = {
    **options_portrait,
    "orientation": "Landscape",
}

# ── Einzelne PDFs erzeugen ─────────────────────────────────────────────────────
tmp_files = []

pages = [
    ("deckblatt.html",  "tmp_deckblatt.pdf",  options_portrait),
    ("heizlast.html",   "tmp_heizlast.pdf",   options_portrait),
    ("hydraulik.html",  "tmp_hydraulik.html",  options_landscape),  # landscape A4
]

# hydraulik.html braucht landscape
pages[2] = ("hydraulik.html", "tmp_hydraulik.pdf", options_landscape)

for html_name, pdf_name, opts in pages:
    html_path = out / html_name
    pdf_path  = out / pdf_name

    if not html_path.exists():
        print(f"WARNUNG: {html_path} nicht gefunden – übersprungen.")
        continue

    print(f"  Konvertiere {html_name} ...", end=" ")
    try:
        pdfkit.from_file(str(html_path), str(pdf_path), options=opts)
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
