# Generated manually to add ProjectLead permissions to Bioinformatician group

from django.db import migrations
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


def add_projectlead_permissions(apps, schema_editor):
    """
    Add ProjectLead permissions to Bioinformatician group.
    """
    try:
        # Get the Bioinformatician group
        bioinfo_group = Group.objects.get(name='Bioinformatician')
        
        # Get content type for ProjectLead model
        projectlead_ct = ContentType.objects.get(app_label='core', model='projectlead')
        
        # Get all permissions for ProjectLead model
        view_projectlead = Permission.objects.get(content_type=projectlead_ct, codename='view_projectlead')
        add_projectlead = Permission.objects.get(content_type=projectlead_ct, codename='add_projectlead')
        change_projectlead = Permission.objects.get(content_type=projectlead_ct, codename='change_projectlead')
        delete_projectlead = Permission.objects.get(content_type=projectlead_ct, codename='delete_projectlead')
        
        # Add ProjectLead permissions to Bioinformatician group
        bioinfo_group.permissions.add(
            view_projectlead,
            add_projectlead,
            change_projectlead,
            delete_projectlead
        )
        
        # Also add view permission to PI group for consistency
        pi_group = Group.objects.get(name='PI')
        pi_group.permissions.add(view_projectlead)
        
    except (Group.DoesNotExist, ContentType.DoesNotExist, Permission.DoesNotExist) as e:
        # If groups or permissions don't exist, skip this migration
        # This can happen during initial setup
        pass


def remove_projectlead_permissions(apps, schema_editor):
    """
    Remove ProjectLead permissions from Bioinformatician group.
    """
    try:
        # Get the groups
        bioinfo_group = Group.objects.get(name='Bioinformatician')
        pi_group = Group.objects.get(name='PI')
        
        # Get content type for ProjectLead model
        projectlead_ct = ContentType.objects.get(app_label='core', model='projectlead')
        
        # Get all permissions for ProjectLead model
        view_projectlead = Permission.objects.get(content_type=projectlead_ct, codename='view_projectlead')
        add_projectlead = Permission.objects.get(content_type=projectlead_ct, codename='add_projectlead')
        change_projectlead = Permission.objects.get(content_type=projectlead_ct, codename='change_projectlead')
        delete_projectlead = Permission.objects.get(content_type=projectlead_ct, codename='delete_projectlead')
        
        # Remove ProjectLead permissions from both groups
        bioinfo_group.permissions.remove(
            view_projectlead,
            add_projectlead,
            change_projectlead,
            delete_projectlead
        )
        
        pi_group.permissions.remove(view_projectlead)
        
    except (Group.DoesNotExist, ContentType.DoesNotExist, Permission.DoesNotExist) as e:
        # If groups or permissions don't exist, skip this migration
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_case_other_id_alter_case_status'),
    ]

    operations = [
        migrations.RunPython(add_projectlead_permissions, remove_projectlead_permissions),
    ] 