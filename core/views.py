from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Count
import csv
from io import TextIOWrapper

from .models import Project, Case, Accession, Comment, ProjectLead
from .forms import ProjectForm, CaseForm, CommentForm, AccessionFormSet, ProjectLeadForm, ProjectFilterForm, CaseFilterForm, BatchCaseForm, CSVImportForm

@login_required
def home(request):
    """
    Home page view showing all projects
    """
    # Initialize filter form
    filter_form = ProjectFilterForm(request.GET)
    
    # Start with all projects
    projects = Project.objects.all()
    
    # Apply filters if the form is valid
    if filter_form.is_valid():
        project_name = filter_form.cleaned_data.get('name')
        project_lead = filter_form.cleaned_data.get('project_lead')
        
        if project_name:
            projects = projects.filter(name__icontains=project_name)
            
        if project_lead:
            projects = projects.filter(project_lead=project_lead)
    
    # Annotate with case count
    projects = projects.annotate(cases_count=Count('cases'))
    
    # Statistics for all projects
    total_projects = Project.objects.count()
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
        'filter_form': filter_form,
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
            cases = cases.filter(name__icontains=case_name)
        
        if case_status:
            cases = cases.filter(status=case_status)
            
        if case_tier:
            cases = cases.filter(tier=case_tier)
    
    # Project statistics - always based on all cases
    all_cases = project.cases.all()
    total_cases = all_cases.count()
    cases_by_status = all_cases.values('status').annotate(count=Count('id'))
    cases_by_tier = all_cases.values('tier').annotate(count=Count('id'))
    
    # Check if user is part of Bioinformatician group for edit permissions (previously PI)
    can_edit = request.user.groups.filter(name='Bioinformatician').exists() or request.user.is_superuser
    
    return render(request, 'core/project_detail.html', {
        'project': project,
        'cases': cases,
        'total_cases': total_cases,
        'cases_by_status': cases_by_status,
        'cases_by_tier': cases_by_tier,
        'can_edit': can_edit,
        'filter_form': filter_form,
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
@permission_required('core.add_case', raise_exception=True)
def batch_case_create(request, project_id):
    """
    View for creating multiple cases in a batch within a project
    """
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        form = BatchCaseForm(request.POST)
        if form.is_valid():
            batch_size = form.cleaned_data['batch_size']
            batch_name = form.cleaned_data['batch_name']
            status = form.cleaned_data['status']
            rna_coverage = form.cleaned_data['rna_coverage']
            dna_t_coverage = form.cleaned_data['dna_t_coverage']
            dna_n_coverage = form.cleaned_data['dna_n_coverage']
            
            cases_created = 0
            
            # Create the specified number of cases
            for i in range(1, batch_size + 1):
                case_name = f"{batch_name}-{i}"
                
                # Check if a case with this name already exists in the project
                if Case.objects.filter(project=project, name=case_name).exists():
                    continue
                
                case = Case(
                    project=project,
                    name=case_name,
                    status=status,
                    rna_coverage=rna_coverage,
                    dna_t_coverage=dna_t_coverage,
                    dna_n_coverage=dna_n_coverage
                )
                case.save()
                cases_created += 1
            
            if cases_created > 0:
                messages.success(
                    request, 
                    _('Successfully created {count} cases in batch "{batch}"!').format(
                        count=cases_created, 
                        batch=batch_name
                    )
                )
            else:
                messages.warning(
                    request, 
                    _('No new cases were created. Cases with these names may already exist.')
                )
                
            return redirect('project_detail', project_id=project.id)
    else:
        form = BatchCaseForm()
    
    return render(request, 'core/batch_case_form.html', {
        'form': form, 
        'project': project,
        'title': _('Create Cases in Batch')
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
                required_headers = ['CaseID', 'Status', 'DNAT', 'DNAN', 'RNA']
                csv_headers = reader.fieldnames
                
                if not all(header in csv_headers for header in required_headers):
                    messages.error(
                        request, 
                        _('CSV file is missing required headers. Please use the template.')
                    )
                    return redirect('csv_case_import', project_id=project.id)
                
                # Track counts
                created_count = 0
                updated_count = 0
                error_rows = []
                
                # Map CSV status to model status
                status_mapping = {}
                for status_value, status_display in Case.STATUS_CHOICES:
                    status_mapping[status_display] = status_value
                
                # Process each row
                for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header row
                    case_id = row['CaseID'].strip()
                    
                    # Skip empty rows
                    if not case_id:
                        continue
                    
                    # Map CSV status to model status
                    status = row['Status'].strip()
                    if status not in status_mapping:
                        error_rows.append(f"Row {row_num}: Invalid status '{status}'")
                        continue
                    
                    # Parse coverage values
                    try:
                        dna_t = float(row['DNAT']) if row['DNAT'].strip() else None
                        dna_n = float(row['DNAN']) if row['DNAN'].strip() else None
                        rna = float(row['RNA']) if row['RNA'].strip() else None
                    except ValueError:
                        error_rows.append(f"Row {row_num}: Invalid numeric values")
                        continue
                    
                    # Check if case exists
                    case, created = Case.objects.get_or_create(
                        project=project,
                        name=case_id,
                        defaults={
                            'status': status_mapping[status],
                            'dna_t_coverage': dna_t,
                            'dna_n_coverage': dna_n,
                            'rna_coverage': rna
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        # Update existing case
                        case.status = status_mapping[status]
                        case.dna_t_coverage = dna_t
                        case.dna_n_coverage = dna_n
                        case.rna_coverage = rna
                        case.save()
                        updated_count += 1
                
                # Show success message with counts
                if error_rows:
                    messages.warning(
                        request, 
                        _('Import completed with some errors: {}').format(', '.join(error_rows))
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
