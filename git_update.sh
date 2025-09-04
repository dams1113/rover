#!/bin/bash

cd /home/rover/rover || exit
echo "📡 Mise à jour en cours via Git..."

# Forcer un reset si nécessaire
git fetch origin main
git reset --hard origin/main

# Facultatif : redémarrage du service
echo "🔁 Redémarrage du service systemd"
sudo systemctl restart rover.service
