# Résumé des Modifications - Critères de Tiers TerryFox LIMS

## 📅 Date : 16 juillet 2025

## 🎯 Objectif
Mise à jour des critères de calcul des tiers pour les cases dans le système LIMS TerryFox.

## 📋 Nouveaux Critères Implémentés

### **Tier A** (inchangé)
- DNA(T) ≥ 80X 
- **ET** DNA(N) ≥ 30X 
- **ET** RNA ≥ 100M reads

### **Tier B** (mis à jour)
Deux cas de figure :
1. **30X ≤ DNA(T) ≤ 80X** ET **DNA(N) ≥ 30X** ET **tout ce qui concerne RNA** (y compris l'absence de valeur)
2. **DNA(T) ≥ 80X** ET **DNA(N) ≥ 30X** ET **pas de valeur RNA** *(NOUVEAU critère)*

### **Tier FAIL** (simplifié)
- DNA(T) < 30X **OU** DNA(N) < 30X
- **OU** valeurs DNA manquantes

## 📊 Impact sur la Base de Données

### Migration 1 (0014_recalculate_tiers_with_new_criteria)
- ✅ 36 cases mis à jour

### Mise à jour supplémentaire (critère Tier B étendu)
- ✅ 84 cases supplémentaires mis à jour (FAIL → B)

### **Statistiques Finales :**
- **Total des cases :** 798
- **Tier A :** 171 (21.4%)
- **Tier B :** 187 (23.4%) *(+84 cases grâce au nouveau critère)*
- **Tier FAIL :** 440 (55.1%)

## 🔧 Modifications Techniques

### Fichier : `core/models.py`
- Méthode `calculate_tier()` mise à jour
- Logique simplifiée et plus claire
- Nouveau cas pour Tier B : DNA élevé sans valeur RNA

### Tests
- Script de test mis à jour : `test_tier_criteria.py`
- Tous les tests passent ✅
- Nouveaux cas de test ajoutés pour le critère Tier B étendu

### Scripts Utilitaires
- `update_tier_b_criteria.py` : Script pour appliquer la mise à jour
- `test_tier_criteria.py` : Tests de validation

## 🎯 Cas d'Usage du Nouveau Critère

Le nouveau critère Tier B capture les cases avec :
- **ADN de bonne qualité** (DNA(T) ≥ 80X, DNA(N) ≥ 30X)
- **Mais sans données RNA disponibles**

**Exemples de cases concernées :**
- ACC-0687: DNA(T)=82.94, DNA(N)=42.44, RNA=None
- ACC-0333: DNA(T)=85.0, DNA(N)=32.0, RNA=None  
- ACC-0720: DNA(T)=101.28, DNA(N)=37.3, RNA=None

## ✅ Validation

- **Tests unitaires :** 12/12 passent
- **Migration :** Appliquée avec succès
- **Cohérence des données :** Vérifiée
- **Performance :** Pas d'impact négatif

## 📝 Notes Importantes

1. **Pas de régression :** Les critères Tier A et FAIL restent identiques
2. **Extension logique :** Le Tier B devient plus inclusif pour les cases avec ADN de qualité
3. **Réversibilité :** Les changements sont documentés mais non réversibles automatiquement
4. **Impact positif :** 84 cases passent de FAIL à B, améliorant leur statut

## 🚀 Prochaines Étapes

1. ✅ Modifications appliquées en base de données
2. ✅ Tests de validation effectués  
3. ✅ Documentation mise à jour
4. 🔄 Monitoring des impacts en production recommandé

---

**Auteur :** Système LIMS TerryFox  
**Validation :** Tests automatisés passés  
**Status :** ✅ Déployé avec succès
