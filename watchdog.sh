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
    
    # Redémarrer si nécessaire
    if [ "$need_restart" = true ]; then
        restart_service
    else
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
