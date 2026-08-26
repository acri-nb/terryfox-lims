#!/usr/bin/env python3
"""Refait les captures du README a partir d'une base de DEMONSTRATION.

Le depot est public : aucune capture ne doit montrer un identifiant de
biobanque reel. Le script refuse donc de travailler sur autre chose qu'une base
peuplee par ops/seed_demo.py, et fabrique la sienne si on ne lui en donne pas.

    python ops/screenshots.py                 # base jetable, captures refaites
    python ops/screenshots.py --db /tmp/x.sqlite3

Demande playwright et son chromium :

    pip install playwright && python -m playwright install chromium
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

REPO = Path(__file__).resolve().parent.parent
SORTIE = REPO / "docs" / "screenshots"

#: Un poste de travail ordinaire. Le rendu Retina (x2) evite le texte baveux
#: une fois l'image redimensionnee par GitHub.
LARGEUR, HAUTEUR, ECHELLE = 1440, 900, 2


def port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def attendre(base, essais=60):
    for _ in range(essais):
        try:
            urlopen(base + "/accounts/login/", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def capturer(page, base, chemin, fichier, pleine=True, avant=None, ancre=None):
    """`ancre` cadre la vue sur une section plutot que sur le haut de page.

    Sans cela une capture de la liste des cas commence au milieu des
    statistiques du projet : le lecteur voit une moitie de tableau et une
    moitie de ce qui le precede, et l'image n'illustre plus rien.
    """
    page.goto(base + chemin, wait_until="networkidle")
    if avant:
        avant(page)
    if ancre:
        # Le defilement est calcule puis RELU : scrollTo peut etre clampe (page
        # trop courte) ou annule par un changement de hauteur declenche par
        # `avant`. Sans relecture, la capture repart silencieusement du haut.
        vise = page.evaluate(
            "s => { const e = document.querySelector(s); if (!e) return null;"
            "       return Math.max(0, e.getBoundingClientRect().top"
            "                          + window.scrollY - 28); }", ancre)
        if vise is None:
            raise SystemExit(f"ECHEC: ancre {ancre} absente de {chemin}")
        page.evaluate("y => window.scrollTo({top: y, behavior: 'instant'})", vise)
        page.wait_for_timeout(250)
        obtenu, fond = page.evaluate(
            "[Math.round(window.scrollY),"
            " Math.round(document.documentElement.scrollHeight - window.innerHeight)]")
        # Atteindre le bas sans atteindre la cible est normal : une page filtree
        # a peu de lignes et ne peut pas defiler plus loin. Le signaler
        # quand meme serait du bruit ; le taire quand la cause est autre
        # ferait passer une capture cadree au hasard.
        if abs(obtenu - vise) > 4 and obtenu < fond - 4:
            print(f"    ATTENTION {ancre}: vise {vise:.0f} px, obtenu {obtenu} px")
    page.wait_for_timeout(400)
    cible = SORTIE / fichier
    page.screenshot(path=str(cible), full_page=pleine)
    print(f"  {fichier:24s} {cible.stat().st_size / 1024:6.0f} Ko")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="base de demonstration existante")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("ECHEC: pip install playwright && python -m playwright install chromium")

    jetable = None
    if args.db:
        base_db = args.db
    else:
        jetable = tempfile.mkdtemp(prefix="lims-demo-")
        base_db = os.path.join(jetable, "demo.sqlite3")
        env = {**os.environ, "DATABASE_PATH": base_db}
        subprocess.run([sys.executable, "manage.py", "migrate", "--run-syncdb", "-v", "0"],
                       cwd=REPO, env=env, check=True)
        subprocess.run([sys.executable, "ops/seed_demo.py"], cwd=REPO, env=env, check=True)

    SORTIE.mkdir(parents=True, exist_ok=True)
    port = port_libre()
    url = f"http://127.0.0.1:{port}"
    serveur = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=REPO, env={**os.environ, "DATABASE_PATH": base_db},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        if not attendre(url):
            sys.exit("ECHEC: le serveur de developpement n'a pas repondu")

        with sync_playwright() as p:
            nav = p.chromium.launch()
            ctx = nav.new_context(viewport={"width": LARGEUR, "height": HAUTEUR},
                                  device_scale_factor=ECHELLE)
            page = ctx.new_page()

            page.goto(url + "/accounts/login/")
            page.fill("input[name=username]", "demo")
            page.fill("input[name=password]", "demo")
            page.click("button[type=submit], input[type=submit]")
            page.wait_for_load_state("networkidle")

            capturer(page, url, "/", "01-dashboard.png")

            # Le premier projet de la liste, quel que soit son identifiant.
            page.goto(url + "/", wait_until="networkidle")
            lien = page.locator("#projects-region tbody tr a").first.get_attribute("href")

            capturer(page, url, lien, "02-cases.png",
                     pleine=False, ancre="#cases-heading")

            def filtrer(pg):
                """Le filtre en direct : on tape, et rien d'autre.

                Aucun clic sur un bouton. L'attente couvre les 250 ms de repit
                du script plus l'aller-retour.
                """
                pg.fill("input[name=name]", "BBN-8")
                pg.wait_for_timeout(1200)

            capturer(page, url, lien, "03-live-filter.png",
                     pleine=False, avant=filtrer, ancre="#cases-heading")

            def selectionner(pg):
                boites = pg.locator(".case-check")
                for i in range(min(4, boites.count())):
                    boites.nth(i).click()
                pg.wait_for_timeout(300)

            capturer(page, url, lien, "04-bulk-status.png",
                     pleine=False, avant=selectionner, ancre="#case-table")

            page.goto(url + lien, wait_until="networkidle")
            cas = page.locator("#cases-region tbody tr td a").first.get_attribute("href")
            capturer(page, url, cas, "05-case.png")

            nav.close()
    finally:
        serveur.terminate()
        serveur.wait(timeout=10)
        if jetable:
            shutil.rmtree(jetable, ignore_errors=True)

    print(f"\n  captures dans {SORTIE.relative_to(REPO)}/")


if __name__ == "__main__":
    main()
