# main.py
"""
Escaneo WiFi y utilidades.
Devuelve una lista de diccionarios con la info de cada red:
  "SSID", "BSSID", "Señal", "Frecuencia", "Banda", "Canal",
  "Seguridad", "AnchoCanal", "Tecnologia", "Estimacion_m", "Fabricante"
Requiere: pywifi y vendor_lookup.get_vendor (opcional).
"""

import math
import time
from os import system

try:
    import pywifi
    from pywifi import const
except Exception:
    pywifi = None
    const = None

# vendor_lookup debe existir (archivo separado). Si no, la app seguirá sin fabricante.
try:
    from vendor_lookup import get_vendor
except Exception:
    def get_vendor(_):
        return "Desconocido"

# limpiar pantalla (solo para ejecuciones en consola)
try:
    system('cls')
except Exception:
    pass


# ---------- Helpers de frecuencia / canal / banda ----------
def normalize_freq_mhz(raw_freq):
    """Convierte la frecuencia recibida a MHz (int) si es posible."""
    if raw_freq is None:
        return None
    try:
        f = float(raw_freq)
    except Exception:
        return None
    # si vienen en Hz o kHz, convertir
    if f > 1e8:  # Hz
        f = f / 1e6
    elif f > 1e4:  # kHz
        f = f / 1e3
    return int(round(f))


def freq_to_channel(freq_mhz):
    """Convierte frecuencia (MHz) a canal (int) o 'Desconocido'."""
    if not freq_mhz:
        return "Desconocido"
    f = int(round(freq_mhz))
    # 2.4 GHz
    if 2412 <= f <= 2472:
        return 1 + (f - 2412) // 5
    if f == 2484:
        return 14
    # 5 GHz approximate mapping (not exact para todos los países)
    if 5000 <= f <= 5900:
        return (f - 5000) // 5
    # 6 GHz / 5925+ (WiFi 6E)
    if 5925 <= f <= 7125:
        return 1 + (f - 5955) // 5
    return "Desconocido"


def band_from_freq(freq_mhz):
    """Devuelve banda legible según freq en MHz."""
    if not freq_mhz:
        return "Desconocida"
    f = int(round(freq_mhz))
    if 2400 <= f < 2500:
        return "2.4 GHz"
    if 5000 <= f < 5900:
        return "5 GHz"
    if 5925 <= f <= 7125:
        return "6 GHz"
    return "Desconocida"


# ---------- AKM / Seguridad ----------
def akm_to_text(akm_list):
    """
    Convierte lista akm (valores numeric devueltos por pywifi) a texto legible.
    Si pywifi/const no está disponible, intenta devolver una representación básica.
    """
    if not akm_list:
        return "Desconocido"
    mapping = {}
    if const is not None:
        # algunos nombres pueden no existir según versión de pywifi; usaremos get con fallback
        mapping = {
            getattr(const, "AKM_TYPE_NONE", None): "Abierta",
            getattr(const, "AKM_TYPE_WPA", None): "WPA",
            getattr(const, "AKM_TYPE_WPAPSK", None): "WPA-PSK",
            getattr(const, "AKM_TYPE_WPA2", None): "WPA2",
            getattr(const, "AKM_TYPE_WPA2PSK", None): "WPA2-PSK",
            getattr(const, "AKM_TYPE_WPA3", None): "WPA3",
            getattr(const, "AKM_TYPE_UNKNOWN", None): "Desconocido"
        }
    readable = []
    for a in akm_list:
        if a in mapping and mapping[a]:
            readable.append(mapping[a])
        else:
            readable.append(f"AKM({a})")
    # eliminar duplicados manteniendo orden
    seen = set()
    out = []
    for x in readable:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return ", ".join(out) if out else "Desconocido"


# ---------- Estimación de distancia (mejorada) ----------
def fspl_1m_db(freq_mhz):
    c = 3e8
    f_hz = float(freq_mhz) * 1e6
    return 20.0 * math.log10((4.0 * math.pi * 1.0 * f_hz) / c)


def estimate_distance_meters(rssi_dbm, tx_power_dbm=20.0, freq_mhz=2412.0, path_loss_exp=3.2):
    try:
        if rssi_dbm is None:
            return None
        if freq_mhz is None or freq_mhz <= 0:
            freq_mhz = 2412.0
        if rssi_dbm >= -20:
            return 0.05
        pl_d = float(tx_power_dbm) - float(rssi_dbm)
        pl_1m = fspl_1m_db(freq_mhz)
        exponent = (pl_d - pl_1m) / (10.0 * float(path_loss_exp))
        distance = 10.0 ** exponent
        if math.isnan(distance) or distance <= 0:
            return None
        distance = max(0.05, min(distance, 1000.0))
        return round(distance, 2)
    except Exception:
        return None


