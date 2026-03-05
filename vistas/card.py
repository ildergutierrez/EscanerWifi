"""
vistas/card.py – Tarjeta de red WiFi
"""
# ── stdlib ────────────────────────────────────────────────────────────────
import sys
import os
import subprocess
import platform
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
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QScrollArea, QGridLayout, QPushButton, QFrame, QDialog,
    QTextEdit, QHBoxLayout, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QIcon, QCursor, QMouseEvent

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
    from ui_ia.main_window import MainWindow as NetGuardWindow
    NETGUARD_OK = True
except ImportError as _e:
    print(f"NetGuard no disponible: {_e}")
    NETGUARD_OK = False
    NetGuardWindow = None

# ── Constantes visuales ───────────────────────────────────────────────────
CARD_WIDTH  = 320
CARD_HEIGHT = 160

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


# ═══════════════════════════════════════════════════════════════════════════
# PEGA AQUÍ EL RESTO DEL CÓDIGO ORIGINAL DE card.py (clase Card y lo demás)
# Solo se corrigió el bloque de imports de arriba — nada más cambia.
# ═══════════════════════════════════════════════════════════════════════════
from vistas.workers import RouterCapacityWorker

class Card(QFrame):
    def __init__(self, red: dict, parent=None):
        super().__init__(parent)
        self.red = red
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        
        # Verificar si es la red conectada y aplicar estilo
        self._apply_connection_style()
        
        self._build_ui()
        # Cargar información del router en segundo plano
        self._load_router_info()

    def _apply_connection_style(self):
        """Aplicar estilo de borde según si está conectado o no"""
        ssid = self.red.get("SSID")
        bssid = self.red.get("BSSID")
        
        if ssid and is_current_network(ssid, bssid):
            # Borde VERDE para red conectada
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLOR_CARD};
                    border-radius: 8px;
                    border: 3px solid {COLOR_SUCCESS};
                    position: relative;
                }}
                QLabel {{
                    color: {COLOR_TEXT};
                    background-color: transparent;
                }}
            """)
        else:
            # Borde ROJO para otras redes
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLOR_CARD};
                    border-radius: 8px;
                    border: 2px solid {COLOR_NoCONETCT};
                    position: relative;
                }}
                QLabel {{
                    color: {COLOR_TEXT};
                    background-color: transparent;
                }}
            """)

    def _load_router_info(self):
        """Cargar información del router en segundo plano"""
        mac = self.red.get("BSSID")
        vendor = self.red.get("Fabricante")
        wifi_tech = self.red.get("Tecnologia", "")
        
        if mac and vendor:
            self.router_worker = RouterCapacityWorker(mac, vendor, wifi_tech)
            self.router_worker.finished.connect(self._on_router_info_loaded)
            self.router_worker.error.connect(lambda e: print(f"Error router info: {e}"))
            self.router_worker.start()

    def _on_router_info_loaded(self, router_info):
        """Callback cuando se carga la información del router"""
        if router_info and router_info.get("max_devices"):
            self.red["router_max_devices"] = router_info["max_devices"]
            self.red["router_model"] = router_info.get("model", "No detectado")
            # Actualizar la UI con el modelo del router
            self._update_router_model()

    def _update_router_model(self):
        """Actualizar el modelo del router en la tarjeta"""
        try:
            router_model = self.red.get("router_model", "")
            # Solo actualizar si no es "No detectado"
            if router_model and router_model != "No detectado":
                # Buscar la etiqueta del router en el layout
                router_label = self._find_router_label()
                if router_label:
                    router_label.setText(f"🛜 {router_model}")
        except Exception as e:
            print(f"Error actualizando modelo del router: {e}")

    def _find_router_label(self):
        """Buscar la etiqueta del router en el layout de la tarjeta"""
        try:
            layout = self.layout()
            if not layout:
                return None
                
            # Buscar recursivamente en el layout
            return self._find_router_label_in_layout(layout)
        except Exception:
            return None

    def _find_router_label_in_layout(self, layout):
        """Buscar recursivamente la etiqueta del router en un layout"""
        try:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if not item:
                    continue
                    
                # Si es un widget, verificar si es la etiqueta del router
                widget = item.widget()
                if widget:
                    if (hasattr(widget, 'objectName') and 
                        widget.objectName() == "router_info_label"):
                        return widget
                    # También verificar por el texto actual
                    if (isinstance(widget, QLabel) and 
                        "🛜" in widget.text()):
                        return widget
                
                # Si es un layout, buscar recursivamente
                if item.layout():
                    found = self._find_router_label_in_layout(item.layout())
                    if found:
                        return found
                        
            return None
        except Exception:
            return None

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # Header con SSID y señal
        header_layout = QHBoxLayout()
        
        ssid_lbl = QLabel(self.red.get("SSID", "<sin nombre>"))
        ssid_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        ssid_lbl.setStyleSheet(f"color: {COLOR_ACCENT};")
        header_layout.addWidget(ssid_lbl, stretch=1)

        # Indicador de señal
        signal = self.red.get("Señal")
        signal_lbl = QLabel(f"{signal} dBm" if signal else "N/A")
        signal_lbl.setFont(QFont("Segoe UI", 12))
        signal_color = signal_color_by_dbm(signal)
        signal_lbl.setStyleSheet(f"color: {signal_color}; font-weight: bold;")
        header_layout.addWidget(signal_lbl)

        layout.addLayout(header_layout)

        # Información de la red
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        # Frecuencia y Canal
        freq = self.red.get("Frecuencia")
        canal = self.red.get("Canal")
        freq_text = f"{freq} MHz • Canal {canal}" if freq and canal else "Frecuencia no disponible"
        freq_lbl = QLabel(f"📶 {freq_text}")
        freq_lbl.setFont(QFont("Segoe UI", 12))
        freq_lbl.setStyleSheet(f"color: {COLOR_MUTED};")
        info_layout.addWidget(freq_lbl)

        # Seguridad
        security = self.red.get("Seguridad", "N/A")
        security_lbl = QLabel(f"🔐 {security}")
        security_lbl.setFont(QFont("Segoe UI", 12))
        security_lbl.setStyleSheet(f"color: {COLOR_MUTED};")
        info_layout.addWidget(security_lbl)

        layout.addLayout(info_layout)
        layout.addStretch()
        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().show_traffic_for_bssid(self.red.get("BSSID"), self.red)
        else:
            super().mousePressEvent(event)

# ----------------- Diálogo de Dispositivos CON MEDICIÓN DE VELOCIDAD -----------------