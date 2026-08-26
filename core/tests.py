"""
Suite de tests d'amorce du TerryFox LIMS.

Ces tests tournent sur une base de test creee et detruite par Django : ils ne
touchent jamais db.sqlite3. Lancer avec :

    python manage.py test core
    python manage.py test core.TierCalculationTests

Ils couvrent en priorite ce qui, en cas de regression, fait perdre ou fausser
des donnees : le calcul du tier, la suppression douce, et l'import CSV.
"""

from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext, override_settings
from django.urls import reverse
from django.utils import timezone

from . import statuses
from .models import (
    BatchOperation, Case, Comment, IdentifierSequence, Project, ProjectLead,
    Specimen, format_acc,
)


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
            project=self.project, name="ACC-0042", biobank_id="N-BBN 440",
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
        self.assertEqual(self.case.biobank_id, "N-BBN 440")
        self.assertEqual(self.case.tier, "A", "le tier ne doit pas basculer en FAIL")

    def test_supplied_values_still_overwrite(self):
        self._import("CaseID,Other_ID,Status,DNAT,DNAN,RNA\nACC-0042,,Completed,123.4,,\n")

        self.case.refresh_from_db()
        self.assertEqual(self.case.dna_t_coverage, 123.4)
        self.assertEqual(self.case.dna_n_coverage, 34.22, "les cellules vides restent inchangees")

    def test_both_biobank_headers_are_accepted(self):
        """Les equipes ont des fichiers au format Other_ID : ils doivent marcher."""
        for header in ("Biobank_ID", "Other_ID"):
            with self.subTest(header=header):
                self._import(
                    f"CaseID,{header},Status,DNAT,DNAN,RNA\n"
                    f"ACC-0042,VIA-{header},Completed,,,\n"
                )
                self.case.refresh_from_db()
                self.assertEqual(self.case.biobank_id, f"VIA-{header}")

    def test_new_case_is_created_with_blanks_as_null(self):
        self._import("CaseID,Other_ID,Status,DNAT,DNAN,RNA\nACC-9999,,Received,,,\n")

        new = Case.objects.get(name="ACC-9999")
        self.assertIsNone(new.dna_t_coverage)
        self.assertEqual(new.tier, "FAIL")


class ProjectListingTests(TestCase):
    """Pagination et absence de N+1 sur la page projet.

    Avant correction : 522 requetes, 1,1 s et 926 Ko pour les 256 cas de P06,
    parce que chaque carte appelait case.accessions.count et case.comments.count.
    """

    PAGE_SIZE = 100

    def setUp(self):
        self.admin = User.objects.create_superuser("admin2", password="x")
        self.project = Project.objects.create(name="P gros", created_by=self.admin)
        for i in range(250):
            case = Case.objects.create(
                project=self.project, name=f"ACC-{i:04d}",
                status=Case.STATUS_COMPLETED,
                dna_t_coverage=85, dna_n_coverage=35, rna_coverage=100,
            )
            if i < 10:
                Comment.objects.create(case=case, text="note", user=self.admin)
        self.client = Client()
        self.client.force_login(self.admin)
        self.url = reverse("project_detail", kwargs={"project_id": self.project.id})

    def test_query_count_does_not_grow_with_case_count(self):
        """L'invariant qui compte n'est pas un chiffre absolu, c'est l'absence de N+1.

        On compare un petit projet a un gros : le nombre de requetes doit etre
        identique. Avec l'ancien code il valait 2xN+10, soit 522 pour 256 cas.
        """
        small = Project.objects.create(name="P petit", created_by=self.admin)
        for i in range(3):
            case = Case.objects.create(project=small, name=f"ACC-9{i:03d}")
            Comment.objects.create(case=case, text="note", user=self.admin)

        small_url = reverse("project_detail", kwargs={"project_id": small.id})
        with CaptureQueriesContext(connection) as few:
            self.client.get(small_url)
        with CaptureQueriesContext(connection) as many:
            self.client.get(self.url)

        self.assertEqual(
            len(few.captured_queries), len(many.captured_queries),
            f"3 cas -> {len(few.captured_queries)} requetes, "
            f"250 cas -> {len(many.captured_queries)} : le nombre de requetes "
            f"depend du nombre de cas, le N+1 est de retour",
        )
        self.assertLess(len(many.captured_queries), 20)

    def test_pages_cover_every_case_exactly_once(self):
        seen = []
        for page in (1, 2, 3):
            response = self.client.get(self.url, {"page": page})
            seen += [c.name for c in response.context["cases"]]
        self.assertEqual(len(seen), 250)
        self.assertEqual(len(set(seen)), 250, "un cas apparait sur deux pages")

    def test_out_of_range_and_invalid_pages_do_not_500(self):
        for page in ("0", "999", "abc", "-1", ""):
            with self.subTest(page=page):
                self.assertEqual(self.client.get(self.url, {"page": page}).status_code, 200)

    def test_filters_survive_pagination(self):
        response = self.client.get(self.url, {"status": Case.STATUS_COMPLETED, "page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"status={Case.STATUS_COMPLETED}", response.context["querystring"])

    def test_statistics_cover_all_cases_not_just_the_page(self):
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["cases"]), self.PAGE_SIZE)
        self.assertEqual(response.context["total_cases"], 250)

    def test_annotated_counts_match_reality(self):
        response = self.client.get(self.url)
        for case in list(response.context["cases"])[:15]:
            with self.subTest(case=case.name):
                self.assertEqual(case.comments_count, case.comments.count())
                self.assertEqual(case.accessions_count, case.accessions.count())

    def test_deleted_cases_never_appear(self):
        Case.objects.filter(name__lt="ACC-0010").update(deleted_at=timezone.now())
        response = self.client.get(self.url)
        self.assertEqual(response.context["filtered_count"], 240)


