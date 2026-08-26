"""Le filtre filtre-t-il vraiment ?

`LiveFilterTests` (core/tests.py) verifie le CONTRAT entre les gabarits et le
script : les attributs poses, les identifiants de region presents dans toutes
les reponses. C'est ce qui casse en pratique, et c'est peu couteux a verifier.
Mais aucun de ces tests n'execute une ligne de JavaScript : ils passeraient tous
sur un script vide.

Ce module comble ce trou en executant reellement static/js/live-filter.js dans
un DOM (jsdom) contre un serveur Django vivant, puis en tapant dans le champ.

Il se met de cote quand node ou jsdom manquent, ce qui est le cas courant :

    npm install jsdom@24
    LIMS_JSDOM=$PWD/node_modules/jsdom python manage.py test core.test_e2e_livefilter
"""
import json
import os
import shutil
import subprocess
import unittest

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from .models import Case, Project, ProjectLead

JSDOM = os.environ.get("LIMS_JSDOM")
HARNAIS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "ops", "live_filter_harness.js")

DISPONIBLE = bool(JSDOM) and shutil.which("node") is not None and os.path.exists(HARNAIS)
RAISON = "node + jsdom requis : npm install jsdom@24 puis LIMS_JSDOM=$PWD/node_modules/jsdom"


@unittest.skipUnless(DISPONIBLE, RAISON)
class LiveFilterBrowserTests(StaticLiveServerTestCase):
    """Le script tourne pour de vrai, et on tape dans le champ."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin_e2e", password="x")
        self.alpha = ProjectLead.objects.create(name="Dr Alpha")
        self.beta = ProjectLead.objects.create(name="Dr Beta")
        self.p1 = Project.objects.create(name="P alpha", project_lead=self.alpha,
                                         created_by=self.admin)
        self.p2 = Project.objects.create(name="P beta", project_lead=self.beta,
                                         created_by=self.admin)
        for i in range(6):
            Case.objects.create(project=self.p1, biobank_id=f"AA-{i:03d}").ensure_specimens()
        for i in range(4):
            Case.objects.create(project=self.p2, biobank_id=f"BB-{i:03d}").ensure_specimens()
        self.client.force_login(self.admin)
        self.sid = self.client.cookies["sessionid"].value

    def _taper(self, chemin, region, champ, valeur):
        sortie = subprocess.run(
            ["node", HARNAIS, self.live_server_url + chemin, self.sid,
             "static/js/live-filter.js", region, champ, valeur],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "LIMS_JSDOM": JSDOM},
        )
        if not sortie.stdout.strip():
            self.fail(f"le harnais n'a rien renvoye.\n{sortie.stderr[:1500]}")
        resultat = json.loads(sortie.stdout.strip().splitlines()[-1])
        self.assertNotIn("erreur", resultat, resultat.get("erreur"))
        return resultat

    def test_typing_narrows_the_project_list_without_any_click(self):
        r = self._taper(reverse("home"), "#projects-region", "input[name=name]", "alpha")
        self.assertEqual(r["lignes_avant"], 2)
        self.assertEqual(r["lignes_apres"], 1, "le tableau n'a pas ete filtre")

    def test_the_filter_button_disappears_once_the_script_runs(self):
        """Il ne doit plus rien rester a cliquer."""
        r = self._taper(reverse("home"), "#projects-region", "input[name=name]", "alpha")
        self.assertTrue(r["bouton_masque"], "le bouton Filter est reste visible")

    def test_picking_a_lead_filters_on_the_spot(self):
        r = self._taper(reverse("home"), "#projects-region",
                        "select[name=project_lead]", str(self.beta.id))
        self.assertEqual(r["lignes_apres"], 1)

    def test_typing_narrows_the_case_list_of_a_project(self):
        r = self._taper(reverse("project_detail", kwargs={"project_id": self.p1.id}),
                        "#cases-region", "input[name=name]", "AA-003")
        self.assertEqual(r["lignes_avant"], 6)
        self.assertEqual(r["lignes_apres"], 1)

    def test_the_caret_stays_in_the_field_while_typing(self):
        """Le formulaire est hors de la region remplacee, justement pour cela.

        S'il etait dedans, chaque rafraichissement detruirait le champ et
        renverrait le curseur au corps de la page : on ne pourrait pas taper
        plus d'un caractere.
        """
        r = self._taper(reverse("project_detail", kwargs={"project_id": self.p1.id}),
                        "#cases-region", "input[name=name]", "AA-003")
        self.assertTrue(r["focus_conserve"], "le curseur a quitte le champ")

    def test_one_keystroke_makes_one_request(self):
        r = self._taper(reverse("home"), "#projects-region", "input[name=name]", "alpha")
        self.assertEqual(len(r["requetes"]), 1, r["requetes"])

    def test_the_address_follows_the_filter(self):
        """Signets, partage et rechargement doivent retomber sur la meme vue."""
        r = self._taper(reverse("home"), "#projects-region", "input[name=name]", "alpha")
        self.assertEqual(r["adresse"], "?name=alpha")
