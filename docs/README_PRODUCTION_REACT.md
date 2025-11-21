# TerryFox LIMS - Production React Deployment Guide

## 🚀 Vue d'ensemble

Cette documentation décrit comment déployer TerryFox LIMS avec l'interface React moderne en production. Le système intègre parfaitement Django backend et React frontend dans un seul déploiement.

## 📋 Prérequis

### Logiciels requis
- **Python 3.9+** avec conda
- **Node.js 16+** avec npm  
- **OpenSSL** pour les certificats HTTPS
- **Django 4.x** avec les extensions nécessaires

### Vérification des prérequis
```bash
# Vérifier Python/conda
conda --version
python --version

# Vérifier Node.js/npm
node --version
npm --version

# Vérifier OpenSSL
openssl version
```

## 🏗️ Architecture de déploiement

```
┌─────────────────────────────────────────────────────────────┐
│                    HTTPS (Port 443)                        │
├─────────────────────────────────────────────────────────────┤
│                Django + Werkzeug SSL                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  Django Views   │  │   REST API      │  │ Static Files│ │
│  │ (Templates)     │  │ (JSON/JWT)      │  │ (React)     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                     SQLite Database                        │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 Interfaces disponibles

### 1. Interface Classique Django
- **URL** : `https://localhost:443/`
- **Technologie** : Django templates + Bootstrap 5
- **Usage** : Interface traditionnelle, fonctionnelle et stable

### 2. Interface Moderne React  
- **URL** : `https://localhost:443/react/`
- **Technologie** : React + Material-UI + TypeScript
- **Usage** : Interface moderne avec graphiques et UX améliorée

### 3. API REST
- **URL** : `https://localhost:443/api/`
- **Technologie** : Django REST Framework + JWT
- **Usage** : API pour React et intégrations externes

## 📦 Déploiement automatique

### Script de production complet
```bash
# Exécuter en tant que root (port 443)
sudo ./start_production_react.sh
```

### Script de test (port 8443)
```bash
# Exécuter en tant qu'utilisateur normal
./test_production_react.sh
```

## 🔧 Déploiement manuel étape par étape

### 1. Préparation de l'environnement
```bash
# Activer l'environnement conda
conda activate django

# Installer les dépendances Python
pip install python-decouple django-extensions werkzeug pyOpenSSL requests

# Vérifier les dépendances Node.js
cd frontend
npm install
```

### 2. Construction de React
```bash
cd frontend
npm run build
cd ..
```

### 3. Configuration SSL
```bash
# Créer le répertoire SSL
mkdir -p ~/ssl

# Générer les certificats auto-signés
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ~/ssl/terryfox.key -out ~/ssl/terryfox.crt \
  -subj "/C=CA/ST=Quebec/L=Local/O=TerryFox/OU=LIMS/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:10.220.115.67"
```

### 4. Collecte des fichiers statiques
```bash
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod
```

### 5. Démarrage du serveur
```bash
# Production (port 443 - nécessite sudo)
sudo python manage.py runserver_plus 0.0.0.0:443 \
  --settings=terryfox_lims.settings_prod \
  --cert-file=~/ssl/terryfox.crt \
  --key-file=~/ssl/terryfox.key

# Test (port 8443 - utilisateur normal)
python manage.py runserver_plus 127.0.0.1:8443 \
  --settings=terryfox_lims.settings_prod \
  --cert-file=~/ssl/terryfox.crt \
  --key-file=~/ssl/terryfox.key
```

## 🔍 Tests et validation

### Tests de connectivité
```bash
# Interface classique
curl -k -I https://localhost:443/

# Interface React
curl -k -I https://localhost:443/react/

# API REST
curl -k -I https://localhost:443/api/projects/

# Fichiers statiques React
curl -k -I https://localhost:443/static/js/main.c82aa5b0.js
curl -k -I https://localhost:443/static/css/main.e6c13ad2.css
```

### Tests fonctionnels
1. **Authentification** : Login/logout sur les deux interfaces
2. **Navigation** : Tous les menus et liens fonctionnent
3. **CRUD** : Création, lecture, mise à jour, suppression
4. **API** : Endpoints REST répondent correctement
5. **Responsive** : Interface React s'adapte aux différentes tailles

## 📁 Structure des fichiers

