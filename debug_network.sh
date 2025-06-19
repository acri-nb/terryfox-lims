#!/bin/bash

echo "=== DIAGNOSTIC RÉSEAU TERRYFOX LIMS ==="
echo ""

# Vérifier les interfaces réseau
echo "1. INTERFACES RÉSEAU ACTIVES :"
ip addr show | grep -E "inet.*scope global"
echo ""

# Vérifier les adresses IP configurées
echo "2. ADRESSES IP DÉTECTÉES :"
hostname -I
echo ""

# Tester si le port 8443 est accessible sur différentes interfaces
echo "3. TEST CONNECTIVITÉ PORT 8443 :"

# Liste des IPs à tester depuis ALLOWED_HOSTS
IPS=("127.0.0.1" "192.168.7.13" "10.220.115.67")

for ip in "${IPS[@]}"; do
    echo -n "Testing $ip:8443... "
    if timeout 3 bash -c "</dev/tcp/$ip/8443" 2>/dev/null; then
        echo "✅ ACCESSIBLE"
    else
        echo "❌ NON ACCESSIBLE"
    fi
done

echo ""

# Vérifier si le processus Django écoute bien
echo "4. PROCESSUS DJANGO EN ÉCOUTE :"
netstat -tlnp | grep :8443 || ss -tlnp | grep :8443
echo ""

# Vérifier les certificats SSL générés
echo "5. CERTIFICATS SSL :"
SSL_DIR=~/ssl
CERTFILE=$SSL_DIR/terryfox.crt

if [ -f "$CERTFILE" ]; then
    echo "Certificat existant - SANs inclus :"
    openssl x509 -in "$CERTFILE" -text -noout | grep -A 10 "Subject Alternative Name" || echo "Aucun SAN trouvé"
else
    echo "❌ Certificat non trouvé dans $SSL_DIR"
fi

echo ""
echo "=== FIN DIAGNOSTIC ==="
