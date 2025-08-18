def avance():
    print("[MOTEUR] Avance")

def recule():
    print("[MOTEUR] Recule")

def stop():
    print("[MOTEUR] Stop")

def handle_movement(cmd):
    print(f"[MOTEUR] Commande reçue : {cmd}")

    if cmd == "AVANCE":
        avance()
    elif cmd == "RECULE":
        recule()
    elif cmd == "STOP":
        stop()
    else:
        print("[MOTEUR] Commande inconnue")
