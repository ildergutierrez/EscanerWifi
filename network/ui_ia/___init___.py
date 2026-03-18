# EscanerWifi/network/ui_ia/__init__.py
import sys
import os

_UI_IA_DIR   = os.path.dirname(os.path.abspath(__file__))
_NETWORK_DIR = os.path.dirname(_UI_IA_DIR)
_PROJ_ROOT   = os.path.dirname(_NETWORK_DIR)
_BACKEND_DIR = os.path.join(_PROJ_ROOT, "backend")

for _p in (_PROJ_ROOT, _BACKEND_DIR, _NETWORK_DIR, _UI_IA_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)