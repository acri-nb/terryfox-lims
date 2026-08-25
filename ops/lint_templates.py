#!/usr/bin/env python3
"""
Controle statique des gabarits : les motifs qui cassent sur un ecran etroit.

L'interface a ete concue sur un ecran large et rendue illisible sur telephone :
l'en-tete de la page projet alignait six boutons sans retour a la ligne, soit
environ 1050 px de contenu dans un viewport de 360. Ces regles attrapent la
famille de motifs qui produit ce resultat, pour qu'elle ne revienne pas.

Volontairement statique : mesurer une mise en page demande un navigateur, mais
les CAUSES sont reconnaissables dans le gabarit.

    python3 ops/lint_templates.py
    python3 ops/lint_templates.py --list-rules
"""

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"


def _lignes_avec(contenu, motif):
    """Numeros de ligne (1-indexes) ou le motif apparait."""
    return [
        (i + 1, ligne.strip())
        for i, ligne in enumerate(contenu.split("\n"))
        if motif.search(ligne)
    ]


# --- regles -----------------------------------------------------------------

RE_FLEX = re.compile(r'class="[^"]*\bd-flex\b[^"]*"')
RE_WRAP = re.compile(r'\bflex-wrap\b|\bflex-column\b')
RE_MINW = re.compile(r'style="[^"]*min-width:\s*\d+px')
RE_TABLE = re.compile(r"<table")
RE_RESP = re.compile(r"table-responsive")
RE_NOWRAP = re.compile(r'style="[^"]*white-space:\s*nowrap')


RE_OUVRE = re.compile(r"<(div|form|ul|li|nav|section)\b")
RE_FERME = re.compile(r"</(div|form|ul|li|nav|section)>")
RE_BOUTON = re.compile(r'class="[^"]*\bbtn\b[^"]*"[^>]*>(.*?)</(?:a|button)>', re.S)
RE_CONTROLE = re.compile(r'class="[^"]*\b(?:form-control|form-select)\b')
RE_TITRE = re.compile(r"<h[12][^>]*>(.*?)</h[12]>", re.S)
RE_BALISE = re.compile(r"<[^>]+>")
RE_DJANGO = re.compile(r"\{[%{#].*?[%}#]\}", re.S)

#: Largeur utile a l'interieur de .container-xl sur un telephone de 360 px :
#: 360 moins 2 x 12 px de gouttiere.
BUDGET_PX = 336

#: Plex Sans 500 a 14,5 px : environ 7,5 px par caractere. Un bouton ajoute
#: 24 px de remplissage, 16 px pour son icone et 8 px de marge.
PX_PAR_CARACTERE = 7.5
SUPPLEMENT_BOUTON = 48
#: Un h1 est a 24 px : environ 13 px par caractere.
PX_PAR_CARACTERE_TITRE = 13
#: Un <input> ou un <select> refuse de descendre sous sa taille minimale
#: automatique -- de l'ordre de 160 a 200 px selon le contenu.
LARGEUR_CONTROLE = 170


def _texte_visible(html):
    """Le texte reellement rendu : sans balises ni syntaxe de gabarit.

    Une variable {{ x }} est comptee pour 12 caracteres : on ne peut pas
    connaitre sa valeur, et c'est l'ordre de grandeur d'un nom de projet ou
    d'un nom d'utilisateur.
    """
    sans_django = RE_DJANGO.sub("x" * 12, html)
    return " ".join(RE_BALISE.sub("", sans_django).split())


def _contenu_du_bloc(lignes, depart):
    """Les lignes de l'element ouvert a `depart`, jusqu'a sa fermeture."""
    profondeur = 0
    bloc = []
    for ligne in lignes[depart:depart + 60]:
        bloc.append(ligne)
        profondeur += len(RE_OUVRE.findall(ligne))
        profondeur -= len(RE_FERME.findall(ligne))
        if profondeur <= 0 and len(bloc) > 1:
            break
    return bloc


def _largeur_estimee(bloc):
    """Largeur qu'occuperait la rangee si rien ne pouvait se replier."""
    html = "\n".join(bloc)
    total = 0.0
    detail = []

    for corps in RE_BOUTON.findall(html):
        libelle = _texte_visible(corps)
        largeur = len(libelle) * PX_PAR_CARACTERE + SUPPLEMENT_BOUTON
        total += largeur
        detail.append(f"{libelle[:22]} {largeur:.0f}px")

    for titre in RE_TITRE.findall(html):
        libelle = _texte_visible(titre)
        largeur = len(libelle) * PX_PAR_CARACTERE_TITRE
        total += largeur
        detail.append(f"titre {largeur:.0f}px")

    n_controles = len(RE_CONTROLE.findall(html))
    if n_controles:
        total += n_controles * LARGEUR_CONTROLE
        detail.append(f"{n_controles} champ(s) {n_controles * LARGEUR_CONTROLE}px")

    return total, detail