class IdentifierTests(TestCase):
    """L'ACC est genere par le LIMS ; le Biobank ID est ce par quoi on cherche."""

    def setUp(self):
        self.editor = make_editor("editor4")
        self.project = Project.objects.create(name="P ids", created_by=self.editor)
        self.client = Client()
        self.client.force_login(self.editor)

    def test_acc_is_assigned_and_formatted(self):
        case = Case.objects.create(project=self.project, biobank_id="N-BBN 1")
        self.assertIsNotNone(case.acc_number)
        self.assertEqual(case.name, format_acc(case.acc_number))

    def test_acc_numbers_never_repeat(self):
        numbers = {Case.objects.create(project=self.project).acc_number for _ in range(20)}
        self.assertEqual(len(numbers), 20)

    def test_allocation_is_monotonic_and_skips_no_gaps_backwards(self):
        first = IdentifierSequence.allocate(3)
        second = IdentifierSequence.allocate(2)
        self.assertEqual(first, list(range(first[0], first[0] + 3)))
        self.assertGreater(second[0], first[-1], "le compteur ne doit jamais revenir en arriere")

    def test_deleting_a_case_does_not_free_its_number_for_reuse(self):
        case = Case.objects.create(project=self.project)
        taken = case.acc_number
        case.soft_delete()
        self.assertGreater(Case.objects.create(project=self.project).acc_number, taken)

    def test_duplicate_acc_is_refused(self):
        from django.db.utils import IntegrityError
        case = Case.objects.create(project=self.project)
        with self.assertRaises(IntegrityError):
            Case.objects.create(project=self.project, acc_number=case.acc_number)

    def test_biobank_id_is_normalised(self):
        case = Case.objects.create(project=self.project, biobank_id="   N-BBN 9   ")
        self.assertEqual(case.biobank_id, "N-BBN 9")
        self.assertIsNone(Case.objects.create(project=self.project, biobank_id="   ").biobank_id)

    def test_duplicate_biobank_id_names_the_conflicting_case(self):
        existing = Case.objects.create(project=self.project, biobank_id="N-BBN 42")
        response = self.client.post(
            reverse("case_create", kwargs={"project_id": self.project.id}),
            {"biobank_id": "n-bbn 42", "specimen_types": ["normal_dna", "tumour_dna", "tumour_rna"]},
        )
        body = response.content.decode()
        self.assertIn(existing.name, body, "le message doit nommer le cas en conflit")
        self.assertIn(self.project.name, body, "et son projet")

    def test_duplicate_biobank_id_can_be_forced(self):
        Case.objects.create(project=self.project, biobank_id="N-BBN 43")
        self.client.post(
            reverse("case_create", kwargs={"project_id": self.project.id}),
            {"biobank_id": "N-BBN 43", "specimen_types": ["normal_dna"], "confirm_duplicate": "1"},
        )
        self.assertEqual(Case.objects.filter(biobank_id="N-BBN 43").count(), 2)

    def test_project_search_finds_by_acc_and_by_biobank_id(self):
        case = Case.objects.create(project=self.project, biobank_id="N-BBN 77")
        url = reverse("project_detail", kwargs={"project_id": self.project.id})
        for term in (case.name, "N-BBN 77", "bbn 77"):
            with self.subTest(term=term):
                found = [c.name for c in self.client.get(url, {"name": term}).context["cases"]]
                self.assertIn(case.name, found)

    def test_global_search_spans_projects(self):
        other = Project.objects.create(name="P autre", created_by=self.editor)
        here = Case.objects.create(project=self.project, biobank_id="SHARED-1")
        there = Case.objects.create(project=other, biobank_id="SHARED-2")
        results = self.client.get(reverse("case_search"), {"q": "SHARED"}).context["results"]
        self.assertEqual({c.name for c in results}, {here.name, there.name})

    def test_batch_paste_creates_one_case_per_line(self):
        self.client.post(
            reverse("batch_case_create", kwargs={"project_id": self.project.id}),
            {"biobank_ids": "L-1\nL-2\n\n  L-3  ", "status": Case.STATUS_CREATED, "specimen_types": ["normal_dna", "tumour_dna", "tumour_rna"]},
        )
        created = Case.objects.filter(biobank_id__startswith="L-").order_by("acc_number")
        self.assertEqual([c.biobank_id for c in created], ["L-1", "L-2", "L-3"])
        numbers = [c.acc_number for c in created]
        self.assertEqual(numbers, list(range(numbers[0], numbers[0] + 3)))

    def test_batch_refuses_a_list_repeating_itself(self):
        self.client.post(
            reverse("batch_case_create", kwargs={"project_id": self.project.id}),
            {"biobank_ids": "D-1\nD-2\nD-1", "status": Case.STATUS_CREATED, "specimen_types": ["normal_dna", "tumour_dna", "tumour_rna"]},
        )
        self.assertEqual(Case.objects.count(), 0, "aucun cas ne doit etre cree")


