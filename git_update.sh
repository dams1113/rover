#!/bin/bash
cd /home/rover/rover || exit
echo "📡 Mise à jour en cours via Git..."

# Réinitialise tous les fichiers modifiés
git reset --hard HEAD

# Supprime les fichiers non suivis (⚠️ attention à ne pas supprimer des fichiers utiles)
git clean -fd

# Fait le pull
git pull origin main
