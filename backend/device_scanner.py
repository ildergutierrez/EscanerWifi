# device_scanner.py
"""
Escáner de dispositivos conectados a una red WiFi.
Versión adaptada para Linux y Windows.
"""

import subprocess
import re
import platform
import ipaddress
from typing import List, Dict, Optional
import threading
import time
import socket
import json
from datetime import datetime

# ----------------------------------------------------------------------
# Compatibilidad con ap_device_scanner
# ----------------------------------------------------------------------
try:
    from ap_device_scanner import get_connected_devices as ap_get_connected_devices, get_devices_count as ap_get_devices_count
    HAS_AP_SCANNER = True
except ImportError:
    HAS_AP_SCANNER = False
    print("⚠️  No se pudo importar ap_device_scanner")

# ----------------------------------------------------------------------
# Base de datos de fabricantes simplificada
# ----------------------------------------------------------------------
VENDOR_DB = {
    'apple': ['000393', '000502', '000A27', '001451', '001E52'],
    'samsung': ['001247', '001599', '001D25', '0023B1'],
    'huawei': ['001882', '001E10', '002568', 'A8494D'],
    'xiaomi': ['14F65A', '283B96', '80B686', 'F8A45F'],
    'tp-link': ['001C10', '001D7E', '50BD5F', 'B0BE76'],
    'dell': ['001DE1', '00215D', '0022B0', '002708'],
    'lenovo': ['0015B9', '00246C', '00264A', '6C5F1C'],
    'microsoft': ['00155D', '001E4C', '00248C', '0050F2'],
    'cisco': ['000142', '00100D', '001146', '00142B'],
    'netgear': ['00095C', '0015F2', '001E2A', '002375'],
}