```
terryfox-lims/
├── frontend/
│   ├── build/                      # Build React (généré)
│   │   ├── static/
│   │   │   ├── js/                # JavaScript React
│   │   │   └── css/               # CSS React
│   │   └── index.html
│   ├── src/                       # Code source React
│   └── package.json
├── staticfiles/                   # Fichiers statiques collectés
│   ├── js/                       # JS React + Django admin
│   ├── css/                      # CSS React + Django admin
│   └── admin/                    # Fichiers Django admin
├── templates/
│   ├── react_app.html           # Template dev React
│   ├── react_app_production.html # Template prod React
│   └── base.html                # Template Django
├── core/
│   ├── views.py                 # Vues Django + Vue React
│   ├── api_views.py             # API REST
│   └── models.py                # Modèles de données
├── terryfox_lims/
│   ├── settings_prod.py         # Configuration production
│   └── urls.py                  # URLs principales
├── start_production_react.sh    # Script production complet
├── test_production_react.sh     # Script test
└── db.sqlite3                   # Base de données
```

## ⚙️ Configuration avancée

### Variables d'environnement
```bash
# Dans settings_prod.py
DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '10.220.115.67']

# Répertoires statiques
STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'frontend' / 'build' / 'static',  # React build
]

# Templates React
TEMPLATES[0]['DIRS'].append(BASE_DIR / 'frontend' / 'build')
```

### Nginx (optionnel)
Pour un déploiement avec Nginx, utilisez `terryfox_nginx_prod.conf` :
```bash
# Copier la configuration
sudo cp terryfox_nginx_prod.conf /etc/nginx/sites-available/terryfox
sudo ln -s /etc/nginx/sites-available/terryfox /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 🐛 Dépannage

### Problèmes courants

#### 1. Erreur "Module not found" React
```bash
# Reconstruire React
cd frontend
rm -rf node_modules build
npm install
npm run build
cd ..
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod
```

#### 2. Certificats SSL invalides
```bash
# Régénérer les certificats
rm -rf ~/ssl
mkdir ~/ssl
# Puis exécuter la commande openssl ci-dessus
```

#### 3. Fichiers statiques non trouvés
```bash
# Vérifier la collecte
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod
ls -la staticfiles/js/
ls -la staticfiles/css/
```

#### 4. API 500 errors
```bash
# Vérifier les logs
tail -f logs/django.log

# Vérifier les migrations
python manage.py migrate --settings=terryfox_lims.settings_prod
```

### Logs utiles
```bash
# Logs Django
tail -f logs/django.log

# Processus en cours
ps aux | grep runserver_plus

# Ports utilisés
netstat -tlnp | grep :443
netstat -tlnp | grep :8443
```

## 🔐 Sécurité

### Certificats de production
Pour la production réelle, utilisez des certificats valides :
```bash
# Let's Encrypt (recommandé)
sudo certbot certonly --standalone -d your-domain.com

# Ou certificats d'entreprise
# Copiez vos certificats dans ~/ssl/
```

### Paramètres de sécurité
- ✅ HTTPS obligatoire
- ✅ Headers de sécurité activés
- ✅ CORS configuré pour React
- ✅ JWT pour l'authentification API
- ✅ Permissions utilisateur respectées

## 📊 Monitoring

### Métriques importantes
- **Temps de réponse** : Interface React vs Django
- **Utilisation mémoire** : Processus Python
- **Taille des fichiers** : Build React (~1MB JS)
- **Erreurs** : Logs Django et console navigateur

### Commandes de monitoring
```bash
# Taille du build React
du -sh frontend/build/

# Processus Django
ps aux | grep python | grep manage.py

# Connexions actives
ss -tlnp | grep :443
```

## 🚀 Mise en production

### Checklist finale
- [ ] Build React créé et testé
- [ ] Certificats SSL valides installés
- [ ] Base de données migrée
- [ ] Fichiers statiques collectés
- [ ] Tests de connectivité réussis
- [ ] Interfaces fonctionnelles
- [ ] API accessible
- [ ] Permissions utilisateur vérifiées
- [ ] Backup de la base de données effectué

### Commande de déploiement finale
```bash
# Déploiement complet en une commande
sudo ./start_production_react.sh
```

---

## 📞 Support

Pour toute question ou problème :
1. Vérifiez les logs : `tail -f logs/django.log`
2. Testez la connectivité : scripts de test fournis
3. Consultez cette documentation
4. Vérifiez les processus : `ps aux | grep runserver_plus`

**Version** : 1.0  
**Dernière mise à jour** : Juin 2025  
**Compatibilité** : Django 4.x + React 18.x 