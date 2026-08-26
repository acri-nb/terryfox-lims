from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth.models import User, Group
import csv
import re
from io import TextIOWrapper
from datetime import datetime
import string
import random

import logging

from . import exports, statuses
from .models import BatchOperation, SpecimenStatusChange, Project, Case, Specimen, Accession, Comment, ProjectLead, IdentifierSequence

from .forms import ProjectForm, CaseForm, CaseStatusForm, SpecimenFormSet, CommentForm, AccessionFormSet, ProjectLeadForm, ProjectFilterForm, CaseFilterForm, BatchCaseForm, BulkStatusForm, ResubmitForm, CSVImportForm, UserCreateForm, BatchUserCreateForm, UserUpdateForm

# Nombre de cas affiches par page. Le plus gros projet en compte 256 ; a 100 par
# page la recherche et les filtres restent le chemin principal pour retrouver un
# cas, la pagination n'etant qu'un garde-fou sur le poids de la page.
CASES_PER_PAGE = 100

logger = logging.getLogger(__name__)

@login_required
def home(request):
    """Tableau de bord : ou en est le consortium, en un coup d'oeil.

    Les repartitions sont dessinees en barres d'une SEULE teinte : elles
    encodent une magnitude, pas une identite. Les couleurs de tier
    n'apparaissent qu'en pastille, toujours accompagnees de leur lettre --
    l'ambre et le rouge sont indistinguables en deuteranopie, la couleur ne
    peut donc jamais porter seule l'information.
    """
    filter_form = ProjectFilterForm(request.GET)
    projects = Project.objects.all()

    if filter_form.is_valid():
        project_name = filter_form.cleaned_data.get('name')
        project_lead = filter_form.cleaned_data.get('project_lead')
        if project_name:
            projects = projects.filter(name__icontains=project_name)
        if project_lead:
            projects = projects.filter(project_lead=project_lead)

    projects = (projects
                .select_related('project_lead')
                .annotate(
                    cases_count=Count('cases', distinct=True),
                    priority_count=Count(
                        'cases', distinct=True, filter=Q(cases__is_priority=True)),
                )
                .order_by('name'))

    total_projects = Project.objects.count()
    total_cases = Case.objects.count()
    total_priority = Case.objects.filter(is_priority=True).count()
    total_to_classify = (Case.objects
                         .filter(specimens__status=statuses.UNKNOWN_LEGACY)
                         .distinct().count())

    # Repartition par ETAPE plutot que par statut : trois barres se lisent,
    # onze n'apprennent rien de plus.
    par_statut = dict(Case.objects.values_list('status')
                      .annotate(n=Count('id')).order_by())
    par_etape = []
    for etape in statuses.ORDERED_STAGES + [statuses.STAGE_LEGACY]:
        n = sum(v for slug, v in par_statut.items()
                if statuses.STAGE_OF.get(slug) == etape)
        if n or etape != statuses.STAGE_LEGACY:
            par_etape.append({
                'label': statuses.STAGE_LABELS[etape],
                'count': n,
                'pct': round(100 * n / total_cases) if total_cases else 0,
            })

    cases_by_status = [
        {'status': slug,
         'status_display': statuses.LABEL_OF.get(slug, slug),
         'count': n,
         'pct': round(100 * n / total_cases) if total_cases else 0}
        for slug, n in sorted(par_statut.items(), key=lambda kv: -kv[1])
    ]

    cases_by_tier = [
        {'tier': tier, 'count': n,
         'pct': round(100 * n / total_cases) if total_cases else 0}
        for tier, n in sorted(
            Case.objects.values_list('tier').annotate(n=Count('id')).order_by(),
            key=lambda kv: ['A', 'B', 'FAIL'].index(kv[0]) if kv[0] in ('A', 'B', 'FAIL') else 9)
    ]

    projects_by_lead = (Project.objects.values('project_lead__name')
                        .annotate(count=Count('id')).order_by('-count'))

    return render(request, 'core/home.html', {
        'projects': projects,
        'total_projects': total_projects,
        'total_cases': total_cases,
        'total_priority': total_priority,
        'total_to_classify': total_to_classify,
        'stages': par_etape,
        'cases_by_status': cases_by_status,
        'cases_by_tier': cases_by_tier,
        'projects_by_lead': projects_by_lead,
        'filter_form': filter_form,
    })


SEARCH_LIMIT = 200


@login_required
def case_search(request):
    """Recherche d'un cas dans tous les projets, par ACC ou par Biobank ID.

    L'application n'avait aucune recherche transverse : retrouver un cas dont on
    ignore le projet obligeait a ouvrir les projets un par un. C'est pourtant le
    geste le plus courant quand on arrive avec un identifiant de biobanque en
    main.
    """
    query = (request.GET.get('q') or '').strip()
    results = []
    total = 0

    if query:
        matches = (
            Case.objects
            .filter(Q(name__icontains=query) | Q(biobank_id__icontains=query))
            .select_related('project')
            .order_by('name')
        )
        total = matches.count()
        results = matches[:SEARCH_LIMIT]

    return render(request, 'core/case_search.html', {
        'query': query,
        'results': results,
        'total': total,
        'truncated': total > SEARCH_LIMIT,
        'limit': SEARCH_LIMIT,
    })


