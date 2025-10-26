import subprocess
import platform
import re
import time
from typing import Dict, List, Optional
import socket
import threading
from datetime import datetime, timedelta
from network_status import is_connected_to_network, get_current_network_info

# Cache para almacenar dispositivos recientemente vistos
device_cache = {}
CACHE_DURATION = 300  # 5 minutos

def get_connected_devices(red_info: Dict = None) -> Dict:
    """
    Obtiene dispositivos conectados a una red WiFi específica.
    SOLO funciona si el dispositivo está conectado a esa red.
    
    Args:
        red_info: Información de la red (BSSID, SSID, etc.)
    
    Returns:
        Dict con información de dispositivos
    """
    try:
        # Verificar si estamos conectados a la red objetivo
        target_ssid = red_info.get("SSID") if red_info else None
        target_bssid = red_info.get("BSSID") if red_info else None
        
        if not target_ssid or not is_connected_to_network(target_ssid, target_bssid):
            # No estamos conectados a esta red - retornar lista vacía
            return {
                'success': True,
                'devices': [],
                'total_devices': 0,
                'max_devices': red_info.get("router_max_devices", 50) if red_info else 50,
                'usage_percentage': 0,
                'scan_performed': False,
                'message': 'No conectado a esta red'
            }
        
        # Estamos conectados a la red - proceder con escaneo
        system = platform.system().lower()
        
        if system == "windows":
            devices = _scan_windows(red_info)
        elif system == "linux":
            devices = _scan_linux(red_info)
        elif system == "darwin":
            devices = _scan_macos(red_info)
        else:
            devices = []
        
        # Filtrar dispositivos activos
        active_devices = _filter_active_devices(devices, red_info)
        
        # Actualizar cache
        _update_device_cache(active_devices)
        
        # Calcular métricas
        max_devices = red_info.get("router_max_devices", 50) if red_info else 50
        total_devices = len(active_devices)
        usage_percentage = min(100, int((total_devices / max_devices) * 100)) if max_devices > 0 else 0
        
        return {
            'success': True,
            'devices': active_devices,
            'total_devices': total_devices,
            'max_devices': max_devices,
            'usage_percentage': usage_percentage,
            'scan_performed': True,
            'message': 'Escaneo completado',
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'devices': [],
            'total_devices': 0,
            'max_devices': red_info.get("router_max_devices", 50) if red_info else 50,
            'usage_percentage': 0,
            'scan_performed': False,
            'message': f'Error en escaneo: {str(e)}'
        }

