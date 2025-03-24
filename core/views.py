from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Count

from .models import Project, Case, Accession, Comment, ProjectLead
from .forms import ProjectForm, CaseForm, CommentForm, AccessionFormSet, ProjectLeadForm

@login_required
def home(request):
    """
    Home page view showing all projects
    """
    projects = Project.objects.all().annotate(cases_count=Count('cases'))
    
    # Statistics for all projects
    total_projects = projects.count()
    total_cases = Case.objects.count()
    
    # Projects by project lead
    projects_by_lead = Project.objects.values('project_lead__name').annotate(count=Count('id')).order_by('-count')
    
    # Cases by status and tier
    cases_by_status = Case.objects.values('status').annotate(count=Count('id')).order_by('-count')
    cases_by_tier = Case.objects.values('tier').annotate(count=Count('id')).order_by('-count')
    
    return render(request, 'core/home.html', {
        'projects': projects,
        'total_projects': total_projects,
        'total_cases': total_cases,
        'projects_by_lead': projects_by_lead,
        'cases_by_status': cases_by_status,
        'cases_by_tier': cases_by_tier,
    })

@login_required
def project_detail(request, project_id):
    """
    View for showing project details including all cases
    """
    project = get_object_or_404(Project, id=project_id)
    cases = project.cases.all()
    
    # Project statistics
    total_cases = cases.count()
    cases_by_status = cases.values('status').annotate(count=Count('id'))
    cases_by_tier = cases.values('tier').annotate(count=Count('id'))
    
    # Check if user is part of Bioinformatician group for edit permissions (previously PI)
    can_edit = request.user.groups.filter(name='Bioinformatician').exists() or request.user.is_superuser
    
    return render(request, 'core/project_detail.html', {
        'project': project,
        'cases': cases,
        'total_cases': total_cases,
        'cases_by_status': cases_by_status,
        'cases_by_tier': cases_by_tier,
        'can_edit': can_edit
    })

@login_required
def case_detail(request, case_id):
    """
    View for showing case details
    """
    case = get_object_or_404(Case, id=case_id)
    comments = case.comments.all().order_by('-created_at')
    accessions = case.accessions.all()
    
    # Check if user is part of Bioinformatician group for edit permissions (previously PI)
    can_edit = request.user.groups.filter(name='Bioinformatician').exists() or request.user.is_superuser
    
    # Initialize forms
    comment_form = None
    case_form = None
    accession_formset = None
    
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
            
            elif 'accession_update' in request.POST:
                accession_formset = AccessionFormSet(request.POST, instance=case)
                if accession_formset.is_valid():
                    accession_formset.save()
                    messages.success(request, _('Accession numbers updated successfully!'))
                    return redirect('case_detail', case_id=case.id)
        
        # Initialize forms if not POST
        if comment_form is None:
            comment_form = CommentForm()
        if case_form is None:
            case_form = CaseForm(instance=case)
        if accession_formset is None:
            accession_formset = AccessionFormSet(instance=case)
    
    return render(request, 'core/case_detail.html', {
        'case': case,
        'project': case.project,
        'comments': comments,
        'accessions': accessions,
        'can_edit': can_edit,
        'comment_form': comment_form,
        'case_form': case_form,
        'accession_formset': accession_formset,
    })

# CRUD operations for Projects, only for Bioinformatician users (previously PI)
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
    
    if request.method == 'POST':
        project.delete()
        messages.success(request, _('Project deleted successfully!'))
        return redirect('home')
    
    return render(request, 'core/project_confirm_delete.html', {'project': project})

# CRUD operations for Cases, only for Bioinformatician users (previously PI)
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
            case.save()
            messages.success(request, _('Case created successfully!'))
            return redirect('case_detail', case_id=case.id)
    else:
        form = CaseForm()
    
    return render(request, 'core/case_form.html', {
        'form': form, 
        'project': project,
        'title': _('Create Case')
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
        case.delete()
        messages.success(request, _('Case deleted successfully!'))
        return redirect('project_detail', project_id=project_id)
    
    return render(request, 'core/case_confirm_delete.html', {'case': case})

# CRUD operations for Project Leads, only for Bioinformatician users
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
