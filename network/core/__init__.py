# EscanerWifi/network/core/__init__.py
# Asegura que network/ y la raíz estén en sys.path para que
# ia_detector.py, monitor.py y scaner.py puedan importar
# desde backend/ y entre sí.
import sys
import os

_CORE_DIR    = os.path.dirname(os.path.abspath(__file__))   # EscanerWifi/network/core/
_NETWORK_DIR = os.path.dirname(_CORE_DIR)                   # EscanerWifi/network/
_PROJ_ROOT   = os.path.dirname(_NETWORK_DIR)                # EscanerWifi/
_BACKEND_DIR = os.path.join(_PROJ_ROOT, "backend")          # EscanerWifi/backend/

for _p in (_PROJ_ROOT, _BACKEND_DIR, _NETWORK_DIR, _CORE_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)