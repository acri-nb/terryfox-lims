from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User, Group
import string
import random

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
        # 'name' (l'ACC) n'est plus saisissable : le LIMS l'attribue.
        fields = ['biobank_id', 'status', 'rna_coverage', 'dna_t_coverage', 'dna_n_coverage', 'tier']
        widgets = {
            'biobank_id': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. N-BBN 440',
                'autocomplete': 'off', 'autocapitalize': 'off', 'spellcheck': 'false',
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'rna_coverage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'RNA Coverage in M'}),
            'dna_t_coverage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'DNA (T) Coverage in X'}),
            'dna_n_coverage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'DNA (N) Coverage in X'}),
            'tier': forms.Select(attrs={'class': 'form-select', 'disabled': 'disabled'}),
        }
        help_texts = {
            'biobank_id': _('The identifier the biobank uses. This is what people search by.'),
            'rna_coverage': _('RNA Coverage in million reads (M)'),
            'dna_t_coverage': _('DNA Tumor Coverage in X'),
            'dna_n_coverage': _('DNA Normal Coverage in X'),
            'tier': _('Tier will be calculated automatically based on coverage values'),
        }
    
    # Case a cocher posee par le bouton "Create anyway" du modele : elle permet
    # de passer outre le controle souple de doublon de Biobank ID.
    confirm_duplicate = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le tier est derive des couvertures, jamais saisi.
        self.fields['tier'].disabled = True

    def clean_biobank_id(self):
        """Controle souple : nomme le cas en conflit plutot que de bloquer.

        Sans ce controle, une contrainte de base de donnees afficherait a la
        technicienne un message du type
        'Constraint "uniq_biobank_id" is violated' -- inexploitable. Et une
        contrainte dure la bloquerait un jour sur le vrai identifiant d'un
        patient, deux projets partageant un meme espace de numerotation nu.
        """
        value = (self.cleaned_data.get('biobank_id') or '').strip()
        if not value:
            return None

        if self.data.get('confirm_duplicate'):
            return value

        probe = Case(biobank_id=value)
        if self.instance and self.instance.pk:
            probe.pk = self.instance.pk
        conflict = probe.find_biobank_id_conflict()
        if conflict:
            self.biobank_id_conflict = conflict
            raise forms.ValidationError(
                _('Biobank ID "%(value)s" is already used by %(acc)s in %(project)s.'),
                code='duplicate',
                params={
                    'value': value,
                    'acc': conflict.name,
                    'project': conflict.project.name,
                },
            )
        return value