class DeviceScanner:
    def __init__(self):
        self.system = platform.system().lower()
        self.active_devices = []
        
    def get_network_range(self, gateway_ip: str) -> str:
        """
        Obtiene el rango de red a partir de la IP del gateway.
        """
        try:
            ip_parts = gateway_ip.split('.')
            if len(ip_parts) == 4:
                return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
            return f"{gateway_ip}/24"
        except Exception:
            return f"{gateway_ip}/24"
    
    def get_default_gateway(self) -> Optional[str]:
        """
        Obtiene la IP del gateway por defecto.
        """
        try:
            if self.system == "windows":
                result = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=10)
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if "Default Gateway" in line or "Puerta de enlace predeterminada" in line:
                        for j in range(i, min(i+5, len(lines))):
                            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', lines[j])
                            if ip_match:
                                return ip_match.group(1)
            
            elif self.system in ["linux", "darwin"]:
                # Método 1: ip route
                try:
                    result = subprocess.run(['ip', 'route'], capture_output=True, text=True, timeout=5)
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if "default" in line:
                            ip_match = re.search(r'default via ([\d\.]+)', line)
                            if ip_match:
                                return ip_match.group(1)
                except:
                    pass
                
                # Método 2: netstat (fallback)
                try:
                    result = subprocess.run(['netstat', '-rn'], capture_output=True, text=True, timeout=5)
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if line.startswith('0.0.0.0') or line.startswith('default'):
                            parts = line.split()
                            if len(parts) >= 2:
                                return parts[1]
                except:
                    pass
                
                # Método 3: route (fallback más antiguo)
                try:
                    result = subprocess.run(['route', '-n'], capture_output=True, text=True, timeout=5)
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if line.startswith('0.0.0.0'):
                            parts = line.split()
                            if len(parts) >= 2:
                                return parts[1]
                except:
                    pass
            
            return None
        except Exception as e:
            print(f"❌ Error obteniendo gateway: {e}")
            return None
    
    def get_local_ip(self) -> Optional[str]:
        """Obtiene la IP local del sistema"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return None
    
    def estimate_max_devices(self, red_info: Dict) -> int:
        """
        Estima el número máximo de dispositivos que puede soportar la red.
        Basado en tecnología, ancho de canal, y estándares WiFi.
        """
        try:
            tecnologia = red_info.get("Tecnologia", "").lower()
            banda = red_info.get("Banda", "").lower()
            ancho_canal = red_info.get("AnchoCanal", "20 MHz")
            
            # Estimación base por tecnología
            if "wifi 6" in tecnologia or "ax" in tecnologia:
                base_capacity = 150
            elif "wifi 5" in tecnologia or "ac" in tecnologia:
                base_capacity = 100
            elif "n" in tecnologia:
                base_capacity = 50
            elif "g" in tecnologia:
                base_capacity = 25
            else:
                base_capacity = 15
            
            # Ajuste por banda
            if "5" in banda:
                base_capacity = int(base_capacity * 1.2)
            
            # Ajuste por ancho de canal
            if "40" in ancho_canal:
                base_capacity = int(base_capacity * 1.3)
            elif "80" in ancho_canal:
                base_capacity = int(base_capacity * 1.6)
            elif "160" in ancho_canal:
                base_capacity = int(base_capacity * 2.0)
            
            return max(10, min(base_capacity, 250))
            
        except Exception:
            return 50
    
    # ------------------------------------------------------------------
    # ESCANEO PARA LINUX - ADAPTADO
    # ------------------------------------------------------------------
    def scan_arp_linux(self, network_range: str) -> List[Dict]:
        """
        Escaneo ARP para Linux - Versión adaptada.
        """
        devices = []
        
        print(f"[LINUX] Iniciando escaneo en {network_range}")
        
        # Método 1: Usar ip neighbor (moderno, no requiere root para ver)
        try:
            result = subprocess.run(['ip', 'neighbor', 'show'], 
                                   capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 5:
                        ip = parts[0]
                        mac = parts[4].upper()
                        state = parts[5] if len(parts) > 5 else ''
                        
                        # Solo considerar dispositivos con estado válido
                        if state in ('REACHABLE', 'STALE', 'DELAY', 'PERMANENT'):
                            if self._is_valid_ip(ip) and self._is_valid_mac(mac):
                                vendor = self._get_vendor_from_mac(mac)
                                devices.append({
                                    'ip': ip,
                                    'mac': mac,
                                    'vendor': vendor,
                                    'type': self._guess_device_type(mac, vendor),
                                    'status': state
                                })
                if devices:
                    print(f"[LINUX] ip neighbor encontró {len(devices)} dispositivos")
                    return devices
        except Exception as e:
            print(f"[LINUX] Error con ip neighbor: {e}")
        
        # Método 2: arp -a (tradicional)
        try:
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=15)
            lines = result.stdout.split('\n')
            
            for line in lines:
                # Formato típico: ? (192.168.1.1) at 00:11:22:33:44:55 [ether] on wlan0
                ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                mac_match = re.search(r'at\s+([0-9a-fA-F:]{17})', line)
                
                if ip_match and mac_match:
                    ip = ip_match.group(1)
                    mac = mac_match.group(1).upper()
                    
                    if self._is_valid_ip(ip) and self._is_valid_mac(mac):
                        vendor = self._get_vendor_from_mac(mac)
                        devices.append({
                            'ip': ip,
                            'mac': mac,
                            'vendor': vendor,
                            'type': self._guess_device_type(mac, vendor),
                            'status': 'detected'
                        })
            
            if devices:
                print(f"[LINUX] arp -a encontró {len(devices)} dispositivos")
                return devices
        except Exception as e:
            print(f"[LINUX] Error con arp -a: {e}")
        
        # Método 3: arp -n (formato numérico)
        try:
            result = subprocess.run(['arp', '-n'], capture_output=True, text=True, timeout=10)
            lines = result.stdout.split('\n')
            
            # Saltar encabezado
            for line in lines[1:]:
                if not line.strip():
                    continue
                    
                parts = line.split()
                if len(parts) >= 3:
                    ip = parts[0]
                    mac = parts[2].upper()
                    
                    if self._is_valid_ip(ip) and self._is_valid_mac(mac):
                        vendor = self._get_vendor_from_mac(mac)
                        devices.append({
                            'ip': ip,
                            'mac': mac,
                            'vendor': vendor,
                            'type': self._guess_device_type(mac, vendor),
                            'status': 'detected'
                        })
            
            if devices:
                print(f"[LINUX] arp -n encontró {len(devices)} dispositivos")
                return devices
        except Exception as e:
            print(f"[LINUX] Error con arp -n: {e}")
        
        # Método 4: Intentar nmap si está disponible (requiere root)
        try:
            # Verificar si nmap está instalado
            subprocess.run(['which', 'nmap'], capture_output=True, check=True)
            
            # Escanear solo el gateway y algunas IPs comunes
            gateway = self.get_default_gateway()
            if gateway:
                subnet = '.'.join(gateway.split('.')[:3]) + '.'
                
                # Escanear IPs comunes
                common_ips = [f"{subnet}1", f"{subnet}2", f"{subnet}100", f"{subnet}101", f"{subnet}254"]
                
                for ip in common_ips:
                    try:
                        result = subprocess.run(['nmap', '-sn', ip], 
                                               capture_output=True, text=True, timeout=5)
                        # Buscar MAC en la salida (simplificado)
                        mac_match = re.search(r'MAC Address: ([0-9A-F:]{17})', result.stdout)
                        if mac_match:
                            mac = mac_match.group(1).upper()
                            if self._is_valid_mac(mac):
                                vendor = self._get_vendor_from_mac(mac)
                                devices.append({
                                    'ip': ip,
                                    'mac': mac,
                                    'vendor': vendor,
                                    'type': self._guess_device_type(mac, vendor),
                                    'status': 'nmap'
                                })
                    except:
                        continue
        except:
            pass  # nmap no disponible o error
        
        # Método 5: Agregar dispositivo local si no hay otros
        if len(devices) == 0:
            local_ip = self.get_local_ip()
            if local_ip:
                local_mac = self._get_local_mac_linux()
                if local_mac:
                    vendor = self._get_vendor_from_mac(local_mac)
                    devices.append({
                        'ip': local_ip,
                        'mac': local_mac,
                        'vendor': vendor,
                        'type': "🖥️ Computadora Local",
                        'status': 'local'
                    })
        
        return devices
    
    def _get_local_mac_linux(self) -> Optional[str]:
        """Obtiene MAC local en Linux"""
        try:
            # Método 1: /sys/class/net/
            interfaces = ['wlan0', 'eth0', 'enp0s3', 'enp0s8', 'eno1', 'wlp2s0', 'wlp3s0']
            for iface in interfaces:
                try:
                    with open(f'/sys/class/net/{iface}/address', 'r') as f:
                        mac = f.read().strip().upper()
                        if self._is_valid_mac(mac):
                            return mac
                except:
                    continue
            
            # Método 2: ip link
            res = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
            if res.returncode == 0:
                current_iface = None
                for line in res.stdout.splitlines():
                    if ':' in line and not 'link/ether' in line:
                        # Línea de interfaz: 2: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP>
                        iface_match = re.search(r'\d+: (\w+):', line)
                        if iface_match:
                            current_iface = iface_match.group(1)
                    elif 'link/ether' in line and current_iface:
                        mac_match = re.search(r'link/ether ([0-9a-f:]{17})', line)
                        if mac_match:
                            return mac_match.group(1).upper()
        except:
            pass
        return None
    
    # ------------------------------------------------------------------
    # ESCANEO PARA WINDOWS (sin cambios)
    # ------------------------------------------------------------------
    def scan_arp_windows(self, network_range: str) -> List[Dict]:
        """
        Escaneo ARP para Windows.
        """
        devices = []
        try:
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=15)
            lines = result.stdout.split('\n')
            current_interface = None
            
            for line in lines:
                line = line.strip()
                
                if "Interface" in line and "---" not in line:
                    ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    if ip_match:
                        current_interface = ip_match.group(1)
                
                elif line and current_interface:
                    parts = re.split(r'\s+', line)
                    if len(parts) >= 3 and ("dinámico" in line.lower() or "dynamic" in line.lower()):
                        ip = parts[0]
                        mac = parts[1].replace('-', ':').upper()
                        
                        if self._is_valid_ip(ip) and self._is_valid_mac(mac):
                            devices.append({
                                'ip': ip,
                                'mac': mac,
                                'vendor': self._get_vendor_from_mac(mac),
                                'type': self._guess_device_type(mac, self._get_vendor_from_mac(mac))
                            })
            
            return devices
            
        except Exception as e:
            print(f"❌ Error en escaneo ARP Windows: {e}")
            return []
    
    # ------------------------------------------------------------------
    # ESCANEO PARA macOS
    # ------------------------------------------------------------------
    def scan_arp_macos(self, network_range: str) -> List[Dict]:
        """
        Escaneo ARP para macOS.
        """
        devices = []
        try:
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=15)
            lines = result.stdout.split('\n')
            
            for line in lines:
                ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                mac_match = re.search(r'at\s+([0-9a-fA-F:]+)', line)
                
                if ip_match and mac_match:
                    ip = ip_match.group(1)
                    mac = mac_match.group(1).upper()
                    
                    if self._is_valid_ip(ip) and self._is_valid_mac(mac):
                        devices.append({
                            'ip': ip,
                            'mac': mac,
                            'vendor': self._get_vendor_from_mac(mac),
                            'type': self._guess_device_type(mac, self._get_vendor_from_mac(mac))
                        })
            
            return devices
            
        except Exception as e:
            print(f"❌ Error en escaneo ARP macOS: {e}")
            return []
    
    def _guess_device_type(self, mac: str, vendor: str) -> str:
        """
        Intenta adivinar el tipo de dispositivo basado en el fabricante y MAC.
        """
        vendor_lower = vendor.lower() if vendor else ""
        mac_upper = mac.upper() if mac else ""
        
        # Por fabricante
        if any(word in vendor_lower for word in ['apple', 'iphone', 'ipad', 'macbook']):
            return "📱 Apple"
        elif any(word in vendor_lower for word in ['samsung', 'galaxy']):
            return "📱 Samsung"
        elif any(word in vendor_lower for word in ['huawei', 'honor']):
            return "📱 Huawei"
        elif any(word in vendor_lower for word in ['xiaomi', 'redmi', 'poco']):
            return "📱 Xiaomi"
        elif any(word in vendor_lower for word in ['sony', 'xperia']):
            return "📱 Sony"
        elif any(word in vendor_lower for word in ['lg']):
            return "📱 LG"
        elif any(word in vendor_lower for word in ['motorola', 'moto']):
            return "📱 Motorola"
        
        # Por prefix de MAC común
        if mac_upper.startswith('B8:27:EB'):
            return "🖥️ Raspberry Pi"
        elif mac_upper.startswith('00:50:56'):
            return "🖥️ VMware"
        elif mac_upper.startswith('00:0C:29'):
            return "🖥️ Virtual Machine"
        elif mac_upper.startswith('08:00:27') or mac_upper.startswith('0A:00:27'):
            return "🖥️ VirtualBox"
        elif mac_upper.startswith('C0:C9:E3') or mac_upper.startswith('DC:54:AD'):
            return "🛜 Router"
        
        # Por OUI conocidos de dispositivos IoT
        iot_prefixes = ['00:1E:42', '00:23:4D', '00:26:5A']
        if any(mac_upper.startswith(prefix) for prefix in iot_prefixes):
            return "📟 IoT"
        
        return "💻 Computadora"
    
    def _is_valid_ip(self, ip: str) -> bool:
        try:
            ipaddress.IPv4Address(ip)
            return True
        except:
            return False
    
    def _is_valid_mac(self, mac: str) -> bool:
        if not mac:
            return False
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
        return bool(mac_pattern.match(mac))
    
    def _get_vendor_from_mac(self, mac: str) -> str:
        """
        Obtiene fabricante desde prefijo MAC usando base de datos local.
        """
        if not mac or not self._is_valid_mac(mac):
            return "Desconocido"
        
        # Extraer OUI (primeros 6 caracteres sin :)
        oui = mac.replace(':', '').replace('-', '').upper()[:6]
        
        # Buscar en base de datos
        for vendor, prefixes in VENDOR_DB.items():
            if oui in prefixes:
                return vendor.title()
        
        return "Desconocido"
    
    def scan_network(self, red_info: Dict = None) -> Dict:
        """
        Escanea la red en busca de dispositivos conectados.
        
        Args:
            red_info: Información de la red para estimar capacidad máxima
            
        Returns:
            Dict: Información del escaneo
        """
        print(f"🔍 Escaneando dispositivos en la red ({self.system})...")
        
        # Intentar usar ap_device_scanner primero si está disponible
        if HAS_AP_SCANNER and red_info:
            try:
                print("🔄 Usando ap_device_scanner...")
                result = ap_get_connected_devices(red_info)
                if result.get('success', False) and result.get('devices'):
                    print(f"✅ ap_device_scanner encontró {len(result['devices'])} dispositivos")
                    return result
            except Exception as e:
                print(f"⚠️  Error con ap_device_scanner: {e}")
        
        # Si ap_device_scanner falla, usar método propio
        gateway = self.get_default_gateway()
        if not gateway:
            return {
                'success': False,
                'error': 'No se pudo detectar el gateway',
                'devices': [],
                'total_devices': 0,
                'max_devices': 50,
                'gateway': None,
                'usage_percentage': 0
            }
        
        network_range = self.get_network_range(gateway)
        print(f"📡 Rango de red: {network_range}")
        
        devices = []
        
        if self.system == "windows":
            devices = self.scan_arp_windows(network_range)
        elif self.system == "linux":
            devices = self.scan_arp_linux(network_range)
        elif self.system == "darwin":
            devices = self.scan_arp_macos(network_range)
        else:
            return {
                'success': False,
                'error': f'Sistema operativo no soportado: {self.system}',
                'devices': [],
                'total_devices': 0,
                'max_devices': 50,
                'gateway': gateway,
                'usage_percentage': 0
            }
        
        # Filtrar dispositivos únicos por MAC
        unique_devices = []
        seen_macs = set()
        
        for device in devices:
            if device.get('mac') and device['mac'] != "DESCONOCIDO" and device['mac'] not in seen_macs:
                unique_devices.append(device)
                seen_macs.add(device['mac'])
        
        # Estimar capacidad máxima
        max_devices = self.estimate_max_devices(red_info) if red_info else 50
        usage_percentage = min(100, int((len(unique_devices) / max_devices) * 100)) if max_devices > 0 else 0
        
        print(f"✅ Encontrados {len(unique_devices)} dispositivos únicos")
        print(f"📊 Capacidad estimada: {max_devices} dispositivos ({usage_percentage}% de uso)")
        
        return {
            'success': True,
            'devices': unique_devices,
            'total_devices': len(unique_devices),
            'max_devices': max_devices,
            'usage_percentage': usage_percentage,
            'gateway': gateway,
            'network_range': network_range
        }

# Funciones de conveniencia
def get_connected_devices(red_info: Dict = None) -> Dict:
    """API pública - Obtiene dispositivos conectados"""
    scanner = DeviceScanner()
    return scanner.scan_network(red_info)

def get_devices_count(red_info: Dict = None) -> int:
    """API pública - Obtiene número de dispositivos"""
    scanner = DeviceScanner()
    result = scanner.scan_network(red_info)
    return result['total_devices'] if result['success'] else 0

# ----------------------------------------------------------------------
# Para depuración
# ----------------------------------------------------------------------
'''if __name__ == "__main__":
    print("🚀 Iniciando escáner de dispositivos...")
    print(f"📊 Sistema: {platform.system()} {platform.release()}")
    
    # Información de ejemplo de una red
    red_ejemplo = {
        "SSID": "MiRed_WiFi",
        "Tecnologia": "WiFi 5 (ac)",
        "Banda": "5 GHz",
        "AnchoCanal": "80 MHz"
    }
    
    scanner = DeviceScanner()
    result = scanner.scan_network(red_ejemplo)
    
    if result['success']:
        print(f"\n📊 RESULTADOS DEL ESCANEO:")
        print(f"📍 Gateway: {result['gateway']}")
        print(f"🌐 Rango: {result['network_range']}")
        print(f"📱 Dispositivos conectados: {result['total_devices']}")
        print(f"🚀 Capacidad máxima estimada: {result['max_devices']}")
        print(f"📈 Uso de la red: {result['usage_percentage']}%")
        
        if result['devices']:
            print(f"\n📋 LISTA DE DISPOSITIVOS:")
            for i, device in enumerate(result['devices'], 1):
                print(f"  {i}. {device.get('type', 'Desconocido')} | IP: {device.get('ip', 'N/A')} | MAC: {device.get('mac', 'N/A')} | Fabricante: {device.get('vendor', 'Desconocido')}")
    else:
        print(f"❌ Error: {result.get('error', 'Desconocido')}")'''