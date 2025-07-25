# Generated by Django 4.2.20 on 2025-07-16 15:04

from django.db import migrations


def recalculate_tiers_updated(apps, schema_editor):
    """Recalculate tiers for all cases with updated Tier B criteria."""
    Case = apps.get_model('core', 'Case')
    
    def calculate_new_tier(case):
        """Calculate tier based on updated coverage criteria."""
        # Return FAIL if DNA coverage values are missing or below thresholds
        if case.dna_t_coverage is None or case.dna_n_coverage is None:
            return 'FAIL'
            
        # Tier FAIL: DNA(T) < 30X OR DNA(N) < 30X
        if case.dna_t_coverage < 30 or case.dna_n_coverage < 30:
            return 'FAIL'
        
        # Tier A: DNA(T) >= 80X, DNA(N) >= 30X, RNA >= 100M reads
        if (case.dna_t_coverage >= 80 and case.dna_n_coverage >= 30 and 
            case.rna_coverage is not None and case.rna_coverage >= 100):
            return 'A'
        
        # Tier B: Deux cas possibles
        # 1. 30X <= DNA(T) <= 80X, DNA(N) >= 30X, tout ce qui concerne RNA
        # 2. DNA(T) >= 80X, DNA(N) >= 30X, pas de valeur de RNA
        if ((30 <= case.dna_t_coverage <= 80 and case.dna_n_coverage >= 30) or 
            (case.dna_t_coverage >= 80 and case.dna_n_coverage >= 30 and case.rna_coverage is None)):
            return 'B'
        
        # Default to FAIL for any other case
        return 'FAIL'
    
    # Get all cases and recalculate their tiers
    cases_to_update = []
    for case in Case.objects.all():
        old_tier = case.tier
        new_tier = calculate_new_tier(case)
        if old_tier != new_tier:
            case.tier = new_tier
            cases_to_update.append(case)
    
    # Bulk update to improve performance
    if cases_to_update:
        Case.objects.bulk_update(cases_to_update, ['tier'])
        print(f"Updated {len(cases_to_update)} cases with updated Tier B criteria")


def reverse_recalculate_tiers_updated(apps, schema_editor):
    """Reverse operation - this is not reversible as we don't store old values."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_recalculate_tiers_with_new_criteria'),
    ]

    operations = [
        migrations.RunPython(recalculate_tiers_updated, reverse_recalculate_tiers_updated),
    ]

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_recalculate_tiers_with_new_criteria'),
    ]

    operations = [
    ]
