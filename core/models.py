from django.db import models
from django.contrib.auth.models import User, Group
from django.utils.translation import gettext_lazy as _

class ProjectLead(models.Model):
    """Model representing a project lead in the LIMS."""
    name = models.CharField(max_length=255, unique=True)
    
    def __str__(self):
        return self.name
        
    class Meta:
        ordering = ['name']
        verbose_name = _('Project Lead')
        verbose_name_plural = _('Project Leads')

class Project(models.Model):
    """Model representing a research project in the LIMS."""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    project_lead = models.ForeignKey(
        ProjectLead, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='projects',
        verbose_name=_('Project Lead')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_projects')

    def __str__(self):
        return self.name

    def get_cases_count(self):
        """Return the number of cases in this project."""
        return self.cases.count()
    
    @classmethod
    def get_unique_project_leads(cls):
        """Return all unique project leads."""
        return ProjectLead.objects.all().order_by('name')

class Case(models.Model):
    """Model representing a case within a project."""
    
    # Status options
    STATUS_RECEIVED = 'received'
    STATUS_LIBRARY_PREPPED = 'library_prepped'
    STATUS_TRANSFERRED = 'transferred_to_nfl'
    STATUS_BIOINFO = 'bioinfo_analysis'
    STATUS_COMPLETED = 'completed'
    
    STATUS_CHOICES = [
        (STATUS_RECEIVED, _('Recieved')),
        (STATUS_LIBRARY_PREPPED, _('Library Prepped')),
        (STATUS_TRANSFERRED, _('Transferred to NFL')),
        (STATUS_BIOINFO, _('Bioinfo Analysis')),
        (STATUS_COMPLETED, _('Completed')),
    ]
    
    # Tier options
    TIER_A = 'A'
    TIER_B = 'B'
    TIER_FA = 'FAIL'
    
    TIER_CHOICES = [
        (TIER_A, _('A')),
        (TIER_B, _('B')),
        (TIER_FA, _('FAIL')),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='cases')
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    
    # Coverage values
    rna_coverage = models.FloatField(null=True, blank=True, verbose_name=_('RNA Coverage (M)'))
    dna_t_coverage = models.FloatField(null=True, blank=True, verbose_name=_('DNA (T) Coverage (X)'))
    dna_n_coverage = models.FloatField(null=True, blank=True, verbose_name=_('DNA (N) Coverage (X)'))
    
    tier = models.CharField(max_length=4, choices=TIER_CHOICES, default=TIER_A)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Override save method to calculate tier based on coverage values."""
        self.tier = self.calculate_tier()
        super().save(*args, **kwargs)
    
    def calculate_tier(self):
        """Calculate tier based on coverage values."""
        # Return default tier if any coverage value is missing
        if any(value is None for value in [self.rna_coverage, self.dna_t_coverage, self.dna_n_coverage]):
            return self.tier
        
        # Tier A: DNA(T) >= 80X, DNA(N) >= 30X, RNA >= 100M reads
        if self.dna_t_coverage >= 80 and self.dna_n_coverage >= 30 and self.rna_coverage >= 100:
            return self.TIER_A
        
        # Tier B: 30X <= DNA(T) < 80X, DNA(N) >= 30X, RNA >= 100M reads
        if (30 <= self.dna_t_coverage < 80) and self.dna_n_coverage >= 30 and self.rna_coverage >= 100:
            return self.TIER_B
        
        # FAIL: DNA(T) < 30X OR DNA(N) < 30X OR RNA < 100M reads
        return self.TIER_FA
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"

class Accession(models.Model):
    """Model to store accession numbers for a case."""
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='accessions')
    accession_number = models.CharField(max_length=255)
    
    def __str__(self):
        return self.accession_number

class Comment(models.Model):
    """Model to store comments for a case."""
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.case}"

# Create groups for different user roles
def create_groups():
    """Create PI and Bioinformatician groups if they don't exist."""
    Group.objects.get_or_create(name='PI')
    Group.objects.get_or_create(name='Bioinformatician')

# Create a signal to automatically create groups when Django starts
from django.db.models.signals import post_migrate
from django.dispatch import receiver

@receiver(post_migrate)
def init_groups(sender, **kwargs):
    """Initialize groups after migration."""
    if sender.name == 'core':
        create_groups()
