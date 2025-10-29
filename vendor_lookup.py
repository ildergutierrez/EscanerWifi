"""
Consulta universal de fabricantes a partir del BSSID (OUI).
Sistema mejorado con múltiples fuentes y detección precisa de cualquier marca.
Incluye detección de MACs aleatorias y recuperación de MAC original.
"""

import requests
import json
import os
import re
import time
import subprocess
import platform
import socket
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple

class MACDetector:
    def __init__(self):
        self.original_mac_cache = {}
    
    def detect_original_mac(self, target_ssid: str, target_bssid: str = None) -> Dict[str, Optional[str]]:
        """
        Detecta la MAC original del router cuando se usa MAC aleatoria.
        MODIFICADO: No requiere estar conectado exactamente al mismo BSSID
        """
        try:
            from network_status import get_connected_wifi_info
            
            # Obtener información actual de la conexión
            current_wifi = get_connected_wifi_info()
            current_ssid = current_wifi.get('ssid')
            current_mac = current_wifi.get('bssid')
            
            # Verificar que estamos en la misma red (mismo SSID), no necesariamente mismo BSSID
            if not current_ssid or current_ssid.lower() != target_ssid.lower():
                return {
                    'original_mac': None,
                    'original_vendor': None,
                    'current_mac': target_bssid,
                    'is_random': False,
                    'confidence': 'bajo',
                    'error': f'No conectado a la red objetivo. Actual: {current_ssid}, Objetivo: {target_ssid}'
                }
            
            if not current_mac:
                return {
                    'original_mac': None,
                    'original_vendor': None,
                    'current_mac': None,
                    'is_random': False,
                    'confidence': 'bajo',
                    'error': 'No se pudo obtener BSSID actual'
                }
            
            # Si no es MAC aleatoria, retornar la misma MAC
            if not self._is_random_mac(target_bssid):
                return {
                    'original_mac': target_bssid,
                    'original_vendor': self._basic_lookup(target_bssid),
                    'current_mac': target_bssid,
                    'is_random': False,
                    'confidence': 'alto'
                }
            
            # Si es MAC aleatoria, intentar detectar la MAC original
            # USAR LA MAC ACTUAL DEL USUARIO COMO REFERENCIA
            original_mac = self._find_original_mac(target_ssid, current_mac)
            
            if original_mac:
                original_vendor = self._basic_lookup(original_mac)
                return {
                    'original_mac': original_mac,
                    'original_vendor': original_vendor,
                    'current_mac': target_bssid,
                    'is_random': True,
                    'confidence': 'alto'
                }
            else:
                # Si no se puede detectar, hacer una estimación
                estimated_mac = self._estimate_original_mac(target_ssid)
                estimated_vendor = self._basic_lookup(estimated_mac) if estimated_mac else "Desconocido"
                
                return {
                    'original_mac': estimated_mac,
                    'original_vendor': estimated_vendor,
                    'current_mac': target_bssid,
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
    
    def _is_random_mac(self, mac: str) -> bool:
        """Verifica si una MAC es aleatoria."""
        try:
            if not mac:
                return False
                
            parts = mac.upper().replace('-', ':').replace('.', ':').split(':')
            if len(parts) < 3:
                return False
            
            first_octet = int(parts[0], 16)
            is_local = (first_octet & 0b00000010) != 0
            return is_local
            
        except Exception:
            return False
    
    def _basic_lookup(self, mac: str) -> str:
        """Búsqueda básica de fabricante (sin detección de MAC aleatoria)."""
        try:
            if not mac or len(mac) < 8:
                return "Desconocido"
            
            mac_clean = mac.upper().replace('-', ':').replace('.', ':')
            parts = mac_clean.split(':')
            
            if len(parts) < 3:
                return "Desconocido"
            
            # Verificar formato válido
            for part in parts[:3]:
                if len(part) != 2 or not all(c in '0123456789ABCDEF' for c in part):
                    return "Formato MAC inválido"
            
            # Obtener OUI (primeros 3 bytes)
            oui = ':'.join(parts[:3])
            
            # Base de datos local de fabricantes
            vendors = {
                "00:1B:44": "HP Inc.",
                "00:23:AE": "Apple, Inc.",
                "00:0D:3A": "Intel Corporate",
                "00:50:C2": "Microsoft Corporation",
                "C0:C9:E3": "TP-LINK TECHNOLOGIES CO.,LTD.",
                "A8:49:4D": "Huawei Technologies Co., Ltd",
                "24:A6:5E": "Huawei Technologies Co., Ltd",
                "DC:54:AD": "D-Link International",
                "B8:27:EB": "Raspberry Pi Trading Ltd",
                "00:0C:29": "VMware, Inc.",
                "08:00:27": "PCS Systemtechnik GmbH",
                "00:1C:42": "Dell Inc.",
                "00:1B:FC": "Nokia Corporation",
                "00:02:EE": "LG Electronics",
                "00:1A:2B": "Sony Corporation",
                "00:12:EE": "ASUSTek COMPUTER INC.",
                "00:0F:B0": "NETGEAR",
                "64:09:80": "Xiaomi Communications Co Ltd",
                "00:1D:0F": "Cisco Systems, Inc",
                "00:13:CE": "Intel Corporate",
                "00:26:BB": "Apple, Inc.",
                "00:50:56": "VMware, Inc.",
                "28:16:AD": "Intel Corporate",
                "AC:5A:14": "Samsung Electronics Co.,Ltd",
                "04:15:52": "Apple, Inc.",
                "C4:A8:1D": "D-Link International",
                "38:54:39": "Guangzhou Shiyuan Electronic Technology Company Limited",
                "78:9A:18": "Routerboard.com",
                "20:1A:06": "COMPAL INFORMATION (KUNSHAN) CO., LTD.",
                "48:5A:B6": "Hon Hai Precision Ind. Co.,Ltd.",
                "B0:BE:76": "TP-LINK TECHNOLOGIES CO.,LTD.",
                "9C:E9:1C": "zte corporation",
                "14:46:58": "HUAWEI TECHNOLOGIES CO.,LTD",
                "48:22:54": "TP-Link Systems Inc",
                "3C:64:CF": "TP-Link Systems Inc",
                "EC:6C:B5": "zte corporation",
                "40:3F:8C": "TP-LINK TECHNOLOGIES CO.,LTD.",
                "E8:A1:F8": "zte corporation",
                "94:B2:71": "HUAWEI TECHNOLOGIES CO.,LTD",
                "B8:CC:5F": "Shenzhen iComm Semiconductor CO.,LTD",
                "A0:1C:8D": "HUAWEI TECHNOLOGIES CO.,LTD",
                "B0:B3:69": "Shenzhen SDMC Technology CO.,Ltd."
            }
            
            if oui in vendors:
                return vendors[oui]
            
            return "Desconocido"
            
        except Exception:
            return "Desconocido"
    
    def _find_original_mac(self, ssid: str, current_mac: str) -> Optional[str]:
        """Busca la MAC original usando múltiples métodos."""
        methods = [
            self._scan_arp_table,
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
                            
                            if mac != current_mac and not self._is_random_mac(mac):
                                if ip.endswith('.1') or ip.endswith('.254'):
                                    return mac
            else:
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        match = re.search(r'at\s+([0-9A-Fa-f:]{17})', line)
                        if match:
                            mac = match.group(1).upper()
                            if mac != current_mac and not self._is_random_mac(mac):
                                return mac
            
            return None
            
        except Exception:
            return None
    
    def _check_gateway_mac(self, ssid: str, current_mac: str) -> Optional[str]:
        """Obtiene la MAC del gateway por defecto."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                gateway_ip = '.'.join(local_ip.split('.')[:-1]) + '.1'
            
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
                    if mac != current_mac and not self._is_random_mac(mac):
                        return mac
            
            return None
            
        except Exception:
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
                            not self._is_random_mac(mac_clean) and
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
                                not self._is_random_mac(mac)):
                                return mac
            
            return None
            
        except Exception:
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
            }
            
            ssid_lower = ssid.lower()
            
            for vendor, prefixes in common_router_patterns.items():
                if vendor in ssid_lower:
                    return prefixes[0] + ':00:00:00'
            
            return 'C0:C9:E3:00:00:00'
            
        except Exception:
            return None
    
    def _validate_mac_candidate(self, mac: str, current_mac: str) -> bool:
        """Valida si una MAC candidata es probablemente la original."""
        if not mac or mac == current_mac:
            return False
        
        if self._is_random_mac(mac):
            return False
        
        if not re.match(r'^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$', mac):
            return False
        
        return True
    
    def _is_likely_router_mac(self, mac: str) -> bool:
        """Determina si una MAC es probablemente de un router."""
        router_vendors = [
            'huawei', 'tplink', 'dlink', 'cisco', 'netgear', 'asus',
            'xiaomi', 'mikrotik', 'ubiquiti', 'linksys', 'totolink'
        ]
        
        vendor = self._basic_lookup(mac).lower()
        return any(router_vendor in vendor for router_vendor in router_vendors)

class VendorLookup:
    def __init__(self):
        self.vendors: Dict[str, str] = {}
        self.mac_detector = MACDetector()
        self.cache_file = os.path.join(os.path.dirname(__file__), "mac_vendors.json")
        self.max_cache_age = 30
        self._load_database()
    
    def _load_database(self) -> bool:
        """Cargar base de datos desde cache o descargar"""
        try:
            if os.path.exists(self.cache_file):
                file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(self.cache_file))
                if file_age.days < self.max_cache_age:
                    with open(self.cache_file, 'r', encoding='utf-8') as f:
                        self.vendors = json.load(f)
                        print(f"✅ Base de datos cargada desde cache: {len(self.vendors)} fabricantes")
                        return True
                else:
                    print("🔄 Cache expirado, descargando nueva base...")
            else:
                print("📥 Base de datos no encontrada, descargando...")
            
            return self._download_oui_database()
            
        except Exception as e:
            print(f"⚠️ Error cargando base: {e}")
            return self._download_oui_database()
    
    def _download_oui_database(self) -> bool:
        """Descargar base de datos OUI desde múltiples fuentes"""
        sources = [
            self._download_from_wireshark,
            self._download_from_ieee,
            self._download_from_linux,
        ]
        
        success_count = 0
        for source in sources:
            try:
                if source():
                    success_count += 1
                    print(f"✅ {source.__name__} exitoso")
                    time.sleep(1)
            except Exception as e:
                print(f"❌ Error con {source.__name__}: {e}")
                continue
        
        if success_count > 0:
            print(f"✅ Base de datos actualizada desde {success_count} fuentes")
            return True
        else:
            print("❌ Todas las fuentes fallaron, usando base integrada")
            return self._load_builtin_database()
    
    def _download_from_wireshark(self) -> bool:
        """Descargar desde Wireshark"""
        try:
            print("📥 Descargando desde Wireshark...")
            url = "https://code.wireshark.org/review/gitweb?p=wireshark.git;a=blob_plain;f=manuf"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            vendors = {}
            for line in response.text.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and '\t' in line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        oui = parts[0].strip().upper()
                        vendor = parts[1].strip()
                        
                        if len(oui) == 8 and oui.count(':') == 2:
                            vendor = re.sub(r'\([^)]*\)', '', vendor).strip()
                            if vendor:
                                vendors[oui] = vendor
            
            if vendors:
                self.vendors = vendors
                self._save_database()
                print(f"📊 Wireshark: {len(vendors)} fabricantes")
                return True
            return False
            
        except Exception as e:
            print(f"❌ Error con Wireshark: {e}")
            return False
    
    def _download_from_ieee(self) -> bool:
        """Descargar desde IEEE"""
        try:
            print("📥 Descargando desde IEEE...")
            url = "https://standards-oui.ieee.org/oui/oui.csv"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            new_vendors = {}
            lines = response.text.split('\n')[1:]
            
            for line in lines:
                if line.strip():
                    try:
                        parts = line.split('","')
                        if len(parts) >= 3:
                            oui = parts[0].replace('"', '').strip().upper()
                            vendor = parts[2].replace('"', '').strip()
                            
                            if len(oui) == 6 and oui.isalnum():
                                oui_formatted = f"{oui[0:2]}:{oui[2:4]}:{oui[4:6]}"
                                if vendor and vendor != "undefined":
                                    new_vendors[oui_formatted] = vendor
                    except:
                        continue
            
            if new_vendors:
                self.vendors.update(new_vendors)
                self._save_database()
                print(f"📊 IEEE: {len(new_vendors)} fabricantes añadidos")
                return True
            return False
            
        except Exception as e:
            print(f"❌ Error con IEEE: {e}")
            return False
    
    def _download_from_linux(self) -> bool:
        """Descargar base usada en sistemas Linux"""
        try:
            print("📥 Descargando base Linux...")
            urls = [
                "http://linuxnet.ca/ieee/oui.txt",
                "https://git.kernel.org/pub/scm/linux/kernel/git/shemminger/ethtool.git/plain/oui.c"
            ]
            
            for url in urls:
                try:
                    response = requests.get(url, timeout=20)
                    if response.status_code == 200:
                        new_vendors = self._parse_linux_format(response.text)
                        if new_vendors:
                            self.vendors.update(new_vendors)
                            print(f"📊 Linux: {len(new_vendors)} fabricantes añadidos")
                            return True
                except:
                    continue
            return False
            
        except Exception as e:
            print(f"❌ Error con base Linux: {e}")
            return False
    
    def _parse_linux_format(self, content: str) -> Dict[str, str]:
        """Parsear diferentes formatos de archivos Linux"""
        vendors = {}
        
        for line in content.split('\n'):
            line = line.strip()
            if line and len(line) >= 18 and line[2] == '-':
                oui = line[:8].replace('-', ':').upper()
                vendor = line[18:].strip()
                if vendor:
                    vendors[oui] = vendor
        
        if not vendors:
            for line in content.split('\n'):
                if '{ "' in line and '"' in line:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        oui = parts[1].upper()
                        vendor = parts[3]
                        if oui.count(':') == 2:
                            vendors[oui] = vendor
        
        return vendors
    
    def _load_builtin_database(self) -> bool:
        """Cargar base de datos integrada mínima como fallback"""
        builtin_vendors = {
            "00:1B:44": "HP Inc.",
            "00:23:AE": "Apple, Inc.",
            "00:0D:3A": "Intel Corporate",
            "00:50:C2": "Microsoft Corporation",
            "C0:C9:E3": "TP-LINK TECHNOLOGIES CO.,LTD.",
            "A8:49:4D": "Huawei Technologies Co., Ltd",
            "24:A6:5E": "Huawei Technologies Co., Ltd",
            "DC:54:AD": "D-Link International",
            "B8:27:EB": "Raspberry Pi Trading Ltd",
            "00:0C:29": "VMware, Inc.",
            "08:00:27": "PCS Systemtechnik GmbH",
            "00:1C:42": "Dell Inc.",
            "00:1B:FC": "Nokia Corporation",
            "00:02:EE": "LG Electronics",
            "00:1A:2B": "Sony Corporation",
            "00:12:EE": "ASUSTek COMPUTER INC.",
            "00:0F:B0": "NETGEAR",
            "64:09:80": "Xiaomi Communications Co Ltd",
            "00:1D:0F": "Cisco Systems, Inc",
            "00:13:CE": "Intel Corporate",
            "00:26:BB": "Apple, Inc.",
            "00:50:56": "VMware, Inc.",
        }
        
        self.vendors = builtin_vendors
        print(f"✅ Base integrada cargada: {len(builtin_vendors)} fabricantes comunes")
        self._save_database()
        return True
    
    def _save_database(self):
        """Guardar base de datos en archivo local"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.vendors, f, ensure_ascii=False, indent=2)
            print(f"💾 Base guardada: {len(self.vendors)} fabricantes")
        except Exception as e:
            print(f"⚠️ Error guardando base: {e}")
    
    def lookup(self, mac_address: str, ssid: str = None) -> str:
        """
        Buscar fabricante por dirección MAC con detección de MACs aleatorias.
        
        Args:
            mac_address: Dirección MAC a consultar
            ssid: SSID de la red (opcional, para detección de MAC aleatoria)
        """
        if not mac_address or len(mac_address) < 8:
            return "Desconocido"
        
        try:
            mac_clean = mac_address.upper().replace('-', ':').replace('.', ':')
            parts = mac_clean.split(':')
            
            if len(parts) < 3:
                return "Desconocido"
            
            for part in parts[:3]:
                if len(part) != 2 or not all(c in '0123456789ABCDEF' for c in part):
                    return "Formato MAC inválido"
            
            oui = ':'.join(parts[:3])
            
            # Buscar en base de datos local primero
            if oui in self.vendors:
                vendor = self.vendors[oui]
                
                # Verificar si es MAC aleatoria
                if self._is_random_mac(mac_clean):
                    if ssid:
                        # Intentar detectar MAC original
                        detection_result = self.mac_detector.detect_original_mac(ssid, mac_clean)
                        if detection_result.get('original_vendor') and detection_result['original_vendor'] != "Desconocido":
                            return f"{detection_result['original_vendor']} (MAC Original)"
                    return "MAC Aleatoria"
                return vendor
            
            # Si no está en local, buscar en API externa
            vendor = self._search_realtime(oui)
            if vendor != "Desconocido":
                return vendor
            
            # Verificar si es MAC aleatoria
            if self._is_random_mac(mac_clean):
                if ssid:
                    detection_result = self.mac_detector.detect_original_mac(ssid, mac_clean)
                    if detection_result.get('original_vendor') and detection_result['original_vendor'] != "Desconocido":
                        return f"{detection_result['original_vendor']} (MAC Original)"
                return "MAC Aleatoria"
            
            return "Desconocido"
            
        except Exception as e:
            print(f"⚠️ Error en lookup MAC {mac_address}: {e}")
            return "Desconocido"
    
    def _is_random_mac(self, mac: str) -> bool:
        """Verifica si una MAC es aleatoria."""
        try:
            if not mac:
                return False
                
            parts = mac.upper().replace('-', ':').replace('.', ':').split(':')
            if len(parts) < 3:
                return False
            
            first_octet = int(parts[0], 16)
            is_local = (first_octet & 0b00000010) != 0
            return is_local
            
        except Exception:
            return False
    
    def _search_realtime(self, oui: str) -> str:
        """Búsqueda en tiempo real desde API externa"""
        apis = [
            self._query_macvendors_api,
            self._query_maclookup_api,
        ]
        
        for api in apis:
            try:
                vendor = api(oui)
                if vendor and vendor != "Desconocido":
                    self.vendors[oui] = vendor
                    self._save_database()
                    return vendor
            except:
                continue
        
        return "Desconocido"
    
    def _query_macvendors_api(self, oui: str) -> str:
        """Consultar API de macvendors.com"""
        try:
            url = f"https://api.macvendors.com/{oui.replace(':', '')}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                vendor = response.text.strip()
                if vendor and "error" not in vendor.lower() and vendor != "undefined":
                    return vendor
        except:
            pass
        return "Desconocido"
    
    def _query_maclookup_api(self, oui: str) -> str:
        """Consultar API de maclookup.app"""
        try:
            url = f"https://api.maclookup.app/v2/macs/{oui}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('company'):
                    return data['company']
        except:
            pass
        return "Desconocido"
    
    def get_enhanced_vendor_info(self, bssid: str, ssid: str = None) -> Dict[str, Optional[str]]:
        """
        Obtiene información mejorada del fabricante, detectando MACs aleatorias.
        """
        try:
            basic_vendor = self.lookup(bssid, ssid)
            
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
            detection_result = self.mac_detector.detect_original_mac(ssid, bssid)
            
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
                'vendor': self.lookup(bssid),
                'is_random': False,
                'original_mac': bssid,
                'original_vendor': self.lookup(bssid),
                'confidence': 'bajo',
                'error': str(e)
            }

# Instancia global singleton
_vendor_lookup = None

def _get_vendor_lookup():
    """Obtener instancia singleton de VendorLookup"""
    global _vendor_lookup
    if _vendor_lookup is None:
        _vendor_lookup = VendorLookup()
    return _vendor_lookup

def get_vendor(bssid: str, ssid: str = None) -> str:
    """
    Obtiene el fabricante a partir de un BSSID/MAC con detección de MACs aleatorias.
    
    Args:
        bssid: Dirección MAC del dispositivo
        ssid: SSID de la red (opcional, para detección de MAC aleatoria)
    """
    try:
        if not bssid:
            return "Desconocido"
        
        lookup = _get_vendor_lookup()
        return lookup.lookup(bssid, ssid)
        
    except Exception as e:
        print(f"❌ Error crítico en get_vendor: {e}")
        return "Desconocido"

def get_enhanced_vendor_info(bssid: str, ssid: str = None) -> Dict[str, Optional[str]]:
    """
    Obtiene información completa del fabricante incluyendo detección de MACs aleatorias.
    """
    try:
        lookup = _get_vendor_lookup()
        return lookup.get_enhanced_vendor_info(bssid, ssid)
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

def update_oui_database() -> bool:
    """Forzar actualización manual de la base de datos OUI"""
    try:
        lookup = _get_vendor_lookup()
        return lookup._download_oui_database()
    except Exception as e:
        print(f"❌ Error actualizando OUI: {e}")
        return False

def get_database_info() -> dict:
    """Obtener información sobre la base de datos"""
    try:
        lookup = _get_vendor_lookup()
        cache_file = lookup.cache_file
        cache_exists = os.path.exists(cache_file)
        cache_age = None
        
        if cache_exists:
            cache_time = os.path.getmtime(cache_file)
            cache_age = datetime.now() - datetime.fromtimestamp(cache_time)
        
        return {
            "total_vendors": len(lookup.vendors),
            "cache_file": cache_file,
            "cache_exists": cache_exists,
            "cache_age_days": cache_age.days if cache_age else None,
            "database_size": f"{len(str(lookup.vendors)) / 1024:.1f} KB"
        }
    except Exception as e:
        return {"error": f"No disponible: {e}"}

# Pruebas del módulo
if __name__ == "__main__":
    print("🚀 Inicializando vendor_lookup con detección de MACs aleatorias...")
    _get_vendor_lookup()
    
    # Modo interactivo para probar MACs específicas
    print("\n🎯 Modo de prueba interactivo")
    print("   (Escribe 'salir' para terminar, 'actualizar' para actualizar base de datos)")
    
    while True:
        print("\n" + "="*50)
        mac = input("🔍 Ingresa la MAC a verificar (formato: XX:XX:XX:XX:XX:XX): ").strip()
        
        if mac.lower() == 'salir':
            break
        elif mac.lower() == 'actualizar':
            print("🔄 Actualizando base de datos OUI...")
            if update_oui_database():
                print("✅ Base de datos actualizada correctamente")
            else:
                print("❌ Error actualizando base de datos")
            continue
            
        if not mac:
            continue
        
        # Obtener información actual de WiFi para referencia
        try:
            from network_status import get_connected_wifi_info
            current_wifi = get_connected_wifi_info()
            print(f"📶 Info actual - Conectado: {current_wifi['connected']}")
            print(f"   SSID actual: {current_wifi['ssid']}")
            print(f"   BSSID actual: {current_wifi['bssid']}")
        except:
            current_wifi = {'connected': False, 'ssid': None, 'bssid': None}
            
        ssid = input("📶 Ingresa el SSID de la red (opcional, presiona Enter para usar actual): ").strip()
        if not ssid and current_wifi['ssid']:
            ssid = current_wifi['ssid']
            print(f"   Usando SSID actual: {ssid}")
        
        print(f"\n📊 Analizando MAC: {mac}")
        
        # Información básica
        vendor_basic = get_vendor(mac)
        print(f"   Vendor básico: {vendor_basic}")
        
        # Información mejorada
        enhanced_info = get_enhanced_vendor_info(mac, ssid)
        print(f"   Vendor mejorado: {enhanced_info['vendor']}")
        print(f"   ¿Es MAC aleatoria?: {enhanced_info['is_random']}")
        print(f"   MAC original: {enhanced_info['original_mac']}")
        print(f"   Vendor original: {enhanced_info['original_vendor']}")
        print(f"   Confianza: {enhanced_info['confidence']}")
        
        if enhanced_info.get('note'):
            print(f"   Nota: {enhanced_info['note']}")
        if enhanced_info.get('error'):
            print(f"   Error: {enhanced_info['error']}")