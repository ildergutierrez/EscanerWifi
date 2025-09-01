from os import system
import pywifi
from pywifi import const
import time

# Librerías necesarias
# pip install pywifi
# pip install comtypes
# pip install pywin32

# --- Funciones auxiliares ---
def normalize_freq_mhz(raw_freq):
    """Devuelve frecuencia en MHz a partir de valor en Hz/kHz/MHz."""
    f = float(raw_freq)
    if f > 1e8:        # ej. 2462000000 Hz
        f = f / 1e6
    elif f > 1e4:      # ej. 2462000 kHz
        f = f / 1e3
    return round(f)

def freq_to_channel(freq_mhz):
    f = int(round(freq_mhz))
    # print("entro: ", f)
    # 2.4 GHz
    if 2412 <= f <= 2472:
        return 1 + (f - 2412) // 5
    if f == 2484:
        return 14
    # 5 GHz
    if 5000 <= f <= 5900:
        return (f - 5000) // 5
    # 6 GHz (WiFi 6E)
    if 5925 <= f <= 7125:
        return 1 + (f - 5955) // 5
    return "Desconocido"

def band_from_freq(freq_mhz):
    f = int(round(freq_mhz))
    if 2400 <= f < 2500:
        return "2.4 GHz"
    if 5000 <= f < 5900:
        return "5 GHz"
    if 5925 <= f <= 7125:
        return "6 GHz"
    return "Desconocida"

def akm_to_text(akm_list):
    """Convierte la lista akm (códigos) a una cadena legible."""
    mapping = {
        const.AKM_TYPE_NONE: "Abierta",
        const.AKM_TYPE_WPA: "WPA",
        const.AKM_TYPE_WPAPSK: "WPA-PSK",
        const.AKM_TYPE_WPA2: "WPA2",
        const.AKM_TYPE_WPA2PSK: "WPA2-PSK",
    }
    readable = []
    for a in akm_list:
        if a in mapping:
            readable.append(mapping[a])
        else:
            if a == 4:  # fallback común: WPA2-PSK
                readable.append("WPA2-PSK")
            else:
                readable.append(f"Desconocido ({a})")
    return ", ".join(dict.fromkeys(readable))

def clean_bssid(bssid):
    return bssid.strip().rstrip(":")

# --- Escaneo WiFi ---
def scan_wifi():
    wifis = []
    wifi = pywifi.PyWiFi()
    iface = wifi.interfaces()[0]

    iface.scan()
    # time.sleep(3)
    results = iface.scan_results()

    for network in results:
        ssid = network.ssid
        bssid = clean_bssid(network.bssid)
        signal = network.signal
        freq_mhz = normalize_freq_mhz(network.freq)
        canal = freq_to_channel(freq_mhz)
        banda = band_from_freq(freq_mhz)
        seguridad = akm_to_text(network.akm)

        wifis.append([ssid, bssid, signal, freq_mhz, banda, canal, seguridad])

    return wifis

# --- Main ---
if __name__ == "__main__":
    while True:
        system("cls")
        try:
            redes = scan_wifi()
            for wifi in redes:
                print(f"SSID: {wifi[0]}")
                print(f"BSSID (MAC): {wifi[1]}")
                print(f"Señal: {wifi[2]} dBm")
                print(f"Frecuencia: {wifi[3]} MHz")
                print(f"Banda: {wifi[4]}")
                print(f"Canal: {wifi[5]}")
                print(f"Seguridad: {wifi[6]}\n")
                print("-" * 40)
            print(f"Total de redes encontradas: {len(redes)}")
            time.sleep(1)
        except:
            print("Activa el wi-fi")
            time.sleep(1)