#!/bin/bash

cd /home/rover/rover || exit 1

echo "📡 Mise à jour en cours via Git..."

# Réinitialise les fichiers modifiés localement
git reset --hard HEAD
git clean -fd

# Fait le pull depuis la branche main
git pull origin main

# Redémarre le service systemd proprement
echo "🔁 Redémarrage du bot Rover..."
sudo systemctl restart rover.service
