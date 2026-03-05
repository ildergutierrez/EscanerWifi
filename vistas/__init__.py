# EscanerWifi/vistas/__init__.py
# Asegura que raíz, backend/ y network/ estén en sys.path
# para que todos los módulos de vistas/ usen imports con prefijo explícito.
import sys
import os

_VISTAS_DIR  = os.path.dirname(os.path.abspath(__file__))   # EscanerWifi/vistas/
_PROJ_ROOT   = os.path.dirname(_VISTAS_DIR)                 # EscanerWifi/
_BACKEND_DIR = os.path.join(_PROJ_ROOT, "backend")          # EscanerWifi/backend/
_NETWORK_DIR = os.path.join(_PROJ_ROOT, "network")          # EscanerWifi/network/

for _p in (_PROJ_ROOT, _BACKEND_DIR, _NETWORK_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)