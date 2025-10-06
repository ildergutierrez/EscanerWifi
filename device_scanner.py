# device_scanner.py
"""
Escáner de dispositivos conectados a una red WiFi.
Usa ARP scanning para detectar dispositivos activos en la red.
Incluye estimación de capacidad máxima.
"""

import subprocess
import re
import platform
import ipaddress
from typing import List, Dict, Optional
import threading
import time

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
                result = subprocess.run(['ip', 'route'], capture_output=True, text=True, timeout=10)
                lines = result.stdout.split('\n')
                for line in lines:
                    if "default" in line:
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if ip_match:
                            return ip_match.group(1)
            
            return None
        except Exception as e:
            print(f"❌ Error obteniendo gateway: {e}")
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
                base_capacity = 150  # WiFi 6 soporta más dispositivos
            elif "wifi 5" in tecnologia or "ac" in tecnologia:
                base_capacity = 100
            elif "n" in tecnologia:
                base_capacity = 50
            elif "g" in tecnologia:
                base_capacity = 25
            else:  # WiFi b
                base_capacity = 15
            
            # Ajuste por banda
            if "5" in banda:
                base_capacity = int(base_capacity * 1.2)  # 5GHz tiene más canales
            
            # Ajuste por ancho de canal
            if "40" in ancho_canal:
                base_capacity = int(base_capacity * 1.3)
            elif "80" in ancho_canal:
                base_capacity = int(base_capacity * 1.6)
            elif "160" in ancho_canal:
                base_capacity = int(base_capacity * 2.0)
            
            # Considerar uso doméstico vs empresarial
            ssid = red_info.get("SSID", "").lower()
            if any(word in ssid for word in ["corp", "office", "empresa", "business"]):
                base_capacity = int(base_capacity * 0.8)  # Redes empresariales tienen más usuarios
            
            return max(10, min(base_capacity, 250))  # Límites razonables
            
        except Exception:
            return 50  # Valor por defecto
    
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
                    if len(parts) >= 3 and "dinámico" in line.lower() or "dynamic" in line.lower():
                        ip = parts[0]
                        mac = parts[1].replace('-', ':').upper()
                        
                        if self._is_valid_ip(ip) and self._is_valid_mac(mac):
                            devices.append({
                                'ip': ip,
                                'mac': mac,
                                'interface': current_interface,
                                'vendor': self._get_vendor_from_mac(mac),
                                'type': self._guess_device_type(mac, self._get_vendor_from_mac(mac))
                            })
            
            return devices
            
        except Exception as e:
            print(f"❌ Error en escaneo ARP Windows: {e}")
            return []
    
    def scan_arp_linux(self, network_range: str) -> List[Dict]:
        """
        Escaneo ARP para Linux.
        """
        devices = []
        try:
            try:
                result = subprocess.run(['arp-scan', '--localnet'], capture_output=True, text=True, timeout=30)
                lines = result.stdout.split('\n')
                
                for line in lines:
                    parts = re.split(r'\s+', line.strip())
                    if len(parts) >= 2 and self._is_valid_ip(parts[0]) and self._is_valid_mac(parts[1]):
                        vendor = ' '.join(parts[2:]) if len(parts) > 2 else "Desconocido"
                        devices.append({
                            'ip': parts[0],
                            'mac': parts[1].upper(),
                            'vendor': vendor,
                            'type': self._guess_device_type(parts[1], vendor)
                        })
                
                if devices:
                    return devices
            except:
                pass
            
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
            print(f"❌ Error en escaneo ARP Linux: {e}")
            return []
    
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
        vendor_lower = vendor.lower()
        mac_prefix = mac[:8].upper()
        
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
        elif any(word in vendor_lower for word in ['lg', 'g series']):
            return "📱 LG"
        elif any(word in vendor_lower for word in ['motorola', 'moto']):
            return "📱 Motorola"
        elif any(word in vendor_lower for word in ['nokia']):
            return "📱 Nokia"
        
        # Por prefix de MAC común
        router_prefixes = ['C0:C9:E3', 'DC:54:AD', '00:1B:44', '00:1D:0F']
        if any(mac.startswith(prefix) for prefix in router_prefixes):
            return "🛜 Router"
        elif mac.startswith('B8:27:EB'):
            return "🖥️ Raspberry Pi"
        elif mac.startswith('00:50:56'):
            return "🖥️ VMware"
        elif mac.startswith('00:0C:29'):
            return "🖥️ Virtual Machine"
        elif mac.startswith('08:00:27') or mac.startswith('0A:00:27'):
            return "🖥️ VirtualBox"
        
        # Por OUI conocidos de dispositivos IoT
        iot_prefixes = ['00:1E:42', '00:23:4D', '00:26:5A']
        if any(mac.startswith(prefix) for prefix in iot_prefixes):
            return "📟 IoT"
        
        return "💻 Computadora"

    def _get_mac_from_arp(self, ip: str) -> Optional[str]:
        """
        Obtiene MAC desde la tabla ARP.
        """
        try:
            if self.system == "windows":
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=5)
                lines = result.stdout.split('\n')
                for line in lines:
                    if ip in line:
                        mac_match = re.search(r'([0-9A-Fa-f-]{17})', line)
                        if mac_match:
                            return mac_match.group(1).replace('-', ':').upper()
            
            elif self.system in ["linux", "darwin"]:
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=5)
                lines = result.stdout.split('\n')
                for line in lines:
                    if ip in line:
                        mac_match = re.search(r'at\s+([0-9a-fA-F:]+)', line)
                        if mac_match:
                            return mac_match.group(1).upper()
            
            return None
        except:
            return None
    
    def _is_valid_ip(self, ip: str) -> bool:
        try:
            ipaddress.IPv4Address(ip)
            return True
        except:
            return False
    
    def _is_valid_mac(self, mac: str) -> bool:
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
        return bool(mac_pattern.match(mac))
    
    def _get_vendor_from_mac(self, mac: str) -> str:
        try:
            from vendor_lookup import get_vendor
            return get_vendor(mac)
        except:
            return "Desconocido"
    
    def scan_network(self, red_info: Dict = None) -> Dict:
        """
        Escanea la red en busca de dispositivos conectados.
        
        Args:
            red_info: Información de la red para estimar capacidad máxima
            
        Returns:
            Dict: Información del escaneo
        """
        print("🔍 Escaneando dispositivos en la red...")
        
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
        
        # Filtrar dispositivos únicos por MAC
        unique_devices = []
        seen_macs = set()
        
        for device in devices:
            if device['mac'] and device['mac'] != "Desconocida" and device['mac'] not in seen_macs:
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
    scanner = DeviceScanner()
    return scanner.scan_network(red_info)

