#!/usr/bin/env python3
"""
Rend un rapport Markdown en PDF.

Reutilise les jetons du systeme de design de l'application et ses polices IBM
Plex, deja presentes dans static/fonts : le document imprime ressemble a
l'interface qu'il decrit, et rien n'est telecharge au moment du rendu.

    python3 ops/render_report.py docs/RAPPORT_V2.md
    python3 ops/render_report.py docs/RAPPORT_V2.md --out /tmp/rapport.pdf
"""

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
POLICES = REPO / "static" / "fonts"

EXTENSIONS = ["tables", "attr_list", "sane_lists", "toc", "md_in_html"]

FEUILLE = """
@font-face {{
  font-family: 'Plex Sans'; font-weight: 400;
  src: url('file://{p}/plex-sans-400.woff2') format('woff2');
}}
@font-face {{
  font-family: 'Plex Sans'; font-weight: 500;
  src: url('file://{p}/plex-sans-500.woff2') format('woff2');
}}
@font-face {{
  font-family: 'Plex Sans'; font-weight: 600;
  src: url('file://{p}/plex-sans-600.woff2') format('woff2');
}}
@font-face {{
  font-family: 'Plex Mono'; font-weight: 400;
  src: url('file://{p}/plex-mono-400.woff2') format('woff2');
}}

/* Memes jetons que static/css/lims.css. */
:root {{
  --ink: #12222e; --ink-2: #44555f; --ink-3: #6b7a84;
  --rule: #dde3e7; --rule-strong: #b6c1c8;
  --surface-2: #f7f9fa;
  --accent: #1c5d99; --accent-bg: #e8f0f8;
  --good: #16733f; --good-bg: #e6f4ec;
  --warn: #8a5300; --warn-bg: #fdf1dc;
}}

@page {{
  size: A4;
  margin: 20mm 18mm 18mm 18mm;
  @bottom-center {{
    content: counter(page) " / " counter(pages);
    font-family: 'Plex Mono', monospace;
    font-size: 8pt;
    color: #6b7a84;
  }}
  @bottom-right {{
    content: "TerryFox LIMS v2";
    font-family: 'Plex Sans', sans-serif;
    font-size: 8pt;
    color: #b6c1c8;
  }}
}}

/* La premiere page porte le titre : pas de numero. */
@page :first {{
  margin-top: 30mm;
  @bottom-center {{ content: ""; }}
  @bottom-right {{ content: ""; }}
}}

body {{
  font-family: 'Plex Sans', sans-serif;
  font-size: 9.6pt;
  line-height: 1.5;
  color: var(--ink);
  hyphens: auto;
}}

h1 {{
  font-size: 21pt; font-weight: 600; line-height: 1.15;
  letter-spacing: -.015em; margin: 0 0 4mm;
}}
h2 {{
  font-size: 13pt; font-weight: 600; margin: 9mm 0 3mm;
  padding-bottom: 1.5mm; border-bottom: 1.5pt solid var(--ink);
  break-after: avoid; break-before: auto;
}}
h3 {{
  font-size: 10.6pt; font-weight: 600; margin: 6mm 0 2mm;
  color: var(--accent); break-after: avoid;
}}
h4 {{ font-size: 9.6pt; font-weight: 600; margin: 4mm 0 1.5mm; break-after: avoid; }}

p {{ margin: 0 0 2.6mm; orphans: 3; widows: 3; }}

strong {{ font-weight: 600; }}

ul, ol {{ margin: 0 0 3mm; padding-left: 5mm; }}
li {{ margin-bottom: 1.2mm; }}

code {{
  font-family: 'Plex Mono', monospace;
  font-size: .87em;
  background: var(--surface-2);
  border: .5pt solid var(--rule);
  border-radius: 1pt;
  padding: 0 1pt;
  word-break: break-word;
}}

table {{
  width: 100%;
  border-collapse: collapse;
  margin: 0 0 4mm;
  font-size: 8.6pt;
}}
/* Un tableau long doit traverser la page plutot que de laisser un quart de
   page vide en attendant de tenir entier. Ce sont les LIGNES qu'on protege,
   et l'en-tete se repete sur chaque page. */
thead {{ display: table-header-group; }}
tr {{ break-inside: avoid; }}
thead th {{
  background: var(--surface-2);
  border-bottom: 1pt solid var(--rule-strong);
  color: var(--ink-3);
  font-family: 'Plex Mono', monospace;
  font-size: 7.4pt;
  font-weight: 400;
  letter-spacing: .06em;
  text-transform: uppercase;
  text-align: left;
  padding: 1.6mm 2mm;
}}
tbody td {{
  border-bottom: .5pt solid var(--rule);
  padding: 1.6mm 2mm;
  vertical-align: top;
}}
tbody tr:nth-child(even) td {{ background: #fbfcfd; }}

blockquote {{
  margin: 0 0 4mm;
  padding: 2.5mm 3.5mm;
  background: var(--accent-bg);
  border-left: 2pt solid var(--accent);
  break-inside: avoid;
}}
blockquote p {{ margin: 0; }}
blockquote p + p {{ margin-top: 2mm; }}

hr {{
  border: 0;
  border-top: .5pt solid var(--rule);
  margin: 7mm 0;
}}

em {{ color: var(--ink-2); }}

/* Le sous-titre en tete de document. */
h1 + p strong {{ font-size: 11pt; font-weight: 500; }}
"""

GABARIT = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>{titre}</title>
<style>{feuille}</style></head><body>{corps}</body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="fichier Markdown")
    ap.add_argument("--out", help="fichier PDF (defaut : meme nom en .pdf)")
    args = ap.parse_args()

    try:
        import markdown
        from weasyprint import HTML
    except ImportError as exc:
        print(f"ECHEC: dependance manquante ({exc}).\n"
              f"       pip install markdown weasyprint", file=sys.stderr)
        sys.exit(1)

    source = Path(args.source)
    if not source.is_file():
        print(f"ECHEC: {source} introuvable", file=sys.stderr)
        sys.exit(1)

    sortie = Path(args.out) if args.out else source.with_suffix(".pdf")

    corps = markdown.markdown(source.read_text(), extensions=EXTENSIONS)
    titre = source.stem.replace("_", " ")
    html = GABARIT.format(titre=titre, feuille=FEUILLE.format(p=POLICES), corps=corps)

    HTML(string=html, base_url=str(REPO)).write_pdf(str(sortie))

    taille = sortie.stat().st_size
    print(f"  {source}  ->  {sortie}  ({taille / 1024:.0f} Ko)")


if __name__ == "__main__":
    main()
