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
        fields = ['name', 'other_id', 'status', 'rna_coverage', 'dna_t_coverage', 'dna_n_coverage', 'tier']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'other_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Other ID (optional)'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'rna_coverage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'RNA Coverage in M'}),
            'dna_t_coverage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'DNA (T) Coverage in X'}),
            'dna_n_coverage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'DNA (N) Coverage in X'}),
            'tier': forms.Select(attrs={'class': 'form-select', 'disabled': 'disabled'}),
        }
        help_texts = {
            'other_id': _('Optional alternative identifier for this case'),
            'rna_coverage': _('RNA Coverage in million reads (M)'),
            'dna_t_coverage': _('DNA Tumor Coverage in X'),
            'dna_n_coverage': _('DNA Normal Coverage in X'),
            'tier': _('Tier will be calculated automatically based on coverage values'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make tier field read-only - it will be calculated automatically
        self.fields['tier'].disabled = True

class BatchCaseForm(forms.Form):
    """Form for creating multiple cases in a batch."""
    min_case_number = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label=_('Number of the first case'),
        help_text=_('First case number in the sequence')
    )
    max_case_number = forms.IntegerField(
        min_value=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label=_('Number of the last case'),
        help_text=_('Last case number in the sequence')
    )
    batch_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label=_('Batch Name'),
        help_text=_('Will be used as prefix for case names (e.g., "Lung" with range 5-7 will create cases named "Lung-5", "Lung-6", "Lung-7")')
    )
    status = forms.ChoiceField(
        choices=Case.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('Default Status'),
        initial=Case.STATUS_RECEIVED
    )
    rna_coverage = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'RNA Coverage in M'}),
        label=_('Default RNA Coverage (M)'),
        help_text=_('RNA Coverage in million reads (M)')
    )
    dna_t_coverage = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'DNA (T) Coverage in X'}),
        label=_('Default DNA (T) Coverage (X)'),
        help_text=_('DNA Tumor Coverage in X')
    )
    dna_n_coverage = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'DNA (N) Coverage in X'}),
        label=_('Default DNA (N) Coverage (X)'),
        help_text=_('DNA Normal Coverage in X')
    )

    def clean(self):
        cleaned_data = super().clean()
        min_case_number = cleaned_data.get('min_case_number')
        max_case_number = cleaned_data.get('max_case_number')
        
        if min_case_number is not None and max_case_number is not None:
            if max_case_number < min_case_number:
                raise forms.ValidationError(_("The last case number must be greater than or equal to the first case number."))
            
            # Check that at least 2 cases will be created
            if (max_case_number - min_case_number + 1) < 2:
                raise forms.ValidationError(_("You must create at least 2 cases in a batch."))
        
        return cleaned_data

class CSVImportForm(forms.Form):
    """Form for importing cases from a CSV file."""
    csv_file = forms.FileField(
        label=_('CSV File'),
        help_text=_('Upload a CSV file with case data.'),
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'})
    )

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

class ProjectFilterForm(forms.Form):
    """Form for filtering projects on the home page."""
    name = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by project name...')
        })
    )
    project_lead = forms.ModelChoiceField(
        queryset=ProjectLead.objects.all(),
        required=False,
        empty_label=_("All Project Leads"),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order project leads by name
        self.fields['project_lead'].queryset = ProjectLead.objects.all().order_by('name')

class CaseFilterForm(forms.Form):
    """Form for filtering cases on the project detail page."""
    name = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by name...')
        })
    )
    status = forms.ChoiceField(
        choices=[('', _('All Statuses'))] + Case.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    tier = forms.ChoiceField(
        choices=[('', _('All Tiers'))] + Case.TIER_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    ) 