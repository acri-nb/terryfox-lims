# Déploiement de TerryFox LIMS avec Nginx (OBSOLÈTE)

> ⚠️ **IMPORTANT** : Ce document décrit l'ancienne méthode de déploiement avec Nginx.
> 
> **La nouvelle architecture robuste utilise Gunicorn directement** et ne nécessite plus Nginx.
> 
> 👉 **Consultez `PRODUCTION.md` pour la méthode recommandée.**

---

## 🚀 Nouvelle Architecture (Recommandée)

Le système TerryFox LIMS utilise maintenant :
- **Gunicorn** comme serveur WSGI robuste
- **SSL natif** sur le port 443
- **systemd** pour la gestion des services
- **Watchdog** pour la surveillance automatique

**Accès direct** :
- https://10.220.115.67 (réseau)
- https://localhost (local)

**Avantages** :
- ✅ Plus simple à maintenir
- ✅ Moins de composants à gérer
- ✅ Surveillance automatique
- ✅ Redémarrage automatique
- ✅ Logs centralisés

---

## Ancienne Méthode Nginx (pour référence)

> Cette section est conservée pour référence historique.

### Pourquoi Nginx était utilisé ?

Nginx agissait comme un proxy inverse qui offrait plusieurs avantages :

1. **Accès multi-utilisateurs** : Permettait à plusieurs personnes d'accéder au LIMS via l'adresse IP de la VM
2. **Sécurité améliorée** : Nginx gérait les connexions externes, protégeant l'application Django
3. **Performances optimisées** : Mise en cache, compression et gestion efficace des connexions
4. **Gestion simplifiée des certificats SSL** : Configuration centralisée des certificats

**Note** : Ces avantages sont maintenant intégrés directement dans la nouvelle architecture Gunicorn.

## 🔄 Migration vers la Nouvelle Architecture

Pour migrer de l'ancienne configuration Nginx vers la nouvelle :

```bash
# 1. Arrêter l'ancien système
sudo systemctl stop nginx
sudo pkill -f runserver_plus

# 2. Démarrer le nouveau système robuste
sudo systemctl start terryfox-lims.service
sudo systemctl enable terryfox-lims.service
sudo systemctl enable --now terryfox-lims-watchdog.timer

# 3. Vérifier le fonctionnement
sudo systemctl status terryfox-lims.service
curl -k -I https://10.220.115.67/
```

### Configuration Rapide (Ancienne Méthode - Obsolète)

> ⚠️ **Cette section est obsolète** - utilisez la nouvelle méthode ci-dessus.

```bash
# Étape 1 : Configuration de Nginx (à faire une seule fois)
sudo ./setup_nginx_production.sh

# Étape 2 : Démarrage du backend LIMS
./start_lims_backend.sh
```

## Comparaison des Architectures

### 🚀 Nouvelle Architecture (Gunicorn)

```
Utilisateur → https://10.220.115.67:443 → Gunicorn (SSL natif) → Django
                                            ↓
                                      systemd + watchdog
                                            ↓
                                    Logs centralisés
```

**Avantages** :
- Architecture simplifiée
- SSL natif intégré
- Surveillance automatique
- Redémarrage automatique
- Logs centralisés
- Moins de points de défaillance

### 📜 Ancienne Architecture (Nginx - Obsolète)

```
Utilisateur → https://10.220.115.67:443 → Nginx → localhost:8443 → Django
```

**Inconvénients** :
- Plus complexe à maintenir
- Deux serveurs à gérer (Nginx + Django)
- Configuration SSL dupliquée
- Surveillance manuelle
- Logs dispersés

## Dépannage

### Pour la Nouvelle Architecture (Gunicorn)

```bash
# Vérifier le statut du service
sudo systemctl status terryfox-lims.service

# Voir les logs en temps réel
sudo journalctl -u terryfox-lims.service -f

# Vérifier les processus Gunicorn
ps aux | grep gunicorn

# Tester la connectivité
curl -k -I https://10.220.115.67/

# Redémarrer si nécessaire
sudo systemctl restart terryfox-lims.service
```

### Pour l'Ancienne Architecture (Nginx - Obsolète)

Si vous utilisez encore l'ancienne configuration :

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
