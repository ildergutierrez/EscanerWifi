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


# ---------- Estimación de distancia MEJORADA ----------
def fspl_1m_db(freq_mhz):
    """Calcula la pérdida de trayectoria en espacio libre a 1 metro"""
    c = 3e8
    f_hz = float(freq_mhz) * 1e6
    return 20.0 * math.log10((4.0 * math.pi * 1.0 * f_hz) / c)

def estimate_distance_realistic(rssi_dbm, freq_mhz=2412.0, environment="indoor"):
    """
    Calcula distancia basada en RSSI usando modelo mejorado con parámetros realistas
    
    Args:
        rssi_dbm: Señal recibida en dBm
        freq_mhz: Frecuencia en MHz
        environment: Tipo de ambiente ("indoor", "outdoor", "free_space")
    """
    try:
        if rssi_dbm is None or rssi_dbm >= 0:
            return None
            
        # Parámetros REALES basados en equipos comerciales
        if freq_mhz is None or freq_mhz <= 0:
            freq_mhz = 2412.0
            
        # Potencias de transmisión REALES según estándares y equipos
        if 2400 <= freq_mhz <= 2500:  # 2.4 GHz
            tx_power_dbm = 20.0  # Típico para routers 2.4GHz (100mW)
            antenna_gain_tx = 2.0  # Ganancia típica antena router (2-3 dBi)
            antenna_gain_rx = 0.0  # Ganancia antena dispositivo cliente
        elif 5000 <= freq_mhz <= 5900:  # 5 GHz
            tx_power_dbm = 23.0  # Típico para routers 5GHz (200mW)
            antenna_gain_tx = 3.0  # Mayor ganancia en 5GHz
            antenna_gain_rx = 0.0
        elif 5925 <= freq_mhz <= 7125:  # 6 GHz
            tx_power_dbm = 24.0  # WiFi 6E puede usar más potencia
            antenna_gain_tx = 4.0
            antenna_gain_rx = 0.0
        else:
            tx_power_dbm = 20.0
            antenna_gain_tx = 2.0
            antenna_gain_rx = 0.0
        
        # Exponentes de pérdida REALES según ambiente
        if environment == "free_space":
            path_loss_exp = 2.0  # Espacio libre (teórico)
            shadow_margin = 0.0  # Sin desvanecimiento
        elif environment == "outdoor":
            path_loss_exp = 2.7  # Exterior con algunos obstáculos
            shadow_margin = 5.0  # Margen por sombra
        else:  # indoor (default)
            path_loss_exp = 3.5  # Interior con paredes (más realista)
            shadow_margin = 10.0  # Mayor margen por obstáculos
        
        # Ajustar exponente por frecuencia (mayor frecuencia = mayor atenuación)
        if freq_mhz > 5000:  # 5 GHz y 6 GHz
            path_loss_exp += 0.3  # Mayor atenuación en frecuencias altas
            shadow_margin += 2.0
        
        # Pérdida a 1 metro (referencia)
        loss_1m = fspl_1m_db(freq_mhz)
        
        # Potencia efectiva considerando ganancias de antena
        effective_tx_power = tx_power_dbm + antenna_gain_tx + antenna_gain_rx
        
        # Pérdida total medida (considerando margen de sombra)
        total_loss = float(effective_tx_power) - float(rssi_dbm) - shadow_margin
        
        # Fórmula de distancia realista
        if total_loss <= loss_1m:
            return 0.1  # Distancia mínima
            
        # Despejar distancia: d = 10^((PL(d) - PL(1m)) / (10 * n))
        exponent = (total_loss - loss_1m) / (10.0 * path_loss_exp)
        distance = 10.0 ** exponent
        
        if math.isnan(distance) or distance <= 0:
            return None
        
        # Límites REALISTAS según ambiente y frecuencia
        if environment == "indoor":
            max_distance = 50.0  # Interior típico
        elif environment == "outdoor":
            max_distance = 150.0  # Exterior sin obstáculos
        else:
            max_distance = 300.0  # Espacio libre teórico
        
        # Reducir distancia máxima para frecuencias altas
        if freq_mhz > 5000:
            max_distance *= 0.7  # 30% menos en 5GHz
        if freq_mhz > 5900:
            max_distance *= 0.6  # 40% menos en 6GHz
            
        distance = max(0.1, min(distance, max_distance))
        
        return round(distance, 1)
        
    except Exception:
        return None