def regle_flex_sans_retour(chemin, contenu):
    """Une rangee flex qui ne tient pas sur un telephone, et ne peut pas se replier.

    Les enfants d'un conteneur flex ont min-width:auto : ils refusent de
    retrecir sous la largeur de leur contenu. Sans flex-wrap, la rangee garde
    donc sa largeur quoi qu'il arrive et pousse la page entiere. C'est ce qui
    rendait l'en-tete de la page projet large de ~1050 px dans un viewport de
    360.

    On n'estime pas la mise en page -- cela demanderait un navigateur -- mais la
    LARGEUR RECLAMEE par le contenu, ce qui suffit a distinguer une rangee qui
    tient d'une rangee qui deborde. Une barre a deux elements courts passe ;
    un titre suivi de deux boutons ne passe pas.
    """
    lignes = contenu.split("\n")
    problemes = []
    for index, ligne in enumerate(lignes):
        if not RE_FLEX.search(ligne) or RE_WRAP.search(ligne):
            continue
        largeur, detail = _largeur_estimee(_contenu_du_bloc(lignes, index))
        if largeur > BUDGET_PX:
            problemes.append((
                index + 1,
                f"~{largeur:.0f}px reclames pour {BUDGET_PX}px — " + ", ".join(detail[:4]),
            ))
    return problemes


def regle_min_width_en_dur(chemin, contenu):
    """Un min-width en pixels dans un attribut style empeche l'element de retrecir."""
    return [(n, l[:96]) for n, l in _lignes_avec(contenu, RE_MINW)]


def regle_table_sans_conteneur(chemin, contenu):
    """Un tableau doit defiler DANS son conteneur, pas pousser la page."""
    problemes = []
    for m in RE_TABLE.finditer(contenu):
        avant = contenu[max(0, m.start() - 400):m.start()]
        if not RE_RESP.search(avant):
            numero = contenu[:m.start()].count("\n") + 1
            problemes.append((numero, "<table> hors .table-responsive"))
    return problemes


def regle_nowrap(chemin, contenu):
    """white-space: nowrap en ligne fige une largeur que rien ne peut reduire."""
    return [(n, l[:96]) for n, l in _lignes_avec(contenu, RE_NOWRAP)]


REGLES = [
    ("flex-sans-retour", regle_flex_sans_retour,
     "conteneur d-flex sans flex-wrap : la rangee ne peut pas se replier"),
    ("min-width-en-dur", regle_min_width_en_dur,
     "min-width en px dans un style : l'element ne peut pas retrecir"),
    ("table-sans-conteneur", regle_table_sans_conteneur,
     "tableau hors .table-responsive : il pousse la page au lieu de defiler"),
    ("nowrap-en-ligne", regle_nowrap,
     "white-space: nowrap en ligne : largeur figee"),
]


def analyser():
    resultats = {}
    for fichier in sorted(TEMPLATES.rglob("*.html")):
        contenu = fichier.read_text()
        for nom, regle, _desc in REGLES:
            for numero, extrait in regle(fichier, contenu):
                resultats.setdefault(nom, []).append(
                    (fichier.relative_to(REPO), numero, extrait))
    return resultats


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-rules", action="store_true")
    ap.add_argument("--quiet", action="store_true",
                    help="ne rien afficher, ne renvoyer qu'un code de sortie")
    args = ap.parse_args()

    if args.list_rules:
        for nom, _r, desc in REGLES:
            print(f"  {nom:22s} {desc}")
        return

    resultats = analyser()
    total = sum(len(v) for v in resultats.values())

    if not args.quiet:
        for nom, _r, desc in REGLES:
            trouves = resultats.get(nom, [])
            if not trouves:
                print(f"  ok    {nom}")
                continue
            print(f"  {len(trouves):4d}  {nom} — {desc}")
            for chemin, numero, extrait in trouves[:8]:
                print(f"          {chemin}:{numero}  {extrait}")
            if len(trouves) > 8:
                print(f"          … et {len(trouves) - 8} de plus")
        print(f"\n  {total} occurrence(s)")

    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
