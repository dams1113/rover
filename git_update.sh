#!/bin/bash
# Script de mise à jour Git pour le Rover
# ⚠️ Ne fait JAMAIS planter systemd

cd /home/rover/rover || exit 0

echo "📡 Mise à jour en cours via Git..."

# Sauvegarde temporaire des logs si présents
if [ -d logs ]; then
    mkdir -p /tmp/rover_logs
    cp -r logs/* /tmp/rover_logs/ 2>/dev/null
fi

# Forcer la récupération et nettoyage complet
git fetch origin || true
git reset --hard origin/main || true
git clean -fdx || true

# Recréation des dossiers ignorés
mkdir -p logs map

# Restauration des logs sauvegardés
if [ -d /tmp/rover_logs ]; then
    cp -r /tmp/rover_logs/* logs/ 2>/dev/null
    rm -rf /tmp/rover_logs
fi

echo "✅ Mise à jour terminée."
exit 0