# ---------- Función para detectar ambiente automáticamente ----------
def detect_environment(redes):
    """
    Detecta el tipo de ambiente basado en las redes escaneadas
    """
    if not redes:
        return "indoor"
    
    # Contar redes fuertes (señal > -50 dBm)
    strong_networks = sum(1 for net in redes if net.get("Señal", -100) > -50)
    
    if strong_networks >= 3:
        return "indoor"  # Muchas redes fuertes = interior
    else:
        return "outdoor"  # Pocas redes = posible exterior

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


# ---------- Escaneo principal MEJORADO ----------
def scan_wifi_realistic(wait_time=1.2, environment="auto"):
    """
    Escanea redes WiFi con estimación de distancia REALISTA
    Devuelve lista de diccionarios con campos:
    SSID, BSSID, Señal, Frecuencia, Banda, Canal, AnchoCanal, Seguridad, 
    Tecnologia, Estimacion_m, Ambiente
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
    
    # Primera pasada: recolectar todas las redes básicas
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

        tecnologia = infer_wifi_generation(freq)

        redes.append({
            "SSID": ssid,
            "BSSID": bssid,
            "Señal": signal,
            "Frecuencia": freq,
            "Banda": banda,
            "Canal": canal,
            "AnchoCanal": ancho,
            "Seguridad": seguridad,
            "Tecnologia": tecnologia
        })

    # Detectar ambiente si es automático
    if environment == "auto":
        detected_env = detect_environment(redes)
    else:
        detected_env = environment

    # Segunda pasada: calcular distancias con ambiente detectado
    for red in redes:
        est = estimate_distance_realistic(
            red["Señal"], 
            red["Frecuencia"] or 2412.0, 
            detected_env
        )
        
        # Agregar campos calculados
        red.update({
            "Estimacion_m": est,
            "Ambiente": detected_env
        })

    redes_sorted = sorted(redes, key=lambda x: x.get("Señal", -9999), reverse=True)
    return redes_sorted
# Función original mantenida para compatibilidad
def scan_wifi(tx_power_dbm_default=20.0, path_loss_exp_default=3.2, wait_time=1.2):
    """
    Función legacy - usa scan_wifi_realistic por defecto
    """
    return scan_wifi_realistic(wait_time=wait_time, environment="auto")


# Si ejecutas este archivo directamente, muestra un listado simple
# if __name__ == "__main__":
#     try:
#         print("Escaneando redes WiFi con estimación realista...")
#         redes = scan_wifi_realistic(environment="auto")
        
#         print(f"\n{'='*80}")
#         print(f"ESCANEO COMPLETADO - {len(redes)} redes encontradas")
#         print(f"Ambiente detectado: {redes[0]['Ambiente'] if redes else 'N/A'}")
#         print(f"{'='*80}")
        
#         for i, r in enumerate(redes, 1):
#             print(f"\n--- Red #{i} ---")
#             print(f"SSID: {r['SSID']}")
#             print(f"BSSID: {r['BSSID']}")
#             print(f"Señal: {r['Señal']} dBm")
#             print(f"Frecuencia: {r['Frecuencia']} MHz")
#             print(f"Banda: {r['Banda']}")
#             print(f"Canal: {r['Canal']}")
#             print(f"Seguridad: {r['Seguridad']}")
#             print(f"Ancho de canal: {r['AnchoCanal']}")
#             print(f"Distancia estimada: {r['Estimacion_m']} metros")
#             print(f"Tecnología: {r['Tecnologia']}")
#             print(f"Ambiente: {r['Ambiente']}")
            
#     except Exception as e:
#         print("Error durante el escaneo:", e)