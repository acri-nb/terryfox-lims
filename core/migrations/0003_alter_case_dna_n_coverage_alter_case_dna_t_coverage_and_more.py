# Generated by Django 4.2.20 on 2025-03-14 17:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_swap_pi_bioinfo_permissions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='case',
            name='dna_n_coverage',
            field=models.FloatField(blank=True, null=True, verbose_name='DNA (N) Coverage (X)'),
        ),
        migrations.AlterField(
            model_name='case',
            name='dna_t_coverage',
            field=models.FloatField(blank=True, null=True, verbose_name='DNA (T) Coverage (X)'),
        ),
        migrations.AlterField(
            model_name='case',
            name='rna_coverage',
            field=models.FloatField(blank=True, null=True, verbose_name='RNA Coverage (M)'),
        ),
        migrations.AlterField(
            model_name='case',
            name='tier',
            field=models.CharField(choices=[('A', 'A'), ('B', 'B'), ('FAIL', 'FAIL')], default='A', max_length=4),
        ),
    ]
