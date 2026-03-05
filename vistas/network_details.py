"""
vistas/network_details.py – Ventana de detalles y análisis de una red WiFi
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


from vistas.workers import VendorWorker, SuggestionWorker
from vistas.devices_dialog import DevicesDialog, SuggestionWindow


class NetworkDetailsDialog(QDialog):
    def __init__(self, bssid: str, red_meta: dict, parent=None):
        super().__init__(parent)

        # Ventana independiente — no modal, aparece en la barra de tareas
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self.bssid    = bssid
        self.red_meta = red_meta

        # Control de threads activos
        self.vendor_worker       = None
        self.suggestion_workers  = {}
        self.vendor_completed    = False
        self._is_closing         = False
        self._devices_win        = None

        # Información de MAC aleatoria
        self.mac_aleatoria          = False
        self.mac_original           = bssid
        self.esta_conectado_a_red   = False

        # Textos originales de botones (para restaurar después de "Analizando...")
        self.botones_texto_original = {}

        self.set_icon()
        self.setWindowTitle(f"Análisis de Red - {red_meta.get('SSID', 'Red')}")
        self.setMinimumSize(800, 650)
        self.setup_ui()

    def set_icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "../img","wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG};
                color: {COLOR_TEXT};
                font-family: 'Segoe UI';
            }}
            QFrame {{
                background-color: {COLOR_CARD};
                border-radius: 6px;
                border: 1px solid {COLOR_CARD_BORDER};
            }}
        """)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(20, 20, 20, 20)
        outer_layout.setSpacing(15)
        self.setLayout(outer_layout)

        # Título
        title_lbl = QLabel(f"Análisis de Red: {self.red_meta.get('SSID', 'Desconocida')}")
        title_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"""
            QLabel {{
                color: #FFFFFF;
                padding: 15px;
                background-color: {COLOR_CARD};
                border-radius: 6px;
                border-left: 4px solid {COLOR_ACCENT};
            }}
        """)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer_layout.addWidget(title_lbl)

        # Contenedor de información
        info_frame = QFrame()
        info_layout = QFormLayout()
        info_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        info_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        info_layout.setHorizontalSpacing(30)
        info_layout.setVerticalSpacing(12)
        info_frame.setLayout(info_layout)
        outer_layout.addWidget(info_frame)

        def make_field_label(text):
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {COLOR_ACCENT};")
            return lbl

        def make_value_label(text):
            lbl = QLabel(str(text))
            lbl.setFont(QFont("Segoe UI", 10))
            lbl.setStyleSheet(f"color: {COLOR_TEXT};")
            lbl.setWordWrap(True)
            return lbl

        datos = [
            ("SSID",               self.red_meta.get("SSID", "<sin nombre>")),
            ("Dirección MAC",      self.bssid),
            ("Fabricante",         "Buscando..."),
            ("Intensidad de señal", f"{self.red_meta.get('Señal', 'N/A')} dBm"),
            ("Frecuencia",         f"{self.red_meta.get('Frecuencia', 'N/A')} MHz"),
            ("Banda",              self.red_meta.get("Banda", "Desconocida")),
            ("Canal",              self.red_meta.get("Canal", "Desconocido")),
            ("Seguridad",          self.red_meta.get("Seguridad", "Desconocido")),
            ("Ancho de canal",     self.red_meta.get("AnchoCanal", "Desconocido")),
            ("Distancia estimada", f"≈ {self.red_meta.get('Estimacion_m', 'N/A')} metros"),
            ("Tecnología",         self.red_meta.get("Tecnologia", "Desconocida")),
            ("Autenticación",      self.red_meta.get("Autenticación", "Desconocida")),
            ("Cifrado",            self.red_meta.get("Cifrado", "Desconocida")),
            ("Ambiente",           self.red_meta.get("Ambiente", "Desconocido").capitalize()),
        ]

        for field, value in datos:
            if field == "Fabricante":
                self.vendor_lbl = make_value_label("🔄 Buscando fabricante...")
                info_layout.addRow(make_field_label(field + ":"), self.vendor_lbl)
            elif field == "Intensidad de señal":
                signal_lbl = make_value_label(value)
                signal_color = signal_color_by_dbm(self.red_meta.get("Señal"))
                signal_lbl.setStyleSheet(f"color: {signal_color}; font-weight: bold;")
                info_layout.addRow(make_field_label(field + ":"), signal_lbl)
            else:
                info_layout.addRow(make_field_label(field + ":"), make_value_label(value))

        # Botones de análisis
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        buttons_frame.setLayout(buttons_layout)

        self.btn_tecn = QPushButton("🔍 Análisis de Tecnología")
        self.btn_tecn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_tecn.setMinimumHeight(45)
        self.btn_tecn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: white;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover    {{ background-color: #106EBE; }}
            QPushButton:pressed  {{ background-color: #005A9E; }}
            QPushButton:disabled {{ background-color: #505050; color: #A0A0A0; }}
        """)

        self.btn_proto = QPushButton("🔒 Análisis de Protocolo")
        self.btn_proto.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_proto.setMinimumHeight(45)
        self.btn_proto.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SUCCESS};
                color: white;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover    {{ background-color: #0E6C0E; }}
            QPushButton:pressed  {{ background-color: #0C5C0C; }}
            QPushButton:disabled {{ background-color: #505050; color: #A0A0A0; }}
        """)

        self.btn_devices = QPushButton("📱 Ver Dispositivos Conectados")
        self.btn_devices.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_devices.setMinimumHeight(45)
        self.btn_devices.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFB900;
                color: black;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover    {{ background-color: #FFA500; }}
            QPushButton:pressed  {{ background-color: #CC9200; }}
            QPushButton:disabled {{ background-color: #505050; color: #A0A0A0; }}
        """)

        buttons_layout.addWidget(self.btn_tecn)
        buttons_layout.addWidget(self.btn_proto)
        buttons_layout.addWidget(self.btn_devices)

        self.btn_tecn.clicked.connect(lambda: self._handle_sugerencia("tecnologia"))
        self.btn_proto.clicked.connect(lambda: self._handle_sugerencia("protocolo"))
        self.btn_devices.clicked.connect(self._show_devices)

        outer_layout.addWidget(buttons_frame)

        self._check_connection_status()
        self._start_vendor_lookup()

    def _check_connection_status(self):
        ssid  = self.red_meta.get("SSID")
        bssid = self.red_meta.get("BSSID")

        self.esta_conectado_a_red = is_connected_to_network(ssid, bssid)

        self.btn_devices.setEnabled(False)
        if not self.esta_conectado_a_red:
            self.btn_devices.setText("🔒 Conéctate a la red")
        else:
            self.btn_devices.setText("⏳ Esperando fabricante...")

    def _update_buttons_state(self):
        vendor_ready          = self.vendor_completed
        has_active_suggestions = any(w.isRunning() for w in self.suggestion_workers.values())

        self.btn_tecn.setEnabled(vendor_ready and not has_active_suggestions)
        self.btn_proto.setEnabled(vendor_ready and not has_active_suggestions)

        if self.esta_conectado_a_red:
            self.btn_devices.setEnabled(vendor_ready and not has_active_suggestions)
        else:
            self.btn_devices.setEnabled(False)
            self.btn_devices.setText("🔒 Conéctate a la red")

        if not vendor_ready:
            self.btn_tecn.setText("⏳ Esperando fabricante...")
            self.btn_proto.setText("⏳ Esperando fabricante...")
            if self.esta_conectado_a_red:
                self.btn_devices.setText("⏳ Esperando fabricante...")
        elif not has_active_suggestions:
            if "tecnologia" not in self.botones_texto_original:
                self.btn_tecn.setText("🔍 Análisis de Tecnología")
            if "protocolo" not in self.botones_texto_original:
                self.btn_proto.setText("🔒 Análisis de Protocolo")
            if self.esta_conectado_a_red:
                self.btn_devices.setText("📱 Ver Dispositivos Conectados")

    def _start_vendor_lookup(self):
        self.vendor_worker = VendorWorker(self.bssid, self.red_meta.get("SSID"))
        self.vendor_worker.finished.connect(self._on_vendor_finished)
        self.vendor_worker.error.connect(lambda e: print(f"Error vendor: {e}"))
        self.vendor_worker.finished.connect(self.vendor_worker.deleteLater)
        self.vendor_worker.start()
        self._update_buttons_state()

    def _on_vendor_finished(self, vendor):
        if not self._is_closing:
            enhanced_info = get_enhanced_vendor_info(self.bssid, self.red_meta.get("SSID"))

            if enhanced_info['is_random'] and enhanced_info['original_vendor'] != "Desconocido":
                self.vendor_lbl.setText(
                    f"{enhanced_info['original_vendor']} ({enhanced_info['original_mac']})"
                )
                self.red_meta["Fabricante"] = enhanced_info['original_vendor']
            else:
                self.vendor_lbl.setText(vendor)
                self.red_meta["Fabricante"] = vendor

            self.mac_aleatoria = enhanced_info['is_random']
            self.mac_original  = enhanced_info['original_mac']

            can_scan_devices = enhanced_info.get('can_scan_devices', False) and self.esta_conectado_a_red

            if can_scan_devices:
                self.btn_devices.setEnabled(True)
                self.btn_devices.setText("📱 Ver Dispositivos Conectados")
            else:
                self.btn_devices.setEnabled(False)
                self.btn_devices.setText(
                    "🔒 Conéctate a la red" if not self.esta_conectado_a_red
                    else "🔒 No se puede escanear"
                )

            self.vendor_completed = True
            self.vendor_worker    = None
            self._update_buttons_state()

    def _handle_sugerencia(self, tipo):
        if not self.vendor_completed or self._is_closing:
            return

        if tipo in self.suggestion_workers and self.suggestion_workers[tipo].isRunning():
            return

        if tipo == "tecnologia":
            self.botones_texto_original[tipo] = self.btn_tecn.text()
            self.btn_tecn.setText("🔄 Analizando...")
            self.btn_tecn.setEnabled(False)
        else:
            self.botones_texto_original[tipo] = self.btn_proto.text()
            self.btn_proto.setText("🔄 Analizando...")
            self.btn_proto.setEnabled(False)

        worker = SuggestionWorker(self.red_meta, tipo)
        self.suggestion_workers[tipo] = worker

        worker.finished.connect(lambda result: self._on_suggestion_finished(tipo, result))
        worker.error.connect(lambda e: self._on_suggestion_error(tipo, e))
        worker.finished.connect(worker.deleteLater)

        self._update_buttons_state()
        worker.start()

    def _on_suggestion_error(self, tipo, error_msg):
        if tipo in self.botones_texto_original:
            texto_original = self.botones_texto_original[tipo]
            if tipo == "tecnologia":
                self.btn_tecn.setText(texto_original)
                self.btn_tecn.setEnabled(True)
            else:
                self.btn_proto.setText(texto_original)
                self.btn_proto.setEnabled(True)
            del self.botones_texto_original[tipo]

        QMessageBox.warning(
            self,
            "Error en análisis",
            f"No se pudo completar el análisis de {tipo}.\n\nError: {error_msg}"
        )

        if tipo in self.suggestion_workers:
            del self.suggestion_workers[tipo]
        self._update_buttons_state()

    def _on_suggestion_finished(self, tipo, result):
        if not self._is_closing and tipo in self.suggestion_workers:
            if tipo in self.botones_texto_original:
                texto_original = self.botones_texto_original[tipo]
                if tipo == "tecnologia":
                    self.btn_tecn.setText(texto_original)
                    self.btn_tecn.setEnabled(True)
                else:
                    self.btn_proto.setText(texto_original)
                    self.btn_proto.setEnabled(True)
                del self.botones_texto_original[tipo]

            del self.suggestion_workers[tipo]
            self._update_buttons_state()

            if not self._is_closing:
                titulo = "Análisis de Tecnología" if tipo == "tecnologia" else "Análisis de Protocolo"
                suggestion_dialog = SuggestionWindow(titulo, result, parent=self)
                suggestion_dialog.exec()

    def _show_devices(self):
        """Abrir ventana de dispositivos — independiente, no modal.
        Si ya está abierta la focaliza en lugar de abrir otra.
        """
        if self.esta_conectado_a_red and self.mac_aleatoria and self.mac_original:
            self.red_meta["BSSID_Original"] = self.mac_original

        if self._devices_win is not None:
            try:
                if self._devices_win.isVisible():
                    self._devices_win.showNormal()
                    self._devices_win.raise_()
                    self._devices_win.activateWindow()
                    return
            except RuntimeError:
                pass
            self._devices_win = None

        win = DevicesDialog(self.red_meta, parent=None)
        win.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        win.destroyed.connect(lambda: setattr(self, '_devices_win', None))
        self._devices_win = win
        win.show()
        win.raise_()
        win.activateWindow()

    def closeEvent(self, event):
        self._is_closing = True

        if self.vendor_worker and self.vendor_worker.isRunning():
            self.vendor_worker.stop()

        for worker in self.suggestion_workers.values():
            if worker and worker.isRunning():
                worker.stop()

        if self._devices_win is not None:
            try:
                self._devices_win.close()
            except RuntimeError:
                pass
            self._devices_win = None

        self.vendor_worker = None
        self.suggestion_workers.clear()
        self.botones_texto_original.clear()

        event.accept()