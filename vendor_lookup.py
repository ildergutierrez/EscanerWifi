# vendor_lookup.py
"""
Consulta de fabricantes a partir del BSSID (OUI).
Usa la librería local mac-vendor-lookup (versión síncrona).
"""

import os
import time
from mac_vendor_lookup import MacLookup  # Asegúrate de tener la versión síncrona

_lookup = MacLookup()

# Ruta propia para guardar la base de datos local
VENDOR_FILE = os.path.join(os.path.expanduser("~"), ".mac-vendors.txt")

# Tiempo máximo (30 días) antes de volver a actualizar automáticamente
MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def _ensure_updated():
    """
    Verifica si la base OUI necesita actualizarse y la actualiza automáticamente.
    """
    try:
        if not os.path.exists(VENDOR_FILE):
            _lookup.update_vendors()
        else:
            age = time.time() - os.path.getmtime(VENDOR_FILE)
            if age > MAX_AGE_SECONDS:
                _lookup.update_vendors()
        _lookup.load_vendors()
    except Exception:
        # Si falla, seguimos con la base que tengamos
        pass


def get_vendor(bssid: str) -> str:
    """
    Obtiene el fabricante a partir de un BSSID.
    """
    if not bssid:
        return "Desconocido"

    # Revisar si es MAC aleatoria
    try:
        first_octet = int(bssid.split(":")[0], 16)
        if first_octet & 0b10:  # bit LAA
            return "MAC aleatoria / sin fabricante"
    except Exception:
        return "Desconocido"

    # Asegurar que la base esté actualizada
    _ensure_updated()

    try:
        vendor = _lookup.lookup(bssid)
        if vendor:
            return vendor
    except Exception:
        return "Desconocido"

    return "Desconocido"


def update_oui_database() -> bool:
    """
    Fuerza actualización manual de la base OUI (IEEE).
    """
    try:
        _lookup.update_vendors()
        _lookup.load_vendors()
        return True
    except Exception:
        return False


# Ejemplo de uso:
# if __name__ == "__main__":
#     test_bssid = "00:1A:2B:3C:4D:5E"
#     print(f"Fabricante de {test_bssid}: {get_vendor(test_bssid)}")
