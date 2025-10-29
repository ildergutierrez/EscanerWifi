import subprocess
import platform
import re
import time
import json
import threading
from typing import Dict, List, Optional
import socket
import threading
from datetime import datetime, timedelta
from network_status import is_connected_to_network, get_current_network_info

# ----------------------------------------------------------------------
# Cache y base de datos de fabricantes (sin cambios)
# ----------------------------------------------------------------------
device_cache = {}
CACHE_DURATION = 120  # 3 minutos

def _load_vendor_database():
    try:
        with open('vendor_database.json', 'r') as f:
            return json.load(f)
    except:
        return {}

VENDOR_DB = _load_vendor_database()

# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def _is_valid_mac(mac: str) -> bool:
    if not mac:
        return False
    mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
    return re.match(mac_pattern, mac) is not None

def _is_valid_ip(ip: str) -> bool:
    if not ip:
        return False
    try:
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        for p in parts:
            if not p.isdigit() or not 0 <= int(p) <= 255:
                return False
        if ip.startswith('127.') or ip.startswith('169.254.') \
           or ip == '255.255.255.255' or ip == '0.0.0.0':
            return False
        return True
    except:
        return False

def _ping_ip_fast(ip: str) -> bool:
    try:
        param = '-n' if platform.system().lower() == "windows" else '-c'
        w = '-w' if platform.system().lower() == "windows" else '-W'
        cmd = ['ping', param, '1', w, '1', ip]
        result = subprocess.run(cmd, capture_output=True, timeout=2)
        return result.returncode == 0
    except:
        return False

def _check_device_ports(ip: str, ports: List[int] = None) -> bool:
    if ports is None:
        ports = [80, 443, 22, 135, 139, 445]
    for port in ports[:2]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex((ip, port)) == 0:
                    return True
        except:
            continue
    return False

def _get_mac_from_arp_fast(ip: str) -> Optional[str]:
    try:
        result = subprocess.run(['arp', '-a', ip], capture_output=True,
                                text=True, timeout=2)
        if result.returncode == 0:
            m = re.search(r'([0-9A-Fa-f:-]{17})', result.stdout)
            if m:
                mac = m.group(1).upper().replace('-', ':')
                if _is_valid_mac(mac):
                    return mac
    except:
        pass
    return None

def _get_default_gateway() -> Optional[str]:
    """Gateway por defecto (solo Windows/Linux)"""
    try:
        if platform.system().lower() == "windows":
            res = subprocess.run(['route', 'print', '0.0.0.0'],
                                 capture_output=True, text=True,
                                 encoding='cp850', errors='replace')
            for line in res.stdout.splitlines():
                if '0.0.0.0' in line:
                    parts = re.split(r'\s+', line)
                    if len(parts) > 2:
                        return parts[2]
        else:
            res = subprocess.run(['ip', 'route', 'show', 'default'],
                                 capture_output=True, text=True)
            m = re.search(r'default via ([\d.]+)', res.stdout)
            if m:
                return m.group(1)
    except:
        pass
    return None

def _get_common_ips(base_ip: str) -> List[str]:
    common = [f"{base_ip}.1", f"{base_ip}.254"]
    for i in range(2, 30):
        common.append(f"{base_ip}.{i}")
    return common

# ----------------------------------------------------------------------
# Creación y clasificación de dispositivos
# ----------------------------------------------------------------------
def _create_device_info(ip: str, mac: str) -> Dict:
    device_type = _classify_device_type(mac)
    vendor = _get_vendor_from_mac(mac)
    return {
        'ip': ip,
        'mac': mac,
        'type': device_type,
        'vendor': vendor,
        'last_seen': datetime.now().isoformat(),
        'status': 'active'
    }