def get_devices_count(red_info: Dict = None) -> int:
    scanner = DeviceScanner()
    result = scanner.scan_network(red_info)
    return result['total_devices'] if result['success'] else 0

# Ejemplo de uso
# if __name__ == "__main__":
#     print("🚀 Iniciando escáner de dispositivos...")
    
#     # Información de ejemplo de una red
#     red_ejemplo = {
#         "SSID": "MiRed_WiFi",
#         "Tecnologia": "WiFi 5 (ac)",
#         "Banda": "5 GHz",
#         "AnchoCanal": "80 MHz"
#     }
    
#     scanner = DeviceScanner()
#     result = scanner.scan_network(red_ejemplo)
    
#     if result['success']:
#         print(f"\n📊 RESULTADOS DEL ESCANEO:")
#         print(f"📍 Gateway: {result['gateway']}")
#         print(f"🌐 Rango: {result['network_range']}")
#         print(f"📱 Dispositivos conectados: {result['total_devices']}")
#         print(f"🚀 Capacidad máxima estimada: {result['max_devices']}")
#         print(f"📈 Uso de la red: {result['usage_percentage']}%")
        
#         if result['devices']:
#             print(f"\n📋 LISTA DE DISPOSITIVOS:")
#             for i, device in enumerate(result['devices'], 1):
#                 print(f"  {i}. {device['type']} | IP: {device['ip']} | MAC: {device['mac']} | Fabricante: {device['vendor']}")
#     else:
#         print(f"❌ Error: {result['error']}")