class PriorityTests(TestCase):
    """Un cas urgent qui sort de l'ecran par le defilement vide la demande."""

    def setUp(self):
        self.editor = make_editor("editor5")
        self.project = Project.objects.create(name="P prio", created_by=self.editor)
        # Cree dans l'ordre alphabetique inverse de la priorite, pour que seul
        # l'epinglage puisse expliquer l'ordre obtenu.
        self.ordinaire = Case.objects.create(project=self.project, biobank_id="B-1")
        self.urgent = Case.objects.create(project=self.project, biobank_id="B-2", is_priority=True)
        self.client = Client()
        self.client.force_login(self.editor)
        self.url = reverse("project_detail", kwargs={"project_id": self.project.id})

    def test_priority_defaults_to_false(self):
        self.assertFalse(self.ordinaire.is_priority)

    def test_priority_cases_are_pinned_first(self):
        listed = [c.name for c in self.client.get(self.url).context["cases"]]
        self.assertEqual(listed[0], self.urgent.name)
        self.assertLess(self.urgent.acc_number, 10 ** 9)
        self.assertGreater(self.urgent.acc_number, self.ordinaire.acc_number,
                           "l'urgent a pourtant un ACC plus grand")

    def test_priority_filter_narrows_the_list(self):
        response = self.client.get(self.url, {"priority": "on"})
        self.assertEqual([c.name for c in response.context["cases"]], [self.urgent.name])

    def test_priority_is_visible_in_the_list(self):
        body = self.client.get(self.url).content.decode()
        self.assertIn("is-priority", body, "le filet ambre doit etre pose sur la carte")

    def test_batch_can_flag_the_whole_batch(self):
        self.client.post(
            reverse("batch_case_create", kwargs={"project_id": self.project.id}),
            {"biobank_ids": "U-1\nU-2", "status": Case.STATUS_CREATED, "is_priority": "on", "specimen_types": ["normal_dna"]},
        )
        created = Case.objects.filter(biobank_id__startswith="U-")
        self.assertEqual(created.count(), 2)
        self.assertTrue(all(c.is_priority for c in created))

    def test_case_form_can_set_and_clear_the_flag(self):
        url = reverse("case_detail", kwargs={"case_id": self.ordinaire.id})
        self.client.post(url, {
            "case_update": "1", "biobank_id": "B-1", "is_priority": "on",
        })
        self.ordinaire.refresh_from_db()
        self.assertTrue(self.ordinaire.is_priority)

        self.client.post(url, {"case_update": "1", "biobank_id": "B-1"})
        self.ordinaire.refresh_from_db()
        self.assertFalse(self.ordinaire.is_priority)


class ReferredProjectTests(TestCase):
    """Les cas referes par un medecin ont leur propre categorie."""

    def test_project_defaults_to_research(self):
        user = User.objects.create_user("u9", password="x")
        self.assertEqual(
            Project.objects.create(name="P", created_by=user).kind,
            Project.KIND_RESEARCH,
        )

    def test_referred_kind_is_available(self):
        user = User.objects.create_user("u10", password="x")
        referred = Project.objects.create(
            name="Referred Cases", kind=Project.KIND_REFERRED, created_by=user)
        self.assertEqual(referred.get_kind_display(), "Referred cases")


class SpecimenTests(TestCase):
    """Tumeur et normal sont des entites distinctes, suivies independamment.

    Le statut du cas en est DERIVE, comme le tier l'est deja des couvertures.
    """

    def setUp(self):
        self.editor = make_editor("editor6")
        self.project = Project.objects.create(name="P spec", created_by=self.editor)
        self.case = Case.objects.create(project=self.project, biobank_id="S-1")
        self.case.ensure_specimens()
        self.client = Client()
        self.client.force_login(self.editor)
        self.url = reverse("case_detail", kwargs={"case_id": self.case.id})

    def _set(self, specimen_type, **kwargs):
        specimen = self.case.specimens.get(specimen_type=specimen_type)
        for key, value in kwargs.items():
            setattr(specimen, key, value)
        specimen.save()
        self.case.refresh_from_db()
        return specimen

    def test_a_case_gets_the_three_specimens_by_default(self):
        self.assertEqual(
            [s.specimen_type for s in self.case.specimens_in_order()],
            Specimen.ORDERED_TYPES,
        )

    def test_a_case_is_never_forced_to_three_specimens(self):
        """Sinon un protocole sans ARN resterait 'en attente' a perpetuite."""
        autre = Case.objects.create(project=self.project, biobank_id="S-2")
        autre.ensure_specimens([Specimen.TYPE_NORMAL_DNA, Specimen.TYPE_TUMOUR_DNA])
        self.assertEqual(autre.specimens.count(), 2)
        self.assertFalse(autre.specimens.filter(specimen_type=Specimen.TYPE_TUMOUR_RNA).exists())

    def test_case_status_is_the_least_advanced_specimen(self):
        self._set(Specimen.TYPE_NORMAL_DNA, status=statuses.ANALYSIS_COMPLETE)
        self._set(Specimen.TYPE_TUMOUR_DNA, status=statuses.ANALYSIS_COMPLETE)
        self._set(Specimen.TYPE_TUMOUR_RNA, status=statuses.RECEIVED)
        self.assertEqual(self.case.status, statuses.RECEIVED)

    def test_a_specimen_to_classify_does_not_drag_the_case_backwards(self):
        """Le point qui evite de faire regresser 855 cas a l'ecran.

        Un cas dont l'ADN est analyse et dont l'ARN reste a classer doit
        continuer d'afficher l'avancee reelle de son ADN.
        """
        self._set(Specimen.TYPE_NORMAL_DNA, status=statuses.ANALYSIS_COMPLETE)
        self._set(Specimen.TYPE_TUMOUR_DNA, status=statuses.ANALYSIS_COMPLETE)
        self._set(Specimen.TYPE_TUMOUR_RNA, status=statuses.UNKNOWN_LEGACY)
        self.assertEqual(self.case.status, statuses.ANALYSIS_COMPLETE)
        self.assertEqual(self.case.specimens_to_classify(), 1)

    def test_everything_to_classify_shows_as_such(self):
        for specimen_type in Specimen.ORDERED_TYPES:
            self._set(specimen_type, status=statuses.UNKNOWN_LEGACY)
        self.assertEqual(self.case.status, statuses.UNKNOWN_LEGACY)

    def test_coverage_mirrors_onto_the_case_and_drives_the_tier(self):
        self._set(Specimen.TYPE_TUMOUR_DNA, coverage=85)
        self._set(Specimen.TYPE_NORMAL_DNA, coverage=35)
        self._set(Specimen.TYPE_TUMOUR_RNA, coverage=120)

        self.assertEqual(self.case.dna_t_coverage, 85)
        self.assertEqual(self.case.dna_n_coverage, 35)
        self.assertEqual(self.case.rna_coverage, 120)
        self.assertEqual(self.case.tier, "A")

        self._set(Specimen.TYPE_TUMOUR_DNA, coverage=12)
        self.assertEqual(self.case.tier, "FAIL", "sous 30X le tier doit tomber")

    def test_one_dropdown_moves_every_specimen(self):
        """L'action la plus frequente du systeme ne doit pas tripler."""
        self.client.post(self.url, {
            "status_update": "1",
            "status": statuses.SEQUENCING_COMPLETE,
            "apply_to": "all",
        })
        self.case.refresh_from_db()
        self.assertTrue(all(s.status == statuses.SEQUENCING_COMPLETE
                            for s in self.case.specimens_in_order()))
        self.assertEqual(self.case.status, statuses.SEQUENCING_COMPLETE)

    def test_a_single_specimen_can_be_targeted(self):
        self.client.post(self.url, {
            "status_update": "1", "status": statuses.ANALYZING, "apply_to": "all"})
        self.client.post(self.url, {
            "status_update": "1", "status": statuses.RECEIVED,
            "apply_to": Specimen.TYPE_TUMOUR_RNA})

        self.case.refresh_from_db()
        par_type = {s.specimen_type: s.status for s in self.case.specimens_in_order()}
        self.assertEqual(par_type[Specimen.TYPE_TUMOUR_RNA], statuses.RECEIVED)
        self.assertEqual(par_type[Specimen.TYPE_TUMOUR_DNA], statuses.ANALYZING)
        self.assertEqual(self.case.status, statuses.RECEIVED)

    def test_apply_to_only_offers_specimens_that_exist(self):
        autre = Case.objects.create(project=self.project, biobank_id="S-3")
        autre.ensure_specimens([Specimen.TYPE_NORMAL_DNA])
        response = self.client.get(reverse("case_detail", kwargs={"case_id": autre.id}))
        choix = dict(response.context["status_form"].fields["apply_to"].choices)
        self.assertIn(Specimen.TYPE_NORMAL_DNA, choix)
        self.assertNotIn(Specimen.TYPE_TUMOUR_RNA, choix)

    def test_legacy_status_is_never_offered_for_entry(self):
        self.assertNotIn(statuses.UNKNOWN_LEGACY, statuses.SELECTABLE)
        proposables = [
            slug
            for _groupe, options in statuses.GROUPED_CHOICES
            for slug, _label in options
        ]
        self.assertNotIn(statuses.UNKNOWN_LEGACY, proposables)

    def test_legacy_status_stays_findable_in_filters(self):
        """Sinon personne ne peut retrouver les cas qu'on lui demande de reclasser."""
        from .forms import CaseFilterForm
        choix = [slug for slug, _ in CaseFilterForm().fields["status"].choices]
        self.assertIn(statuses.UNKNOWN_LEGACY, choix)


