import datetime

def log(message):
    with open("/home/pi/rover/log.txt", "a") as f:
        f.write(f"[{datetime.datetime.now()}] {message}\n")
    print(message)
