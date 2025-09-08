#!/bin/bash
# Script de mise à jour Git pour le Rover
# ⚠️ Ne fait JAMAIS planter systemd

cd /home/rover/rover || exit 0

echo "📡 Mise à jour en cours via Git..."

# Récupération sans bloquer si erreur
git fetch origin || true
git checkout origin/main -- . ':!main.py'


echo "✅ Mise à jour terminée."
exit 0