class BulkStatusTests(TestCase):
    """Changement de statut en lot : ce que Mathieu a demande pour tuer l'aller-retour CSV."""

    def setUp(self):
        self.editor = make_editor("editor7")
        self.project = Project.objects.create(name="P lot", created_by=self.editor)
        self.cases = []
        for i in range(40):
            case = Case.objects.create(project=self.project, biobank_id=f"L-{i:03d}")
            case.ensure_specimens()
            self.cases.append(case)
        self.client = Client()
        self.client.force_login(self.editor)
        self.url = reverse("bulk_status_update", kwargs={"project_id": self.project.id})

    def _apply(self, cases, status, apply_to="all"):
        return self.client.post(self.url, {
            "case_ids": [c.id for c in cases],
            "apply_to": apply_to,
            "status": status,
        }, follow=True)

    def test_forty_cases_move_in_one_request(self):
        self._apply(self.cases, statuses.SEQUENCING_COMPLETE)
        moved = Case.objects.filter(
            project=self.project, status=statuses.SEQUENCING_COMPLETE).count()
        self.assertEqual(moved, 40)

    def test_only_selected_cases_move(self):
        self._apply(self.cases[:10], statuses.RECEIVED)
        self.assertEqual(
            Case.objects.filter(project=self.project, status=statuses.RECEIVED).count(), 10)
        self.assertEqual(
            Case.objects.filter(project=self.project, status=statuses.DEFAULT).count(), 30)

    def test_a_single_specimen_type_can_be_targeted(self):
        self._apply(self.cases[:5], statuses.ANALYZING, apply_to=Specimen.TYPE_TUMOUR_RNA)
        case = Case.objects.get(id=self.cases[0].id)
        par_type = {s.specimen_type: s.status for s in case.specimens_in_order()}
        self.assertEqual(par_type[Specimen.TYPE_TUMOUR_RNA], statuses.ANALYZING)
        self.assertEqual(par_type[Specimen.TYPE_TUMOUR_DNA], statuses.DEFAULT)

    def test_the_operation_is_logged_line_by_line(self):
        self._apply(self.cases[:3], statuses.RECEIVED)
        operation = BatchOperation.objects.get()
        self.assertEqual(operation.case_count, 3)
        self.assertEqual(operation.changes.count(), 9, "3 cas x 3 specimens")
        self.assertEqual(operation.performed_by, self.editor)

    def test_undo_restores_every_specimen(self):
        self._apply(self.cases[:5], statuses.RECEIVED)
        operation = BatchOperation.objects.get()

        self.client.post(reverse("bulk_status_undo", kwargs={"batch_id": operation.id}),
                         follow=True)

        for case in Case.objects.filter(id__in=[c.id for c in self.cases[:5]]):
            self.assertEqual(case.status, statuses.DEFAULT)
        operation.refresh_from_db()
        self.assertTrue(operation.is_undone)

    def test_undo_leaves_alone_what_changed_afterwards(self):
        """Annuler ne doit pas ecraser le travail fait apres l'operation."""
        self._apply(self.cases[:5], statuses.RECEIVED)
        operation = BatchOperation.objects.get()

        touche = Case.objects.get(id=self.cases[0].id)
        specimen = touche.specimens_in_order()[0]
        specimen.status = statuses.ANALYZING
        specimen.save()

        self.client.post(reverse("bulk_status_undo", kwargs={"batch_id": operation.id}),
                         follow=True)

        specimen.refresh_from_db()
        self.assertEqual(specimen.status, statuses.ANALYZING)
        # les autres sont bien revenus
        autre = Case.objects.get(id=self.cases[1].id)
        self.assertEqual(autre.status, statuses.DEFAULT)

    def test_undoing_twice_changes_nothing_more(self):
        self._apply(self.cases[:3], statuses.RECEIVED)
        operation = BatchOperation.objects.get()
        url = reverse("bulk_status_undo", kwargs={"batch_id": operation.id})
        self.client.post(url, follow=True)
        self.assertEqual(operation.undo(), 0)

    def test_an_empty_selection_changes_nothing(self):
        self.client.post(self.url, {"case_ids": [], "apply_to": "all",
                                    "status": statuses.RECEIVED}, follow=True)
        self.assertEqual(BatchOperation.objects.count(), 0)
        self.assertEqual(
            Case.objects.filter(project=self.project, status=statuses.DEFAULT).count(), 40)

    def test_applying_the_status_they_already_have_records_nothing(self):
        self._apply(self.cases[:3], statuses.DEFAULT)
        self.assertEqual(BatchOperation.objects.count(), 0,
                         "une operation sans effet ne doit pas polluer le journal")

    def test_a_viewer_cannot_apply_a_batch(self):
        viewer = User.objects.create_user("viewer2", password="x")
        viewer.groups.add(Group.objects.get_or_create(name="viewer")[0])
        client = Client()
        client.force_login(viewer)
        response = client.post(self.url, {
            "case_ids": [self.cases[0].id], "apply_to": "all",
            "status": statuses.RECEIVED})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Case.objects.get(id=self.cases[0].id).status, statuses.DEFAULT)

    def test_the_table_carries_checkboxes_and_the_action_bar(self):
        body = self.client.get(
            reverse("project_detail", kwargs={"project_id": self.project.id})
        ).content.decode()
        self.assertIn('name="case_ids"', body)
        self.assertIn('id="select-all"', body)
        self.assertIn('id="bulk-bar"', body)