@login_required
def project_detail(request, project_id):
    """
    View for showing project details including all cases
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Initialize filter form
    filter_form = CaseFilterForm(request.GET)
    
    # Start with all cases for this project
    cases = project.cases.all()
    
    # Apply filters if the form is valid
    if filter_form.is_valid():
        case_name = filter_form.cleaned_data.get('name')
        case_status = filter_form.cleaned_data.get('status')
        case_tier = filter_form.cleaned_data.get('tier')
        
        if case_name:
            # Un seul champ, deux identifiants : personne ne doit avoir a savoir
            # dans lequel des deux chercher.
            cases = cases.filter(
                Q(name__icontains=case_name) | Q(biobank_id__icontains=case_name)
            )

        if case_status:
            cases = cases.filter(status=case_status)
            
        if case_tier:
            cases = cases.filter(tier=case_tier)

        if filter_form.cleaned_data.get('priority'):
            cases = cases.filter(is_priority=True)

        if filter_form.cleaned_data.get('to_classify'):
            cases = cases.filter(specimens__status=statuses.UNKNOWN_LEGACY).distinct()
    
    # Les compteurs affiches sur chaque carte ({{ case.accessions.count }} et
    # {{ case.comments.count }}) declenchaient une requete chacun, par cas :
    # 522 requetes et 1,1 s sur P06 et ses 256 cas. Deux annotations suffisent.
    # prefetch des specimens : le tableau en affiche la progression sur chaque
    # ligne. Sans cela on remplacerait le N+1 des compteurs par celui des
    # specimens, soit 3 requetes par cas.
    cases = cases.prefetch_related('specimens').annotate(
        accessions_count=Count('accessions', distinct=True),
        comments_count=Count('comments', distinct=True),
        # Le statut du cas vaut celui du specimen le moins avance PARMI CEUX
        # DONT L'ETAT EST CONNU. Un cas dont l'ADN est analyse et dont l'ARN
        # reste a classer afficherait donc « Analysis complete » tout court, ce
        # qui le declarerait termine a tort. Ce compteur rend l'attente visible
        # a cote de la pastille, sans faire regresser les 855 cas reellement
        # termines.
        to_classify=Count(
            'specimens', distinct=True,
            filter=Q(specimens__status=statuses.UNKNOWN_LEGACY),
        ),
    ).order_by('-is_priority', 'name')

    # Pagination : la page renvoyait jusqu'a 926 Ko de HTML d'un coup.
    paginator = Paginator(cases, CASES_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    # get_elided_page_range insere des points de suspension si le nombre de pages
    # grandit, plutot que d'aligner cinquante numeros.
    page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)

    # Les liens de pagination doivent conserver les filtres en cours, sinon
    # passer a la page 2 fait perdre la recherche.
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()

    # Project statistics - always based on all cases
    all_cases = project.cases.all()
    total_cases = all_cases.count()
    
    # Get status statistics with proper display names
    cases_by_status_raw = all_cases.values('status').annotate(count=Count('id'))
    cases_by_status = []
    status_choices_dict = dict(statuses.ALL_CHOICES)
    for stat in cases_by_status_raw:
        cases_by_status.append({
            'status': stat['status'],
            'status_display': status_choices_dict.get(stat['status'], stat['status']),
            'count': stat['count']
        })
    
    cases_by_tier = all_cases.values('tier').annotate(count=Count('id'))

    # Combien de cas trainent encore un specimen herite de la v1 dont l'etat
    # reste a etablir : c'est la file de travail que l'outil de changement en
    # lot est fait pour vider.
    cases_to_classify = all_cases.filter(
        specimens__status=statuses.UNKNOWN_LEGACY).distinct().count()

    # Check if user is part of the 'editor' group for editing permissions
    can_edit = request.user.groups.filter(name='editor').exists() or request.user.is_superuser

    # Derniere application en lot de cet utilisateur, si elle est encore
    # annulable : la banniere d'annulation ne doit apparaitre qu'une fois, et
    # seulement a qui vient de la declencher.
    last_batch = None
    batch_id = request.session.get('last_batch_id')
    if can_edit and batch_id:
        last_batch = BatchOperation.objects.filter(
            id=batch_id, project=project, undone_at__isnull=True).first()
        if last_batch is None:
            request.session.pop('last_batch_id', None)

    return render(request, 'core/project_detail.html', {
        'bulk_form': BulkStatusForm() if can_edit else None,
        'last_batch': last_batch,
        'project': project,
        'cases': page_obj,          # iterable comme avant : le template ne change pas
        'page_obj': page_obj,
        'paginator': paginator,
        'page_range': page_range,
        'page_ellipsis': Paginator.ELLIPSIS,
        'querystring': querystring,
        'filtered_count': paginator.count,
        'total_cases': total_cases,
        'cases_by_status': cases_by_status,
        'cases_by_tier': cases_by_tier,
        'cases_to_classify': cases_to_classify,
        'can_edit': can_edit,
        'filter_form': filter_form,
    })

@login_required
def case_detail(request, case_id):
    """Fiche d'un cas : identite, statut, specimens, accessions, commentaires."""
    # all_objects : une tentative archivee reste consultable par son URL, un
    # vieux lien ou un commentaire doit continuer de mener quelque part.
    case = get_object_or_404(
        Case.all_objects.select_related('project', 'superseded_by')
                        .prefetch_related('specimens'),
        id=case_id,
    )
    comments = case.comments.select_related('user').order_by('-created_at')
    accessions = case.accessions.all()

    can_edit = request.user.groups.filter(name='editor').exists() or request.user.is_superuser
    # Une tentative archivee est en lecture seule : proposer des formulaires qui
    # ne changeront rien de visible est pire que ne rien proposer.
    can_edit = can_edit and not case.is_archived

    comment_form = case_form = accession_formset = None
    status_form = specimen_formset = None

    if can_edit:
        if request.method == 'POST':
            if 'comment_submit' in request.POST:
                comment_form = CommentForm(request.POST)
                if comment_form.is_valid():
                    comment = comment_form.save(commit=False)
                    comment.case = case
                    comment.user = request.user
                    comment.save()
                    messages.success(request, _('Comment added successfully!'))
                    return redirect('case_detail', case_id=case.id)

            elif 'case_update' in request.POST:
                case_form = CaseForm(request.POST, instance=case)
                if case_form.is_valid():
                    case_form.save()
                    messages.success(request, _('Case updated successfully!'))
                    return redirect('case_detail', case_id=case.id)

            elif 'status_update' in request.POST:
                # Le chemin par defaut : un menu, un bouton, tous les specimens.
                status_form = CaseStatusForm(request.POST, case=case)
                if status_form.is_valid():
                    touches = status_form.apply()
                    if touches:
                        messages.success(
                            request,
                            _('{count} specimen(s) moved to {status}.').format(
                                count=touches,
                                status=statuses.LABEL_OF[status_form.cleaned_data['status']],
                            ))
                    else:
                        messages.info(request, _('Nothing to change: already at that status.'))
                    return redirect('case_detail', case_id=case.id)

            elif 'specimen_update' in request.POST:
                specimen_formset = SpecimenFormSet(request.POST, instance=case)
                if specimen_formset.is_valid():
                    specimen_formset.save()
                    # Les couvertures des specimens viennent de changer : le cas
                    # doit reprendre ses miroirs et recalculer son tier.
                    case.sync_from_specimens()
                    messages.success(request, _('Specimens updated.'))
                    return redirect('case_detail', case_id=case.id)

            elif 'accession_update' in request.POST:
                accession_formset = AccessionFormSet(request.POST, instance=case)
                if accession_formset.is_valid():
                    accession_formset.save()
                    messages.success(request, _('Accession numbers updated successfully!'))
                    return redirect('case_detail', case_id=case.id)

        if comment_form is None:
            comment_form = CommentForm()
        if case_form is None:
            case_form = CaseForm(instance=case)
        if status_form is None:
            status_form = CaseStatusForm(case=case, initial={'status': case.status})
        if specimen_formset is None:
            specimen_formset = SpecimenFormSet(instance=case)
        if accession_formset is None:
            accession_formset = AccessionFormSet(instance=case)

    return render(request, 'core/case_detail.html', {
        'case': case,
        'project': case.project,
        'specimens': case.specimens_in_order(),
        'previous_attempts': case.previous_attempts(),
        'blocking': case.blocking_specimen(),
        'to_classify': case.specimens_to_classify(),
        'stages': statuses.ORDERED_STAGES,
        'comments': comments,
        'accessions': accessions,
        'can_edit': can_edit,
        'comment_form': comment_form,
        'case_form': case_form,
        'status_form': status_form,
        'specimen_formset': specimen_formset,
        'accession_formset': accession_formset,
    })