def _classify_device_type(mac: str) -> str:
    if not mac or mac == 'N/A':
        return 'Dispositivo'
    mac_upper = mac.upper()
    mac_prefix = mac_upper.replace(':', '')[:6].upper()

    for vendor, prefixes in VENDOR_DB.items():
        if mac_prefix in prefixes:
            if vendor == 'apple':     return 'Dispositivo Apple'
            if vendor == 'samsung':   return 'Dispositivo Samsung'
            if vendor == 'huawei':    return 'Dispositivo Huawei'
            if vendor == 'xiaomi':    return 'Dispositivo Xiaomi'
            if vendor == 'microsoft': return 'Dispositivo Microsoft'
            if vendor == 'dell':      return 'Computadora Dell'
            if vendor == 'lenovo':    return 'Computadora Lenovo'
            if vendor == 'tp-link':   return 'Router/AP'

    oui_db = {
        '00:03:93': 'Apple', '00:05:02': 'Apple', '00:0A:27': 'Apple',
        '00:12:47': 'Samsung', '00:15:99': 'Samsung',
        '00:18:82': 'Huawei', '00:1C:10': 'TP-Link',
        '00:1D:7E': 'TP-Link', '00:1E:1F': 'Google',
        '00:21:29': 'Cisco', '00:50:7F': 'Netgear',
        '14:F6:5A': 'Xiaomi', '28:EF:01': 'Google',
    }
    oui = mac_upper[:8]
    if oui in oui_db:
        v = oui_db[oui]
        if v == 'Apple':    return 'Dispositivo Apple'
        if v == 'Samsung':  return 'Dispositivo Samsung'
        if v == 'Huawei':   return 'Dispositivo Huawei'
        if v == 'TP-Link':  return 'Router/AP'

    first = int(mac_upper.split(':')[0], 16)
    if first & 0x02: return 'Dispositivo Móvil'
    if first & 0x01: return 'Dispositivo de Red'
    return 'Dispositivo'

def _get_vendor_from_mac(mac: str) -> str:
    if not mac or mac == 'N/A':
        return "Desconocido"
    mac_prefix = mac.upper().replace(':', '')[:6].upper()
    for vendor, prefixes in VENDOR_DB.items():
        if mac_prefix in prefixes:
            return vendor.title()
    return "Fabricante Desconocido"

