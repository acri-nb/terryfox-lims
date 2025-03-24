from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from .models import Project, Case, Comment, Accession, ProjectLead

class ProjectLeadForm(forms.ModelForm):
    """Form for creating and updating project leads."""
    
    class Meta:
        model = ProjectLead
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Project Lead Name')}),
        }

class ProjectForm(forms.ModelForm):
    """Form for creating and updating projects."""
    
    class Meta:
        model = Project
        fields = ['name', 'description', 'project_lead']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'project_lead': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Create blank option for project_lead
        self.fields['project_lead'].empty_label = _('-- Select a Project Lead --')

class CaseForm(forms.ModelForm):
    """Form for creating and updating cases."""
    
    class Meta:
        model = Case
        fields = ['name', 'status', 'rna_coverage', 'dna_t_coverage', 'dna_n_coverage', 'tier']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'rna_coverage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'RNA Coverage in M'}),
            'dna_t_coverage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'DNA (T) Coverage in X'}),
            'dna_n_coverage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'DNA (N) Coverage in X'}),
            'tier': forms.Select(attrs={'class': 'form-select', 'disabled': 'disabled'}),
        }
        help_texts = {
            'rna_coverage': _('RNA Coverage in million reads (M)'),
            'dna_t_coverage': _('DNA Tumor Coverage in X'),
            'dna_n_coverage': _('DNA Normal Coverage in X'),
            'tier': _('Tier will be calculated automatically based on coverage values'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make tier field read-only - it will be calculated automatically
        self.fields['tier'].disabled = True

class CommentForm(forms.ModelForm):
    """Form for adding comments to a case."""
    
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Add a comment...')}),
        }
        labels = {
            'text': '',
        }

class AccessionForm(forms.ModelForm):
    """Form for accession numbers."""
    
    class Meta:
        model = Accession
        fields = ['accession_number']
        widgets = {
            'accession_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Accession number')}),
        }
        labels = {
            'accession_number': '',
        }

# Create a formset for handling multiple accessions for a case
AccessionFormSet = inlineformset_factory(
    Case,
    Accession,
    form=AccessionForm,
    extra=1,
    can_delete=True
) 