# Opérations CRUD pour les Projets, uniquement pour les utilisateurs 'editor'
@login_required
@permission_required('core.change_case', raise_exception=True)
def bulk_status_update(request, project_id):
    """Applique un statut a tous les cas coches, en une transaction.

    Remplace l'aller-retour CSV : plus de telechargement, plus de re-televersement.
    Chaque specimen touche laisse une ligne de journal, ce qui rend l'operation
    annulable -- une modification de masse sans retour possible est un piege.
    """
    project = get_object_or_404(Project, id=project_id)
    retour = request.POST.get('next') or reverse('project_detail', args=[project.id])

    if request.method != 'POST':
        return redirect(retour)

    form = BulkStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, _('Pick a status before applying.'))
        return redirect(retour)

    ids = form.selected_ids()
    if not ids:
        messages.warning(request, _('No case was selected.'))
        return redirect(retour)

    cible = form.cleaned_data['apply_to']
    nouveau = form.cleaned_data['status']

    cases = Case.objects.filter(project=project, id__in=ids).prefetch_related('specimens')

    with transaction.atomic():
        operation = BatchOperation.objects.create(
            project=project,
            performed_by=request.user,
            status_set=nouveau,
            applied_to=cible,
        )

        journal, touches, cas_touches = [], 0, set()
        for case in cases:
            for specimen in case.specimens.all():
                if cible != BulkStatusForm.APPLY_ALL and specimen.specimen_type != cible:
                    continue
                if specimen.status == nouveau:
                    continue
                journal.append(SpecimenStatusChange(
                    batch=operation, specimen=specimen,
                    old_status=specimen.status, new_status=nouveau,
                ))
                specimen.status = nouveau
                specimen.save(update_fields=['status', 'updated_at'])
                cas_touches.add(case.id)
                touches += 1

        SpecimenStatusChange.objects.bulk_create(journal, batch_size=500)

        for case in Case.objects.filter(id__in=cas_touches):
            case.sync_from_specimens()

        if touches:
            operation.case_count = len(cas_touches)
            operation.save(update_fields=['case_count'])
        else:
            operation.delete()

    if touches:
        messages.success(
            request,
            _('{cases} case(s) moved to {status} ({specimens} specimen(s)).').format(
                cases=len(cas_touches),
                status=statuses.LABEL_OF[nouveau],
                specimens=touches,
            ))
        request.session['last_batch_id'] = operation.id
    else:
        messages.info(request, _('Nothing to change: those cases were already there.'))

    return redirect(retour)


