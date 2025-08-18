import serial

def parse_gpgga(line):
    try:
        parts = line.split(',')
        if parts[0] != "$GPGGA":
            return None

        lat_raw = parts[2]
        lat_dir = parts[3]
        lon_raw = parts[4]
        lon_dir = parts[5]
        fix = parts[6]
        sats = parts[7]
        altitude = parts[9]

        lat = convert_to_decimal(lat_raw, lat_dir)
        lon = convert_to_decimal(lon_raw, lon_dir)
        altitude = float(altitude) if altitude else None
        fix_status = "OK" if fix == "1" else "NOK"

        return {
            "latitude": lat,
            "longitude": lon,
            "altitude": altitude,
            "satellites": int(sats),
            "fix": fix_status
        }

    except Exception as e:
        return {"error": str(e)}

def convert_to_decimal(coord, direction):
    if not coord:
        return None
    deg = int(float(coord) / 100)
    min = float(coord) - deg * 100
    decimal = deg + min / 60
    if direction in ['S', 'W']:
        decimal = -decimal
    return round(decimal, 6)

def get_gps_data():
    try:
        with serial.Serial("/dev/serial0", 9600, timeout=1) as ser:
            for _ in range(10):
                line = ser.readline().decode("ascii", errors="replace").strip()
                if "$GPGGA" in line:
                    return parse_gpgga(line)
        return {"error": "Pas de trame GPGGA reçue"}
    except FileNotFoundError:
        return {"error": "capteur absent ou non branché"}
    except serial.SerialException as e:
        return {"error": f"Erreur série : {e}"}
    except Exception as e:
        return {"error": f"Erreur GPS : {e}"}
