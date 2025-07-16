from django.db import migrations

def rename_groups(apps, schema_editor):
    """
    Rename existing groups from PI to viewer and Bioinformatician to editor.
    """
    Group = apps.get_model('auth', 'Group')
    
    # Rename PI to viewer
    try:
        pi_group = Group.objects.get(name='PI')
        pi_group.name = 'viewer'
        pi_group.save()
        print("Successfully renamed 'PI' group to 'viewer'")
    except Group.DoesNotExist:
        print("'PI' group not found, creating 'viewer' group")
        Group.objects.get_or_create(name='viewer')
    
    # Rename Bioinformatician to editor
    try:
        bio_group = Group.objects.get(name='Bioinformatician')
        bio_group.name = 'editor'
        bio_group.save()
        print("Successfully renamed 'Bioinformatician' group to 'editor'")
    except Group.DoesNotExist:
        print("'Bioinformatician' group not found, creating 'editor' group")
        Group.objects.get_or_create(name='editor')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),  # Adjust this to match your actual initial migration
    ]

    operations = [
        migrations.RunPython(rename_groups, migrations.RunPython.noop),
    ]