@login_required
@permission_required('core.change_case', raise_exception=True)
def bulk_status_undo(request, batch_id):
    """Annule une application en lot, sans ecraser ce qui a bouge depuis."""
    operation = get_object_or_404(BatchOperation, id=batch_id)
    retour = request.POST.get('next') or reverse('project_detail', args=[operation.project_id])

    if request.method != 'POST':
        return redirect(retour)

    if operation.is_undone:
        messages.info(request, _('That change was already undone.'))
        return redirect(retour)

    total = operation.changes.count()
    rendus = operation.undo(user=request.user)
    intacts = total - rendus

    if intacts:
        messages.warning(
            request,
            _('{done} specimen(s) restored. {kept} were left alone because they '
              'changed again after this operation.').format(done=rendus, kept=intacts))
    else:
        messages.success(
            request, _('{done} specimen(s) restored.').format(done=rendus))

    request.session.pop('last_batch_id', None)
    return redirect(retour)


@login_required
@permission_required('core.add_case', raise_exception=True)
def case_resubmit(request, case_id):
    """Ouvre une nouvelle tentative pour le meme patient, sous le meme ACC."""
    case = get_object_or_404(
        Case.all_objects.select_related('project').prefetch_related('specimens'),
        id=case_id)

    if case.is_archived:
        messages.error(
            request,
            _('This attempt was already superseded. Resubmit from the current one.'))
        return redirect('case_detail', case_id=case.superseded_by_id or case.id)

    if request.method == 'POST':
        form = ResubmitForm(request.POST, case=case)
        if form.is_valid():
            suivant = case.resubmit(
                user=request.user,
                carry_forward=form.cleaned_data['carry_forward'],
                note=form.cleaned_data['note'],
            )
            messages.success(
                request,
                _('{acc} is now attempt {n}. The previous attempt is archived with '
                  'its comments and coverage.').format(acc=suivant.name, n=suivant.attempt))
            return redirect('case_detail', case_id=suivant.id)
    else:
        form = ResubmitForm(case=case)

    return render(request, 'core/case_resubmit.html', {
        'case': case,
        'project': case.project,
        'specimens': case.specimens_in_order(),
        'form': form,
    })


@login_required
@permission_required('core.add_project', raise_exception=True)
def project_create(request):
    """
    View for creating a new project
    """
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            messages.success(request, _('Project created successfully!'))
            return redirect('project_detail', project_id=project.id)
    else:
        form = ProjectForm()
    
    return render(request, 'core/project_form.html', {'form': form, 'title': _('Create Project')})

@login_required
@permission_required('core.change_project', raise_exception=True)
def project_update(request, project_id):
    """
    View for updating an existing project
    """
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, _('Project updated successfully!'))
            return redirect('project_detail', project_id=project.id)
    else:
        form = ProjectForm(instance=project)
    
    return render(request, 'core/project_form.html', {
        'form': form, 
        'project': project,
        'title': _('Update Project')
    })

@login_required
@permission_required('core.delete_project', raise_exception=True)
def project_delete(request, project_id):
    """
    View for deleting a project
    """
    project = get_object_or_404(Project, id=project_id)
    cases_count = project.get_cases_count()

    if request.method == 'POST':
        # GARDE-FOU : supprimer un projet emportait ses cas en cascade. Il faut
        # desormais recopier le nom du projet -- un clic distrait ne suffit plus
        # a retirer 256 cas -- et rien n'est efface, seulement marque.
        typed = (request.POST.get('confirm_name') or '').strip()
        if typed != project.name:
            messages.error(
                request,
                _('The name you typed does not match. Nothing was deleted.')
            )
            return render(request, 'core/project_confirm_delete.html', {
                'project': project, 'cases_count': cases_count,
            })

        project.soft_delete()
        messages.success(
            request,
            _('Project "{}" and its {} case(s) were removed. Nothing is lost: an '
              'administrator can restore them.').format(project.name, cases_count)
        )
        return redirect('home')
    
    return render(request, 'core/project_confirm_delete.html', {
        'project': project, 'cases_count': cases_count,
    })

