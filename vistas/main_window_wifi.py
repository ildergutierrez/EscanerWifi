"""
vistas/main_window_wifi.py – Ventana principal del escáner WiFi
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
    from network.ui_ia.main_window import MainWindow as NetGuardWindow
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


from vistas.workers import ScanWorker, RouterCapacityWorker
from vistas.card import Card
from vistas.network_details import NetworkDetailsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.set_icon()

        self.setWindowTitle("Escáner WiFi Corporativo")
        self.setMinimumSize(1200, 800)

        # Referencia a la ventana de detalles activa
        self.active_dialog = None

        # Cache de información de routers
        self.router_info_cache = {}

        # Workers activos
        self.scan_worker = None
        self.active_workers = []

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Título principal con icono
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(20, 20, 20, 20)
        title_layout.setSpacing(15)

        icon_path = os.path.join(os.path.dirname(__file__), "../img","wifi2.1.png")
        if os.path.exists(icon_path):
            icon_label = QLabel()
            icon_label.setPixmap(QIcon(icon_path).pixmap(60, 60))
            title_layout.addWidget(icon_label)

        title = QLabel("Escáner WiFi Corporativo")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet("QLabel { color: #FFFFFF; background-color: transparent; }")
        title_layout.addWidget(title)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_widget.setStyleSheet(f"QWidget {{ background-color: {COLOR_CARD}; border-radius: 8px; }}")
        main_layout.addWidget(title_widget)

        # Contador de redes
        self.cantidad_label = QLabel("Redes detectadas: 0")
        self.cantidad_label.setFont(QFont("Segoe UI", 12))
        self.cantidad_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT};
                padding: 10px;
                background-color: {COLOR_CARD};
                border-radius: 6px;
                border-left: 3px solid {COLOR_SUCCESS};
            }}
        """)
        self.cantidad_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.cantidad_label)

        # Área de scroll
        self.scroll = QScrollArea()
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {COLOR_BG};
                border: 1px solid {COLOR_CARD_BORDER};
                border-radius: 6px;
            }}
            QScrollBar:vertical {{
                background-color: {COLOR_CARD};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLOR_ACCENT};
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #106EBE;
            }}
        """)
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet(f"background-color: {COLOR_BG};")
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setContentsMargins(20, 20, 20, 20)
        self.grid.setHorizontalSpacing(20)
        self.grid.setVerticalSpacing(20)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll)

        # Mensaje de escaneo inicial
        self.scanning_label = QLabel("Escaneando redes WiFi...")
        self.scanning_label.setFont(QFont("Segoe UI", 14))
        self.scanning_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_MUTED};
                padding: 30px;
                background-color: {COLOR_CARD};
                border-radius: 8px;
                border: 2px dashed {COLOR_CARD_BORDER};
            }}
        """)
        self.scanning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.scanning_label, 0, 0, 1, 1)

        self.redes = []
        self.is_first_scan = True

        # Timer para escaneo automático cada 3 segundos
        self.timer = QTimer()
        self.timer.timeout.connect(self.lanzar_scan)
        self.timer.start(3000)
        self.lanzar_scan()

        self.setStyleSheet(f"QMainWindow {{ background-color: {COLOR_BG}; }}")

    def set_icon(self):
        icon_path = os.path.join(os.path.dirname(__file__),"../img", "wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def closeEvent(self, event):
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()

        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.stop()

        if self.active_dialog and self.active_dialog.isVisible():
            self.active_dialog.close()

        for worker in self.active_workers:
            if worker and worker.isRunning():
                worker.stop()

        self._clear_console()
        event.accept()

    def _clear_console(self):
        try:
            system = platform.system().lower()
            if system == "windows":
                subprocess.call('cls', shell=True)
            elif system in ["linux", "darwin"]:
                subprocess.call('clear', shell=True)
            else:
                print('\n' * 50)
        except Exception:
            print('\n' * 50)

    def lanzar_scan(self):
        if not self.scan_worker or not self.scan_worker.isRunning():
            self.scan_worker = ScanWorker()
            self.scan_worker.finished.connect(self._scan_done)
            self.scan_worker.error.connect(lambda e: print(f"Error escaneo: {e}"))
            self.scan_worker.start()

    def _scan_done(self, redes):
        self.redes = redes
        self.cantidad_label.setText(f"Redes detectadas: {len(redes)}")

        if self.is_first_scan and redes:
            self.scanning_label.hide()
            self.is_first_scan = False

        self.construir_cards()
        QTimer.singleShot(2000, self.update_router_capacities)

    def construir_cards(self):
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w:
                w.setParent(None)

        if not self.redes:
            no_networks_label = QLabel("Escaneando Redes Wifi Cercanas, Esto Podria Demorar Unos Segundos")
            no_networks_label.setFont(QFont("Segoe UI", 13))
            no_networks_label.setStyleSheet(f"""
                QLabel {{
                    color: {COLOR_MUTED};
                    padding: 40px;
                    background-color: {COLOR_CARD};
                    border-radius: 8px;
                    border: 2px dashed {COLOR_CARD_BORDER};
                }}
            """)
            no_networks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(no_networks_label, 0, 0, 1, 1)
            return

        ancho_px = max(1, self.scroll_content.width() or self.width())
        num_cols = max(1, ancho_px // (CARD_WIDTH + 30))

        for idx, red in enumerate(self.redes):
            row, col = divmod(idx, num_cols)
            card = Card(red)
            self.grid.addWidget(card, row, col)

    def update_router_capacities(self):
        for i in range(self.grid.count()):
            item = self.grid.itemAt(i)
            if item and item.widget():
                card = item.widget()
                if (hasattr(card, 'red') and
                    card.red.get("BSSID") and
                    card.red.get("Fabricante") and
                    card.red.get("BSSID") not in self.router_info_cache):
                    self._load_router_info_for_card(card)

    def _load_router_info_for_card(self, card):
        mac = card.red["BSSID"]
        vendor = card.red["Fabricante"]
        wifi_tech = card.red.get("Tecnologia", "")

        worker = RouterCapacityWorker(mac, vendor, wifi_tech)
        worker.finished.connect(lambda info, c=card: self._on_card_router_info_loaded(info, c))
        worker.error.connect(lambda e: print(f"Error router capacity: {e}"))

        self.active_workers.append(worker)
        worker.start()

    def _on_card_router_info_loaded(self, router_info, card):
        try:
            if router_info and router_info.get("max_devices"):
                self.router_info_cache[card.red["BSSID"]] = router_info
                card.red["router_max_devices"] = router_info["max_devices"]
                card.red["router_model"] = router_info.get("model", "No detectado")
                card._update_router_model()

            if hasattr(self, 'active_workers'):
                for i, worker in enumerate(self.active_workers):
                    if not worker.isRunning():
                        self.active_workers.pop(i)
                        break
        except Exception as e:
            print(f"Error procesando información del router: {e}")

    def resizeEvent(self, event):
        self.construir_cards()
        return super().resizeEvent(event)

    def show_traffic_for_bssid(self, bssid: str, red_meta: dict = None):
        """Abrir ventana de análisis — independiente, no modal.
        Si ya está abierta para el mismo BSSID la focaliza en lugar de abrir otra.
        """
        if self.active_dialog and self.active_dialog.isVisible():
            if getattr(self.active_dialog, 'bssid', None) == bssid:
                self.active_dialog.showNormal()
                self.active_dialog.raise_()
                self.active_dialog.activateWindow()
                return
            # Red distinta: cerrar la anterior antes de abrir la nueva
            self.active_dialog.close()
            self.active_dialog = None

        win = NetworkDetailsDialog(bssid, red_meta or {}, parent=None)
        win.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        win.destroyed.connect(self._on_dialog_closed)
        self.active_dialog = win
        win.show()
        win.raise_()
        win.activateWindow()

    def _on_dialog_closed(self):
        self.active_dialog = None