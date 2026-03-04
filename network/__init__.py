# EscanerWifi/network/__init__.py
# Asegura que network/ y la raíz del proyecto estén en sys.path
# para que los módulos de network (NetGuard, ui_ia, core) se importen
# correctamente desde cualquier parte del proyecto.
import sys
import os

_NETWORK_DIR = os.path.dirname(os.path.abspath(__file__))   # EscanerWifi/network/
_PROJ_ROOT   = os.path.dirname(_NETWORK_DIR)                # EscanerWifi/

for _p in (_PROJ_ROOT, _NETWORK_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)