class BatchCaseForm(forms.Form):
    """Creation en lot : on colle une liste de Biobank ID, un par ligne.

    L'ancien formulaire fabriquait des noms a partir d'un prefixe et d'un
    intervalle numerique ("Lung-5", "Lung-6"...). Ce n'est plus possible :
    l'ACC est desormais attribue par le LIMS. Mais le remplacer par un simple
    champ "nombre de cas" donnerait N cas anonymes, que la technicienne devrait
    ensuite ouvrir un par un pour saisir l'identifiant -- 50 pages pour ce qui
    devrait etre un collage. D'ou la zone de texte.

    Le meme motif existe deja dans ce code : BatchUserCreateForm.
    """

    biobank_ids = forms.CharField(
        label=_('Biobank IDs'),
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace',
            'rows': 12,
            'placeholder': 'N-BBN 501\nN-BBN 502\nN-BBN 503',
            'autocomplete': 'off', 'spellcheck': 'false',
        }),
        help_text=_('One per line. The LIMS assigns the ACC identifiers.'),
    )

    status = forms.ChoiceField(
        label=_('Status for every case'),
        choices=Case.STATUS_CHOICES,
        initial=Case.STATUS_CREATED,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    rna_coverage = forms.FloatField(
        required=False, label=_('RNA Coverage (M)'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text=_('Optional. Applied to every case in the batch.'),
    )
    dna_t_coverage = forms.FloatField(
        required=False, label=_('DNA (T) Coverage (X)'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text=_('Optional. Applied to every case in the batch.'),
    )
    dna_n_coverage = forms.FloatField(
        required=False, label=_('DNA (N) Coverage (X)'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text=_('Optional. Applied to every case in the batch.'),
    )

    # Posee par le bouton "Create anyway" quand des doublons sont signales.
    confirm_duplicates = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def clean_biobank_ids(self):
        """Renvoie la liste nettoyee, et refuse les doublons internes au collage."""
        lignes = [l.strip() for l in (self.cleaned_data['biobank_ids'] or '').splitlines()]
        lignes = [l for l in lignes if l]

        if not lignes:
            raise forms.ValidationError(_('Paste at least one Biobank ID.'))

        vus, doublons = set(), []
        for ligne in lignes:
            cle = ligne.casefold()
            if cle in vus:
                doublons.append(ligne)
            vus.add(cle)
        if doublons:
            raise forms.ValidationError(
                _('The pasted list repeats: %(ids)s'),
                params={'ids': ', '.join(sorted(set(doublons))[:10])},
            )

        return lignes

    def clean(self):
        """Signale les Biobank ID deja presents ailleurs, sans bloquer definitivement."""
        cleaned = super().clean()
        identifiants = cleaned.get('biobank_ids') or []

        if identifiants and not self.data.get('confirm_duplicates'):
            conflits = list(
                Case.objects
                .filter(biobank_id__in=identifiants)
                .select_related('project')[:10]
            )
            if conflits:
                self.conflits = conflits
                apercu = ', '.join(
                    f'{c.biobank_id} ({c.name} in {c.project.name})' for c in conflits
                )
                raise forms.ValidationError(
                    _('Already in the LIMS: %(list)s. Check these are different '
                      'patients before continuing.'),
                    code='duplicates',
                    params={'list': apercu},
                )
        return cleaned


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
    """Filtres de la page projet.

    Le champ conserve le nom `name` : les signets et les liens existants du type
    ?name=ACC-0042 continuent donc de fonctionner. Ce qui change, c'est ce qu'il
    interroge -- l'ACC ET le Biobank ID. Sans cela, la demande "le Biobank ID
    est le champ par lequel on cherche" serait ratee par omission : l'unique
    champ de recherche de la page n'interrogeait que Case.name, devenu une
    chaine generee par le LIMS.
    """

    name = forms.CharField(
        required=False,
        label=_('Search'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('ACC or Biobank ID...'),
            'autocomplete': 'off',
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

class UserCreateForm(forms.ModelForm):
    """Form for creating a single user."""
    
    USER_ROLE_CHOICES = [
        ('viewer', _('Viewer (Read Only)')),
        ('editor', _('Editor (CRUD)')),
        ('admin', _('Admin (Full Access)')),
    ]
    
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('First Name')}),
        label=_('First Name')
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Last Name')}),
        label=_('Last Name')
    )
    role = forms.ChoiceField(
        choices=USER_ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('User Role'),
        initial='viewer'
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
    
    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        
        if first_name and last_name:
            # Generate username
            username = self._generate_username(first_name, last_name)
            
            # Check if username already exists
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError(
                    _('A user with username "{}" already exists. Please use different names.').format(username)
                )
            
            cleaned_data['username'] = username
        
        return cleaned_data
    
    def _generate_username(self, first_name, last_name):
        """Generate username from first name + first letter of last name."""
        return f"{first_name.lower()}{last_name[0].lower()}"
    
    def _generate_password(self, length=12):
        """Generate a random password."""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choices(chars, k=length))

class BatchUserCreateForm(forms.Form):
    """Form for creating multiple users at once."""
    
    USER_ROLE_CHOICES = [
        ('viewer', _('Viewer (Read Only)')),
        ('editor', _('Editor (CRUD)')),
        ('admin', _('Admin (Full Access)')),
    ]
    
    users_data = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 10,
            'placeholder': _('Enter users data, one per line:\nFirst Name, Last Name\nExample:\nAlex, Brousseau\nMarie, Dupont\nJohn, Smith')
        }),
        label=_('Users Data'),
        help_text=_('Enter one user per line in the format: First Name, Last Name')
    )
    
    role = forms.ChoiceField(
        choices=USER_ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('User Role (for all users)'),
        initial='viewer',
        help_text=_('All users will be assigned this role')
    )
    
    def clean_users_data(self):
        users_data = self.cleaned_data['users_data']
        parsed_users = []
        existing_usernames = []
        
        lines = [line.strip() for line in users_data.split('\n') if line.strip()]
        
        if not lines:
            raise forms.ValidationError(_('Please enter at least one user.'))
        
        for i, line in enumerate(lines, 1):
            try:
                parts = [part.strip() for part in line.split(',')]
                if len(parts) != 2:
                    raise forms.ValidationError(
                        _('Line {}: Invalid format. Expected "First Name, Last Name"').format(i)
                    )
                
                first_name, last_name = parts
                
                if not first_name or not last_name:
                    raise forms.ValidationError(
                        _('Line {}: First name and last name cannot be empty').format(i)
                    )
                
                # Generate username
                username = f"{first_name.lower()}{last_name[0].lower()}"
                
                # Check for duplicates in the current batch
                if username in [user['username'] for user in parsed_users]:
                    raise forms.ValidationError(
                        _('Line {}: Duplicate username "{}" in the batch').format(i, username)
                    )
                
                # Check if username already exists in database
                if User.objects.filter(username=username).exists():
                    existing_usernames.append(username)
                
                parsed_users.append({
                    'first_name': first_name,
                    'last_name': last_name,
                    'username': username,
                    'line_number': i
                })
                
            except ValueError:
                raise forms.ValidationError(
                    _('Line {}: Invalid format. Expected "First Name, Last Name"').format(i)
                )
        
        if existing_usernames:
            raise forms.ValidationError(
                _('The following usernames already exist: {}').format(', '.join(existing_usernames))
            )
        
        return parsed_users
    
    def _generate_password(self, length=12):
        """Generate a random password."""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choices(chars, k=length))

