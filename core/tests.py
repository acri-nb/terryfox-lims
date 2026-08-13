"""
Suite de tests d'amorce du TerryFox LIMS.

Ces tests tournent sur une base de test creee et detruite par Django : ils ne
touchent jamais db.sqlite3. Lancer avec :

    python manage.py test core
    python manage.py test core.TierCalculationTests

Ils couvrent en priorite ce qui, en cas de regression, fait perdre ou fausser
des donnees : le calcul du tier, la suppression douce, et l'import CSV.
"""

from django.contrib.auth.models import Group, Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from .models import Case, Comment, Project, ProjectLead


def make_editor(username="editor1"):
    """Un utilisateur du groupe editor, avec les permissions CRUD sur core.

    Les permissions des groupes ne sont pas gerees dans le code (elles sont
    posees en base via l'admin), donc un groupe 'editor' vierge n'a aucun droit
    dans une base de test : on les attribue explicitement ici.
    """
    user = User.objects.create_user(username=username, password="x")
    group, _ = Group.objects.get_or_create(name="editor")
    group.permissions.set(
        Permission.objects.filter(
            content_type__app_label="core",
            codename__in=[
                "add_project", "change_project", "delete_project", "view_project",
                "add_case", "change_case", "delete_case", "view_case",
                "add_projectlead", "change_projectlead", "delete_projectlead", "view_projectlead",
            ],
        )
    )
    user.groups.add(group)
    return user


class TierCalculationTests(TestCase):
    """Le tier est derive des couvertures et jamais saisi.

    Ces valeurs sont le fichier de reference : elles encodent les criteres
    valides par le consortium. Toute modification des seuils doit passer par
    une mise a jour deliberee de ce test, pas par un effet de bord.
    """

    CASES = [
        # (dna_t, dna_n, rna, tier attendu, description)
        (85, 35, 120, "A", "DNA(T)>=80, DNA(N)>=30, RNA>=80"),
        (80, 30, 80, "A", "exactement aux seuils"),
        (75, 35, None, "B", "DNA(T) entre 30 et 80, pas d'ARN"),
        (50, 40, 50, "B", "DNA(T) entre 30 et 80, ARN faible"),
        (30, 30, None, "B", "seuils inferieurs"),
        (85, 35, None, "B", "DNA(T) eleve mais aucune valeur d'ARN"),
        (85, 35, 79, "B", "ARN juste sous le seuil de Tier A"),
        (29, 35, 100, "FAIL", "DNA(T) sous 30"),
        (85, 29, 100, "FAIL", "DNA(N) sous 30"),
        (None, 35, 100, "FAIL", "DNA(T) manquant"),
        (85, None, 100, "FAIL", "DNA(N) manquant"),
        (None, None, None, "FAIL", "aucune couverture"),
    ]

    def test_tier_reference(self):
        for dna_t, dna_n, rna, expected, label in self.CASES:
            with self.subTest(label=label):
                case = Case(dna_t_coverage=dna_t, dna_n_coverage=dna_n, rna_coverage=rna)
                self.assertEqual(case.calculate_tier(), expected, label)

    def test_tier_is_overwritten_on_save(self):
        """Poser un tier a la main ne doit avoir aucun effet."""
        user = User.objects.create_user("u1", password="x")
        project = Project.objects.create(name="P", created_by=user)
        case = Case.objects.create(
            project=project, name="ACC-0001",
            dna_t_coverage=10, dna_n_coverage=10, tier="A",
        )
        self.assertEqual(case.tier, "FAIL")


class SoftDeleteTests(TestCase):
    """Rien ne doit quitter la base par le chemin d'une interface web."""

    def setUp(self):
        self.user = User.objects.create_user("u2", password="x")
        self.project = Project.objects.create(name="Projet test", created_by=self.user)
        for i in range(5):
            case = Case.objects.create(
                project=self.project, name=f"ACC-{i:04d}",
                dna_t_coverage=85, dna_n_coverage=35, rna_coverage=100,
            )
            Comment.objects.create(case=case, text=f"note {i}", user=self.user)

    def test_project_delete_hides_but_keeps_everything(self):
        self.project.soft_delete()

        self.assertEqual(Project.objects.count(), 0)
        self.assertEqual(Case.objects.count(), 0)
        # ... mais tout est toujours la
        self.assertEqual(Project.all_objects.count(), 1)
        self.assertEqual(Case.all_objects.count(), 5)
        self.assertEqual(Comment.objects.count(), 5)

    def test_restore_brings_back_exactly_what_was_removed(self):
        already_gone = Case.objects.first()
        already_gone.soft_delete()

        self.project.soft_delete()
        self.project.restore()

        # Le cas supprime AVANT le projet doit rester supprime.
        self.assertEqual(Case.objects.count(), 4)
        self.assertEqual(Project.objects.count(), 1)

    def test_comment_of_deleted_case_still_resolves(self):
        """base_manager_name : traverser la cle etrangere ne doit pas lever."""
        case = Case.objects.first()
        case.soft_delete()
        comment = Comment.objects.filter(case_id=case.id).first()
        self.assertEqual(comment.case.name, case.name)
        self.assertEqual(comment.case.project.name, "Projet test")

    def test_delete_view_requires_exact_project_name(self):
        editor = make_editor()
        client = Client()
        client.force_login(editor)
        url = reverse("project_delete", kwargs={"project_id": self.project.id})

        client.post(url, {"confirm_name": "mauvais nom"})
        self.assertEqual(Project.objects.count(), 1, "un nom errone ne doit rien supprimer")

        client.post(url, {"confirm_name": self.project.name})
        self.assertEqual(Project.objects.count(), 0)


