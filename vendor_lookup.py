# vendor_lookup.py
"""
Consulta de fabricantes a partir del BSSID (OUI).
Versión con descarga automática desde fuentes oficiales.
"""

import requests
import json
import os
import time
import gzip
import shutil
from datetime import datetime, timedelta
from typing import Optional

class VendorLookup:
    def __init__(self):
        self.vendors = {}
        self.cache_file = os.path.join(os.path.dirname(__file__), "mac_vendors.json")
        self.max_cache_age = 30  # días
        self._load_database()
    
    def _load_database(self):
        """Cargar base de datos desde cache o descargar"""
        try:
            # Verificar si el cache existe y es reciente
            if os.path.exists(self.cache_file):
                file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(self.cache_file))
                if file_age.days < self.max_cache_age:
                    with open(self.cache_file, 'r', encoding='utf-8') as f:
                        self.vendors = json.load(f)
                        print(f"✅ Base de datos cargada: {len(self.vendors)} fabricantes")
                        return True
                else:
                    print("🔄 Cache expirado, descargando nueva base...")
            else:
                print("📥 Base de datos no encontrada, descargando...")
            
            # Descargar nueva base de datos
            return self._download_oui_database()
            
        except Exception as e:
            print(f"⚠️ Error cargando base: {e}")
            return self._download_oui_database()
    
    def _download_oui_database(self):
        """Descargar base de datos OUI desde fuentes alternativas"""
        sources = [
            self._download_from_ieee,
            self._download_from_wireshark,
            self._download_from_linux,
        ]
        
        for source in sources:
            try:
                if source():
                    print("✅ Base de datos descargada exitosamente")
                    return True
            except Exception as e:
                print(f"❌ Error con fuente {source.__name__}: {e}")
                continue
        
        print("❌ Todas las fuentes fallaron, usando base integrada")
        return self._load_builtin_database()
    
    def _download_from_wireshark(self):
        """Descargar desde Wireshark (fuente confiable)"""
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
                        # Solo tomar OUI completos (XX:XX:XX)
                        if len(oui) == 8 and oui.count(':') == 2:
                            vendors[oui] = vendor
            
            self.vendors = vendors
            self._save_database()
            return True
            
        except Exception as e:
            print(f"❌ Error con Wireshark: {e}")
            return False
    
    def _download_from_ieee(self):
        """Descargar desde IEEE (formato CSV)"""
        try:
            print("📥 Descargando desde IEEE...")
            url = "https://standards-oui.ieee.org/oui/oui.csv"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            vendors = {}
            lines = response.text.split('\n')[1:]  # Saltar header
            for line in lines:
                if line.strip():
                    parts = line.split('",')
                    if len(parts) >= 3:
                        oui = parts[0].replace('"', '').strip().upper()
                        vendor = parts[2].replace('"', '').strip()
                        if len(oui) == 8 and oui.count(':') == 2:
                            vendors[oui] = vendor
            
            self.vendors = vendors
            self._save_database()
            return True
            
        except Exception as e:
            print(f"❌ Error con IEEE: {e}")
            return False
    
    def _download_from_linux(self):
        """Descargar base de datos usada en sistemas Linux"""
        try:
            print("📥 Descargando base Linux...")
            url = "https://git.kernel.org/pub/scm/linux/kernel/git/shemminger/ethtool.git/plain/oui.c"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            vendors = {}
            in_oui_table = False
            
            for line in response.text.split('\n'):
                line = line.strip()
                if 'oui_table[]' in line:
                    in_oui_table = True
                    continue
                if in_oui_table and '}' in line:
                    break
                if in_oui_table and '{' in line and '"' in line:
                    # Formato: { "00:00:00", "Vendor Name" },
                    parts = line.split('"')
                    if len(parts) >= 4:
                        oui = parts[1].upper()
                        vendor = parts[3]
                        vendors[oui] = vendor
            
            self.vendors = vendors
            self._save_database()
            return True
            
        except Exception as e:
            print(f"❌ Error con base Linux: {e}")
            return False
    
    def _load_builtin_database(self):
        """Cargar base de datos integrada como fallback"""
        builtin_vendors = {
            "A8:49:4D": "Samsung Electronics Co.,Ltd",
            "C0:C9:E3": "TP-LINK TECHNOLOGIES CO.,LTD.",
            "DC:54:AD": "D-Link International",
            "24:A6:5E": "Samsung Electronics Co.,Ltd",
            "00:50:C2": "Microsoft Corporation",
            "00:0C:29": "VMware, Inc.",
            "00:1B:44": "HP Inc.",
            "00:1D:0F": "Cisco Systems, Inc",
            "00:23:AE": "Apple, Inc.",
            "00:26:BB": "Apple, Inc.",
            "00:50:56": "VMware, Inc.",
            "00:0D:3A": "Intel Corporate",
            "00:13:CE": "Intel Corporate",
            "00:1B:21": "Intel Corporate",
            "00:24:D6": "Intel Corporate",
            "08:00:27": "PCS Systemtechnik GmbH",
            "0A:00:27": "PCS Systemtechnik GmbH",
            "00:1C:42": "Dell Inc.",
            "00:22:19": "Dell Inc.",
            "00:14:22": "Dell Inc.",
            "00:18:8B": "Dell Inc.",
            "00:1D:09": "Dell Inc.",
            "00:0F:1F": "Dell Inc.",
            "00:12:3F": "Dell Inc.",
            "B8:27:EB": "Raspberry Pi Trading Ltd",
            "28:16:AD": "Huawei Technologies Co., Ltd",
            "64:16:66": "Huawei Technologies Co., Ltd",
            "E4:70:B8": "Huawei Technologies Co., Ltd",
            "00:1E:10": "Huawei Technologies Co., Ltd",
            "00:25:9E": "Huawei Technologies Co., Ltd",
            "00:1B:FC": "Nokia Corporation",
            "00:12:62": "Nokia Corporation",
            "00:18:4D": "Nokia Corporation",
            "00:15:A0": "Nokia Corporation",
            "00:1E:3A": "Nokia Corporation",
            "00:23:B3": "Nokia Corporation",
            "00:24:03": "Nokia Corporation",
            "00:26:CC": "Nokia Corporation",
            "00:02:EE": "LG Electronics",
            "00:1F:6B": "LG Electronics",
            "00:21:FB": "LG Electronics",
            "00:23:86": "LG Electronics",
            "00:26:E2": "LG Electronics",
            "00:60:B0": "LG Electronics",
            "00:E0:1C": "LG Electronics",
            "00:0E:6D": "LG Electronics",
            "00:1B:FB": "LG Electronics",
            "00:1E:7D": "LG Electronics",
            "00:22:A9": "LG Electronics",
            "00:24:83": "LG Electronics",
            "00:26:43": "LG Electronics",
            "00:60:1C": "ZyXEL Communications Corporation",
            "00:13:49": "ZyXEL Communications Corporation",
            "00:14:6C": "ZyXEL Communications Corporation",
            "00:17:C5": "ZyXEL Communications Corporation",
            "00:19:CB": "ZyXEL Communications Corporation",
            "00:1B:11": "ZyXEL Communications Corporation",
            "00:1D:19": "ZyXEL Communications Corporation",
            "00:1F:C7": "ZyXEL Communications Corporation",
            "00:21:2A": "ZyXEL Communications Corporation",
            "00:23:5A": "ZyXEL Communications Corporation",
            "00:24:7F": "ZyXEL Communications Corporation",
            "00:26:5A": "ZyXEL Communications Corporation",
        }
        
        self.vendors = builtin_vendors
        print(f"✅ Base integrada cargada: {len(builtin_vendors)} fabricantes")
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
        """Buscar fabricante por dirección MAC"""
        if not mac_address or len(mac_address) < 8:
            return "Desconocido"
        
        try:
            # Limpiar y formatear MAC
            mac_clean = mac_address.upper().replace('-', ':')
            parts = mac_clean.split(':')
            if len(parts) < 3:
                return "Desconocido"
            
            # Verificar si es MAC aleatoria
            first_octet = int(parts[0], 16)
            if first_octet & 0b10:  # bit LAA - MAC aleatoria
                return "MAC aleatoria"
            
            # Obtener OUI (primeros 3 bytes)
            oui = ':'.join(parts[:3])
            
            # Buscar en base de datos
            if oui in self.vendors:
                return self.vendors[oui]
            
            return "Desconocido"
            
        except Exception as e:
            print(f"⚠️ Error en lookup: {e}")
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
    Obtiene el fabricante a partir de un BSSID.
    """
    try:
        if not bssid:
            return "Desconocido"
        
        lookup = _get_vendor_lookup()
        result = lookup.lookup(bssid)
        return result if result else "Desconocido"
        
    except Exception as e:
        print(f"❌ Error crítico en get_vendor: {e}")
        return "Desconocido"

def update_oui_database() -> bool:
    """
    Fuerza actualización manual de la base de datos OUI.
    """
    try:
        lookup = _get_vendor_lookup()
        return lookup._download_oui_database()
    except Exception as e:
        print(f"❌ Error actualizando OUI: {e}")
        return False

def get_database_info() -> dict:
    """
    Obtiene información sobre la base de datos.
    """
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
    except Exception:
        return {"error": "No disponible"}

# Inicialización al importar
try:
    _get_vendor_lookup()
    print("✅ Módulo vendor_lookup inicializado correctamente")
except Exception as e:
    print(f"❌ Error inicializando vendor_lookup: {e}")

# Ejemplo de uso y pruebas
# if __name__ == "__main__":
#     # Test con algunas MAC conocidas
#     test_macs = [
#         "A8:49:4D:2C:32:F4",  # Samsung
#         "C0:C9:E3:62:1F:98",  # TP-Link
#         "DC:54:AD:61:11:0F",  # D-Link
#         "24:A6:5E:1B:78:77",  # Samsung
#         "B8:27:EB:12:34:56",  # Raspberry Pi
#     ]
    
#     print("🧪 Probando vendor lookup...")
#     for mac in test_macs:
#         vendor = get_vendor(mac)
#         print(f"  {mac} -> {vendor}")
    
#     db_info = get_database_info()
#     print(f"📊 Info base de datos: {db_info}")