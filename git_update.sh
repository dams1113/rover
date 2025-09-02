#!/bin/bash
cd /home/rover/rover || exit
echo "Mise à jour en cours via Git..."
git reset --hard HEAD
git pull origin main

