# Exploitation — TerryFox LIMS

Outillage de l'incrément 1 : sauvegardes, déploiement et restauration.
Objectif : rendre la perte de données structurellement impossible plutôt que simplement improbable.

## Règle unique

**Aucun `manage.py migrate` à la main sur ce serveur.** Le seul chemin est `ops/deploy.sh`,
qui refuse de migrer sans point de restauration frais, neutralise le watchdog, et annule
automatiquement si les invariants ne sont plus tenus après coup.

## Installation (une seule fois)

```bash
sudo ./ops/install.sh
```

Sort la base vivante de l'arbre git vers `/var/lib/terryfox-lims/db.sqlite3`, installe la
sauvegarde horaire, et vérifie que l'application répond sur le nouvel emplacement.
L'ancienne base est seulement renommée, jamais supprimée.

À faire ensuite, une fois rassuré :

```bash
git rm --cached db.sqlite3 && git commit -m "chore: la base de production sort du depot"
```

## Usage courant

```bash
# Etat complet : services, migrations, sauvegardes, invariants (lecture seule)
sudo ./ops/status.sh

# État de la base : comptages, tiers, orphelins, doublons
python3 ops/check_invariants.py

# Inventaire des sauvegardes
sudo python3 ops/backup_db.py --list

# Sauvegarde manuelle conservée indéfiniment
sudo python3 ops/backup_db.py --label avant-manipulation

# Déploiement d'une migration
sudo ./ops/deploy.sh 0019_soft_delete

# Migration qui ajoute volontairement des lignes : déclarer l'écart attendu,
# sinon le contrôle d'invariants annule tout
sudo ./ops/deploy.sh 0020_specimens --allow core_specimen=+3987

# Retour arrière
sudo ./ops/restore_db.sh              # choisir dans la liste
sudo ./ops/restore_db.sh <fichier>
```

## Ce que fait `deploy.sh`, dans l'ordre

1. Arrête `terryfox-lims-watchdog.timer` — sans ça, le watchdog relance le service
   toutes les 5 minutes, potentiellement au milieu d'un `migrate`.
2. Sauvegarde étiquetée, vérifiée, conservée indéfiniment. Échec ici = rien ne se passe.
3. Fige les invariants (comptages, distribution des tiers).
4. Arrête le service et vérifie qu'aucun worker n'écrit plus.
5. `migrate` puis `collectstatic` — ce dernier est obligatoire : sans lui,
   `CompressedManifestStaticFilesStorage` renvoie des 500 sur tout le site.
6. Recompare les invariants. **Tout écart non déclaré déclenche une restauration automatique.**
7. Redémarre, attend une réponse HTTP valide, réactive le watchdog.

## Fichiers

| Chemin | Rôle |
|---|---|
| `/var/lib/terryfox-lims/db.sqlite3` | base de production |
| `/var/backups/terryfox-lims/rotating/` | sauvegardes horaires (48 h, 30 j, 12 mois) |
| `/var/backups/terryfox-lims/keep/` | sauvegardes étiquetées, jamais purgées |
| `/var/lib/terryfox-lims/deploy/` | références d'invariants par déploiement |

## Sauvegardes

Timer systemd horaire. Chaque archive est produite par l'API de sauvegarde en ligne de
SQLite — cohérente même pendant que gunicorn écrit, contrairement à un `cp` — puis
**relue et comptée**. Si les comptages ne correspondent pas à la source, le fichier est
supprimé et le service sort en erreur : une sauvegarde non vérifiée inspire une confiance
qu'elle ne mérite pas.

```bash
systemctl status terryfox-lims-backup.timer
journalctl -u terryfox-lims-backup.service -n 50
```

## Exercice de restauration

Une sauvegarde jamais restaurée n'est pas une sauvegarde. À refaire une fois par trimestre :

```bash
cp /var/backups/terryfox-lims/rotating/db-<horodatage>.sqlite3 /tmp/essai.sqlite3
python3 ops/check_invariants.py --db /tmp/essai.sqlite3
DATABASE_PATH=/tmp/essai.sqlite3 python manage.py runserver 8001
```

## Tests

```bash
python manage.py test core     # application
python3 ops/selftest.py        # le controle d'invariants lui-meme
```

`selftest.py` verifie sur des bases synthetiques jetables que le controle
detecte bien une perte de lignes, une suppression douce de masse et une base
corrompue, et qu'il ne bloque pas une migration purement additive. C'est ce
script qui decide d'annuler une migration de production : s'il se degrade en
silence, personne ne s'en apercoit avant l'incident.

33 tests couvrent le calcul du tier (fichier de référence des critères du consortium),
la suppression douce, l'import CSV, la pagination, les identifiants générés et la
recherche, ainsi que la réponse de chaque page. Ils tournent sur une base de test créée
puis détruite par Django : la base de production n'est jamais touchée.
