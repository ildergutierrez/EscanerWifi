# main.py
"""
Escaneo WiFi y utilidades usando netsh (Windows).
Versión corregida para español y formato específico.
"""

import math
import time
import subprocess
import re
import sys
from os import system

# limpiar pantalla
try:
    system('cls')
except Exception:
    pass

# ---------- NUEVA FUNCIÓN: Detección AKM ----------
def get_akm_security(ssid_name):
    """Obtiene información de seguridad AKM del perfil guardado"""
    try:
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'profile', f'name={ssid_name}', 'key=clear'],
            capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=5
        )
        
        if result.returncode != 0:
            return {"seguridad": "Desconocida", "auth": "No disponible", "cipher": "No disponible"}
        
        output = result.stdout
        
        # Buscar autenticación y cifrado
        auth_match = re.search(r'Autenticaci[oó]n\s*:\s*(.+)', output, re.IGNORECASE)
        cipher_match = re.search(r'Cifrado\s*:\s*(.+)', output, re.IGNORECASE)
        
        auth = auth_match.group(1).strip() if auth_match else "No disponible"
        cipher = cipher_match.group(1).strip() if cipher_match else "No disponible"
        
        # Detección AKM
        seguridad = detect_akm_security(auth, cipher, output)
        
        return {
            "seguridad": seguridad,
            "auth": auth,
            "cipher": cipher
        }
        
    except Exception:
        return {"seguridad": "Desconocida", "auth": "No disponible", "cipher": "No disponible"}

def detect_akm_security(auth, cipher, output):
    """Detección específica de AKM"""
    auth_lower = auth.lower() if auth else ""
    cipher_lower = cipher.lower() if cipher else ""
    output_lower = output.lower()
    
    # WPA3
    if 'wpa3' in auth_lower:
        if 'enterprise' in auth_lower:
            return "WPA3-Enterprise"
        elif 'sae' in auth_lower:
            return "WPA3-Personal (SAE)"
        else:
            return "WPA3-Personal"
    
    # WPA2
    if 'wpa2' in auth_lower:
        if 'enterprise' in auth_lower or '802.1x' in output_lower:
            return "WPA2-Enterprise"
        else:
            return "WPA2-Personal"
    
    # WPA
    if 'wpa' in auth_lower:
        if 'enterprise' in auth_lower or '802.1x' in output_lower:
            return "WPA-Enterprise"
        else:
            return "WPA-Personal"
    
    # WEP
    if 'wep' in auth_lower:
        return "WEP"
    
    # OWE
    if 'owe' in auth_lower or 'enhanced open' in auth_lower:
        return "OWE"
    
    # Redes abiertas
    if any(x in auth_lower for x in ['abierta', 'open', 'libre']):
        return "Abierta"
    
    return "Desconocida"

# ---------- Helpers de frecuencia / canal / banda ----------
def normalize_freq_mhz(raw_freq):
    """Convierte la frecuencia recibida a MHz (int) si es posible."""
    if raw_freq is None:
        return None
    try:
        f = float(raw_freq)
    except Exception:
        return None
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
    if 2412 <= f <= 2472:
        return 1 + (f - 2412) // 5
    if f == 2484:
        return 14
    if 5000 <= f <= 5900:
        return (f - 5000) // 5
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

