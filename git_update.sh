#!/bin/bash
# Script de mise à jour Git pour le Rover
# Compatible avec systemd (ne bloque jamais le démarrage)

cd /home/rover/rover || exit 0

echo "[Rover Update] Fetching latest code..."
git fetch origin || true

echo "[Rover Update] Resetting to origin/main..."
git reset --hard origin/main || true

echo "[Rover Update] Update finished."
exit 0