class CsvImportTests(TestCase):
    """Une cellule vide veut dire 'inchange', jamais 'efface'."""

    def setUp(self):
        self.editor = make_editor("editor2")
        self.project = Project.objects.create(name="P CSV", created_by=self.editor)
        self.case = Case.objects.create(
            project=self.project, name="ACC-0042", other_id="N-BBN 440",
            dna_t_coverage=82.46, dna_n_coverage=34.22, rna_coverage=136.3,
        )
        self.client = Client()
        self.client.force_login(self.editor)

    def _import(self, body):
        return self.client.post(
            reverse("csv_case_import", kwargs={"project_id": self.project.id}),
            {"csv_file": SimpleUploadedFile("t.csv", body.encode(), content_type="text/csv")},
            follow=True,
        )

    def test_blank_cells_do_not_erase_coverage(self):
        self.assertEqual(self.case.tier, "A")
        self._import("CaseID,Other_ID,Status,DNAT,DNAN,RNA\nACC-0042,,Completed,,,\n")

        self.case.refresh_from_db()
        self.assertEqual(self.case.dna_t_coverage, 82.46)
        self.assertEqual(self.case.dna_n_coverage, 34.22)
        self.assertEqual(self.case.rna_coverage, 136.3)
        self.assertEqual(self.case.other_id, "N-BBN 440")
        self.assertEqual(self.case.tier, "A", "le tier ne doit pas basculer en FAIL")

    def test_supplied_values_still_overwrite(self):
        self._import("CaseID,Other_ID,Status,DNAT,DNAN,RNA\nACC-0042,,Completed,123.4,,\n")

        self.case.refresh_from_db()
        self.assertEqual(self.case.dna_t_coverage, 123.4)
        self.assertEqual(self.case.dna_n_coverage, 34.22, "les cellules vides restent inchangees")

    def test_new_case_is_created_with_blanks_as_null(self):
        self._import("CaseID,Other_ID,Status,DNAT,DNAN,RNA\nACC-9999,,Received,,,\n")

        new = Case.objects.get(name="ACC-9999")
        self.assertIsNone(new.dna_t_coverage)
        self.assertEqual(new.tier, "FAIL")


class SmokeTests(TestCase):
    """Chaque page repond. Le filet minimal avant toute refonte."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin1", password="x")
        self.lead = ProjectLead.objects.create(name="Dr Test")
        self.project = Project.objects.create(
            name="P smoke", created_by=self.admin, project_lead=self.lead
        )
        self.case = Case.objects.create(
            project=self.project, name="ACC-0001",
            dna_t_coverage=85, dna_n_coverage=35, rna_coverage=100,
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def test_all_pages_respond(self):
        pages = [
            reverse("home"),
            reverse("project_detail", kwargs={"project_id": self.project.id}),
            reverse("project_create"),
            reverse("project_update", kwargs={"project_id": self.project.id}),
            reverse("project_delete", kwargs={"project_id": self.project.id}),
            reverse("case_detail", kwargs={"case_id": self.case.id}),
            reverse("case_create", kwargs={"project_id": self.project.id}),
            reverse("batch_case_create", kwargs={"project_id": self.project.id}),
            reverse("csv_case_import", kwargs={"project_id": self.project.id}),
            reverse("csv_case_export", kwargs={"project_id": self.project.id}),
            reverse("case_delete", kwargs={"case_id": self.case.id}),
            reverse("project_lead_list"),
            reverse("project_lead_create"),
            reverse("project_lead_update", kwargs={"lead_id": self.lead.id}),
            reverse("user_list"),
            reverse("user_create"),
            reverse("batch_user_create"),
        ]
        for url in pages:
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (200, 302))

    def test_anonymous_is_redirected_to_login(self):
        anon = Client()
        response = anon.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_viewer_cannot_reach_create_pages(self):
        viewer = User.objects.create_user("viewer1", password="x")
        viewer.groups.add(Group.objects.get_or_create(name="viewer")[0])
        client = Client()
        client.force_login(viewer)
        self.assertEqual(client.get(reverse("project_create")).status_code, 403)
        self.assertEqual(
            client.get(reverse("case_create", kwargs={"project_id": self.project.id})).status_code,
            403,
        )

    def test_non_superuser_cannot_reach_user_management(self):
        editor = make_editor("editor3")
        client = Client()
        client.force_login(editor)
        response = client.get(reverse("user_list"))
        self.assertEqual(response.status_code, 302, "doit etre renvoye vers l'accueil")