# ---------- Parser MEJORADO para capturar auth y cipher ----------
def parse_netsh_output_corrected(output):
    """
    Parser corregido para capturar autenticación y cifrado del escaneo actual
    """
    redes = []
    
    print("DEBUG - Iniciando parser mejorado")
    
    lines = output.split('\n')
    current_ssid = None
    current_bssid = None
    current_data = {}
    ssid_auth = None
    ssid_cipher = None
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Detectar SSID
        ssid_match = re.match(r'SSID\s+\d+\s*:\s*(.+)', line)
        if ssid_match:
            # Guardar red anterior si existe
            if current_ssid and current_bssid and current_data:
                # Añadir auth y cipher del SSID a los datos de la BSSID
                current_data['auth'] = ssid_auth or ''
                current_data['cipher'] = ssid_cipher or ''
                # OBTENER INFORMACIÓN AKM DEL PERFIL
                akm_info = get_akm_security(current_ssid)
                # Usar AKM si está disponible, sino usar la del escaneo
                if akm_info["seguridad"] != "Desconocida":
                    current_data['seguridad'] = akm_info["seguridad"]
                    current_data['auth'] = akm_info["auth"]
                    current_data['cipher'] = akm_info["cipher"]
                redes.append(create_network_from_data(current_ssid, current_data))
                current_data = {}
            
            current_ssid = ssid_match.group(1).strip()
            ssid_auth = None
            ssid_cipher = None
            print(f"DEBUG - SSID encontrado: '{current_ssid}'")
            i += 1
            continue
        
        # Detectar BSSID
        bssid_match = re.match(r'BSSID\s+\d+\s*:\s*([0-9a-fA-F:-]+)', line)
        if bssid_match and current_ssid:
            # Guardar red anterior si existe
            if current_bssid and current_data:
                # Añadir auth y cipher del SSID a los datos de la BSSID
                current_data['auth'] = ssid_auth or ''
                current_data['cipher'] = ssid_cipher or ''
                # OBTENER INFORMACIÓN AKM DEL PERFIL
                akm_info = get_akm_security(current_ssid)
                if akm_info["seguridad"] != "Desconocida":
                    current_data['seguridad'] = akm_info["seguridad"]
                    current_data['auth'] = akm_info["auth"]
                    current_data['cipher'] = akm_info["cipher"]
                redes.append(create_network_from_data(current_ssid, current_data))
            
            current_bssid = clean_bssid(bssid_match.group(1))
            current_data = {'bssid': current_bssid}
            print(f"DEBUG - BSSID encontrado: {current_bssid}")
            i += 1
            continue
        
        # Capturar autenticación del SSID (está en el bloque del SSID)
        if current_ssid and ('autenticacin' in line.lower() or 'autenticación' in line.lower() or 'authentication' in line.lower()):
            auth_match = re.search(r':\s*(.+)', line)
            if auth_match:
                ssid_auth = auth_match.group(1).strip()
                print(f"DEBUG - Autenticación capturada: '{ssid_auth}'")
        
        # Capturar cifrado del SSID (está en el bloque del SSID)
        if current_ssid and ('cifrado' in line.lower() or 'encryption' in line.lower()):
            cipher_match = re.search(r':\s*(.+)', line)
            if cipher_match:
                ssid_cipher = cipher_match.group(1).strip()
                print(f"DEBUG - Cifrado capturado: '{ssid_cipher}'")
        
        # Procesar información de señal y canal para la BSSID actual
        if current_bssid and current_ssid:
            # Señal
            if 'seal' in line.lower() or 'signal' in line.lower():
                sig_match = re.search(r'(\d+)%', line)
                if sig_match:
                    current_data['signal'] = int(sig_match.group(1))
                    print(f"DEBUG - Señal: {current_data['signal']}%")
            
            # Canal
            elif 'canal' in line.lower() or 'channel' in line.lower():
                chan_match = re.search(r'(\d+)', line)
                if chan_match:
                    current_data['channel'] = int(chan_match.group(1))
                    print(f"DEBUG - Canal: {current_data['channel']}")
        
        i += 1
    
    # Guardar la última red procesada
    if current_ssid and current_bssid and current_data:
        # Añadir auth y cipher del SSID a los datos de la BSSID
        current_data['auth'] = ssid_auth or ''
        current_data['cipher'] = ssid_cipher or ''
        # OBTENER INFORMACIÓN AKM DEL PERFIL
        akm_info = get_akm_security(current_ssid)
        if akm_info["seguridad"] != "Desconocida":
            current_data['seguridad'] = akm_info["seguridad"]
            current_data['auth'] = akm_info["auth"]
            current_data['cipher'] = akm_info["cipher"]
        redes.append(create_network_from_data(current_ssid, current_data))
    
    print(f"DEBUG - Parser completado. {len(redes)} redes encontradas")
    return redes