# Opérations CRUD pour les Cases, uniquement pour les utilisateurs 'editor'
@login_required
@permission_required('core.add_case', raise_exception=True)
def case_create(request, project_id):
    """
    View for creating a new case within a project
    """
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        form = CaseForm(request.POST)
        if form.is_valid():
            case = form.save(commit=False)
            case.project = project
            case.created_by = request.user
            case.save()
            case.ensure_specimens(
                form.cleaned_data.get('specimen_types'),
                preservation=form.cleaned_data.get('preservation'),
            )
            messages.success(
                request,
                _('Case {acc} created with {n} specimen(s).').format(
                    acc=case.name, n=case.specimens.count()),
            )
            return redirect('case_detail', case_id=case.id)
    else:
        form = CaseForm()
    
    return render(request, 'core/case_form.html', {
        'form': form, 
        'project': project,
        'title': _('Create Case')
    })

@login_required
@permission_required('core.add_case', raise_exception=True)
def batch_case_create(request, project_id):
    """Cree un lot de cas a partir d'une liste de Biobank ID collee."""
    project = get_object_or_404(Project, id=project_id)

    if request.method == 'POST':
        form = BatchCaseForm(request.POST)
        if form.is_valid():
            identifiants = form.cleaned_data['biobank_ids']

            # Les ACC sont reserves en une seule fois : un seul aller-retour avec
            # le compteur, et des numeros consecutifs pour tout le lot.
            numeros = IdentifierSequence.allocate(len(identifiants))

            with transaction.atomic():
                cases = []
                for numero, biobank_id in zip(numeros, identifiants):
                    case = Case(
                        project=project,
                        acc_number=numero,
                        biobank_id=biobank_id,
                        created_by=request.user,
                        is_priority=form.cleaned_data['is_priority'],
                        status=form.cleaned_data['status'],
                        rna_coverage=form.cleaned_data['rna_coverage'],
                        dna_t_coverage=form.cleaned_data['dna_t_coverage'],
                        dna_n_coverage=form.cleaned_data['dna_n_coverage'],
                    )
                    case.save()
                    case.ensure_specimens(
                        form.cleaned_data['specimen_types'],
                        status=form.cleaned_data['status'],
                        preservation=form.cleaned_data['preservation'],
                    )
                    cases.append(case)

            messages.success(
                request,
                _('Created {count} cases: {first} to {last}.').format(
                    count=len(cases), first=cases[0].name, last=cases[-1].name,
                )
            )
            return redirect('project_detail', project_id=project.id)
    else:
        form = BatchCaseForm()

    return render(request, 'core/batch_case_form.html', {
        'form': form,
        'project': project,
    })

@login_required
@permission_required('core.delete_case', raise_exception=True)
def case_delete(request, case_id):
    """
    View for deleting a case
    """
    case = get_object_or_404(Case, id=case_id)
    project_id = case.project.id
    
    if request.method == 'POST':
        # Marque, ne supprime pas : les commentaires du cas restent attaches.
        case.soft_delete()
        messages.success(
            request,
            _('Case "{}" was removed. Nothing is lost: an administrator can '
              'restore it.').format(case.name)
        )
        return redirect('project_detail', project_id=project_id)
    
    return render(request, 'core/case_confirm_delete.html', {'case': case})

# Opérations CRUD pour les Project Leads, uniquement pour les utilisateurs 'editor'
@login_required
@permission_required('core.view_projectlead', raise_exception=True)
def project_lead_list(request):
    """
    View for listing all project leads
    """
    leads = ProjectLead.objects.all().order_by('name')
    project_counts = {}
    
    # Get project counts for each lead
    for lead in leads:
        project_counts[lead.id] = lead.projects.count()
    
    # Convert to JSON-serializable dictionary with string keys
    project_counts_json = {str(k): v for k, v in project_counts.items()}
    
    return render(request, 'core/project_lead_list.html', {
        'leads': leads,
        'project_counts': project_counts,
        'project_counts_json': project_counts_json,
    })

@login_required
@permission_required('core.add_projectlead', raise_exception=True)
def project_lead_create(request):
    """
    View for creating a new project lead
    """
    if request.method == 'POST':
        form = ProjectLeadForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Project Lead created successfully!'))
            return redirect('project_lead_list')
    else:
        form = ProjectLeadForm()
    
    return render(request, 'core/project_lead_form.html', {
        'form': form,
        'title': _('Create Project Lead')
    })

