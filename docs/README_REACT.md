# TerryFox LIMS - Interface React Moderne

## Vue d'ensemble

Ce projet contient maintenant deux interfaces :

1. **Interface Django classique** - L'interface originale fonctionnelle
2. **Interface React moderne** - Une nouvelle interface moderne avec Material-UI

## Démarrage rapide

### 1. Démarrer le serveur Django (Backend)

```bash
sudo ./start_production_debug.sh
```

Le serveur Django démarrera sur `https://127.0.0.1:443` avec HTTPS.

### 2. Démarrer le serveur React (Frontend)

Dans un nouveau terminal :

```bash
./start_react_dev.sh
```

Le serveur React démarrera sur `http://localhost:3000`.

## Accès aux interfaces

### Interface Django classique
- URL : `https://127.0.0.1:443/`
- Fonctionnalités : Toutes les fonctionnalités LIMS disponibles
- Statut : ✅ Entièrement fonctionnelle

### Interface React moderne
- URL : `http://localhost:3000/`
- URL alternative : `https://127.0.0.1:443/app/`
- Fonctionnalités : Interface moderne avec Material-UI
- Statut : 🚧 En développement

## Fonctionnalités de l'interface React

### ✅ Implémentées
- **Authentification** : Login/logout avec JWT
- **Dashboard** : Statistiques et graphiques interactifs
- **Projets** : Liste, création, modification, suppression
- **Cases** : Liste, visualisation, filtrage
- **Project Leads** : Gestion complète
- **Navigation** : Interface responsive avec sidebar

### 🎨 Améliorations visuelles
- Design moderne avec Material-UI
- Thème cohérent avec gradients
- Animations et transitions fluides
- Interface responsive (mobile/tablet/desktop)
- Graphiques interactifs avec Recharts
- Icônes Font Awesome et Material Icons

### 🔧 Fonctionnalités techniques
- TypeScript pour la sécurité des types
- Axios pour les appels API
- React Router pour la navigation
- Context API pour la gestion d'état
- Configuration CORS pour l'intégration Django

## Architecture

```
terryfox-lims/
├── core/                     # Django app (backend)
│   ├── api_views.py         # API REST endpoints
│   ├── serializers.py       # Sérialiseurs DRF
│   └── api_urls.py          # URLs API
├── frontend/                # React app (frontend)
│   ├── src/
│   │   ├── components/      # Composants réutilisables
│   │   ├── pages/          # Pages principales
│   │   ├── contexts/       # Gestion d'état React
│   │   └── config.ts       # Configuration API
│   └── package.json
├── templates/
│   └── react_app.html      # Template pour l'app React
└── start_react_dev.sh      # Script de démarrage React
```

## API Endpoints

Le backend Django expose une API REST complète :

- `GET /api/projects/` - Liste des projets
- `POST /api/projects/` - Créer un projet
- `GET /api/projects/{id}/` - Détails d'un projet
- `GET /api/cases/` - Liste des cases
- `GET /api/project-leads/` - Liste des project leads
- `POST /api/auth/token/` - Authentification JWT
- `GET /api/projects/statistics/` - Statistiques dashboard

## Développement

### Prérequis
- Python 3.9+ avec conda
- Node.js 16+ avec npm
- Environnement conda `django` activé

### Installation des dépendances

Backend (déjà installé) :
```bash
conda activate django
pip install djangorestframework django-cors-headers djangorestframework-simplejwt
```

Frontend :
```bash
cd frontend
npm install
```

### Variables d'environnement

L'application React utilise automatiquement :
- `REACT_APP_API_URL=https://127.0.0.1:443/api`
- `PORT=3000`

## Sécurité

- **HTTPS** : Le serveur Django utilise HTTPS avec certificats auto-signés
- **JWT** : Authentification sécurisée avec tokens
- **CORS** : Configuration CORS pour permettre les requêtes cross-origin
- **Permissions** : Respect des permissions Django (viewer, editor, Admin)

## Troubleshooting

### Le serveur React ne démarre pas
```bash
cd frontend
npm install
npm start
```

### Erreurs CORS
Vérifiez que `CORS_ALLOW_ALL_ORIGINS = DEBUG` est dans `settings.py`

### Certificats SSL
Les certificats sont générés automatiquement par `start_production_debug.sh`

### API non accessible
Vérifiez que le serveur Django est démarré avec `sudo ./start_production_debug.sh`

## Prochaines étapes

1. **Édition de cases** : Formulaires d'édition dans React
2. **Import CSV** : Interface pour l'import de cases en lot
3. **Commentaires** : Système de commentaires interactif
4. **Notifications** : Système de notifications en temps réel
5. **Tests** : Tests unitaires et d'intégration
6. **Production** : Configuration pour le déploiement

## Support

Pour toute question ou problème :
1. Vérifiez les logs du serveur Django
2. Vérifiez la console du navigateur pour les erreurs React
3. Utilisez l'interface Django classique comme fallback 