def create_network_from_data(ssid, data):
    """Crea diccionario de red desde datos parseados"""
    signal_dbm = percentage_to_dbm(data.get('signal', 0))
    channel = data.get('channel')
    freq = channel_to_freq(channel)
    
    # Usar seguridad AKM si está disponible, sino calcularla
    if 'seguridad' in data and data['seguridad'] != "Desconocida":
        seguridad = data['seguridad']
        auth = data.get('auth', '')
        cipher = data.get('cipher', '')
    else:
        # Usar get con valor por defecto para evitar None
        auth = data.get('auth', '')
        cipher = data.get('cipher', '')
        # Detectar seguridad
        seguridad = parse_security_corrected(auth, cipher)
    
    print(f"DEBUG create_network_from_data - auth: '{auth}', cipher: '{cipher}', seguridad: '{seguridad}'")
    
    return {
        "SSID": ssid,
        "BSSID": data['bssid'],
        "Señal": signal_dbm,
        "Frecuencia": freq,
        "Banda": band_from_freq(freq),
        "Canal": channel,
        "AnchoCanal": infer_channel_width(freq),
        "Seguridad": seguridad,
        "Autenticación": auth,
        "Cifrado": cipher,
        "Tecnologia": infer_wifi_generation(freq)
    }

def parse_security_corrected(auth, cipher):
    """Parser de seguridad corregido - maneja strings vacíos en lugar de None"""
    # Convertir a string vacío si es None
    auth_str = auth if auth is not None else ''
    cipher_str = cipher if cipher is not None else ''
    
    auth_lower = auth_str.lower().strip()
    cipher_lower = cipher_str.lower().strip()
    
    print(f"DEBUG parse_security - auth: '{auth_lower}', cipher: '{cipher_lower}'")
    
    # Redes abiertas - patrones en español
    if any(x in auth_lower for x in ['abierta', 'open', 'libre']):
        if any(x in cipher_lower for x in ['ninguna', 'none', 'no']):
            return "Abierta"
        return "Abierta"
    
    # Si no hay autenticación especificada pero el cifrado es "ninguna", es abierta
    if not auth_lower and any(x in cipher_lower for x in ['ninguna', 'none']):
        return "Abierta"
    
    # WPA2
    if 'wpa2' in auth_lower:
        return "WPA2-PSK"
    
    # WPA
    if 'wpa' in auth_lower:
        return "WPA-PSK"
    
    # WEP
    if 'wep' in auth_lower:
        return "WEP"
    
    # Si no se reconoce nada, intentar con AKM del perfil
    return "Desconocida"

# ---------- Estimación de distancia ----------
def fspl_1m_db(freq_mhz):
    """Calcula la pérdida de trayectoria en espacio libre a 1 metro"""
    c = 3e8
    f_hz = float(freq_mhz) * 1e6
    return 20.0 * math.log10((4.0 * math.pi * 1.0 * f_hz) / c)

