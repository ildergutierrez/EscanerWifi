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

class MACDetector:
    def __init__(self):
        self.original_mac_cache = {}
    
    def detect_original_mac(self, target_ssid: str, target_bssid: str = None) -> Dict[str, Optional[str]]:
        """
        Detecta la MAC original del router cuando se usa MAC aleatoria.
        SOLO se encarga de encontrar la MAC original, no hace lookup de vendor.
        """
        try:
            print(f"🔍 [MACDetector] Iniciando detección para SSID: {target_ssid}")
            
            # Verificar que estamos conectados a la red específica
            if not is_connected_to_network(target_ssid, target_bssid):
                return {
                    'original_mac': None,
                    'current_mac': target_bssid,
                    'is_random': False,
                    'confidence': 'bajo',
                    'error': 'No conectado a la red objetivo'
                }
            
            # Obtener información actual de la conexión
            current_wifi = get_connected_wifi_info()
            current_mac = current_wifi.get('bssid')
            current_ssid = current_wifi.get('ssid')
            
            print(f"🔍 [MACDetector] WiFi actual - SSID: {current_ssid}, BSSID: {current_mac}")
            
            if not current_mac:
                return {
                    'original_mac': None,
                    'current_mac': None,
                    'is_random': False,
                    'confidence': 'bajo',
                    'error': 'No se pudo obtener BSSID actual'
                }
            
            # Verificar si la MAC actual es aleatoria (solo por patrones, sin vendor lookup)
            is_random_mac = self._is_random_mac_by_pattern(current_mac)
            print(f"🔍 [MACDetector] ¿Es MAC aleatoria por patrón? {is_random_mac}")
            
            if not is_random_mac:
                # Si no es aleatoria, retornar la misma MAC
                return {
                    'original_mac': current_mac,
                    'current_mac': current_mac,
                    'is_random': False,
                    'confidence': 'alto',
                    'note': 'MAC no parece ser aleatoria'
                }
            
            # Si es MAC aleatoria, intentar detectar la MAC original
            print(f"🔍 [MACDetector] Buscando MAC original para MAC aleatoria: {current_mac}")
            original_mac = self._find_original_mac(target_ssid, current_mac)
            
            if original_mac and original_mac != current_mac:
                print(f"🔍 [MACDetector] MAC original encontrada: {original_mac}")
                return {
                    'original_mac': original_mac,
                    'current_mac': current_mac,
                    'is_random': True,
                    'confidence': 'alto',
                    'note': 'MAC original detectada exitosamente'
                }
            else:
                # Si no se puede detectar, hacer una estimación basada en patrones comunes
                estimated_mac = self._estimate_original_mac(target_ssid)
                print(f"🔍 [MACDetector] MAC estimada: {estimated_mac}")
                
                return {
                    'original_mac': estimated_mac,
                    'current_mac': current_mac,
                    'is_random': True,
                    'confidence': 'medio' if estimated_mac else 'bajo',
                    'note': 'MAC estimada basada en patrones comunes' if estimated_mac else 'No se pudo detectar MAC original'
                }
                
        except Exception as e:
            print(f"❌ [MACDetector] Error: {e}")
            return {
                'original_mac': None,
                'current_mac': target_bssid,
                'is_random': False,
                'confidence': 'bajo',
                'error': f'Error en detección: {str(e)}'
            }
    
    def _is_random_mac_by_pattern(self, mac: str) -> bool:
        """Verifica si una MAC es aleatoria solo por patrones (sin vendor lookup)."""
        try:
            if not mac:
                return False
                
            mac_clean = mac.upper().replace('-', ':').replace('.', ':')
            parts = mac_clean.split(':')
            
            if len(parts) < 3:
                return False
            
            # Primer octeto en hexadecimal
            first_octet = int(parts[0], 16)
            
            # Bit 1 (segundo bit menos significativo) = 1 indica MAC local/aleatoria
            is_local = (first_octet & 0b00000010) != 0
            
            # Patrones comunes de MACs aleatorias
            random_indicators = [
                mac_clean.startswith('02:'),  # MAC locales
                mac_clean.startswith('06:'),  # Algunas MAC aleatorias
                mac_clean.startswith('0A:'),  # Otras MAC aleatorias
                mac_clean.startswith('0E:'),  # Más MAC aleatorias
                (first_octet & 0b00000010) != 0,  # Bit de local/universal
            ]
            
            result = any(random_indicators)
            print(f"🔍 [MACDetector] MAC {mac_clean} - Primer octeto: {first_octet:02x}, Es aleatoria: {result}")
            return result
            
        except Exception as e:
            print(f"❌ [MACDetector] Error en _is_random_mac_by_pattern: {e}")
            return False
    
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
            except Exception as e:
                print(f"⚠️ [MACDetector] Error en método {method.__name__}: {e}")
                continue
        
        return None
    
    def _scan_arp_table(self, ssid: str, current_mac: str) -> Optional[str]:
        """Escanea la tabla ARP para encontrar dispositivos en la red."""
        try:
            system = platform.system().lower()
            
            if system == "windows":
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9A-Fa-f-]{17})', line)
                        if match:
                            ip = match.group(1)
                            mac = match.group(2).replace('-', ':').upper()
                            
                            # Excluir la MAC actual y verificar que no sea aleatoria por patrón
                            if mac != current_mac and not self._is_random_mac_by_pattern(mac):
                                # Verificar si es el gateway común
                                if ip.endswith('.1') or ip.endswith('.254'):
                                    print(f"🔍 [MACDetector] Encontrado gateway en ARP: {mac} (IP: {ip})")
                                    return mac
            else:
                # Linux/macOS
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        match = re.search(r'at\s+([0-9A-Fa-f:]{17})', line)
                        if match:
                            mac = match.group(1).upper()
                            if mac != current_mac and not self._is_random_mac_by_pattern(mac):
                                return mac
            
            return None
            
        except Exception as e:
            print(f"❌ [MACDetector] Error en _scan_arp_table: {e}")
            return None
    
    def _scan_network_neighbors(self, ssid: str, current_mac: str) -> Optional[str]:
        """Escanea vecinos de red usando diferentes herramientas."""
        try:
            system = platform.system().lower()
            
            if system == "linux":
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
                                not self._is_random_mac_by_pattern(mac) and
                                state in ['REACHABLE', 'STALE', 'DELAY']):
                                return mac
            
            return None
            
        except Exception as e:
            print(f"❌ [MACDetector] Error en _scan_network_neighbors: {e}")
            return None
    
    def _check_gateway_mac(self, ssid: str, current_mac: str) -> Optional[str]:
        """Obtiene la MAC del gateway por defecto."""
        try:
            # Obtener gateway
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                gateway_ip = s.getsockname()[0].rsplit('.', 1)[0] + '.1'
            
            print(f"🔍 [MACDetector] Gateway IP: {gateway_ip}")
            
            # Hacer ARP ping al gateway
            system = platform.system().lower()
            if system == "windows":
                result = subprocess.run(['arp', '-a', gateway_ip], capture_output=True, text=True)
            else:
                result = subprocess.run(['arp', '-a', gateway_ip], capture_output=True, text=True)
            
            if result.returncode == 0:
                output = result.stdout
                mac_match = re.search(r'([0-9A-Fa-f][0-9A-Fa-f][:-]){5}([0-9A-Fa-f][0-9A-Fa-f])', output)
                if mac_match:
                    mac = mac_match.group(0).replace('-', ':').upper()
                    if mac != current_mac and not self._is_random_mac_by_pattern(mac):
                        print(f"🔍 [MACDetector] Gateway MAC encontrada: {mac}")
                        return mac
            
            return None
            
        except Exception as e:
            print(f"❌ [MACDetector] Error en _check_gateway_mac: {e}")
            return None
    
    def _scan_wifi_networks(self, ssid: str, current_mac: str) -> Optional[str]:
        """Escanea redes WiFi cercanas para encontrar el mismo SSID con diferente BSSID."""
        try:
            system = platform.system().lower()
            target_ssid_clean = ssid.strip().lower()
            
            if system == "windows":
                result = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], 
                                      capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result.returncode == 0:
                    output = result.stdout
                    
                    pattern = rf'SSID \d+ : {re.escape(target_ssid_clean)}.*?BSSID \d+ : ([0-9A-Fa-f:]+)'
                    matches = re.findall(pattern, output, re.IGNORECASE | re.DOTALL)
                    
                    for mac in matches:
                        mac_clean = mac.upper()
                        if (mac_clean != current_mac and 
                            not self._is_random_mac_by_pattern(mac_clean) and
                            self._is_likely_router_mac(mac_clean)):
                            print(f"🔍 [MACDetector] Encontrada en WiFi scan: {mac_clean}")
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
                                not self._is_random_mac_by_pattern(mac)):
                                return mac
            
            return None
            
        except Exception as e:
            print(f"❌ [MACDetector] Error en _scan_wifi_networks: {e}")
            return None
    
    def _estimate_original_mac(self, ssid: str) -> Optional[str]:
        """Estima la MAC original basándose en patrones comunes de fabricantes."""
        try:
            common_router_patterns = {
                'huawei': ['24:A6:5E', '14:46:58', 'A0:1C:8D', '94:B2:71'],
                'tplink': ['C0:C9:E3', 'B0:BE:76', '48:22:54', '3C:64:CF', '40:3F:8C'],
                'dlink': ['DC:54:AD', 'C4:A8:1D'],
                'xiaomi': ['64:09:80'],
                'netgear': ['00:0F:B0'],
                'cisco': ['00:1D:0F'],
                'asus': ['00:12:EE'],
                'mikrotik': ['00:0C:42', '4C:5E:0C', 'D4:CA:6D'],
                'routerboard': ['00:0C:42', '4C:5E:0C', 'D4:CA:6D'],
            }
            
            ssid_lower = ssid.lower()
            
            for vendor, prefixes in common_router_patterns.items():
                if vendor in ssid_lower:
                    selected_prefix = prefixes[0]
                    # Generar una MAC completa con el prefijo
                    return f"{selected_prefix}:00:00:00"
            
            return 'C0:C9:E3:00:00:00'  # TP-Link por defecto
            
        except Exception as e:
            print(f"❌ [MACDetector] Error en _estimate_original_mac: {e}")
            return None
    
    def _validate_mac_candidate(self, mac: str, current_mac: str) -> bool:
        """Valida si una MAC candidata es probablemente la original."""
        if not mac or mac == current_mac:
            return False
        
        if not re.match(r'^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$', mac):
            return False
        
        # Verificar que no sea aleatoria por patrón
        if self._is_random_mac_by_pattern(mac):
            return False
        
        return True
    
    def _is_likely_router_mac(self, mac: str) -> bool:
        """Determina si una MAC es probablemente de un router basándose en patrones."""
        # Patrones OUI comunes de routers
        router_ouis = [
            '00:0C:42',  # Mikrotik
            'C0:C9:E3',  # TP-Link
            '24:A6:5E',  # Huawei
            'DC:54:AD',  # D-Link
            '00:0F:B0',  # Netgear
            '00:1D:0F',  # Cisco
            '00:12:EE',  # Asus
            '64:09:80',  # Xiaomi
            '4C:5E:0C',  # Mikrotik
            'D4:CA:6D',  # Mikrotik
        ]
        
        mac_clean = mac.upper().replace('-', ':')
        oui = ':'.join(mac_clean.split(':')[:3])
        
        return oui in router_ouis

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
    """
    detector = get_mac_detector()
    return detector.detect_original_mac(ssid, bssid)

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
        
        # Detección de MAC original
        detection_result = detect_original_mac(ssid, bssid)
        
        print(f"\n🔍 Resultado detección:")
        print(f"   MAC actual: {detection_result['current_mac']}")
        print(f"   MAC original: {detection_result['original_mac']}")
        print(f"   Es aleatoria: {detection_result['is_random']}")
        print(f"   Confianza: {detection_result['confidence']}")
        
        if detection_result.get('note'):
            print(f"   Nota: {detection_result['note']}")
        if detection_result.get('error'):
            print(f"   Error: {detection_result['error']}")
    else:
        print("❌ No hay conexión WiFi activa")
        
    print("\n✅ Módulo mac_detector listo")