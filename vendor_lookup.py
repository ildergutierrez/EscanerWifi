"""
Consulta universal de fabricantes a partir del BSSID (OUI).
Sistema mejorado con múltiples fuentes y detección precisa de cualquier marca.
"""

import requests
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List

class VendorLookup:
    def __init__(self):
        self.vendors: Dict[str, str] = {}
        self.cache_file = os.path.join(os.path.dirname(__file__), "mac_vendors.json")
        self.max_cache_age = 30  # días
        self._load_database()
    
    def _load_database(self) -> bool:
        """Cargar base de datos desde cache o descargar"""
        try:
            # Verificar si el cache existe y es reciente
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
            
            # Intentar descargar nueva base de datos
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
                    time.sleep(1)  # Espera entre requests
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
        """Descargar desde Wireshark (fuente más confiable y completa)"""
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
                        
                        # Filtrar solo OUI completos (formato XX:XX:XX)
                        if len(oui) == 8 and oui.count(':') == 2:
                            # Limpiar nombre (remover comentarios entre paréntesis)
                            vendor = re.sub(r'\([^)]*\)', '', vendor).strip()
                            if vendor:
                                vendors[oui] = vendor
            
            if vendors:
                self.vendors = vendors  # Reemplazar con datos frescos
                self._save_database()
                print(f"📊 Wireshark: {len(vendors)} fabricantes")
                return True
            return False
            
        except Exception as e:
            print(f"❌ Error con Wireshark: {e}")
            return False
    
    def _download_from_ieee(self) -> bool:
        """Descargar desde IEEE (fuente oficial)"""
        try:
            print("📥 Descargando desde IEEE...")
            url = "https://standards-oui.ieee.org/oui/oui.csv"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            new_vendors = {}
            lines = response.text.split('\n')[1:]  # Saltar header
            
            for line in lines:
                if line.strip():
                    try:
                        # Manejar formato CSV correctamente
                        parts = line.split('","')
                        if len(parts) >= 3:
                            oui = parts[0].replace('"', '').strip().upper()
                            vendor = parts[2].replace('"', '').strip()
                            
                            # Convertir formato IEEE (001122) a MAC (00:11:22)
                            if len(oui) == 6 and oui.isalnum():
                                oui_formatted = f"{oui[0:2]}:{oui[2:4]}:{oui[4:6]}"
                                if vendor and vendor != "undefined":
                                    new_vendors[oui_formatted] = vendor
                    except:
                        continue
            
            if new_vendors:
                self.vendors.update(new_vendors)  # Actualizar, no reemplazar
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
        
        # Formato oui.txt
        for line in content.split('\n'):
            line = line.strip()
            if line and len(line) >= 18 and line[2] == '-':
                oui = line[:8].replace('-', ':').upper()
                vendor = line[18:].strip()
                if vendor:
                    vendors[oui] = vendor
        
        # Formato oui.c
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
            # Fabricantes más comunes globalmente
            "00:1B:44": "HP Inc.",
            "00:23:AE": "Apple, Inc.",
            "00:0D:3A": "Intel Corporate",
            "00:50:C2": "Microsoft Corporation",
            "C0:C9:E3": "TP-LINK TECHNOLOGIES CO.,LTD.",
            "A8:49:4D": "Samsung Electronics Co.,Ltd",
            "24:A6:5E": "Huawei Technologies Co., Ltd",  # CORREGIDO
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
    
    def lookup(self, mac_address: str) -> str:
        """
        Buscar fabricante por dirección MAC.
        Detecta automáticamente cualquier fabricante.
        """
        if not mac_address or len(mac_address) < 8:
            return "Desconocido"
        
        try:
            # Limpiar y normalizar formato MAC
            mac_clean = mac_address.upper().replace('-', ':').replace('.', ':')
            parts = mac_clean.split(':')
            
            if len(parts) < 3:
                return "Desconocido"
            
            # Verificar formato válido
            for part in parts[:3]:
                if len(part) != 2 or not all(c in '0123456789ABCDEF' for c in part):
                    return "Formato MAC inválido"
            
            # Obtener OUI (primeros 3 bytes)
            oui = ':'.join(parts[:3])
            
            # Buscar en base de datos local primero
            if oui in self.vendors:
                return self.vendors[oui]
            
            # Si no está en local, buscar en API externa
            vendor = self._search_realtime(oui)
            if vendor != "Desconocido":
                return vendor
            
            # Último intento: verificar si es MAC aleatoria
            try:
                first_octet = int(parts[0], 16)
                is_local = (first_octet & 0b00000010) != 0
                if is_local:
                    return "MAC Aleatoria"
            except:
                pass
            
            return "Desconocido"
            
        except Exception as e:
            print(f"⚠️ Error en lookup MAC {mac_address}: {e}")
            return "Desconocido"
    
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
                    # Guardar en cache para futuras consultas
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

# Instancia global singleton
_vendor_lookup = None

def _get_vendor_lookup():
    """Obtener instancia singleton de VendorLookup"""
    global _vendor_lookup
    if _vendor_lookup is None:
        _vendor_lookup = VendorLookup()
    return _vendor_lookup

def get_vendor(bssid: str) -> str:
    """
    Obtiene el fabricante a partir de un BSSID/MAC.
    
    Args:
        bssid: Dirección MAC del dispositivo (cualquier formato)
        
    Returns:
        str: Nombre del fabricante o "Desconocido"
    """
    try:
        if not bssid:
            return "Desconocido"
        
        lookup = _get_vendor_lookup()
        return lookup.lookup(bssid)
        
    except Exception as e:
        print(f"❌ Error crítico en get_vendor: {e}")
        return "Desconocido"

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

def test_multiple_vendors():
    """Probar detección de múltiples fabricantes"""
    print("\n🧪 Probando detección de múltiples fabricantes...")
    
    test_macs = [
        # Huawei
        "24:A6:5E:12:34:56",
        "28:16:AD:AB:CD:EF",
        # Samsung
        "A8:49:4D:11:22:33", 
        "AC:5A:14:AA:BB:CC",
        # Apple
        "00:23:AE:44:55:66",
        "04:15:52:77:88:99",
        # TP-Link
        "C0:C9:E3:33:44:55",
        "C4:A8:1D:66:77:88",
        # D-Link
        "DC:54:AD:99:AA:BB",
        # Intel
        "00:0D:3A:CC:DD:EE",
        # Microsoft
        "00:50:C2:FF:11:22",
        # Xiaomi
        "64:09:80:55:66:77",
    ]
    
    for mac in test_macs:
        vendor = get_vendor(mac)
        print(f"  📱 {mac} -> {vendor}")

# Inicialización al importar
if __name__ == "__main__":
    print("🚀 Inicializando vendor_lookup...")
    _get_vendor_lookup()
    
    # Ejecutar pruebas completas
    test_multiple_vendors()
    
    # Mostrar info de la base de datos
    db_info = get_database_info()
    print(f"\n📊 Información de la base de datos:")
    for key, value in db_info.items():
        print(f"   {key}: {value}")
    
    print("✅ Módulo vendor_lookup inicializado correctamente")
else:
    # Inicialización silenciosa cuando se importa como módulo
    try:
        _get_vendor_lookup()
    except Exception as e:
        print(f"❌ Error inicializando vendor_lookup: {e}")