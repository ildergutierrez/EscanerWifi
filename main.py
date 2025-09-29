# main.py
from os import system
import time
import math
import pywifi
from pywifi import const

system("cls")  # limpiar consola al iniciar

# ----------------- Helpers WiFi -----------------
def normalize_freq_mhz(raw_freq):
    """Convierte la frecuencia recibida (Hz/kHz/MHz) a MHz enteros."""
    try:
        f = float(raw_freq)
    except Exception:
        return None
    if f > 1e8:        # ej. 2462000000 Hz
        f /= 1e6
    elif f > 1e4:      # ej. 2462000 kHz
        f /= 1e3
    return int(round(f))

def freq_to_channel(freq_mhz):
    """Convierte frecuencia (MHz) al número de canal WiFi correspondiente."""
    try:
        f = int(round(freq_mhz))
    except Exception:
        return "Desconocido"
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
    try:
        f = int(round(freq_mhz))
    except Exception:
        return "Desconocida"
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
            # fallback: mostrar el número si no se reconoce
            readable.append(f"Desconocido ({a})")
    # eliminar duplicados manteniendo orden
    return ", ".join(dict.fromkeys(readable)) or "Desconocido"

def clean_bssid(bssid):
    """Limpia el BSSID (MAC) removiendo espacios y ':' al final."""
    if not bssid:
        return None
    return bssid.strip().rstrip(":")

# ----------------- Estimación de distancia -----------------
def fspl_1m_db(freq_mhz):
    """Calcula FSPL (Free-space path loss) a 1 metro para freq en MHz."""
    # FSPL(1m) = 20*log10(4*pi*1*f / c)
    f_hz = float(freq_mhz) * 1e6
    c = 3e8
    fspl = 20.0 * math.log10((4.0 * math.pi * 1.0 * f_hz) / c)
    return fspl

def estimate_distance_meters(rssi_dbm, tx_power_dbm=20.0, freq_mhz=2412.0, path_loss_exp=3.0):
    """
    Estima distancia en metros usando modelo log-distance con referencia a 1m.
    - rssi_dbm: RSSI medido en dBm (ej. -50)
    - tx_power_dbm: potencia de transmisión asumida (dBm). Si no la sabes, usar 20.
    - freq_mhz: frecuencia en MHz (ej. 2412)
    - path_loss_exp: exponente n (2=libre espacio, 2.7-3.5 típico interior)
    Devuelve float (metros) o None si no puede estimar.
    """
    try:
        if rssi_dbm is None:
            return None
        pl_d = float(tx_power_dbm) - float(rssi_dbm)   # pérdida observada (dB)
        pl_1m = fspl_1m_db(freq_mhz)
        exponent = (pl_d - pl_1m) / (10.0 * float(path_loss_exp))
        distance_m = 10.0 ** exponent
        # evitar resultados absurdos
        if distance_m < 0.001:
            distance_m = 0.001
        return float(distance_m)
    except Exception:
        return None

# ----------------- Escaneo principal -----------------
def scan_wifi(tx_power_dbm_default=20.0, path_loss_exp_default=3.0, wait_time=1.5):
    """
    Escanea redes WiFi disponibles y devuelve lista de diccionarios con keys:
      SSID, BSSID, Señal, Frecuencia, Banda, Canal, Seguridad, Estimacion_m, TxPower_usado, PathLossExp
    Parámetros:
      - tx_power_dbm_default: potencia asumida si no se conoce (dBm)
      - path_loss_exp_default: exponente de pérdida (n)
      - wait_time: tiempo en segundos para esperar resultados del scan
    """
    wifis = []
    seen = set()

    wifi = pywifi.PyWiFi()
    interfaces = wifi.interfaces()

    if not interfaces:
        raise RuntimeError("No se detectó ningún adaptador WiFi en el sistema.")

    iface = interfaces[0]
    iface.scan()
    time.sleep(wait_time)
    results = iface.scan_results()

    for network in results:
        ssid = network.ssid or "<Sin nombre>"
        bssid = clean_bssid(network.bssid) or ""
        signal = network.signal  # dBm (normalmente negativo)
        freq_mhz = normalize_freq_mhz(network.freq)
        canal = freq_to_channel(freq_mhz)
        banda = band_from_freq(freq_mhz)
        seguridad = akm_to_text(network.akm)

        unique_key = (ssid, bssid, canal)
        if unique_key in seen:
            continue
        seen.add(unique_key)

        # Estimación de distancia (usamos valores por defecto; puedes cambiarlos)
        est_m = None
        try:
            est_m = estimate_distance_meters(
                rssi_dbm=signal,
                tx_power_dbm=tx_power_dbm_default,
                freq_mhz=freq_mhz or 2412.0,
                path_loss_exp=path_loss_exp_default
            )
        except Exception:
            est_m = None

        wifis.append({
            "SSID": ssid,
            "BSSID": bssid,
            "Señal": signal,
            "Frecuencia": freq_mhz,
            "Banda": banda,
            "Canal": canal,
            "Seguridad": seguridad,
            "Estimacion_m": round(est_m, 2) if est_m is not None else None,
            "TxPower_usado": tx_power_dbm_default,
            "PathLossExp": path_loss_exp_default
        })

    # ordenar por señal (mejor primero)
    wifis = sorted(wifis, key=lambda x: x.get("Señal", -9999), reverse=True)
    return wifis

# Para pruebas rápidas:
# if __name__ == "__main__":
#     redes = scan_wifi()
#     for r in redes:
#         print(r)
