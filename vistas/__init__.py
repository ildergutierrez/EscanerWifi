# EscanerWifi/vistas/__init__.py
# Asegura que la raíz del proyecto y backend/ estén en sys.path
# para que todos los archivos de vistas/ puedan importar del backend
# sin importar desde dónde se ejecute el programa.
import sys
import os

_VISTAS_DIR  = os.path.dirname(os.path.abspath(__file__))   # EscanerWifi/vistas/
_PROJ_ROOT   = os.path.dirname(_VISTAS_DIR)                 # EscanerWifi/
_BACKEND_DIR = os.path.join(_PROJ_ROOT, "backend")          # EscanerWifi/backend/
_NETWORK_DIR = os.path.join(_PROJ_ROOT, "network")          # EscanerWifi/network/

for _p in (_PROJ_ROOT, _BACKEND_DIR, _NETWORK_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)