@login_required
@permission_required('core.change_projectlead', raise_exception=True)
def project_lead_update(request, lead_id):
    """
    View for updating an existing project lead
    """
    lead = get_object_or_404(ProjectLead, id=lead_id)
    
    if request.method == 'POST':
        form = ProjectLeadForm(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            messages.success(request, _('Project Lead updated successfully!'))
            return redirect('project_lead_list')
    else:
        form = ProjectLeadForm(instance=lead)
    
    return render(request, 'core/project_lead_form.html', {
        'form': form,
        'lead': lead,
        'title': _('Update Project Lead')
    })

@login_required
@permission_required('core.delete_projectlead', raise_exception=True)
def project_lead_delete(request, lead_id):
    """
    View for deleting a project lead
    """
    lead = get_object_or_404(ProjectLead, id=lead_id)
    
    # Check if there are projects using this lead
    if lead.projects.exists():
        messages.error(request, _('Cannot delete Project Lead that is being used by existing projects.'))
        return redirect('project_lead_list')
    
    if request.method == 'POST':
        lead.delete()
        messages.success(request, _('Project Lead deleted successfully!'))
        return redirect('project_lead_list')
    
    return render(request, 'core/project_lead_confirm_delete.html', {'lead': lead})

@login_required
@permission_required('core.add_case', raise_exception=True)
def csv_case_import(request, project_id):
    """
    View for importing cases from a CSV file
    """
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            # Get the uploaded file
            csv_file = request.FILES['csv_file']
            
            # Check if it's a CSV file
            if not csv_file.name.endswith('.csv'):
                messages.error(request, _('Please upload a CSV file.'))
                return redirect('csv_case_import', project_id=project.id)
            
            # Process the file
            try:
                # Read the CSV file
                csv_data = TextIOWrapper(csv_file.file, encoding='utf-8')
                reader = csv.DictReader(csv_data)
                
                # Validate CSV headers
                # Biobank_ID est le nouveau nom de la colonne. Other_ID reste
                # accepte : les equipes ont des fichiers existants a ce format,
                # et rien ne justifie de les invalider.
                required_headers = ['CaseID', 'Status', 'DNAT', 'DNAN', 'RNA']
                biobank_header = next(
                    (h for h in ('Biobank_ID', 'Other_ID') if h in (reader.fieldnames or [])),
                    None,
                )
                optional_headers = ['source_other_comments']
                csv_headers = reader.fieldnames
                
                if not all(header in csv_headers for header in required_headers) or biobank_header is None:
                    messages.error(
                        request, 
                        _('CSV file is missing required headers. Please use the template.')
                    )
                    return redirect('csv_case_import', project_id=project.id)
                
                # Track counts
                created_count = 0
                updated_count = 0
                preserved_count = 0  # valeurs existantes protegees d'un ecrasement par une cellule vide
                error_rows = []
                
                # Les statuts acceptes couvrent le vocabulaire v1 comme le v2 :
                # les equipes ont des fichiers existants, rien ne justifie de les
                # invalider. Voir statuses.from_any.

                # Process each row
                for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header row
                    case_id = row['CaseID'].strip()
                    
                    # Skip empty rows
                    if not case_id:
                        continue
                    
                    # Biobank ID (facultatif)
                    biobank_id = (row.get(biobank_header) or '').strip() or None
                    
                    # Get source_other_comments (optional field)
                    source_comment = row.get('source_other_comments', '').strip() if 'source_other_comments' in row else None
                    
                    # Statut : accepte un slug v2, un slug v1 ou un libelle v1.
                    status = statuses.from_any(row.get('Status'))
                    if status is None:
                        error_rows.append(
                            f"Row {row_num}: Invalid status '{row.get('Status')}'")
                        continue
                    
                    # Parse coverage values
                    try:
                        dna_t = float(row['DNAT']) if row['DNAT'].strip() else None
                        dna_n = float(row['DNAN']) if row['DNAN'].strip() else None
                        rna = float(row['RNA']) if row['RNA'].strip() else None
                    except ValueError:
                        error_rows.append(f"Row {row_num}: Invalid numeric values")
                        continue
                    
                    # Les couvertures et le statut appartiennent desormais aux
                    # specimens ; les colonnes de Case n'en sont qu'un miroir,
                    # recalcule a chaque ecriture. Ecrire sur le cas serait sans
                    # effet, l'import doit donc viser les specimens.
                    case = Case.objects.filter(project=project, name=case_id).first()
                    created = case is None

                    if created:
                        case = Case(project=project, name=case_id,
                                    biobank_id=biobank_id,
                                    created_by=request.user)
                        match = re.fullmatch(r'ACC-(\d+)', case_id or '')
                        if match:
                            case.acc_number = int(match.group(1))
                        case.save()
                        case.ensure_specimens(status=status)
                        created_count += 1
                    else:
                        if biobank_id is not None:
                            case.biobank_id = biobank_id
                            case.save(update_fields=['biobank_id', 'updated_at'])
                        elif case.biobank_id is not None:
                            preserved_count += 1
                        # Un cas d'avant la v2 peut ne pas encore avoir de
                        # specimens : on les cree plutot que d'ignorer la ligne.
                        case.ensure_specimens()
                        updated_count += 1

                    couvertures = {
                        Specimen.TYPE_TUMOUR_DNA: dna_t,
                        Specimen.TYPE_NORMAL_DNA: dna_n,
                        Specimen.TYPE_TUMOUR_RNA: rna,
                    }
                    for specimen in case.specimens.all():
                        champs = []
                        valeur = couvertures.get(specimen.specimen_type)
                        if valeur is not None:
                            specimen.coverage = valeur
                            champs.append('coverage')
                        elif not created and specimen.coverage is not None:
                            # GARDE-FOU : cellule vide = inchange, jamais efface.
                            preserved_count += 1
                        if specimen.status != status:
                            specimen.status = status
                            champs.append('status')
                        if champs:
                            specimen.save(update_fields=champs + ['updated_at'])

                    case.sync_from_specimens()

                    # Add comment if source_other_comments is provided
                    if source_comment:
                        # Store only the comment text, timestamp and user info are handled by the model
                        Comment.objects.create(
                            case=case,
                            text=source_comment,
                            user=request.user
                        )
                
                # Show success message with counts
                if error_rows:
                    messages.warning(
                        request, 
                        _('Import completed with some errors: {}').format(', '.join(error_rows))
                    )
                
                if preserved_count:
                    messages.info(
                        request,
                        _('{} existing values were kept because their cell was empty in the '
                          'CSV. An empty cell means "unchanged" — to clear a value, edit the '
                          'case directly.').format(preserved_count)
                    )

                messages.success(
                    request,
                    _('CSV import complete! Created: {}, Updated: {}').format(created_count, updated_count)
                )
                return redirect('project_detail', project_id=project.id)
                
            except Exception as e:
                messages.error(request, _('Error processing CSV file: {}').format(str(e)))
                return redirect('csv_case_import', project_id=project.id)
    else:
        form = CSVImportForm()
    
    return render(request, 'core/csv_case_import.html', {
        'form': form,
        'project': project,
    })

@login_required
def csv_case_export(request, project_id):
    """Export d'un projet : un seul fichier, une ligne par cas.

    Le format LARGE est deliberé : c'est celui qu'un PI croise avec sa feuille
    clinique par RECHERCHEV sur le Biobank ID. Un fichier long, une ligne par
    specimen, triplerait son effectif sans qu'il s'en apercoive.
    """
    project = get_object_or_404(Project, id=project_id)

    response = HttpResponse(content_type='text/csv')
    horodatage = datetime.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = (
        f'attachment; filename="cases_{project.name}_{horodatage}.csv"')
    exports.ecrire_cas(response, project=project)
    return response


@login_required
def project_export_bundle(request, project_id):
    """Export complet d'un projet : donnees et metadonnees, en archive ZIP."""
    project = get_object_or_404(Project, id=project_id)
    archive, comptes = exports.construire_archive(
        project=project, scope=f'Project: {project.name}')

    horodatage = datetime.now().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(archive.read(), content_type='application/zip')
    response['Content-Disposition'] = (
        f'attachment; filename="terryfox_{project.name}_{horodatage}.zip"')
    logger.info("Export projet %s par %s : %s",
                project.name, request.user.username, comptes)
    return response


@login_required
def consortium_export(request):
    """Export de tous les projets. Superutilisateurs seulement, et journalise.

    Le fichier reunit les donnees de tous les groupes du consortium : il ne
    circule pas comme un export de projet.
    """
    if not request.user.is_superuser:
        messages.error(
            request,
            _('A consortium-wide export covers every group. Only administrators '
              'can produce one; your own project exports are on the project page.'))
        return redirect('home')

    archive, comptes = exports.construire_archive(scope='All projects (consortium)')

    horodatage = datetime.now().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(archive.read(), content_type='application/zip')
    response['Content-Disposition'] = (
        f'attachment; filename="terryfox_consortium_{horodatage}.zip"')
    # Trace d'audit : qui a extrait l'ensemble du consortium, et quand.
    logger.warning("EXPORT CONSORTIUM par %s (%s) : %s",
                   request.user.username, request.META.get('REMOTE_ADDR', '?'), comptes)
    return response


def _generate_password(length=12):
    """Generate a random password."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

def _assign_user_role(user, role):
    """Assign role to user by adding to appropriate group."""
    # Clear existing groups
    user.groups.clear()
    
    if role == 'admin':
        user.is_superuser = True
        user.is_staff = True
        user.save()
    else:
        user.is_superuser = False
        user.is_staff = False
        user.save()
        
        # Add to appropriate group
        group, created = Group.objects.get_or_create(name=role)
        user.groups.add(group)

@login_required
def user_list(request):
    """
    List all users - Admin only
    """
    if not request.user.is_superuser:
        messages.error(request, _('You do not have permission to access user management.'))
        return redirect('home')
    
    users = User.objects.all().order_by('username')
    
    # Add role information to each user
    users_with_roles = []
    for user in users:
        if user.is_superuser:
            role = 'Admin'
            role_class = 'danger'
        elif user.groups.filter(name='editor').exists():
            role = 'Editor'
            role_class = 'success'
        elif user.groups.filter(name='viewer').exists():
            role = 'Viewer'
            role_class = 'primary'
        else:
            role = 'No Role'
            role_class = 'secondary'
        
        users_with_roles.append({
            'user': user,
            'role': role,
            'role_class': role_class
        })
    
    # Calculate statistics
    total_admins = User.objects.filter(is_superuser=True).count()
    total_editors = User.objects.filter(groups__name='editor').count()
    total_viewers = User.objects.filter(groups__name='viewer').count()
    
    return render(request, 'core/user_list.html', {
        'users_with_roles': users_with_roles,
        'total_admins': total_admins,
        'total_editors': total_editors,
        'total_viewers': total_viewers,
    })

@login_required
def user_create(request):
    """
    Create a single user - Admin only
    """
    if not request.user.is_superuser:
        messages.error(request, _('You do not have permission to create users.'))
        return redirect('home')
    
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            # Create user
            user = User(
                username=form.cleaned_data['username'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                email=''  # Email is optional
            )
            
            # Generate password
            password = _generate_password()
            user.set_password(password)
            user.save()
            
            # Assign role
            role = form.cleaned_data['role']
            _assign_user_role(user, role)
            
            # Store credentials for display
            credentials = f"{user.username}:{password}"
            
            messages.success(request, _(
                'User "{}" created successfully! Username: {} | Password: {} '
                '(Please save these credentials as they will not be shown again)'
            ).format(user.get_full_name(), user.username, password))
            
            return redirect('user_list')
    else:
        form = UserCreateForm()
    
    return render(request, 'core/user_create.html', {
        'form': form,
        'title': _('Create User'),
    })

@login_required
def batch_user_create(request):
    """
    Create multiple users at once - Admin only
    """
    if not request.user.is_superuser:
        messages.error(request, _('You do not have permission to create users.'))
        return redirect('home')
    
    if request.method == 'POST':
        form = BatchUserCreateForm(request.POST)
        if form.is_valid():
            users_data = form.cleaned_data['users_data']
            role = form.cleaned_data['role']
            
            created_users = []
            credentials = []
            
            for user_data in users_data:
                # Create user
                user = User(
                    username=user_data['username'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    email=''  # Email is optional
                )
                
                # Generate password
                password = _generate_password()
                user.set_password(password)
                user.save()
                
                # Assign role
                _assign_user_role(user, role)
                
                created_users.append(user)
                credentials.append(f"{user.username}:{password}")
            
            # Create downloadable credentials file
            response = HttpResponse(content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="user_credentials_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt"'
            
            response.write("# User Credentials - TerryFox LIMS\n")
            response.write(f"# Created on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            response.write(f"# Total users created: {len(created_users)}\n")
            response.write("# Format: username:password\n\n")
            
            for credential in credentials:
                response.write(credential + '\n')
            
            messages.success(request, _(
                '{} users created successfully! Credentials file will be downloaded automatically.'
            ).format(len(created_users)))
            
            return response
    else:
        form = BatchUserCreateForm()
    
    return render(request, 'core/batch_user_create.html', {
        'form': form,
        'title': _('Create Multiple Users'),
    })

@login_required
def user_delete(request, user_id):
    """
    Delete a user - Admin only
    """
    if not request.user.is_superuser:
        messages.error(request, _('You do not have permission to delete users.'))
        return redirect('home')
    
    user_to_delete = get_object_or_404(User, id=user_id)
    
    # Prevent self-deletion
    if user_to_delete == request.user:
        messages.error(request, _('You cannot delete your own account.'))
        return redirect('user_list')
    
    if request.method == 'POST':
        username = user_to_delete.username
        user_to_delete.delete()
        messages.success(request, _('User "{}" has been deleted successfully.').format(username))
        return redirect('user_list')
    
    return render(request, 'core/user_delete.html', {
        'user_to_delete': user_to_delete,
    })

@login_required
def user_update(request, user_id):
    """
    Update a user - Admin only
    """
    if not request.user.is_superuser:
        messages.error(request, _('You do not have permission to update users.'))
        return redirect('home')
    
    user_to_update = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=user_to_update)
        if form.is_valid():
            # Update basic user information
            user = form.save(commit=False)
            
            # Update username if names changed
            if 'username' in form.cleaned_data:
                user.username = form.cleaned_data['username']
            
            user.save()
            
            # Update role
            role = form.cleaned_data['role']
            _assign_user_role(user, role)
            
            # Reset password if requested
            new_password = None
            if form.cleaned_data.get('reset_password'):
                new_password = _generate_password()
                user.set_password(new_password)
                user.save()
            
            # Success message
            if new_password:
                messages.success(request, _(
                    'User "{}" updated successfully! New password: {} '
                    '(Please save this password as it will not be shown again)'
                ).format(user.get_full_name() or user.username, new_password))
            else:
                messages.success(request, _(
                    'User "{}" updated successfully!'
                ).format(user.get_full_name() or user.username))
            
            return redirect('user_list')
    else:
        form = UserUpdateForm(instance=user_to_update)
    
    # Get current role information from database
    if user_to_update.is_superuser:
        current_role = 'Admin'
        current_role_class = 'danger'
    elif user_to_update.groups.filter(name='editor').exists():
        current_role = 'Editor'
        current_role_class = 'success'
    elif user_to_update.groups.filter(name='viewer').exists():
        current_role = 'Viewer'
        current_role_class = 'primary'
    else:
        current_role = 'No Role'
        current_role_class = 'secondary'
    
    return render(request, 'core/user_update.html', {
        'form': form,
        'user_to_update': user_to_update,
        'current_role': current_role,
        'current_role_class': current_role_class,
        'title': _('Update User'),
    })
