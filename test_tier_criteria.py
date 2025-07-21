#!/usr/bin/env python
"""
Script de test pour vérifier les nouveaux critères de calcul des tiers.
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'terryfox_lims.settings')
django.setup()

from core.models import Case

def test_tier_criteria():
    """Test les nouveaux critères de calcul des tiers."""
    
    print("=== Test des nouveaux critères de tier ===\n")
    
    # Test cases avec différents scénarios
    test_cases = [
        # (dna_t, dna_n, rna, expected_tier, description)
        (85, 35, 120, 'A', 'Tier A: DNA(T)>=80, DNA(N)>=30, RNA>=80'),
        (80, 30, 80, 'A', 'Tier A: limites exactes'),
        (75, 35, None, 'B', 'Tier B: DNA(T) entre 30-80, DNA(N)>=30, pas de RNA'),
        (50, 40, 50, 'B', 'Tier B: DNA(T) entre 30-80, DNA(N)>=30, RNA<100'),
        (30, 30, None, 'B', 'Tier B: limites inférieures'),
        (85, 35, None, 'B', 'Tier B: DNA(T)>=80, DNA(N)>=30, pas de RNA (NOUVEAU)'),
        (120, 45, None, 'B', 'Tier B: DNA(T) élevé, DNA(N)>=30, pas de RNA (NOUVEAU)'),
        (85, 35, 79, 'B', 'Tier B: DNA(T)>=80, DNA(N)>=30, RNA<80 (pas Tier A, devient B)'),
        (25, 35, 120, 'FAIL', 'Tier FAIL: DNA(T)<30'),
        (85, 25, 120, 'FAIL', 'Tier FAIL: DNA(N)<30'),
        (None, 35, 120, 'FAIL', 'Tier FAIL: DNA(T) manquant'),
        (85, None, 120, 'FAIL', 'Tier FAIL: DNA(N) manquant'),
    ]
    
    print("Tests unitaires:")
    print("-" * 80)
    
    for i, (dna_t, dna_n, rna, expected, description) in enumerate(test_cases, 1):
        # Créer un case temporaire pour le test
        case = Case(
            dna_t_coverage=dna_t,
            dna_n_coverage=dna_n,
            rna_coverage=rna
        )
        
        actual = case.calculate_tier()
        status = "✓ PASS" if actual == expected else "✗ FAIL"
        
        print(f"Test {i:2d}: {status}")
        print(f"         DNA(T)={dna_t}, DNA(N)={dna_n}, RNA={rna}")
        print(f"         Attendu: {expected}, Obtenu: {actual}")
        print(f"         {description}")
        print()
    
    # Statistiques sur les cases existants
    print("\n=== Statistiques des cases existants ===")
    print("-" * 50)
    
    total_cases = Case.objects.count()
    tier_a_count = Case.objects.filter(tier='A').count()
    tier_b_count = Case.objects.filter(tier='B').count()
    tier_fail_count = Case.objects.filter(tier='FAIL').count()
    
    print(f"Total des cases: {total_cases}")
    print(f"Tier A: {tier_a_count} ({tier_a_count/total_cases*100:.1f}%)")
    print(f"Tier B: {tier_b_count} ({tier_b_count/total_cases*100:.1f}%)")
    print(f"Tier FAIL: {tier_fail_count} ({tier_fail_count/total_cases*100:.1f}%)")
    
    # Exemples de cases pour chaque tier
    print("\n=== Exemples de cases par tier ===")
    print("-" * 50)
    
    for tier in ['A', 'B', 'FAIL']:
        cases = Case.objects.filter(tier=tier)[:3]
        print(f"\nTier {tier} (exemples):")
        for case in cases:
            print(f"  - {case.name}: DNA(T)={case.dna_t_coverage}, "
                  f"DNA(N)={case.dna_n_coverage}, RNA={case.rna_coverage}")

if __name__ == '__main__':
    test_tier_criteria()
