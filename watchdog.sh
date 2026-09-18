#!/bin/bash

# Script de surveillance (watchdog) pour TerryFox LIMS
# Vérifie que le service fonctionne correctement et le redémarre si nécessaire

LOG_FILE="/var/log/terryfox-lims/watchdog.log"

# Fonction de logging
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Vérifier si le processus Gunicorn est en cours d'exécution
check_gunicorn_process() {
    if pgrep -f "gunicorn.*terryfox_lims.wsgi_prod" > /dev/null; then
        log_message "✅ Le processus Gunicorn LIMS est actif"
        return 0
    else
        log_message "❌ Le processus Gunicorn LIMS n'est pas trouvé"
        return 1
    fi
}

# Vérifier si le serveur web répond correctement
check_http_response() {
    local response_code
    response_code=$(timeout 10 curl -k -s -o /dev/null -w "%{http_code}" https://localhost:443/ 2>/dev/null)
    
    if [[ "$response_code" =~ ^(200|301|302)$ ]]; then
        log_message "✅ Le serveur web répond correctement (code: $response_code)"
        return 0
    else
        log_message "❌ Le serveur web ne répond pas correctement (code: $response_code)"
        return 1
    fi
}

# Vérifier l'utilisation de la mémoire du processus
check_memory_usage() {
    local memory_usage
    memory_usage=$(ps -o pid,ppid,cmd,%mem --sort=-%mem | grep "gunicorn.*terryfox_lims" | head -1 | awk '{print $4}')
    
    if [ -n "$memory_usage" ]; then
        # Convertir en nombre entier pour comparaison
        memory_int=$(echo "$memory_usage" | cut -d. -f1)
        
        if [ "$memory_int" -gt 80 ]; then
            log_message "⚠️  Utilisation mémoire élevée: ${memory_usage}%"
            return 1
        else
            log_message "✅ Utilisation mémoire normale: ${memory_usage}%"
            return 0
        fi
    else
        log_message "❌ Impossible de déterminer l'utilisation mémoire"
        return 1
    fi
}

# Vérifier que le schéma de la base correspond au code déployé.
#
# check_http_response() sonde `/` en anonyme, ce qui redirige vers la page de
# connexion SANS jamais interroger core_case. Une base en retard d'une migration
# laisse donc ce contrôle à 302 pendant que TOUTES les pages authentifiées
# renvoient 500. C'est arrivé : le redémarrage du 14 septembre 2026 a chargé du
# code attendant les colonnes de la migration 0032 contre une base restée à
# 0031, et la panne a duré quatre jours pendant que ce script écrivait
# « Tous les contrôles sont OK » toutes les cinq minutes.
#
# On ne redémarre PAS sur cette erreur : un redémarrage ne rejoue aucune
# migration et relancerait la même panne. Seul un déploiement corrige.
PY_ENV="/home/hadriengt/miniconda/envs/django/bin/python"
REPO_DIR="/home/hadriengt/project/lims/terryfox-lims"

check_schema() {
    if [ ! -x "$PY_ENV" ]; then
        log_message "⚠️  Interpréteur introuvable ($PY_ENV) : schéma non vérifié"
        return 0
    fi
    local sortie
    if sortie="$("$PY_ENV" "$REPO_DIR/manage.py" migrate --check \
                 --settings=terryfox_lims.settings_prod 2>&1)"; then
        return 0
    fi

    # `migrate --check` sort en erreur pour deux raisons sans rapport : des
    # migrations en attente, ou une base qu'il n'a pas pu ouvrir. Les confondre
    # ferait crier à la panne un watchdog lancé par erreur sans les droits.
    case "$sortie" in
        *"unable to open database"*|*"Permission denied"*|*"permission denied"*)
            log_message "⚠️  Schéma non vérifiable : base illisible. Ce script tourne-t-il en root ?"
            return 0
            ;;
    esac

    log_message "❌ MIGRATION EN ATTENTE : le code attend un schéma que la base n'a pas."
    log_message "   Les pages authentifiées renvoient 500 alors que / répond 302."
    log_message "   Un redémarrage n'y changera rien. Lancer : sudo $REPO_DIR/ops/deploy.sh <etiquette>"
    return 1
}

# Vérifier la validité du certificat TLS.
#
# Personne ne surveillait l'expiration : celui de la VM a passé 77 jours périmé
# sans qu'aucun contrôle ne le signale. On prévient 30 jours à l'avance, ce qui
# laisse le temps de demander un renouvellement.
#
# Pas de redémarrage ici non plus : relancer gunicorn avec un certificat périmé
# le relance avec un certificat périmé.
check_certificate() {
    local pem
    pem="$(echo | timeout 8 openssl s_client -connect 127.0.0.1:443 2>/dev/null)"
    if [ -z "$pem" ]; then
        log_message "⚠️  Certificat non lisible : port 443 injoignable pour openssl"
        return 0
    fi
    if ! echo "$pem" | openssl x509 -noout -checkend 0 >/dev/null 2>&1; then
        local fin
        fin="$(echo "$pem" | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
        log_message "❌ CERTIFICAT TLS EXPIRÉ (fin : ${fin:-inconnue})"
        log_message "   Les navigateurs qui joignent la VM en direct refusent la connexion."
        log_message "   Un redémarrage n'y changera rien : il faut réinstaller un certificat dans /root/ssl/."
        return 1
    fi
    if ! echo "$pem" | openssl x509 -noout -checkend 2592000 >/dev/null 2>&1; then
        log_message "⚠️  Certificat TLS expire dans moins de 30 jours"
        return 1
    fi
    return 0
}

# Redémarrer le service
restart_service() {
    log_message "🔄 Redémarrage du service terryfox-lims..."
    systemctl restart terryfox-lims.service
    
    # Attendre un peu et vérifier si le redémarrage a réussi
    sleep 10
    
    if check_gunicorn_process; then
        log_message "✅ Service redémarré avec succès"
        return 0
    else
        log_message "❌ Échec du redémarrage du service"
        return 1
    fi
}

# Fonction principale de vérification
main_check() {
    log_message "=== DÉBUT DE LA VÉRIFICATION WATCHDOG ==="
    
    local need_restart=false
    
    # Vérifier le processus Gunicorn
    if ! check_gunicorn_process; then
        need_restart=true
    fi
    
    # Vérifier la réponse HTTP seulement si le processus existe
    if [ "$need_restart" = false ]; then
        if ! check_http_response; then
            need_restart=true
        fi
    fi
    
    # Vérifier l'utilisation mémoire seulement si le processus existe
    if [ "$need_restart" = false ]; then
        check_memory_usage  # Ne pas redémarrer pour la mémoire, juste logger
    fi

    # Le contrôle que la sonde HTTP ne peut pas faire. Il ne déclenche aucun
    # redémarrage : la panne qu'il détecte ne se corrige que par un déploiement.
    local schema_ok=true
    local cert_ok=true
    if [ "$need_restart" = false ]; then
        check_schema || schema_ok=false
        check_certificate || cert_ok=false
    fi
    
    # Redémarrer si nécessaire
    if [ "$need_restart" = true ]; then
        restart_service
    elif [ "$schema_ok" = true ] && [ "$cert_ok" = true ]; then
        log_message "✅ Tous les contrôles sont OK"
    fi
    
    log_message "=== FIN DE LA VÉRIFICATION WATCHDOG ==="
    echo "" >> "$LOG_FILE"  # Ligne vide pour séparer les vérifications
}

# Créer le répertoire de logs s'il n'existe pas
mkdir -p /var/log/terryfox-lims
touch "$LOG_FILE"

# Exécuter la vérification principale
main_check

exit 0