def estimate_distance_realistic(rssi_dbm, freq_mhz=2412.0, environment="indoor"):
    """Calcula distancia basada en RSSI"""
    try:
        if rssi_dbm is None or rssi_dbm >= 0:
            return None
            
        if freq_mhz is None or freq_mhz <= 0:
            freq_mhz = 2412.0
            
        # Parámetros según banda
        if 2400 <= freq_mhz <= 2500:
            tx_power_dbm = 20.0
            antenna_gain_tx = 2.0
        elif 5000 <= freq_mhz <= 5900:
            tx_power_dbm = 23.0
            antenna_gain_tx = 3.0
        elif 5925 <= freq_mhz <= 7125:
            tx_power_dbm = 24.0
            antenna_gain_tx = 4.0
        else:
            tx_power_dbm = 20.0
            antenna_gain_tx = 2.0
        
        # Configuración de ambiente
        if environment == "free_space":
            path_loss_exp = 2.0
            shadow_margin = 0.0
        elif environment == "outdoor":
            path_loss_exp = 2.7
            shadow_margin = 5.0
        else:
            path_loss_exp = 3.5
            shadow_margin = 10.0
        
        if freq_mhz > 5000:
            path_loss_exp += 0.3
            shadow_margin += 2.0
        
        loss_1m = fspl_1m_db(freq_mhz)
        effective_tx_power = tx_power_dbm + antenna_gain_tx
        total_loss = float(effective_tx_power) - float(rssi_dbm) - shadow_margin
        
        if total_loss <= loss_1m:
            return 0.1
            
        exponent = (total_loss - loss_1m) / (10.0 * path_loss_exp)
        distance = 10.0 ** exponent
        
        if math.isnan(distance) or distance <= 0:
            return None
        
        # Límites por ambiente
        if environment == "indoor":
            max_distance = 50.0
        elif environment == "outdoor":
            max_distance = 150.0
        else:
            max_distance = 300.0

        if freq_mhz > 5000:
            max_distance *= 0.7
            
        distance = max(0.1, min(distance, max_distance))
        return round(distance, 1)
        
    except Exception:
        return None


# ---------- Detección de ambiente ----------
def detect_environment(redes):
    """Detecta el tipo de ambiente basado en las redes escaneadas"""
    if not redes:
        return "indoor"
    
    strong_networks = sum(1 for net in redes if net.get("Señal", -100) > -50)
    return "indoor" if strong_networks >= 3 else "outdoor"


# ---------- Tecnología y ancho de canal ----------
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


def infer_channel_width(freq_mhz):
    if freq_mhz is None:
        return "Desconocido"
    f = int(round(freq_mhz))
    if 2400 <= f < 2500:
        return "20 MHz"
    if 5000 <= f < 5900:
        return "20/40/80 MHz"
    if 5925 <= f <= 7125:
        return "20/40/80/160 MHz"
    return "Desconocido"


# ---------- Utilidades ----------
def clean_bssid(bssid):
    """Normaliza el BSSID"""
    if not bssid:
        return ""
    s = bssid.strip().upper().replace("-", ":")
    parts = [p for p in s.split(":") if p != ""]
    if len(parts) == 6:
        return ":".join(parts)
    raw = "".join(parts)
    if len(raw) >= 12:
        raw = raw[:12]
        return ":".join(raw[i:i+2] for i in range(0, 12, 2))
    return s


def percentage_to_dbm(percentage):
    """Convierte porcentaje de señal a dBm (aproximado)"""
    if percentage >= 100:
        return -20
    elif percentage <= 0:
        return -100
    else:
        # Curva no lineal más realista
        return round(-20 - (80 * ((100 - percentage) / 100) ** 1.5), 1)


def channel_to_freq(channel):
    """Convierte número de canal a frecuencia en MHz"""
    if not channel:
        return None
        
    try:
        channel = int(channel)
    except (ValueError, TypeError):
        return None
        
    if channel == 14:
        return 2484
    elif 1 <= channel <= 13:
        return 2412 + (channel - 1) * 5
    elif 36 <= channel <= 64:
        return 5180 + (channel - 36) * 20
    elif 100 <= channel <= 144:
        return 5500 + (channel - 100) * 20
    elif 149 <= channel <= 165:
        return 5745 + (channel - 149) * 20
    elif 169 <= channel <= 196:
        return 5845 + (channel - 169) * 20
    return None


