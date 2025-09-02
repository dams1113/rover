#!/bin/bash
cd /home/rover/rover || exit
<<<<<<< HEAD
echo "Mise à jour en cours via Git..."
=======
echo " Mise à jour en cours via Git..."
>>>>>>> 63d386e41cdb4bbdaeb2a1e58f980c6746164e85
git reset --hard HEAD
git pull origin main

