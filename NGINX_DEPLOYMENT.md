# Déploiement de TerryFox LIMS avec Nginx

Ce document explique comment déployer TerryFox LIMS avec Nginx pour permettre un accès multi-utilisateurs via le nom de domaine complet (FQDN) candig.cair.mun.ca.

## Pourquoi utiliser Nginx ?

Nginx agit comme un proxy inverse qui offre plusieurs avantages :

1. **Accès multi-utilisateurs** : Permet à plusieurs personnes d'accéder au LIMS via l'adresse IP de la VM
2. **Sécurité améliorée** : Nginx gère les connexions externes, protégeant votre application Django
3. **Performances optimisées** : Mise en cache, compression et gestion efficace des connexions
4. **Gestion simplifiée des certificats SSL** : Configuration centralisée des certificats

## Configuration rapide

Pour configurer et démarrer TerryFox LIMS avec Nginx :

```bash
# Étape 1 : Configuration de Nginx (à faire une seule fois)
sudo ./setup_nginx_production.sh

# Étape 2 : Démarrage du backend LIMS
./start_lims_backend.sh
```

Une fois ces commandes exécutées, le LIMS sera accessible à l'adresse :
- **https://candig.cair.mun.ca**

## Comment ça fonctionne

L'architecture mise en place est la suivante :

1. **Backend Django** :
   - S'exécute localement sur `localhost:8443` avec HTTPS
   - Utilise les paramètres de production (`settings_prod.py`)
   - N'est pas directement exposé au réseau

2. **Nginx** :
   - Écoute sur le FQDN `candig.cair.mun.ca` (ports 80 et 443)
   - Redirige automatiquement HTTP vers HTTPS
   - Transfère les requêtes HTTPS vers le backend Django
   - Sert les fichiers statiques directement pour de meilleures performances

## Dépannage

Si vous rencontrez des problèmes d'accès :

1. **Vérifiez que le backend est en cours d'exécution** :
   ```bash
   ps aux | grep runserver_plus
   ```

2. **Vérifiez que Nginx est en cours d'exécution** :
   ```bash
   sudo systemctl status nginx
   ```

3. **Consultez les logs Nginx** :
   ```bash
   sudo tail -f /var/log/nginx/terryfox_error.log
   ```

4. **Exécutez l'outil de diagnostic réseau** :
   ```bash
   ./debug_network.sh
   ```

5. **Vérifiez les certificats SSL** :
   ```bash
   openssl x509 -in ~/ssl/terryfox.crt -text -noout | grep -A 5 "Subject Alternative Name"
   ```

## Configuration avancée

Pour personnaliser davantage la configuration :

1. **Modifier la configuration Nginx** :
   ```bash
   sudo nano /etc/nginx/sites-available/terryfox
   ```

2. **Après modification, redémarrer Nginx** :
   ```bash
   sudo nginx -t && sudo systemctl restart nginx
   ```

## Notes importantes

- Les utilisateurs devront accepter le certificat auto-signé dans leur navigateur
- Si vous disposez d'un nom de domaine, envisagez d'utiliser Let's Encrypt pour des certificats valides
- La configuration actuelle est optimisée pour un environnement de production à petite échelle
