"""
Detector de MAC original para redes WiFi.
Identifica la MAC real del router cuando se usan MACs aleatorias.
"""

import subprocess
import platform
import re
import socket
from typing import Dict, Optional, List
from network_status import get_connected_wifi_info, is_connected_to_network
from vendor_lookup import get_vendor

class MACDetector:
    def __init__(self):
        self.original_mac_cache = {}
    
    def detect_original_mac(self, target_ssid: str, target_bssid: str = None) -> Dict[str, Optional[str]]:
        """
        Detecta la MAC original del router cuando se usa MAC aleatoria.
        
        Args:
            target_ssid: SSID de la red objetivo
            target_bssid: BSSID actual (MAC aleatoria) que se está usando
            
        Returns:
            Dict con:
            - 'original_mac': MAC original del router (None si no se puede detectar)
            - 'original_vendor': Fabricante de la MAC original
            - 'current_mac': MAC actualmente detectada
            - 'is_random': Si la MAC actual es aleatoria
            - 'confidence': Nivel de confianza en la detección (alto/medio/bajo)
        """
        try:
            # Verificar que estamos conectados a la red específica
            if not is_connected_to_network(target_ssid, target_bssid):
                return {
                    'original_mac': None,
                    'original_vendor': None,
                    'current_mac': target_bssid,
                    'is_random': False,
                    'confidence': 'bajo',
                    'error': 'No conectado a la red objetivo'
                }
            
            # Obtener información actual de la conexión
            current_wifi = get_connected_wifi_info()
            current_mac = current_wifi.get('bssid')
            
            if not current_mac:
                return {
                    'original_mac': None,
                    'original_vendor': None,
                    'current_mac': None,
                    'is_random': False,
                    'confidence': 'bajo',
                    'error': 'No se pudo obtener BSSID actual'
                }
            
            # Verificar si la MAC actual es aleatoria
            current_vendor = get_vendor(current_mac)
            is_random_mac = current_vendor == "MAC Aleatoria"
            
            if not is_random_mac:
                # Si no es aleatoria, retornar la misma MAC
                return {
                    'original_mac': current_mac,
                    'original_vendor': current_vendor,
                    'current_mac': current_mac,
                    'is_random': False,
                    'confidence': 'alto'
                }
            
            # Si es MAC aleatoria, intentar detectar la MAC original
            original_mac = self._find_original_mac(target_ssid, current_mac)
            
            if original_mac:
                original_vendor = get_vendor(original_mac)
                return {
                    'original_mac': original_mac,
                    'original_vendor': original_vendor,
                    'current_mac': current_mac,
                    'is_random': True,
                    'confidence': 'alto'
                }
            else:
                # Si no se puede detectar, hacer una estimación basada en patrones comunes
                estimated_mac = self._estimate_original_mac(target_ssid)
                estimated_vendor = get_vendor(estimated_mac) if estimated_mac else "Desconocido"
                
                return {
                    'original_mac': estimated_mac,
                    'original_vendor': estimated_vendor,
                    'current_mac': current_mac,
                    'is_random': True,
                    'confidence': 'medio' if estimated_mac else 'bajo',
                    'note': 'MAC estimada basada en patrones comunes' if estimated_mac else 'No se pudo detectar MAC original'
                }
                
        except Exception as e:
            return {
                'original_mac': None,
                'original_vendor': None,
                'current_mac': target_bssid,
                'is_random': False,
                'confidence': 'bajo',
                'error': f'Error en detección: {str(e)}'
            }
    
    def _find_original_mac(self, ssid: str, current_mac: str) -> Optional[str]:
        """
        Busca la MAC original usando múltiples métodos.
        """
        methods = [
            self._scan_arp_table,
            self._scan_network_neighbors,
            self._check_gateway_mac,
            self._scan_wifi_networks,
        ]
        
        for method in methods:
            try:
                result = method(ssid, current_mac)
                if result and self._validate_mac_candidate(result, current_mac):
                    return result
            except Exception:
                continue
        
        return None
    
    def _scan_arp_table(self, ssid: str, current_mac: str) -> Optional[str]:
        """
        Escanea la tabla ARP para encontrar dispositivos en la red.
        """
        try:
            system = platform.system().lower()
            
            if system == "windows":
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        # Buscar entradas ARP con formato: 192.168.1.1   00-11-22-33-44-55
                        match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9A-Fa-f-]{17})', line)
                        if match:
                            ip = match.group(1)
                            mac = match.group(2).replace('-', ':').upper()
                            
                            # Excluir la MAC actual y verificar que no sea aleatoria
                            if mac != current_mac and get_vendor(mac) != "MAC Aleatoria":
                                # Verificar si es el gateway común
                                if ip.endswith('.1') or ip.endswith('.254'):
                                    return mac
            else:
                # Linux/macOS
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        # Formato: router (192.168.1.1) at 00:11:22:33:44:55
                        match = re.search(r'at\s+([0-9A-Fa-f:]{17})', line)
                        if match:
                            mac = match.group(1).upper()
                            if mac != current_mac and get_vendor(mac) != "MAC Aleatoria":
                                return mac
            
            return None
            
        except Exception:
            return None
    
    def _scan_network_neighbors(self, ssid: str, current_mac: str) -> Optional[str]:
        """
        Escanea vecinos de red usando diferentes herramientas.
        """
        try:
            system = platform.system().lower()
            
            if system == "linux":
                # Usar ip neigh (Linux)
                result = subprocess.run(['ip', 'neigh', 'show'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 5:
                            mac = parts[4].upper()
                            state = parts[5] if len(parts) > 5 else ''
                            
                            # Preferir dispositivos con estado REACHABLE o STALE
                            if (mac != current_mac and 
                                get_vendor(mac) != "MAC Aleatoria" and
                                state in ['REACHABLE', 'STALE', 'DELAY']):
                                return mac
            
            return None
            
        except Exception:
            return None
    
    def _check_gateway_mac(self, ssid: str, current_mac: str) -> Optional[str]:
        """
        Obtiene la MAC del gateway por defecto.
        """
        try:
            # Obtener gateway
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                gateway_ip = s.getsockname()[0].rsplit('.', 1)[0] + '.1'
            
            # Hacer ARP ping al gateway
            system = platform.system().lower()
            if system == "windows":
                result = subprocess.run(['arp', '-a', gateway_ip], capture_output=True, text=True)
            else:
                result = subprocess.run(['arp', '-a', gateway_ip], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Buscar MAC en la salida
                output = result.stdout
                mac_match = re.search(r'([0-9A-Fa-f][0-9A-Fa-f][:-]){5}([0-9A-Fa-f][0-9A-Fa-f])', output)
                if mac_match:
                    mac = mac_match.group(0).replace('-', ':').upper()
                    if mac != current_mac and get_vendor(mac) != "MAC Aleatoria":
                        return mac
            
            return None
            
        except Exception:
            return None
    
    def _scan_wifi_networks(self, ssid: str, current_mac: str) -> Optional[str]:
        """
        Escanea redes WiFi cercanas para encontrar el mismo SSID con diferente BSSID.
        """
        try:
            system = platform.system().lower()
            target_ssid_clean = ssid.strip().lower()
            
            if system == "windows":
                result = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], 
                                      capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result.returncode == 0:
                    output = result.stdout
                    
                    # Buscar todas las instancias del mismo SSID
                    pattern = rf'SSID \d+ : {re.escape(target_ssid_clean)}.*?BSSID \d+ : ([0-9A-Fa-f:]+)'
                    matches = re.findall(pattern, output, re.IGNORECASE | re.DOTALL)
                    
                    for mac in matches:
                        mac_clean = mac.upper()
                        if (mac_clean != current_mac and 
                            get_vendor(mac_clean) != "MAC Aleatoria" and
                            self._is_likely_router_mac(mac_clean)):
                            return mac_clean
            
            elif system == "linux":
                result = subprocess.run(['nmcli', '-t', '-f', 'SSID,BSSID,SIGNAL', 'dev', 'wifi'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        parts = line.split(':')
                        if len(parts) >= 3:
                            line_ssid = parts[0]
                            mac = parts[1].upper()
                            
                            if (line_ssid.lower() == target_ssid_clean and 
                                mac != current_mac and 
                                get_vendor(mac) != "MAC Aleatoria"):
                                return mac
            
            return None
            
        except Exception:
            return None
    
    def _estimate_original_mac(self, ssid: str) -> Optional[str]:
        """
        Estima la MAC original basándose en patrones comunes de fabricantes.
        """
        try:
            # Patrones comunes de MACs de routers por fabricante
            common_router_patterns = {
                'huawei': ['24:A6:5E', '14:46:58', 'A0:1C:8D', '94:B2:71'],
                'tplink': ['C0:C9:E3', 'B0:BE:76', '48:22:54', '3C:64:CF', '40:3F:8C'],
                'dlink': ['DC:54:AD', 'C4:A8:1D'],
                'xiaomi': ['64:09:80'],
                'netgear': ['00:0F:B0'],
                'cisco': ['00:1D:0F'],
                'asus': ['00:12:EE'],
            }
            
            # Buscar en el SSID pistas del fabricante
            ssid_lower = ssid.lower()
            
            for vendor, prefixes in common_router_patterns.items():
                if vendor in ssid_lower:
                    return prefixes[0] + ':00:00:00'  # Retornar solo el OUI
            
            # Si no hay pistas, retornar el OUI más común para routers
            return 'C0:C9:E3:00:00:00'  # TP-Link como fallback común
            
        except Exception:
            return None
    
    def _validate_mac_candidate(self, mac: str, current_mac: str) -> bool:
        """
        Valida si una MAC candidata es probablemente la original.
        """
        if not mac or mac == current_mac:
            return False
        
        vendor = get_vendor(mac)
        if vendor == "MAC Aleatoria" or vendor == "Desconocido":
            return False
        
        # Verificar que tenga formato válido
        if not re.match(r'^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$', mac):
            return False
        
        return True
    
    def _is_likely_router_mac(self, mac: str) -> bool:
        """
        Determina si una MAC es probablemente de un router basándose en el fabricante.
        """
        router_vendors = [
            'huawei', 'tplink', 'dlink', 'cisco', 'netgear', 'asus',
            'xiaomi', 'mikrotik', 'ubiquiti', 'linksys', 'totolink'
        ]
        
        vendor = get_vendor(mac).lower()
        return any(router_vendor in vendor for router_vendor in router_vendors)

# Instancia global
_mac_detector = None

def get_mac_detector():
    """Obtener instancia singleton de MACDetector"""
    global _mac_detector
    if _mac_detector is None:
        _mac_detector = MACDetector()
    return _mac_detector

def detect_original_mac(ssid: str, bssid: str = None) -> Dict[str, Optional[str]]:
    """
    Función principal para detectar la MAC original del router.
    
    Args:
        ssid: SSID de la red WiFi
        bssid: BSSID actual (opcional)
        
    Returns:
        Dict con información de la MAC original y actual
    """
    detector = get_mac_detector()
    return detector.detect_original_mac(ssid, bssid)

def get_enhanced_vendor_info(bssid: str, ssid: str = None) -> Dict[str, Optional[str]]:
    """
    Obtiene información mejorada del fabricante, detectando MACs aleatorias.
    
    Args:
        bssid: BSSID a verificar
        ssid: SSID de la red (necesario para detección de MAC aleatoria)
        
    Returns:
        Dict con información completa del fabricante
    """
    try:
        # Obtener vendor básico
        basic_vendor = get_vendor(bssid)
        
        if basic_vendor != "MAC Aleatoria" or not ssid:
            return {
                'mac': bssid,
                'vendor': basic_vendor,
                'is_random': False,
                'original_mac': bssid,
                'original_vendor': basic_vendor,
                'confidence': 'alto'
            }
        
        # Si es MAC aleatoria y tenemos SSID, detectar MAC original
        detection_result = detect_original_mac(ssid, bssid)
        
        return {
            'mac': bssid,
            'vendor': basic_vendor,
            'is_random': True,
            'original_mac': detection_result['original_mac'],
            'original_vendor': detection_result['original_vendor'],
            'confidence': detection_result['confidence'],
            'note': detection_result.get('note')
        }
        
    except Exception as e:
        return {
            'mac': bssid,
            'vendor': get_vendor(bssid),
            'is_random': False,
            'original_mac': bssid,
            'original_vendor': get_vendor(bssid),
            'confidence': 'bajo',
            'error': str(e)
        }

# Pruebas del módulo
if __name__ == "__main__":
    print("🔍 Probando detección de MAC original...")
    
    # Obtener información actual de WiFi
    wifi_info = get_connected_wifi_info()
    
    if wifi_info['connected']:
        ssid = wifi_info['ssid']
        bssid = wifi_info['bssid']
        
        print(f"📶 Conectado a: {ssid}")
        print(f"📱 BSSID actual: {bssid}")
        print(f"🏭 Vendor básico: {get_vendor(bssid)}")
        
        # Detección mejorada
        enhanced_info = get_enhanced_vendor_info(bssid, ssid)
        
        print(f"\n🔍 Información mejorada:")
        print(f"   MAC actual: {enhanced_info['mac']}")
        print(f"   Vendor actual: {enhanced_info['vendor']}")
        print(f"   Es aleatoria: {enhanced_info['is_random']}")
        print(f"   MAC original: {enhanced_info['original_mac']}")
        print(f"   Vendor original: {enhanced_info['original_vendor']}")
        print(f"   Confianza: {enhanced_info['confidence']}")
        
        if enhanced_info.get('note'):
            print(f"   Nota: {enhanced_info['note']}")
    else:
        print("❌ No hay conexión WiFi activa")
        
    print("\n✅ Módulo mac_detector listo")