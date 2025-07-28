from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Count
from django.contrib.auth.models import User, Group
import csv
from io import TextIOWrapper
from datetime import datetime
import string
import random

from .models import Project, Case, Accession, Comment, ProjectLead
from .forms import ProjectForm, CaseForm, CommentForm, AccessionFormSet, ProjectLeadForm, ProjectFilterForm, CaseFilterForm, BatchCaseForm, CSVImportForm, UserCreateForm, BatchUserCreateForm, UserUpdateForm

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
    
    # Check if user is part of the 'editor' group for editing permissions
    can_edit = request.user.groups.filter(name='editor').exists() or request.user.is_superuser
    
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
    
    # Check if user is part of the 'editor' group for editing permissions
    can_edit = request.user.groups.filter(name='editor').exists() or request.user.is_superuser
    
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

# Opérations CRUD pour les Projets, uniquement pour les utilisateurs 'editor'
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
            min_case_number = form.cleaned_data['min_case_number']
            max_case_number = form.cleaned_data['max_case_number']
            batch_name = form.cleaned_data['batch_name']
            status = form.cleaned_data['status']
            rna_coverage = form.cleaned_data['rna_coverage']
            dna_t_coverage = form.cleaned_data['dna_t_coverage']
            dna_n_coverage = form.cleaned_data['dna_n_coverage']
            
            cases_created = 0
            
            # Create cases with numbers from min to max (inclusive)
            for i in range(min_case_number, max_case_number + 1):
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
                    _('Successfully created {count} cases in batch "{batch}" (from {min} to {max})!').format(
                        count=cases_created, 
                        batch=batch_name,
                        min=min_case_number,
                        max=max_case_number
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
                required_headers = ['CaseID', 'Other_ID', 'Status', 'DNAT', 'DNAN', 'RNA']
                optional_headers = ['source_other_comments']
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
                    
                    # Get Other_ID (optional field)
                    other_id = row['Other_ID'].strip() if row['Other_ID'].strip() else None
                    
                    # Get source_other_comments (optional field)
                    source_comment = row.get('source_other_comments', '').strip() if 'source_other_comments' in row else None
                    
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
                            'other_id': other_id,
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
                        case.other_id = other_id
                        case.status = status_mapping[status]
                        case.dna_t_coverage = dna_t
                        case.dna_n_coverage = dna_n
                        case.rna_coverage = rna
                        case.save()
                        updated_count += 1
                    
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
    """
    Export all cases of a project to CSV
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="cases_{project.name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['CaseID', 'Other_ID', 'Status', 'DNAT', 'DNAN', 'RNA', 'Tier'])
    
    for case in project.cases.all():
        writer.writerow([
            case.name,
            case.other_id or '',
            case.status,
            case.dna_t_coverage or '',
            case.dna_n_coverage or '',
            case.rna_coverage or '',
            case.tier
        ])
    
    return response

# User Management Views (Admin Only)

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
    
    return render(request, 'core/user_list.html', {
        'users_with_roles': users_with_roles,
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
    
    return render(request, 'core/user_update.html', {
        'form': form,
        'user_to_update': user_to_update,
        'title': _('Update User'),
    })
