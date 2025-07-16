#!/usr/bin/env python
"""
Script pour recalculer les tiers avec les nouveaux critères Tier B.
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'terryfox_lims.settings')
django.setup()

from core.models import Case

def update_tier_b_criteria():
    """Met à jour tous les cases avec les nouveaux critères Tier B."""
    
    print("=== Mise à jour des critères Tier B ===")
    print("Nouveau critère ajouté: DNA(T) >= 80X, DNA(N) >= 30X, pas de valeur RNA = Tier B")
    print()
    
    # Recalculer tous les tiers
    cases_to_update = []
    
    for case in Case.objects.all():
        old_tier = case.tier
        # Forcer le recalcul en sauvegardant (cela utilisera la nouvelle logique)
        case.save()
        new_tier = case.tier
        
        if old_tier != new_tier:
            cases_to_update.append({
                'case': case,
                'old_tier': old_tier,
                'new_tier': new_tier
            })
    
    print(f"Cases mis à jour: {len(cases_to_update)}")
    
    if cases_to_update:
        print("\nDétails des changements:")
        print("-" * 80)
        for update in cases_to_update[:10]:  # Afficher les 10 premiers
            case = update['case']
            print(f"{case.name:20} | {update['old_tier']:4} -> {update['new_tier']:4} | "
                  f"DNA(T)={case.dna_t_coverage}, DNA(N)={case.dna_n_coverage}, RNA={case.rna_coverage}")
        
        if len(cases_to_update) > 10:
            print(f"... et {len(cases_to_update) - 10} autres cases")
    
    # Statistiques finales
    print("\n=== Statistiques finales ===")
    total_cases = Case.objects.count()
    tier_a_count = Case.objects.filter(tier='A').count()
    tier_b_count = Case.objects.filter(tier='B').count()
    tier_fail_count = Case.objects.filter(tier='FAIL').count()
    
    print(f"Total des cases: {total_cases}")
    print(f"Tier A: {tier_a_count} ({tier_a_count/total_cases*100:.1f}%)")
    print(f"Tier B: {tier_b_count} ({tier_b_count/total_cases*100:.1f}%)")
    print(f"Tier FAIL: {tier_fail_count} ({tier_fail_count/total_cases*100:.1f}%)")
    
    # Exemples de Tier B avec DNA élevé et pas de RNA
    high_dna_no_rna_b = Case.objects.filter(
        tier='B',
        dna_t_coverage__gte=80,
        dna_n_coverage__gte=30,
        rna_coverage__isnull=True
    )
    
    print(f"\nCases Tier B avec DNA(T) >= 80X, DNA(N) >= 30X, sans RNA: {high_dna_no_rna_b.count()}")
    for case in high_dna_no_rna_b[:5]:
        print(f"  - {case.name}: DNA(T)={case.dna_t_coverage}, DNA(N)={case.dna_n_coverage}, RNA=None")

if __name__ == '__main__':
    update_tier_b_criteria()
