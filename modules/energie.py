import random

def get_battery_status():
    # Simule la tension et le courant
    return {
        "voltage": round(12.5 + random.uniform(-0.5, 0.5), 2),
        "current": round(0.8 + random.uniform(-0.2, 0.2), 2)
    }
