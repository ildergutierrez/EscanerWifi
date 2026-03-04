# EscanerWifi/backend/__init__.py
# Asegura que backend/ y la raíz del proyecto estén en sys.path
# para que los módulos del backend se importen directamente por nombre.
import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))   # EscanerWifi/backend/
_PROJ_ROOT   = os.path.dirname(_BACKEND_DIR)                # EscanerWifi/

for _p in (_PROJ_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)