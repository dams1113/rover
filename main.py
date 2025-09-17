# main.py
import threading
import asyncio
import sys
import time

from bot import discord_bot
from modules.gps_reader import start_gps_loop
from modules.gps_logger import log_loop

def main():
    print("[MAIN] 🚀 Démarrage du Rover...")

    # Boucle GPS
    try:
        start_gps_loop()
        print("[MAIN] ✅ Boucle GPS démarrée")
    except Exception as e:
        print(f"[MAIN][ERREUR] GPS loop: {e}", file=sys.stderr)

    # Logger GPS
    try:
        threading.Thread(target=log_loop, args=(30,), daemon=True).start()
        print("[MAIN] 📝 GPS Logger lancé (30s)")
    except Exception as e:
        print(f"[MAIN][ERREUR] GPS logger: {e}", file=sys.stderr)

    # Bot Discord
    try:
        if not discord_bot.TOKEN or discord_bot.TOKEN.strip() == "":
            print("[MAIN][ERREUR] ❌ Aucun TOKEN Discord défini !")
            while True:
                time.sleep(60)
        print("[MAIN] 🌐 Connexion à Discord...")
        asyncio.run(discord_bot.client.start(discord_bot.TOKEN))
    except Exception as e:
        import traceback
        print(f"[MAIN][ERREUR] Le bot Discord a planté : {e}", file=sys.stderr)
        traceback.print_exc()
        while True:  # boucle infinie pour ne pas tuer le service
            time.sleep(60)

if __name__ == "__main__":
    main()
