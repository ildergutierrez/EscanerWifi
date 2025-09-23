# main.py
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
    """Convierte la frecuencia recibida (Hz/kHz/MHz) a MHz enteros."""
    f = float(raw_freq)
    if f > 1e8:        # ej. 2462000000 Hz
        f /= 1e6
    elif f > 1e4:      # ej. 2462000 kHz
        f /= 1e3
    return round(f)

def freq_to_channel(freq_mhz):
    """Convierte frecuencia (MHz) al número de canal WiFi correspondiente."""
    f = int(round(freq_mhz))
    if 2412 <= f <= 2472:
        return 1 + (f - 2412) // 5   # Banda 2.4 GHz
    if f == 2484:
        return 14
    if 5000 <= f <= 5900:
        return (f - 5000) // 5       # Banda 5 GHz
    if 5925 <= f <= 7125:
        return 1 + (f - 5955) // 5   # Banda 6 GHz (WiFi 6E)
    return "Desconocido"

def band_from_freq(freq_mhz):
    """Devuelve la banda en función de la frecuencia."""
    f = int(round(freq_mhz))
    if 2400 <= f < 2500:
        return "2.4 GHz"
    if 5000 <= f < 5900:
        return "5 GHz"
    if 5925 <= f <= 7125:
        return "6 GHz"
    return "Desconocida"

def akm_to_text(akm_list):
    """Convierte la lista AKM (códigos de seguridad) en texto legible."""
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
    return ", ".join(dict.fromkeys(readable)) or "Desconocido"

def clean_bssid(bssid):
    """Limpia el BSSID (MAC) removiendo espacios y ':' al final."""
    return bssid.strip().rstrip(":")

# --- Escaneo WiFi ---
def scan_wifi():
    """
    Escanea las redes WiFi disponibles.

    Returns:
        list[dict]: Lista de redes encontradas, cada una con:
            {
                "SSID": str,
                "BSSID": str,
                "Señal": int (dBm),
                "Frecuencia": int (MHz),
                "Banda": str,
                "Canal": int | str,
                "Seguridad": str
            }
    """
    system('cls')# Limpiar consola
    wifis = []
    seen = set()

    wifi = pywifi.PyWiFi()
    interfaces = wifi.interfaces()

    if not interfaces:
        raise RuntimeError("No se detectó ningún adaptador WiFi en el sistema.")

    iface = interfaces[0]
    iface.scan()
    time.sleep(1.5)  # esperar un poco más para resultados consistentes
    results = iface.scan_results()

    for network in results:
        ssid = network.ssid or "<Sin nombre>"
        bssid = clean_bssid(network.bssid)
        signal = network.signal
        freq_mhz = normalize_freq_mhz(network.freq)
        canal = freq_to_channel(freq_mhz)
        banda = band_from_freq(freq_mhz)
        seguridad = akm_to_text(network.akm)

        unique_key = (ssid, bssid, canal)
        if unique_key not in seen:
            seen.add(unique_key)
            wifis.append({
                "SSID": ssid,
                "BSSID": bssid,
                "Señal": signal,
                "Frecuencia": freq_mhz,
                "Banda": banda,
                "Canal": canal,
                "Seguridad": seguridad,
            })

    # 🔥 Ordenar por señal (mejor primero)
    return sorted(wifis, key=lambda x: x["Señal"], reverse=True)

'''if __name__ == "__main__":
        # Prueba rápida
    redes = scan_wifi()
    for r in redes:
        print(r)
'''