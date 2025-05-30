# Generated by Django 4.2.20 on 2025-03-24 23:04

from django.db import migrations

def populate_project_leads(apps, schema_editor):
    """
    Create ProjectLead objects from existing project_lead values and
    associate them with the corresponding projects.
    """
    Project = apps.get_model('core', 'Project')
    ProjectLead = apps.get_model('core', 'ProjectLead')
    
    # Dictionary to track created leads
    leads = {}
    
    # Get all unique project lead values
    unique_leads = set()
    for project in Project.objects.all():
        if project.project_lead and project.project_lead.strip():
            unique_leads.add(project.project_lead.strip())
    
    # Create ProjectLead objects
    for name in unique_leads:
        lead = ProjectLead.objects.create(name=name)
        leads[name] = lead
    
    # Associate projects with leads
    for project in Project.objects.all():
        if project.project_lead and project.project_lead.strip():
            lead_name = project.project_lead.strip()
            if lead_name in leads:
                project.project_lead_obj = leads[lead_name]
                project.save(update_fields=['project_lead_obj'])

def reverse_migration(apps, schema_editor):
    """
    This is a data migration so simply do nothing on reversal
    """
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_projectlead_project_project_lead_obj'),
    ]

    operations = [
        migrations.RunPython(populate_project_leads, reverse_migration),
    ]