class UserUpdateForm(forms.ModelForm):
    """Form for updating an existing user."""
    
    USER_ROLE_CHOICES = [
        ('viewer', _('Viewer (Read Only)')),
        ('editor', _('Editor (CRUD)')),
        ('admin', _('Admin (Full Access)')),
    ]
    
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('First Name')}),
        label=_('First Name')
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Last Name')}),
        label=_('Last Name')
    )
    role = forms.ChoiceField(
        choices=USER_ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('User Role')
    )
    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_('Active User'),
        help_text=_('Inactive users cannot log in to the system')
    )
    reset_password = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_('Reset Password'),
        help_text=_('Generate a new temporary password for this user')
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        
        # Set initial role based on user's current role
        if self.instance:
            if self.instance.is_superuser:
                self.fields['role'].initial = 'admin'
            elif self.instance.groups.filter(name='editor').exists():
                self.fields['role'].initial = 'editor'
            elif self.instance.groups.filter(name='viewer').exists():
                self.fields['role'].initial = 'viewer'
    
    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        
        if first_name and last_name and self.instance:
            # Generate new username
            new_username = f"{first_name.lower()}{last_name[0].lower()}"
            
            # Check if username already exists (excluding current user)
            if User.objects.filter(username=new_username).exclude(id=self.instance.id).exists():
                raise forms.ValidationError(
                    _('A user with username "{}" already exists. Please use different names.').format(new_username)
                )
            
            cleaned_data['username'] = new_username
        
        return cleaned_data
    
    def _generate_password(self, length=12):
        """Generate a random password."""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choices(chars, k=length)) 