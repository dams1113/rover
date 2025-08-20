import subprocess
import shutil
import time
import os

P_IDLE = 2.7
P_FULL = 7.0
P_IO_BASE = 0.5
F_MAX = 1500000000
TEMP_REF = 40.0
TEMP_COEF = 0.01
NET_W_PER_MBPS = 0.02

def read_proc_stat_total_idle():
    with open("/proc/stat", "r") as f:
        line = f.readline()
    parts = line.split()
    vals = list(map(int, parts[1:]))
    total = sum(vals[:8])
    idle = vals[3] + vals[4]
    return total, idle

def get_cpu_percent(period=0.5):
    t1, i1 = read_proc_stat_total_idle()
    time.sleep(period)
    t2, i2 = read_proc_stat_total_idle()
    dt = max(1, t2 - t1)
    didle = i2 - i1
    return max(0.0, min(100.0, (1.0 - (didle / dt)) * 100.0))

def get_cpu_freq():
    try:
        out = subprocess.check_output(["vcgencmd", "measure_clock", "arm"], text=True).strip()
        return int(out.split("=")[-1])
    except:
        return F_MAX

def get_temp_c():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            millic = int(f.read().strip())
        return millic / 1000.0
    except:
        return 45.0

def read_net_bytes():
    total = 0
    try:
        with open("/proc/net/dev", "r") as f:
            for line in f:
                if ":" not in line:
                    continue
                iface, data = line.split(":")
                if iface.strip() == "lo":
                    continue
                parts = data.split()
                total += int(parts[0]) + int(parts[8])
    except:
        pass
    return total

def get_power_estimate():
    cpu = get_cpu_percent()
    freq = get_cpu_freq()
    temp = get_temp_c()

    # Simple net bandwidth (optional)
    b1 = read_net_bytes()
    time.sleep(0.5)
    b2 = read_net_bytes()
    mbps = ((b2 - b1) * 8) / (1024 * 1024) / 0.5  # Mbps

    L = max(0.0, min(1.0, cpu / 100.0))
    f = max(0.0, min(1.0, freq / float(F_MAX)))
    dT = max(0.0, temp - TEMP_REF)
    p_temp = dT * TEMP_COEF
    p_net = mbps * NET_W_PER_MBPS
    p = P_IDLE + P_IO_BASE + (P_FULL - P_IDLE) * L * f + p_temp + p_net

    return round(p, 2)  # Puissance estimée en watts