# ---------- Inferencia de generación tecnológica ----------
def infer_wifi_generation(freq_mhz):
    if freq_mhz is None:
        return "Desconocida"
    f = int(round(freq_mhz))
    if 2400 <= f < 2500:
        return "2.4 GHz (b/g/n)"
    if 5000 <= f < 5900:
        return "5 GHz (ac/ax posible)"
    if 5925 <= f <= 7125:
        return "6 GHz (ax / 6E)"
    return "Desconocida"


# ---------- Inferencia de ancho de canal (heurística) -------------
def infer_channel_width(freq_mhz):
    if freq_mhz is None:
        return "Desconocido"
    f = int(round(freq_mhz))
    if 2400 <= f < 2500:
        return "20 MHz (2.4 GHz, común)"
    if 5000 <= f < 5900:
        return "20/40/80/160 MHz (5 GHz, estimado)"
    if 5925 <= f <= 7125:
        return "20/40/80/160 MHz (6 GHz, estimado)"
    return "Desconocida"


# ---------- Utilidades ----------
def clean_bssid(bssid):
    """Normaliza el BSSID: mayúsculas, ':' entre pares y sin ':' final."""
    if not bssid:
        return ""
    s = bssid.strip().upper().replace("-", ":")
    if s.endswith(":"):
        s = s[:-1]
    parts = [p for p in s.split(":") if p != ""]
    if len(parts) == 6:
        return ":".join(parts)
    raw = "".join(parts)
    if len(raw) >= 12:
        raw = raw[:12]
        return ":".join(raw[i:i+2] for i in range(0, 12, 2))
    return s


# ---------- Escaneo principal ----------
def scan_wifi(tx_power_dbm_default=20.0, path_loss_exp_default=3.2, wait_time=1.2):
    """
    Escanea redes WiFi y devuelve lista de diccionarios con campos:
    SSID, BSSID, Señal, Frecuencia, Banda, Canal, AnchoCanal, Seguridad, Tecnologia, Estimacion_m, Fabricante
    """
    if pywifi is None:
        raise RuntimeError("pywifi no disponible. Instala 'pywifi' para usar scan_wifi().")

    wifi = pywifi.PyWiFi()
    ifaces = wifi.interfaces()
    if not ifaces:
        raise RuntimeError("No se detectó adaptador WiFi.")

    iface = ifaces[0]
    iface.scan()
    time.sleep(wait_time)
    results = iface.scan_results()

    redes = []
    seen = set()
    for net in results:
        ssid = net.ssid or "<Sin nombre>"
        raw_bssid = getattr(net, "bssid", "") or ""
        bssid = clean_bssid(raw_bssid)
        signal = getattr(net, "signal", None)
        freq = normalize_freq_mhz(getattr(net, "freq", None))
        canal = freq_to_channel(freq)
        banda = band_from_freq(freq)

        # Seguridad (AKM) a texto
        akm_raw = getattr(net, "akm", None)
        seguridad = akm_to_text(akm_raw) if akm_raw is not None else "Desconocido"

        # Ancho de canal (heurístico)
        ancho = infer_channel_width(freq)

        # evitar duplicados por (BSSID, canal)
        key = (bssid, canal)
        if key in seen:
            continue
        seen.add(key)

        # estimación de distancia
        est = estimate_distance_meters(signal, tx_power_dbm_default, freq or 2412.0, path_loss_exp_default)

        tecnologia = infer_wifi_generation(freq)

        # fabricante (consulta externa o local)
        fabricante = get_vendor(bssid)

        redes.append({
            "SSID": ssid,
            "BSSID": bssid,
            "Señal": signal,
            "Frecuencia": freq,
            "Banda": banda,
            "Canal": canal,
            "AnchoCanal": ancho,
            "Seguridad": seguridad,
            "Tecnologia": tecnologia,
            "Estimacion_m": est,
            "TxPower_usado": tx_power_dbm_default,
            "PathLossExp": path_loss_exp_default,
            "Fabricante": fabricante
        })

    redes_sorted = sorted(redes, key=lambda x: x.get("Señal", -9999), reverse=True)
    return redes_sorted


# Si ejecutas este archivo directamente, muestra un listado simple
if __name__ == "__main__":
    try:
        redes = scan_wifi()
        for r in redes:
            print(
                f"{r['SSID']} | {r['BSSID']} | Señal: {r['Señal']} dBm | {r['Tecnologia']} | "
                f"Dist: {r['Estimacion_m']} m | AnchoCanal: {r['AnchoCanal']} | AKM: {r['Seguridad']} | fa: {r['Fabricante']}"
            )
    except Exception as e:
        print("Error:", e)
