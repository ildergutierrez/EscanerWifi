"""
vistas/workers.py – Workers QThread para el escáner WiFi
"""
# ── stdlib ────────────────────────────────────────────────────────────────
import sys
import os
from typing import Optional, Dict

# ── Rutas del proyecto ────────────────────────────────────────────────────
_VISTAS_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT  = os.path.dirname(_VISTAS_DIR)
_BACKEND    = os.path.join(_PROJ_ROOT, "backend")
_NETWORK    = os.path.join(_PROJ_ROOT, "network")
for _p in (_PROJ_ROOT, _BACKEND, _NETWORK):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── PyQt6 ─────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

# ── Imports del backend (prefijo explícito) ───────────────────────────────
from backend.main import scan_wifi
from backend.ai_suggestions import sugerencia_tecnologia, sugerencia_protocolo
from backend.network_status import (
    get_connected_wifi_info,
    is_current_network,
    get_network_congestion,
    is_connected_to_network,
    get_current_network_info,
)

try:
    from backend.network_speed import test_network_speed
except ImportError:
    def test_network_speed():
        return {"success": False, "error": "Módulo no disponible",
                "download_mbps": 0.0, "upload_mbps": 0.0, "ping_ms": 999.0}

try:
    from backend.vendor_lookup import get_vendor, get_enhanced_vendor_info
except Exception:
    def get_vendor(_): return "Desconocido"
    def get_enhanced_vendor_info(bssid, ssid=None):
        return {"vendor": "Desconocido", "is_random": False,
                "original_mac": bssid, "original_vendor": "Desconocido"}

try:
    from backend.ap_device_scanner import get_connected_devices, get_devices_count
except Exception:
    def get_connected_devices(red_info=None):
        return {"success": False, "devices": [], "total_devices": 0,
                "max_devices": 50, "usage_percentage": 0}
    def get_devices_count(red_info=None): return 0

try:
    from backend.mac_capacidad import get_router_info
except ImportError:
    def get_router_info(mac: str, wifi_tech: str = "", vendor: str = "") -> Dict:
        return {"model": "No detectado", "max_devices": 50,
                "wifi_standard": "Desconocido", "confidence": "low"}

try:
    from network.ui_ia.main_window import MainWindow as NetGuardWindow
    NETGUARD_OK = True
except ImportError as _e:
    print(f"NetGuard no disponible: {_e}")
    NETGUARD_OK = False
    NetGuardWindow = None

# ── Colores ───────────────────────────────────────────────────────────────
CARD_WIDTH        = 320
CARD_HEIGHT       = 160
COLOR_BG          = "#1E1E1E"
COLOR_CARD        = "#2D2D2D"
COLOR_CARD_BORDER = "#404040"
COLOR_TEXT        = "#E0E0E0"
COLOR_ACCENT      = "#0078D4"
COLOR_SUCCESS     = "#107C10"
COLOR_WARNING     = "#D83B01"
COLOR_ERROR       = "#E81123"
COLOR_MUTED       = "#848484"
COLOR_NoCONETCT   = "#79A3A1"


def signal_color_by_dbm(signal_dbm: Optional[float]) -> str:
    try:
        if signal_dbm is None: return COLOR_MUTED
        s = float(signal_dbm)
        if s >= -60: return COLOR_SUCCESS
        if s >= -70: return "#FFB900"
        if s >= -80: return COLOR_WARNING
        return COLOR_ERROR
    except Exception:
        return COLOR_MUTED


# ─────────────────────────────────────────────────────────────────────────
# WORKERS
# ─────────────────────────────────────────────────────────────────────────

class ScanWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._is_running = True

    def run(self):
        try:
            if not self._is_running: return
            redes = scan_wifi()
            if self._is_running:
                self.finished.emit(redes)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))

    def stop(self):
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(1000):
                self.terminate(); self.wait(1000)


class SpeedTestWorker(QThread):
    """Worker para test de velocidad de red (puede tardar varios segundos)."""
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._is_running = True

    def run(self):
        if not self._is_running: return
        try:
            result = test_network_speed()
            if self._is_running:
                self.finished.emit(result)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))

    def stop(self):
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(3000):   # speedtest puede ser lento
                self.terminate(); self.wait(1000)


class SuggestionWorker(QThread):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, red_meta, tipo="tecnologia"):
        super().__init__()
        self.red_meta    = red_meta
        self.tipo        = tipo
        self._is_running = True

    def run(self):
        if not self._is_running: return
        try:
            result = (sugerencia_tecnologia(self.red_meta)
                      if self.tipo == "tecnologia"
                      else sugerencia_protocolo(self.red_meta))
            if self._is_running:
                self.finished.emit(result)
        except Exception as e:
            if self._is_running:
                self.error.emit(f"Error: {e}")

    def stop(self):
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(1000):
                self.terminate(); self.wait(1000)


class VendorWorker(QThread):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, bssid, ssid=None):
        super().__init__()
        self.bssid       = bssid
        self.ssid        = ssid
        self._is_running = True

    def run(self):
        if not self._is_running: return
        try:
            self.msleep(50)
            if not self._is_running: return
            vendor_info = get_enhanced_vendor_info(self.bssid, self.ssid)
            if self._is_running:
                self.finished.emit(vendor_info["vendor"])
        except Exception as e:
            if self._is_running:
                self.error.emit(f"Error en consulta: {e}")

    def stop(self):
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(500):
                self.terminate(); self.wait(500)


class DevicesScanWorker(QThread):
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, red_meta):
        super().__init__()
        self.red_meta    = red_meta
        self._is_running = True

    def run(self):
        if not self._is_running: return
        try:
            result = get_connected_devices(self.red_meta)
            if self._is_running:
                self.finished.emit(result)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))

    def stop(self):
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(1000):
                self.terminate(); self.wait(1000)


class RouterCapacityWorker(QThread):
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, mac: str, vendor: str, wifi_tech: str = ""):
        super().__init__()
        self.mac         = mac
        self.vendor      = vendor
        self.wifi_tech   = wifi_tech
        self._is_running = True

    def run(self):
        if not self._is_running: return
        try:
            router_info = get_router_info(self.mac, self.wifi_tech, self.vendor)
            if self._is_running:
                self.finished.emit(router_info)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))

    def stop(self):
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(1000):
                self.terminate(); self.wait(1000)


# ─────────────────────────────────────────────────────────────────────────
# UI: SuggestionWindow
# ─────────────────────────────────────────────────────────────────────────

class SuggestionWindow(QDialog):
    def __init__(self, titulo: str, texto: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumSize(600, 500)
        self.set_icon()
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout()
        self.setLayout(layout)

        title_lbl = QLabel(titulo)
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet("""
            QLabel {
                color: #FFFFFF; padding: 15px;
                background-color: #2D2D2D;
                border-radius: 8px;
                border-left: 4px solid #0078D4;
            }
        """)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        text_area = QTextEdit()
        text_area.setReadOnly(True)
        text_area.setFont(QFont("Segoe UI", 10))
        text_area.setStyleSheet("""
            QTextEdit {
                background-color: #2D2D2D; color: #E0E0E0;
                border: 1px solid #404040; border-radius: 6px;
                padding: 15px; selection-background-color: #0078D4;
            }
        """)
        text_area.setText(texto)
        layout.addWidget(text_area)

    def set_icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "../img","wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))