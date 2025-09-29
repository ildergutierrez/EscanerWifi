# vendor_lookup.py
"""
Consulta de fabricantes a partir del BSSID (OUI).
Usa la librería local mac-vendor-lookup (basada en la base oficial del IEEE).
"""

import os
import time
from mac_vendor_lookup import MacLookup

_lookup = MacLookup()

# Definimos una ruta propia para guardar la base de datos local
VENDOR_FILE = os.path.join(os.path.expanduser("~"), ".mac-vendors.txt")

# Tiempo máximo (30 días) antes de volver a actualizar automáticamente
MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def _ensure_updated():
    """
    Verifica si la base OUI necesita actualizarse y lo hace automáticamente.
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
        # Si falla, seguimos con lo que tengamos
        pass


def get_vendor(bssid: str) -> str:
    if not bssid:
        return "Desconocido"

    # Revisar si es MAC aleatoria
    try:
        first_octet = int(bssid.split(":")[0], 16)
        if first_octet & 0b10:  # bit LAA
            return "MAC aleatoria / sin fabricante"
    except Exception:
        return "Desconocido"

    # Aseguramos que la base esté actualizada
    _ensure_updated()

    try:
        vendor = _lookup.lookup(bssid)
        if vendor:
            return vendor
    except Exception:
        return "Desconocido"

    return "Desconocido"


def update_oui_database():
    """
    Fuerza actualización manual de la base OUI (IEEE).
    """
    try:
        _lookup.update_vendors()
        _lookup.load_vendors()
        return True
    except Exception:
        return False