# ----------------------------------------------------------------------
# Escaneo por SO
# ----------------------------------------------------------------------
def _scan_windows_optimized(red_info: Dict = None) -> List[Dict]:
    devices = []
    seen_macs = set()

    try:
        local_ip = _get_local_ip_address()
        if not local_ip or not _is_valid_ip(local_ip):
            return _fallback_arp_scan()

        gateway = _get_default_gateway() or "192.168.1.1"
        subnet = '.'.join(local_ip.split('.')[:3]) + '.'

        print(f"[ESCANEO] Escaneando red {subnet}0/24...")
        active_ips = []
        threads = []

        def ping_ip(ip):
            if _ping_ip_fast(ip):
                active_ips.append(ip)

        # 🔧 No se excluye la IP local
        for i in range(1, 255):
            ip = f"{subnet}{i}"
            t = threading.Thread(target=ping_ip, args=(ip,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=3)

        # 🔧 Procesar IPs activas
        for ip in active_ips:
            mac = _get_mac_from_arp_fast(ip)
            if mac and _is_valid_mac(mac) and mac not in seen_macs:
                seen_macs.add(mac)
                devices.append(_create_device_info(ip, mac))

        # ------------------------------------------------------------------
        # 🔧 AGREGAR EQUIPO LOCAL SI NO ESTÁ
        # ------------------------------------------------------------------
        if all(d['ip'] != local_ip for d in devices):
            local_mac = _get_mac_from_arp_fast(local_ip)

            if not local_mac:
                # Intentar obtener la MAC local mediante getmac (Windows)
                try:
                    res = subprocess.run(
                        ["getmac"], capture_output=True, text=True, encoding="cp850", errors="ignore"
                    )
                    m = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', res.stdout)
                    if m:
                        local_mac = m.group(0).replace('-', ':').upper()
                except:
                    pass

            if not local_mac:
                # Último recurso: usar uuid.getnode()
                import uuid
                local_mac = ':'.join(re.findall('..', f"{uuid.getnode():012x}".upper()))

            if _is_valid_mac(local_mac):
                devices.append(_create_device_info(local_ip, local_mac))
                print(f"[DEBUG] Dispositivo local agregado manualmente: {local_ip} ({local_mac})")

        # ------------------------------------------------------------------
        # 🔧 AGREGAR ROUTER SI FALTA
        # ------------------------------------------------------------------
        if gateway not in [d['ip'] for d in devices]:
            router_mac = _get_mac_from_arp_fast(gateway)
            if router_mac and _is_valid_mac(router_mac):
                devices.append(_create_device_info(gateway, router_mac))

        print(f"[ESCANEO] Encontrados {len(devices)} dispositivos activos.")

    except Exception as e:
        print(f"[Windows] Error en escaneo activo: {e}")
        return _fallback_arp_scan()

    return devices


def _get_local_ip_address() -> Optional[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return None

def _fallback_arp_scan() -> List[Dict]:
    devices = []
    seen_macs = set()
    try:
        result = subprocess.run(
            ['arp', '-a'], capture_output=True, text=True,
            encoding='cp850', errors='replace', timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = re.split(r'\s+', line.strip())
                if len(parts) >= 3:
                    ip, mac = parts[0], parts[1].replace('-', ':').upper()
                    
                    if _is_valid_ip(ip) and _is_valid_mac(mac) and mac not in seen_macs:
                        seen_macs.add(mac)
                        devices.append(_create_device_info(ip, mac))
    except:
        pass
    return devices

def _scan_linux_optimized(red_info: Dict = None) -> List[Dict]:
    devices = []
    try:
        res = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            devices.extend(_parse_arp_table(res.stdout, red_info))
        try:
            res = subprocess.run(['ip', 'neighbor', 'show'], capture_output=True,
                                 text=True, timeout=5)
            if res.returncode == 0:
                devices.extend(_parse_ip_neighbor_improved(res.stdout))
        except:
            pass
        verified = [d for d in devices if _ping_ip_fast(d['ip'])]
        return verified
    except Exception as e:
        print(f"[Linux] Error escaneando: {e}")
    return devices

def _scan_macos_optimized(red_info: Dict = None) -> List[Dict]:
    devices = []
    try:
        res = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            devices.extend(_parse_arp_table_macos_improved(res.stdout))
        verified = [d for d in devices if _ping_ip_fast(d['ip'])]
        return verified
    except Exception as e:
        print(f"[macOS] Error escaneando: {e}")
    return devices

# ----------------------------------------------------------------------
# Parsers auxiliares
# ----------------------------------------------------------------------
def _parse_arp_table_windows_improved(arp_output: str) -> List[Dict]:
    return []

def _parse_arp_table_macos_improved(arp_output: str) -> List[Dict]:
    devices = []
    for line in arp_output.splitlines():
        m = re.search(r'\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-fA-F:-]{17})', line)
        if m:
            ip, mac = m.group(1), m.group(2).upper().replace('-', ':')
            if _is_valid_ip(ip) and _is_valid_mac(mac):
                devices.append(_create_device_info(ip, mac))
    return devices

def _parse_ip_neighbor_improved(ip_output: str) -> List[Dict]:
    devices = []
    for line in ip_output.splitlines():
        parts = line.split()
        if len(parts) >= 5:
            ip, mac = parts[0], parts[4].upper()
            state = parts[5] if len(parts) > 5 else ''
            if state in ('REACHABLE', 'STALE', 'DELAY') and _is_valid_ip(ip) and _is_valid_mac(mac):
                devices.append(_create_device_info(ip, mac))
    return devices

def _parse_arp_table(arp_output: str, red_info: Dict = None) -> List[Dict]:
    devices = []
    for line in arp_output.splitlines():
        m = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})', line)
        if m:
            ip, mac = m.group(1), m.group(2).upper().replace('-', ':')
            if _is_valid_ip(ip) and _is_valid_mac(mac):
                devices.append(_create_device_info(ip, mac))
    return devices

# ----------------------------------------------------------------------
# Filtro de dispositivos activos
# ----------------------------------------------------------------------
def _is_device_reachable(device: Dict) -> bool:
    ip = device.get('ip')
    if not ip or ip == 'N/A':
        return False
    return _ping_ip_fast(ip) or _check_device_ports(ip)

def _filter_active_devices(devices: List[Dict], red_info: Dict = None) -> List[Dict]:
    """
    Filtra y valida los dispositivos activos detectados.
    Acepta también los que no responden ping pero tienen MAC válida.
    """
    active = []
    seen = set()
    now = datetime.now()

    for dev in devices:
        ip, mac = dev.get('ip'), dev.get('mac')
        if not _is_valid_ip(ip) or not _is_valid_mac(mac):
            continue
        if mac in seen:
            continue
        seen.add(mac)

        # Router siempre activo
        if red_info and red_info.get('router_ip') == ip:
            active.append(dev)
            continue

        # Cache reciente
        if mac in device_cache and (now - device_cache[mac]) < timedelta(seconds=CACHE_DURATION):
            active.append(dev)
            continue

        # Reintento flexible
        reachable = _ping_ip_fast(ip)
        if not reachable:
            # 🔧 Nuevo: intentar detectar por puertos
            reachable = _check_device_ports(ip)

        # 🔧 Nuevo: si aún no responde pero tiene MAC válida, conservarlo
        if reachable or mac:
            active.append(dev)

    return active


def _update_device_cache(devices: List[Dict]):
    now = datetime.now()
    for d in devices:
        mac = d.get('mac')
        if mac and _is_valid_mac(mac):
            device_cache[mac] = now

# ----------------------------------------------------------------------
# API pública
# ----------------------------------------------------------------------
def get_connected_devices(red_info: Dict = None) -> Dict:
    """
    Devuelve dispositivos conectados a la red indicada en red_info.
    Formato exacto requerido.
    """
    try:
        # 🔧 CORRECCIÓN CLAVES MAYÚSC/MINÚSC
        target_ssid = None
        target_bssid = None
        if red_info:
            target_ssid = red_info.get("SSID") or red_info.get("ssid")
            target_bssid = red_info.get("BSSID") or red_info.get("bssid")

        if not target_ssid or not is_connected_to_network(target_ssid, target_bssid):
            return {
                "success": True,
                "devices": [],
                "total_devices": 0,
                "max_devices": red_info.get("router_max_devices", 50) if red_info else 50,
                "usage_percentage": 0,
                "scan_performed": False,
                "message": "No conectado a esta red"
            }

        system = platform.system().lower()
        if system == "windows":
            raw = _scan_windows_optimized(red_info)
        elif system == "linux":
            raw = _scan_linux_optimized(red_info)
        elif system == "darwin":
            raw = _scan_macos_optimized(red_info)
        else:
            raw = []

        active = _filter_active_devices(raw, red_info)
        _update_device_cache(active)

        max_d = red_info.get("router_max_devices", 50) if red_info else 50
        total = len(active)
        usage = min(100, int(total / max_d * 100)) if max_d else 0

        return {
            "success": True,
            "devices": active,
            "total_devices": total,
            "max_devices": max_d,
            "usage_percentage": usage,
            "scan_performed": True,
            "message": "Escaneo completado",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),  # <- SIEMPRE incluir esta clave
            "devices": [],
            "total_devices": 0,
            "max_devices": red_info.get("router_max_devices", 50) if red_info else 50,
            "usage_percentage": 0,
            "scan_performed": False,
            "message": f"Error en escaneo: {str(e)}"
        }

def get_devices_count(red_info: Dict = None) -> int:
    try:
        return get_connected_devices(red_info).get('total_devices', 0)
    except:
        return 0

# ----------------------------------------------------------------------
# Limpieza de cache
# ----------------------------------------------------------------------
def cleanup_old_cache():
    now = datetime.now()
    to_del = [mac for mac, ts in device_cache.items()
              if now - ts > timedelta(seconds=CACHE_DURATION)]
    for mac in to_del:
        del device_cache[mac]

def start_cache_cleaner():
    def cleaner():
        while True:
            time.sleep(60)
            cleanup_old_cache()
    threading.Thread(target=cleaner, daemon=True).start()

start_cache_cleaner()

if __name__ == "__main__":
    network_info = get_current_network_info()
    result = get_connected_devices(network_info)
    print(json.dumps(result, indent=2, ensure_ascii=False))