class ResubmitTests(TestCase):
    """Meme ACC, nouvelle tentative, ancienne archivee avec son historique."""

    def setUp(self):
        self.editor = make_editor("editor8")
        self.project = Project.objects.create(name="P resub", created_by=self.editor)
        self.case = Case.objects.create(project=self.project, biobank_id="R-1")
        self.case.ensure_specimens()
        for specimen in self.case.specimens.all():
            specimen.coverage = 85 if specimen.specimen_type != Specimen.TYPE_TUMOUR_RNA else 120
            specimen.status = statuses.ANALYSIS_COMPLETE
            specimen.save()
        self.case.refresh_from_db()
        Comment.objects.create(case=self.case, text="note d'origine", user=self.editor)
        self.client = Client()
        self.client.force_login(self.editor)
        self.url = reverse("case_resubmit", kwargs={"case_id": self.case.id})

    def _resubmit(self, carry=(), confirm="RESUBMIT"):
        return self.client.post(self.url, {
            "confirm": confirm, "carry_forward": list(carry), "note": "RNA failed QC",
        }, follow=True)

    def test_the_new_attempt_keeps_the_same_acc(self):
        self._resubmit()
        ancien = Case.all_objects.get(id=self.case.id)
        nouveau = ancien.superseded_by
        self.assertEqual(nouveau.acc_number, ancien.acc_number)
        self.assertEqual(nouveau.name, ancien.name)
        self.assertEqual(nouveau.attempt, 2)

    def test_two_active_cases_can_never_share_an_acc(self):
        """La contrainte porte sur la tentative EN COURS, pas sur l'ACC nu."""
        from django.db.utils import IntegrityError
        with self.assertRaises(IntegrityError):
            Case.objects.create(project=self.project, acc_number=self.case.acc_number)

    def test_the_old_attempt_is_archived_not_deleted(self):
        self._resubmit()
        ancien = Case.all_objects.get(id=self.case.id)
        self.assertTrue(ancien.is_archived)
        self.assertFalse(Case.objects.filter(id=ancien.id).exists(), "masque des listes")
        self.assertTrue(Case.all_objects.filter(id=ancien.id).exists(), "toujours en base")

    def test_history_and_coverage_stay_with_the_archived_attempt(self):
        """Rien n'est copie, donc rien ne peut se perdre dans la copie."""
        avant = [s.coverage for s in self.case.specimens_in_order()]
        self._resubmit()
        ancien = Case.all_objects.get(id=self.case.id)
        self.assertEqual([s.coverage for s in ancien.specimens_in_order()], avant)
        self.assertTrue(ancien.comments.filter(text="note d'origine").exists())

    def test_a_carried_forward_specimen_keeps_its_result(self):
        self._resubmit(carry=[Specimen.TYPE_NORMAL_DNA])
        nouveau = Case.all_objects.get(id=self.case.id).superseded_by
        par_type = {s.specimen_type: s for s in nouveau.specimens_in_order()}
        self.assertEqual(par_type[Specimen.TYPE_NORMAL_DNA].coverage, 85)
        self.assertEqual(par_type[Specimen.TYPE_NORMAL_DNA].status, statuses.ANALYSIS_COMPLETE)
        self.assertIsNone(par_type[Specimen.TYPE_TUMOUR_DNA].coverage,
                          "un specimen non reporte repart de zero")

    def test_the_new_attempt_keeps_the_same_specimen_types(self):
        deux = Case.objects.create(project=self.project, biobank_id="R-2")
        deux.ensure_specimens([Specimen.TYPE_NORMAL_DNA, Specimen.TYPE_TUMOUR_DNA])
        self.client.post(reverse("case_resubmit", kwargs={"case_id": deux.id}),
                         {"confirm": "RESUBMIT", "carry_forward": []}, follow=True)
        nouveau = Case.all_objects.get(id=deux.id).superseded_by
        self.assertEqual(nouveau.specimens.count(), 2)

    def test_a_wrong_confirmation_changes_nothing(self):
        avant = Case.all_objects.count()
        self._resubmit(confirm="oui")
        self.assertEqual(Case.all_objects.count(), avant)
        self.case.refresh_from_db()
        self.assertFalse(self.case.is_archived)

    def test_both_attempts_get_a_trace_comment(self):
        self._resubmit()
        ancien = Case.all_objects.get(id=self.case.id)
        nouveau = ancien.superseded_by
        self.assertTrue(ancien.comments.filter(text__contains="Resubmitted as attempt 2").exists())
        self.assertTrue(nouveau.comments.filter(text__contains="replacing attempt 1").exists())

    def test_an_archived_attempt_is_read_only_but_still_reachable(self):
        self._resubmit()
        ancien = Case.all_objects.get(id=self.case.id)
        response = self.client.get(reverse("case_detail", kwargs={"case_id": ancien.id}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_edit"])
        self.assertIn("Archived attempt", response.content.decode())

    def test_the_current_attempt_lists_the_previous_ones(self):
        self._resubmit()
        nouveau = Case.all_objects.get(id=self.case.id).superseded_by
        response = self.client.get(reverse("case_detail", kwargs={"case_id": nouveau.id}))
        precedentes = list(response.context["previous_attempts"])
        self.assertEqual([p.attempt for p in precedentes], [1])
        self.assertEqual(precedentes[0].comment_total, 2)

    def test_resubmitting_an_archived_attempt_is_refused(self):
        self._resubmit()
        ancien = Case.all_objects.get(id=self.case.id)
        response = self.client.get(
            reverse("case_resubmit", kwargs={"case_id": ancien.id}), follow=True)
        self.assertEqual(Case.all_objects.filter(acc_number=ancien.acc_number).count(), 2,
                         "aucune troisieme tentative ne doit avoir ete ouverte")


class ExportTests(TestCase):
    """Deux granularites, et une forme de fichier choisie pour ce qu'on en fait."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin3", password="x")
        self.editor = make_editor("editor9")
        self.project = Project.objects.create(name="P export", created_by=self.admin)
        self.case = Case.objects.create(project=self.project, biobank_id="E-1")
        self.case.ensure_specimens()
        for specimen in self.case.specimens.all():
            specimen.coverage = 85
            specimen.status = statuses.ANALYSIS_COMPLETE
            specimen.save()
        Comment.objects.create(case=self.case, user=self.admin,
                               text='ligne 1\nligne 2, avec virgule et "guillemets"')
        self.client = Client()
        self.client.force_login(self.admin)

    def _zip(self, url):
        import io, zipfile
        return zipfile.ZipFile(io.BytesIO(self.client.get(url).content))

    def _rows(self, texte):
        import csv, io
        return list(csv.reader(io.StringIO(texte)))

    def test_project_csv_is_one_wide_row_per_case(self):
        """Le format large : c'est celui qu'un PI croise par RECHERCHEV."""
        response = self.client.get(
            reverse("csv_case_export", kwargs={"project_id": self.project.id}))
        rows = self._rows(response.content.decode())
        self.assertEqual(len(rows) - 1, 1, "une ligne par cas, pas par specimen")
        self.assertIn("Normal_DNA_Coverage_X", rows[0])
        self.assertIn("Tumour_RNA_Coverage_M_reads", rows[0])
        self.assertIn("Biobank_ID", rows[0])

    def test_the_bundle_carries_the_four_files_and_a_readme(self):
        archive = self._zip(
            reverse("project_export_bundle", kwargs={"project_id": self.project.id}))
        self.assertEqual(
            sorted(archive.namelist()),
            ["README.txt", "cases.csv", "cases_archived.csv", "comments.csv", "specimens.csv"],
        )

    def test_the_readme_warns_about_joining_on_acc_alone(self):
        """Le piege de correctitude le plus serieux de ces exports."""
        archive = self._zip(
            reverse("project_export_bundle", kwargs={"project_id": self.project.id}))
        readme = archive.read("README.txt").decode()
        self.assertIn("never on ACC alone", readme)

    def test_archived_attempts_never_land_in_the_active_file(self):
        """Une erreur de filtre gonflerait un effectif publie."""
        self.case.resubmit(user=self.admin)
        archive = self._zip(
            reverse("project_export_bundle", kwargs={"project_id": self.project.id}))

        actifs = self._rows(archive.read("cases.csv").decode())
        archives = self._rows(archive.read("cases_archived.csv").decode())
        self.assertEqual(len(actifs) - 1, 1)
        self.assertEqual(len(archives) - 1, 1)
        self.assertEqual(actifs[1][1], "2", "le fichier actif porte la tentative en cours")
        self.assertEqual(archives[1][1], "1")

    def test_child_files_carry_the_join_key(self):
        archive = self._zip(
            reverse("project_export_bundle", kwargs={"project_id": self.project.id}))
        for nom in ("specimens.csv", "comments.csv"):
            with self.subTest(fichier=nom):
                entete = self._rows(archive.read(nom).decode())[0]
                self.assertIn("ACC", entete)
                self.assertIn("Attempt", entete)

    def test_multiline_comments_survive_the_round_trip(self):
        archive = self._zip(
            reverse("project_export_bundle", kwargs={"project_id": self.project.id}))
        rows = self._rows(archive.read("comments.csv").decode())
        self.assertEqual(len(rows) - 1, 1, "un commentaire multi-lignes reste UNE ligne CSV")
        self.assertIn('guillemets', rows[1][-1])

    def test_a_missing_specimen_reads_as_not_collected(self):
        autre = Case.objects.create(project=self.project, biobank_id="E-2")
        autre.ensure_specimens([Specimen.TYPE_NORMAL_DNA])
        rows = self._rows(self.client.get(
            reverse("csv_case_export", kwargs={"project_id": self.project.id})
        ).content.decode())
        colonne = rows[0].index("Tumour_RNA_Status")
        ligne = next(r for r in rows[1:] if r[2] == "E-2")
        self.assertEqual(ligne[colonne], "not collected",
                         "distinguer 'pas prevu au protocole' de 'en attente'")

    def test_only_an_administrator_gets_the_consortium_export(self):
        client = Client()
        client.force_login(self.editor)
        response = client.get(reverse("consortium_export"), follow=True)
        self.assertNotIn("application/zip", response.get("Content-Type", ""))

    def test_an_editor_keeps_their_own_project_export(self):
        client = Client()
        client.force_login(self.editor)
        response = client.get(
            reverse("project_export_bundle", kwargs={"project_id": self.project.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")

    def test_export_query_count_does_not_grow_with_case_count(self):
        for i in range(30):
            case = Case.objects.create(project=self.project, biobank_id=f"E-1{i:02d}")
            case.ensure_specimens()
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse("project_export_bundle",
                                    kwargs={"project_id": self.project.id}))
        self.assertLess(len(ctx.captured_queries), 25,
                        "un N+1 dans l'export ferait exploser le temps sur 1329 cas")


# Reglages statiques de PRODUCTION, reproduits pour les tests.
#
# STATIC_ROOT en fait partie : sans lui le stockage a manifeste ne trouve pas
# staticfiles.json et echoue pour une raison qui n'a rien a voir avec ce qu'on
# veut verifier. Les reglages de developpement ne definissent pas STATIC_ROOT.
MANIFEST_SETTINGS = {
    "STORAGES": {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    },
    "STATIC_ROOT": str(Path(__file__).resolve().parent.parent / "staticfiles"),
}


class StaticAssetTests(TestCase):
    """Les ressources statiques, avec le stockage de PRODUCTION.

    Le reste de la suite tourne avec StaticFilesStorage, qui ne verifie rien :
    un chemin {% static %} inexistant y passe inapercu et ne casse qu'en
    production, sur toutes les pages a la fois. Ces tests activent le stockage a
    manifeste, qui leve au rendu -- exactement comme le serveur.
    """

    def setUp(self):
        self.admin = User.objects.create_superuser("admin4", password="x")
        self.project = Project.objects.create(name="P static", created_by=self.admin)
        self.case = Case.objects.create(project=self.project, biobank_id="ST-1")
        self.case.ensure_specimens()
        self.lead = ProjectLead.objects.create(name="Dr Static")
        self.client = Client()
        self.client.force_login(self.admin)

    def _pages(self):
        return [
            reverse("home"),
            reverse("project_detail", kwargs={"project_id": self.project.id}),
            reverse("case_detail", kwargs={"case_id": self.case.id}),
            reverse("case_search"),
            reverse("case_create", kwargs={"project_id": self.project.id}),
            reverse("batch_case_create", kwargs={"project_id": self.project.id}),
            reverse("csv_case_import", kwargs={"project_id": self.project.id}),
            reverse("case_resubmit", kwargs={"case_id": self.case.id}),
            reverse("project_lead_list"),
            reverse("project_lead_update", kwargs={"lead_id": self.lead.id}),
            reverse("user_list"),
            reverse("user_create"),
            reverse("project_update", kwargs={"project_id": self.project.id}),
            reverse("project_delete", kwargs={"project_id": self.project.id}),
            reverse("case_delete", kwargs={"case_id": self.case.id}),
        ]

    def test_every_page_renders_with_the_production_storage(self):
        """Un {% static %} manquant renvoie des 500 sur TOUT le site."""
        with override_settings(**MANIFEST_SETTINGS):
            for url in self._pages():
                with self.subTest(url=url):
                    self.assertIn(self.client.get(url).status_code, (200, 302))

    def test_the_login_page_renders_for_an_anonymous_visitor(self):
        """Si base.html casse, plus personne ne peut meme se connecter."""
        with override_settings(**MANIFEST_SETTINGS):
            response = Client().get(reverse("login"))
            self.assertEqual(response.status_code, 200)

    def test_no_template_syntax_leaks_into_the_page(self):
        """Un commentaire {# ... #} sur PLUSIEURS lignes n'en est pas un.

        Django ne reconnait cette syntaxe que sur une seule ligne : etalee sur
        deux, elle n'est pas interpretee et le texte part tel quel dans la page.
        Le meme piege vaut pour une balise mal fermee.
        """
        for url in self._pages():
            with self.subTest(url=url):
                body = self.client.get(url).content.decode()
                for marqueur in ("{#", "{%", "{{"):
                    self.assertNotIn(
                        marqueur, body,
                        f"syntaxe de gabarit non interpretee servie par {url}")

    def test_templates_have_no_mobile_hostile_patterns(self):
        """L'ecran etroit ne doit pas se degrader a la prochaine modification.

        Les enfants d'un conteneur flex ont min-width:auto : sans flex-wrap,
        une rangee chargee garde sa largeur de contenu et pousse la page. C'est
        ce qui rendait l'en-tete de la page projet large de ~1050 px dans un
        viewport de 360. ops/lint_templates.py attrape cette famille de motifs.
        """
        import subprocess
        import sys

        racine = Path(__file__).resolve().parent.parent
        resultat = subprocess.run(
            [sys.executable, str(racine / "ops" / "lint_templates.py")],
            capture_output=True, text=True,
        )
        self.assertEqual(
            resultat.returncode, 0,
            "motifs hostiles au petit ecran :\n" + resultat.stdout,
        )

    def test_the_stylesheet_adapts_to_narrow_screens(self):
        """La feuille n'avait aucun point de rupture de largeur."""
        css = (Path(__file__).resolve().parent.parent
               / "static" / "css" / "lims.css").read_text()
        for point in ("max-width: 991.98px", "max-width: 767.98px", "max-width: 575.98px"):
            with self.subTest(point=point):
                self.assertIn(point, css)
        # Un jeton insecable ne doit jamais elargir la page.
        self.assertIn("overflow-wrap", css)
        # Les champs sous 16 px declenchent le zoom automatique de Safari iOS.
        self.assertIn("font-size: 16px", css)

    def test_no_asset_is_loaded_from_a_cdn(self):
        """Un serveur de laboratoire interne ne doit pas dependre d'un CDN."""
        body = self.client.get(reverse("home")).content.decode()
        for hote in ("cdn.jsdelivr.net", "cdnjs.cloudflare.com", "fonts.googleapis.com"):
            self.assertNotIn(hote, body)

    def test_the_stylesheet_and_fonts_are_collectible(self):
        from django.contrib.staticfiles import finders
        for chemin in ("css/lims.css", "fonts/plex-sans-400.woff2",
                       "fonts/plex-mono-400.woff2",
                       "vendor/bootstrap/bootstrap.min.css",
                       "vendor/bootstrap/bootstrap.bundle.min.js"):
            with self.subTest(chemin=chemin):
                self.assertIsNotNone(finders.find(chemin), f"{chemin} introuvable")


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


class LiveFilterTests(TestCase):
    """Le filtrage en direct.

    Filtrer demandait trois gestes : saisir, cliquer sur "Filter", puis cliquer
    sur "Clear" pour revenir en arriere. Le script rejoue la requete GET et
    remplace les regions marquees `data-live-region`.

    Ces tests portent sur le CONTRAT entre le gabarit et le script, pas sur le
    script lui-meme : le navigateur cherche dans la reponse un element ayant
    l'identifiant de celui qu'il remplace. Si un gabarit perd cet identifiant,
    ou ne le rend que dans certains cas, le filtre cesse silencieusement de
    rafraichir -- l'ecran garde l'ancien resultat sans rien signaler.
    """

    #: gabarit -> (identifiant de region, adresse)
    REGIONS = ("projects-region", "cases-region", "cases-heading", "search-region")

    def setUp(self):
        self.admin = User.objects.create_superuser("admin_lf", password="x")
        self.lead = ProjectLead.objects.create(name="Dr Live")
        self.project = Project.objects.create(
            name="P live", project_lead=self.lead, created_by=self.admin)
        for i in range(30):
            case = Case.objects.create(project=self.project, biobank_id=f"LF-{i:03d}")
            case.ensure_specimens()
        self.client = Client()
        self.client.force_login(self.admin)

    def _home(self, **filtres):
        return self.client.get(reverse("home"), filtres).content.decode()

    def _projet(self, **filtres):
        return self.client.get(
            reverse("project_detail", kwargs={"project_id": self.project.id}),
            filtres,
        ).content.decode()

    def _recherche(self, **filtres):
        return self.client.get(reverse("case_search"), filtres).content.decode()

    # -- le script ---------------------------------------------------------

    def test_the_script_is_loaded_on_every_page(self):
        self.assertIn("js/live-filter.js", self._home())
        self.assertIn("js/live-filter.js", self._projet())

    def test_the_script_file_exists(self):
        chemin = Path(settings.BASE_DIR) / "static" / "js" / "live-filter.js"
        self.assertTrue(chemin.is_file(), "le gabarit reference un fichier absent")

    # -- le contrat gabarit / script ---------------------------------------

    def test_every_filter_form_is_marked_live(self):
        for page in (self._home(), self._projet(), self._recherche()):
            self.assertIn("data-live-filter", page)
            self.assertIn("data-live-submit", page)

    def test_a_region_is_present_on_each_filtered_page(self):
        self.assertIn('id="projects-region"', self._home())
        self.assertIn('id="cases-region"', self._projet())
        self.assertIn('id="cases-heading"', self._projet())
        self.assertIn('id="search-region"', self._recherche(q="LF-000"))

    def test_the_region_survives_a_filter_that_matches_nothing(self):
        """L'invariant dont depend le remplacement.

        Une region rendue seulement quand il y a des resultats disparaitrait de
        la reponse des la premiere recherche infructueuse : le navigateur ne
        trouverait rien a remettre en place et laisserait la liste precedente a
        l'ecran, ce qui se lit comme un filtre sans effet.
        """
        self.assertIn('id="projects-region"', self._home(name="zzz-aucun"))
        self.assertIn('id="cases-region"', self._projet(name="zzz-aucun"))
        self.assertIn('id="cases-heading"', self._projet(name="zzz-aucun"))
        self.assertIn('id="search-region"', self._recherche(q="zzz-aucun"))

    def test_the_region_survives_an_empty_project_and_an_empty_search(self):
        vide = Project.objects.create(name="P vide", created_by=self.admin)
        page = self.client.get(
            reverse("project_detail", kwargs={"project_id": vide.id})).content.decode()
        self.assertIn('id="cases-region"', page)
        self.assertIn('id="search-region"', self._recherche())

    # -- le bouton d'effacement --------------------------------------------

    def test_clear_is_always_rendered_so_the_script_can_reveal_it(self):
        """Rendu sous condition, il n'apparaitrait jamais.

        Le formulaire reste hors de la region remplacee -- c'est ce qui preserve
        le curseur pendant la frappe. Un lien "Clear" conditionne a
        request.GET ne serait donc jamais rendu a nouveau apres un filtre pose
        sans rechargement.
        """
        for page in (self._home(), self._projet()):
            self.assertIn("data-live-clear", page)

    def test_clear_is_hidden_when_no_filter_is_set(self):
        for page in (self._home(), self._projet()):
            debut = page.index("data-live-clear")
            self.assertIn("hidden", page[debut:debut + 400])

    def test_clear_is_visible_once_a_filter_is_set(self):
        for page in (self._home(name="P live"), self._projet(name="LF-000")):
            debut = page.index("data-live-clear")
            self.assertNotIn("hidden", page[debut:page.index(">", debut)])

    # -- le compte annonce --------------------------------------------------

    def test_the_heading_counts_every_match_not_just_the_page(self):
        """`cases` est la page courante, pas l'ensemble des correspondances.

        Le titre annoncait la taille de la page : "100 results" sur un projet
        qui en comptait 200. Le filtre devenant vivant, ce nombre bouge a
        chaque frappe et se lit comme un decompte.
        """
        with mock.patch("core.views.CASES_PER_PAGE", 10):
            page = self._projet(name="LF-")
        self.assertIn("30 results", page)
        self.assertNotIn("10 results", page)

    def test_filtering_actually_narrows_the_result(self):
        self.assertIn("(1 result)", self._projet(name="LF-007"))