def _scan_windows(red_info: Dict = None) -> List[Dict]:
    """Escaneo de dispositivos en Windows"""
    devices = []
    
    try:
        # Método 1: ARP table
        result = subprocess.run(['arp', '-a'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            devices.extend(_parse_arp_table(result.stdout, red_info))
        
        # Método 2: net view (solo dispositivos de red Windows)
        try:
            result = subprocess.run(['net', 'view'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode == 0:
                devices.extend(_parse_net_view(result.stdout))
        except:
            pass
            
    except Exception as e:
        print(f"Error en escaneo Windows: {e}")
    
    return devices

def _scan_linux(red_info: Dict = None) -> List[Dict]:
    """Escaneo de dispositivos en Linux"""
    devices = []
    
    try:
        # Método 1: ARP table
        result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
        if result.returncode == 0:
            devices.extend(_parse_arp_table(result.stdout, red_info))
        
        # Método 2: nmap (si está disponible)
        try:
            # Obtener rango de red desde IP local
            network_info = get_current_network_info()
            if network_info.get('ip_address') and network_info.get('subnet_mask'):
                network_range = _calculate_network_range(network_info['ip_address'], network_info['subnet_mask'])
                if network_range:
                    result = subprocess.run(['nmap', '-sn', network_range], capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        devices.extend(_parse_nmap_scan(result.stdout))
        except:
            pass
            
        # Método 3: ip neigh
        try:
            result = subprocess.run(['ip', 'neighbor', 'show'], capture_output=True, text=True)
            if result.returncode == 0:
                devices.extend(_parse_ip_neighbor(result.stdout, red_info))
        except:
            pass
            
    except Exception as e:
        print(f"Error en escaneo Linux: {e}")
    
    return devices

def _scan_macos(red_info: Dict = None) -> List[Dict]:
    """Escaneo de dispositivos en macOS"""
    devices = []
    
    try:
        # Método 1: ARP table
        result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
        if result.returncode == 0:
            devices.extend(_parse_arp_table(result.stdout, red_info))
        
        # Método 2: Bonjour (mDNS)
        try:
            result = subprocess.run(['dns-sd', '-B', '_services._dns-sd._udp'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                devices.extend(_parse_bonjour_scan(result.stdout))
        except:
            pass
            
    except Exception as e:
        print(f"Error en escaneo macOS: {e}")
    
    return devices

def _calculate_network_range(ip_address: str, subnet_mask: str) -> Optional[str]:
    """Calcular rango de red desde IP y máscara"""
    try:
        ip_parts = [int(part) for part in ip_address.split('.')]
        mask_parts = [int(part) for part in subnet_mask.split('.')]
        
        network_parts = []
        for i in range(4):
            network_parts.append(ip_parts[i] & mask_parts[i])
        
        # Calcular dirección de red
        network_ip = '.'.join(str(part) for part in network_parts)
        
        # Calcular CIDR
        cidr = sum(bin(int(part)).count('1') for part in subnet_mask.split('.'))
        
        return f"{network_ip}/{cidr}"
        
    except Exception:
        return None

def _parse_arp_table(arp_output: str, red_info: Dict = None) -> List[Dict]:
    """Parsear tabla ARP"""
    devices = []
    lines = arp_output.split('\n')
    
    for line in lines:
        try:
            # Patrones para diferentes formatos de ARP
            patterns = [
                r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]{17})\s+(\w+)',  # Windows/Linux
                r'\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-fA-F:-]{17})',     # macOS
            ]
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    ip = match.group(1)
                    mac = match.group(2).upper().replace('-', ':')
                    
                    # Solo incluir si es una entrada válida (no incompleta)
                    if mac != '00:00:00:00:00:00' and not mac.startswith('FF:FF:FF:'):
                        device_type = _classify_device_type(mac)
                        vendor = _get_vendor_from_mac(mac)
                        
                        device_info = {
                            'ip': ip,
                            'mac': mac,
                            'type': device_type,
                            'vendor': vendor,
                            'last_seen': datetime.now(),
                            'status': 'active'
                        }
                        
                        devices.append(device_info)
                    
                    break
                    
        except Exception as e:
            continue
    
    return devices

def _parse_net_view(netview_output: str) -> List[Dict]:
    """Parsear salida de net view (Windows)"""
    devices = []
    lines = netview_output.split('\n')
    
    for line in lines:
        if '\\\\' in line:
            try:
                computer_name = line.split('\\\\')[-1].strip()
                devices.append({
                    'ip': 'N/A',
                    'mac': 'N/A',
                    'type': '💻 Computadora',
                    'vendor': 'Sistema Windows',
                    'hostname': computer_name,
                    'last_seen': datetime.now()
                })
            except:
                continue
    
    return devices

def _parse_nmap_scan(nmap_output: str) -> List[Dict]:
    """Parsear salida de nmap"""
    devices = []
    lines = nmap_output.split('\n')
    
    current_ip = None
    current_mac = None
    
    for line in lines:
        # Buscar IP
        ip_match = re.search(r'Nmap scan report for (\d+\.\d+\.\d+\.\d+)', line)
        if ip_match:
            current_ip = ip_match.group(1)
        
        # Buscar MAC
        mac_match = re.search(r'MAC Address: ([0-9A-Fa-f:]{17})', line)
        if mac_match and current_ip:
            current_mac = mac_match.group(1).upper()
            
            device_type = _classify_device_type(current_mac)
            vendor = _get_vendor_from_mac(current_mac)
            
            devices.append({
                'ip': current_ip,
                'mac': current_mac,
                'type': device_type,
                'vendor': vendor,
                'last_seen': datetime.now(),
                'status': 'active'
            })
            
            current_ip = None
            current_mac = None
    
    return devices

def _parse_ip_neighbor(ip_output: str, red_info: Dict = None) -> List[Dict]:
    """Parsear salida de ip neighbor (Linux)"""
    devices = []
    lines = ip_output.split('\n')
    
    for line in lines:
        try:
            parts = line.split()
            if len(parts) >= 5:
                ip = parts[0]
                mac = parts[4].upper()
                state = parts[5] if len(parts) > 5 else 'UNKNOWN'
                
                # Solo dispositivos reachable o stale
                if state in ['REACHABLE', 'STALE', 'DELAY']:
                    device_type = _classify_device_type(mac)
                    vendor = _get_vendor_from_mac(mac)
                    
                    device_info = {
                        'ip': ip,
                        'mac': mac,
                        'type': device_type,
                        'vendor': vendor,
                        'last_seen': datetime.now(),
                        'status': 'active' if state == 'REACHABLE' else 'inactive'
                    }
                    
                    devices.append(device_info)
                        
        except Exception:
            continue
    
    return devices

def _parse_bonjour_scan(bonjour_output: str) -> List[Dict]:
    """Parsear salida de Bonjour (macOS)"""
    devices = []
    lines = bonjour_output.split('\n')
    
    for line in lines:
        if '._tcp' in line and 'localhost' not in line:
            try:
                parts = line.split()
                if len(parts) >= 6:
                    service = parts[0]
                    domain = parts[1]
                    hostname = parts[5] if len(parts) > 5 else 'Unknown'
                    
                    devices.append({
                        'ip': 'N/A',
                        'mac': 'N/A',
                        'type': '🍎 Dispositivo Apple',
                        'vendor': 'Apple',
                        'hostname': hostname,
                        'service': service,
                        'last_seen': datetime.now()
                    })
            except:
                continue
    
    return devices

def _classify_device_type(mac: str) -> str:
    """Clasificar tipo de dispositivo basado en MAC"""
    if not mac or mac == 'N/A':
        return '💻 Dispositivo'
    
    mac_upper = mac.upper()
    
    # Apple devices
    if mac_upper.startswith(('00:03:93', '00:05:02', '00:0A:27', '00:0A:95', 
                           '00:1B:63', '00:1C:B3', '00:1D:4F', '00:1E:52',
                           '00:1E:C2', '00:22:41', '00:23:6C', '00:23:DF',
                           '00:24:36', '00:25:00', '00:25:4B', '00:25:BC',
                           '00:26:08', '00:26:4A', '00:26:B0', '00:26:BB')):
        return '📱 Dispositivo Apple'
    
    # Samsung
    if mac_upper.startswith(('00:12:47', '00:15:99', '00:16:32', '00:16:6B',
                           '00:17:C9', '00:18:AF', '00:1A:8A', '00:1B:98',
                           '00:1C:43', '00:1D:25', '00:1D:F6', '00:1E:7D',
                           '00:1F:AF', '00:21:4C', '00:21:D1', '00:22:47')):
        return '📱 Dispositivo Samsung'
    
    # Huawei
    if mac_upper.startswith(('00:18:82', '00:1E:10', '00:25:68', '00:25:9E',
                           '00:36:76', '00:46:4B', '00:66:4B', '08:19:A6')):
        return '📱 Dispositivo Huawei'
    
    # Xiaomi
    if mac_upper.startswith(('00:9E:08', '0C:1D:AF', '10:2A:B3', '14:F6:5A',
                           '28:6C:07', '34:80:B3', '40:D3:2D', '64:CC:2E',
                           '7C:1D:D9', '8C:BE:BE', 'AC:E0:10', 'BC:AD:28')):
        return '📱 Dispositivo Xiaomi'
    
    # Google
    if mac_upper.startswith(('00:1E:1F', '08:9E:08', '0C:74:C2', '10:2F:6B',
                           '14:DD:A9', '18:65:90', '1C:B3:C9', '20:DF:B9',
                           '28:EF:01', '34:4D:F7', '38:8B:59', '3C:5A:B4')):
        return '📱 Dispositivo Google'
    
    # Microsoft
    if mac_upper.startswith(('00:0D:3A', '00:15:5D', '00:1C:42', '00:22:48',
                           '00:25:AE', '00:50:F2', '00:90:7F', '04:0C:CE',
                           '08:0C:0B', '0C:84:DC', '10:5C:2A', '14:9D:5E')):
        return '💻 Dispositivo Microsoft'
    
    # Routers comunes
    if mac_upper.startswith(('00:1C:10', '00:1D:7E', '00:21:29', '00:22:3F',
                           '00:23:8E', '00:24:01', '00:26:4A', '00:50:7F',
                           '00:90:4C', '00:A0:C5', '00:E0:FC', '04:8D:38',
                           '08:18:1A', '08:76:FF', '0C:82:68', '10:0D:7F')):
        return '🛜 Router/AP'
    
    # Por OUI común
    first_octet = int(mac_upper.split(':')[0], 16)
    
    # Dispositivos móviles (segundo bit del primer octeto)
    if first_octet & 0x02:
        return '📱 Dispositivo Móvil'
    
    # Dispositivos de red
    if first_octet & 0x01:
        return '🌐 Dispositivo de Red'
    
    return '💻 Dispositivo'

def _get_vendor_from_mac(mac: str) -> str:
    """Obtener fabricante desde MAC (simplificado)"""
    if not mac or mac == 'N/A':
        return "Desconocido"
    
    # Diccionario simplificado de OUI
    oui_db = {
        '00:03:93': 'Apple',
        '00:05:02': 'Apple',
        '00:0A:27': 'Apple',
        '00:0A:95': 'Apple',
        '00:12:47': 'Samsung',
        '00:15:99': 'Samsung',
        '00:16:32': 'Samsung',
        '00:18:82': 'Huawei',
        '00:1C:10': 'TP-Link',
        '00:1D:7E': 'TP-Link',
        '00:1E:1F': 'Google',
        '00:21:29': 'Cisco',
        '00:22:3F': 'Cisco',
        '00:23:8E': 'Cisco',
        '00:24:01': 'Cisco',
        '00:25:00': 'Apple',
        '00:26:4A': 'Apple',
        '00:50:7F': 'Netgear',
        '00:90:4C': 'Netgear',
        '00:A0:C5': 'Netgear',
        '00:E0:FC': 'Huawei',
        '04:8D:38': 'Netgear',
        '08:18:1A': 'Samsung',
        '08:76:FF': 'TP-Link',
        '0C:82:68': 'TP-Link',
        '10:0D:7F': 'Netgear',
        '14:F6:5A': 'Xiaomi',
        '28:EF:01': 'Google',
        '34:80:B3': 'Xiaomi',
        '38:8B:59': 'Google',
        '40:D3:2D': 'Xiaomi',
        '64:CC:2E': 'Xiaomi',
        '7C:1D:D9': 'Xiaomi',
        '8C:BE:BE': 'Xiaomi',
        'AC:E0:10': 'Xiaomi',
        'BC:AD:28': 'Xiaomi',
    }
    
    oui = mac.upper()[:8]
    return oui_db.get(oui, "Fabricante Desconocido")

def _filter_active_devices(devices: List[Dict], red_info: Dict = None) -> List[Dict]:
    """Filtrar dispositivos activos"""
    active_devices = []
    now = datetime.now()
    
    for device in devices:
        # Solo dispositivos con IP válida
        if device.get('ip') in ['N/A', '0.0.0.0', '127.0.0.1']:
            continue
            
        # Verificar si está en cache reciente
        mac = device.get('mac')
        if mac and mac in device_cache:
            cache_time = device_cache[mac]
            if now - cache_time < timedelta(seconds=CACHE_DURATION):
                active_devices.append(device)
                continue
        
        # Para nuevos dispositivos, verificar conectividad
        if _is_device_reachable(device):
            active_devices.append(device)
    
    return active_devices

def _is_device_reachable(device: Dict) -> bool:
    """Verificar si el dispositivo está alcanzable"""
    try:
        ip = device.get('ip')
        if not ip or ip == 'N/A':
            return False
        
        # Intentar ping (timeout corto)
        if platform.system().lower() == "windows":
            cmd = ['ping', '-n', '1', '-w', '1000', ip]
        else:
            cmd = ['ping', '-c', '1', '-W', '1', ip]
        
        result = subprocess.run(cmd, capture_output=True, timeout=2)
        return result.returncode == 0
        
    except:
        return False

def _update_device_cache(devices: List[Dict]):
    """Actualizar cache de dispositivos"""
    now = datetime.now()
    
    for device in devices:
        mac = device.get('mac')
        if mac and mac != 'N/A':
            device_cache[mac] = now

def get_devices_count(red_info: Dict = None) -> int:
    """Obtener conteo de dispositivos conectados"""
    try:
        result = get_connected_devices(red_info)
        return result.get('total_devices', 0)
    except:
        return 0

# Función para limpiar cache antigua
def cleanup_old_cache():
    """Limpiar cache de dispositivos antiguos"""
    now = datetime.now()
    old_macs = []
    
    for mac, timestamp in device_cache.items():
        if now - timestamp > timedelta(seconds=CACHE_DURATION):
            old_macs.append(mac)
    
    for mac in old_macs:
        del device_cache[mac]

# Limpiar cache periódicamente
def start_cache_cleaner():
    """Iniciar limpiador de cache en segundo plano"""
    def cleaner():
        while True:
            time.sleep(60)  # Cada minuto
            cleanup_old_cache()
    
    thread = threading.Thread(target=cleaner, daemon=True)
    thread.start()

# Iniciar limpiador de cache al importar
start_cache_cleaner()