# ---------- Escaneo principal ----------
def scan_wifi_netsh(environment="auto"):
    """
    Escanea redes WiFi usando netsh con soporte para español
    """
    try:
        print("Ejecutando escaneo WiFi...")
        
        # Ejecutar comando netsh
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=45
        )
        
        if result.returncode != 0:
            print(f"Error en netsh (código {result.returncode})")
            if result.stderr:
                print("Stderr:", result.stderr)
            return []
        
        output = result.stdout
        
        # Verificar si hay redes
        if "No hay redes inalámbricas" in output or "No wireless networks" in output:
            print("No se encontraron redes inalámbricas en el área")
            return []
        
        # Usar parser corregido
        redes = parse_netsh_output_corrected(output)
        
        if not redes:
            print("No se pudieron parsear redes. Verificando formato de salida...")
            return []
        
        # Detectar ambiente y calcular distancias
        detected_env = detect_environment(redes) if environment == "auto" else environment
        
        for red in redes:
            est = estimate_distance_realistic(
                red["Señal"], 
                red["Frecuencia"] or 2412.0, 
                detected_env
            )
            red.update({
                "Estimacion_m": est,
                "Ambiente": detected_env
            })

        return sorted(redes, key=lambda x: x.get("Señal", -9999), reverse=True)
        
    except subprocess.TimeoutExpired:
        print("Tiempo de espera agotado para el escaneo WiFi")
        return []
    except Exception as e:
        print(f"Error inesperado: {e}")
        return []


# ---------- Funciones de compatibilidad ----------
def scan_wifi_realistic(wait_time=1.2, environment="auto"):
    return scan_wifi_netsh(environment=environment)


def scan_wifi(tx_power_dbm_default=20.0, path_loss_exp_default=3.2, wait_time=1.2):
    return scan_wifi_netsh(environment="auto")


# ---------- Función principal ----------
if __name__ == "__main__":
    try:
        print("Escaneando redes WiFi con netsh (Windows)...")
        print("Esto puede tomar hasta 45 segundos...")
        
        # Verificar que netsh existe
        try:
            subprocess.run(['netsh', '/?'], capture_output=True, timeout=5)
        except FileNotFoundError:
            print("ERROR: 'netsh' no encontrado. Este script solo funciona en Windows.")
            sys.exit(1)
        
        redes = scan_wifi_netsh(environment="auto")
        
        print(f"\n{'='*80}")
        print(f"ESCANEO COMPLETADO - {len(redes)} redes encontradas")
        if redes:
            print(f"Ambiente detectado: {redes[0]['Ambiente']}")
        print(f"{'='*80}")
        
        if redes:
            for i, r in enumerate(redes, 1):
                print(f"\n--- Red #{i} ---")
                print(f"SSID: {r['SSID']}")
                print(f"BSSID: {r['BSSID']}")
                print(f"Señal: {r['Señal']} dBm")
                if r['Frecuencia']:
                    print(f"Frecuencia: {r['Frecuencia']} MHz")
                print(f"Banda: {r['Banda']}")
                if r['Canal']:
                    print(f"Canal: {r['Canal']}")
                print(f"Seguridad: {r['Seguridad']}")
                print(f"Autenticación: {r['Autenticación']}")
                print(f"Cifrado: {r['Cifrado']}")
                print(f"Ancho de canal: {r['AnchoCanal']}")
                if r['Estimacion_m']:
                    print(f"Distancia estimada: {r['Estimacion_m']} metros")
                print(f"Tecnología: {r['Tecnologia']}")
                print(f"Ambiente: {r['Ambiente']}")
        else:
            print("\nNo se encontraron redes. Posibles causas:")
            print("1. El adaptador WiFi está apagado")
            print("2. No hay redes disponibles en el área")
            print("3. Problemas de permisos (ejecutar como administrador)")
            print("4. El controlador WiFi no funciona correctamente")
            
    except Exception as e:
        print(f"Error durante el escaneo: {e}")