"""
vistas/devices_dialog.py – Ventana de dispositivos conectados con test de velocidad
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
    get_current_network_info,   # fuente única — NO importar desde ap_device_scanner
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


# ── Workers de vistas ─────────────────────────────────────────────────────
from vistas.workers import SpeedTestWorker, RouterCapacityWorker, DevicesScanWorker


# ─────────────────────────────────────────────────────────────────────────
# SuggestionWindow — ventana de resultados de análisis IA
# ─────────────────────────────────────────────────────────────────────────

class SuggestionWindow(QDialog):
    def __init__(self, titulo: str, texto: str, parent=None):
        super().__init__(parent)

        self.set_icon()
        self.setWindowTitle(titulo)
        self.setMinimumSize(600, 500)
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
                color: #FFFFFF;
                padding: 15px;
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
                background-color: #2D2D2D;
                color: #E0E0E0;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 15px;
                selection-background-color: #0078D4;
            }
        """)
        text_area.setText(texto)
        layout.addWidget(text_area)

    def set_icon(self):
        icon_path = os.path.join(os.path.dirname(__file__),"../img", "wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))


# ─────────────────────────────────────────────────────────────────────────
# DevicesDialog — ventana de dispositivos conectados
# ─────────────────────────────────────────────────────────────────────────

class DevicesDialog(QDialog):
    def __init__(self, red_meta: dict, parent=None):
        super().__init__(parent)

        # Ventana independiente — no modal, aparece en la barra de tareas
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self.red_meta        = red_meta
        self.router_capacity = 50
        self.router_model    = "No detectado"
        self.current_devices = 0
        self.is_connected_to_network = False

        # Workers
        self.capacity_worker  = None
        self.scan_worker      = None
        self.speed_worker     = None
        self.netguard_window  = None  # referencia fuerte — evita GC prematuro

        # Datos de velocidad
        self.speed_data = {
            "download_mbps": 0.0,
            "upload_mbps":   0.0,
            "ping_ms":       0.0,
            "success":       False,
        }

        # Datos de calidad de red
        self.network_quality = {
            "stability":     0.0,
            "packet_loss":   0.0,
            "latency":       0.0,
            "signal_quality": 0.0,
        }

        self.set_icon()
        self.setWindowTitle(f"Dispositivos Conectados - {red_meta.get('SSID', 'Red')}")
        self.setMinimumSize(900, 700)
        self.setup_ui()

        # Timer de actualización automática cada 2 minutos
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._auto_refresh_devices)
        self.refresh_timer.start(120000)

        # Verificar conexión y luego cargar capacidad del router
        self._check_network_connection()
        self._load_router_capacity()

    def set_icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
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

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        self.setLayout(layout)

        # Título
        title_lbl = QLabel(f"Dispositivos en {self.red_meta.get('SSID', 'Red')}")
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
        layout.addWidget(title_lbl)

        # ── Panel de capacidad / estado ───────────────────────────────────
        self.capacity_frame = QFrame()
        capacity_layout = QVBoxLayout()
        capacity_layout.setContentsMargins(20, 15, 20, 15)
        self.capacity_frame.setLayout(capacity_layout)

        self.router_info_lbl = QLabel("🔄 Detectando información del router...")
        self.router_info_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        capacity_layout.addWidget(self.router_info_lbl)

        self.connection_status_lbl = QLabel()
        self.connection_status_lbl.setFont(QFont("Segoe UI", 11))
        capacity_layout.addWidget(self.connection_status_lbl)

        # Calidad de red (fila compacta)
        quality_frame = QFrame()
        quality_layout = QHBoxLayout()
        quality_layout.setContentsMargins(10, 5, 10, 5)
        quality_frame.setLayout(quality_layout)

        quality_title = QLabel("📊 Calidad:")
        quality_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        quality_title.setStyleSheet(f"color: {COLOR_ACCENT}; min-width: 60px;")
        quality_layout.addWidget(quality_title)

        self.stability_lbl = QLabel("🔄 --%")
        self.stability_lbl.setFont(QFont("Segoe UI", 9))
        self.stability_lbl.setToolTip("Estabilidad de la red")
        quality_layout.addWidget(self.stability_lbl)

        self.packet_loss_lbl = QLabel("📦 --%")
        self.packet_loss_lbl.setFont(QFont("Segoe UI", 9))
        self.packet_loss_lbl.setToolTip("Pérdida de paquetes")
        quality_layout.addWidget(self.packet_loss_lbl)

        self.latency_lbl = QLabel("🏓 -- ms")
        self.latency_lbl.setFont(QFont("Segoe UI", 9))
        self.latency_lbl.setToolTip("Latencia/Ping")
        quality_layout.addWidget(self.latency_lbl)

        self.signal_quality_lbl = QLabel("📡 --%")
        self.signal_quality_lbl.setFont(QFont("Segoe UI", 9))
        self.signal_quality_lbl.setToolTip("Calidad de señal")
        quality_layout.addWidget(self.signal_quality_lbl)

        quality_layout.addStretch()
        capacity_layout.addWidget(quality_frame)

        # Velocidad + botones NetGuard
        speed_frame = QFrame()
        speed_layout = QHBoxLayout()
        speed_layout.setContentsMargins(10, 5, 10, 5)
        speed_frame.setLayout(speed_layout)

        speed_title = QLabel("🌐 Velocidad:")
        speed_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        speed_title.setStyleSheet(f"color: {COLOR_ACCENT}; min-width: 60px;")
        speed_layout.addWidget(speed_title)

        self.download_lbl = QLabel("⬇ --.- Mbps")
        self.download_lbl.setFont(QFont("Segoe UI", 9))
        speed_layout.addWidget(self.download_lbl)

        self.upload_lbl = QLabel("⬆ --.- Mbps")
        self.upload_lbl.setFont(QFont("Segoe UI", 9))
        speed_layout.addWidget(self.upload_lbl)

        self.ping_lbl = QLabel("Ping 🏓 -- ms")
        self.ping_lbl.setFont(QFont("Segoe UI", 9))
        speed_layout.addWidget(self.ping_lbl)

        speed_layout.addStretch()

        self.speed_btn = QPushButton("📊 Medir")
        self.speed_btn.setFont(QFont("Segoe UI", 9))
        self.speed_btn.setFixedWidth(80)
        self.speed_btn.clicked.connect(self._start_speed_test)
        speed_layout.addWidget(self.speed_btn)

        if NETGUARD_OK:
            self.netguard_btn = QPushButton("🔒 NetGuard")
            self.netguard_btn.setFont(QFont("Segoe UI", 9))
            self.netguard_btn.setFixedWidth(90)
            self.netguard_btn.setToolTip("Abrir analizador de seguridad de red (puertos y vulnerabilidades)")
            self.netguard_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d419d;
                    color: #e6edf3;
                    border: 1px solid #1f6feb;
                    border-radius: 4px;
                    padding: 3px 6px;
                    font-weight: 600;
                }
                QPushButton:hover    { background-color: #1158c7; }
                QPushButton:disabled { background-color: #333; color: #666; }
            """)
            self.netguard_btn.clicked.connect(self._open_netguard)
            speed_layout.addWidget(self.netguard_btn)

        capacity_layout.addWidget(speed_frame)

        # Contadores de dispositivos
        devices_info_layout = QHBoxLayout()

        self.devices_count_lbl = QLabel("📱 Conectados: --/-- dispositivos")
        self.devices_count_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))

        self.usage_lbl = QLabel("📈 Uso: --%")
        self.usage_lbl.setFont(QFont("Segoe UI", 11))

        devices_info_layout.addWidget(self.devices_count_lbl)
        devices_info_layout.addStretch()
        devices_info_layout.addWidget(self.usage_lbl)

        capacity_layout.addLayout(devices_info_layout)
        layout.addWidget(self.capacity_frame)

        # ── Lista de dispositivos ─────────────────────────────────────────
        self.devices_frame = QFrame()
        devices_layout = QVBoxLayout()
        devices_layout.setContentsMargins(15, 15, 15, 15)
        self.devices_frame.setLayout(devices_layout)

        devices_title = QLabel("📋 Lista de Dispositivos Conectados")
        devices_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        devices_layout.addWidget(devices_title)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.scroll_content = QWidget()
        self.scroll_layout  = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(8)

        self.loading_lbl = QLabel("🔍 Esperando información...")
        self.loading_lbl.setFont(QFont("Segoe UI", 11))
        self.loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_layout.addWidget(self.loading_lbl)
        self.scroll_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_content)
        devices_layout.addWidget(self.scroll_area)
        layout.addWidget(self.devices_frame)

        # Botón cerrar
        buttons_layout = QHBoxLayout()
        btn_close = QPushButton("Cerrar")
        btn_close.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        btn_close.setMinimumHeight(40)
        btn_close.clicked.connect(self.close)
        buttons_layout.addWidget(btn_close)
        layout.addLayout(buttons_layout)

    # ── Lógica de red ─────────────────────────────────────────────────────

    def _auto_refresh_devices(self):
        if self.is_connected_to_network:
            self._update_network_quality()
            self._start_devices_scan()

    def _check_network_connection(self):
        current_network = get_current_network_info()

        if not current_network:
            self.is_connected_to_network = False
            self.connection_status_lbl.setText("🔴 No conectado a ninguna red - Escaneo limitado")
            self.connection_status_lbl.setStyleSheet(f"color: {COLOR_WARNING}; font-weight: bold;")
            return

        target_ssid  = self.red_meta.get("SSID")
        current_ssid = current_network.get("ssid") or current_network.get("SSID")

        self.is_connected_to_network = (current_ssid == target_ssid)

        if self.is_connected_to_network:
            # Actualizar red_meta con claves en mayúsculas para consistencia
            self.red_meta.update({k.upper(): v for k, v in current_network.items()})
            self.connection_status_lbl.setText("🟢 Conectado a esta red - Escaneo activo")
            self.connection_status_lbl.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")
            self._update_network_quality()
        else:
            msg = (
                f"🔶 Conectado a otra red ('{current_ssid}') - Escaneo limitado"
                if current_ssid
                else "🔴 No conectado a esta red - Escaneo limitado"
            )
            self.connection_status_lbl.setText(msg)
            self.connection_status_lbl.setStyleSheet(f"color: {COLOR_WARNING}; font-weight: bold;")

    def _update_network_quality(self):
        if not self.is_connected_to_network:
            return
        try:
            congestion_info = get_network_congestion()
            if congestion_info:
                self.network_quality = {
                    "stability":     congestion_info.get('stability_percentage', 0.0),
                    "packet_loss":   congestion_info.get('packet_loss', 0.0),
                    "latency":       congestion_info.get('latency', 0.0),
                    "signal_quality": congestion_info.get('signal_quality', 0.0),
                }
                self._update_quality_ui()
        except Exception as e:
            print(f"Error obteniendo calidad de red: {e}")

    def _update_quality_ui(self):
        stability = self.network_quality["stability"]
        sc = COLOR_SUCCESS if stability >= 80 else COLOR_WARNING if stability >= 60 else COLOR_ERROR
        self.stability_lbl.setText(f"<span style='color: {sc};'>🔄 {stability:.1f}%</span>")

        packet_loss = self.network_quality["packet_loss"]
        pc = COLOR_SUCCESS if packet_loss <= 5 else COLOR_WARNING if packet_loss <= 15 else COLOR_ERROR
        self.packet_loss_lbl.setText(f"<span style='color: {pc};'>📦 {packet_loss:.1f}%</span>")

        latency = self.network_quality["latency"]
        lc = COLOR_SUCCESS if latency <= 50 else COLOR_WARNING if latency <= 100 else COLOR_ERROR
        self.latency_lbl.setText(f"<span style='color: {lc};'>🏓 {latency:.1f}ms</span>")

        signal_quality = self.network_quality["signal_quality"]
        sqc = COLOR_SUCCESS if signal_quality >= 80 else COLOR_WARNING if signal_quality >= 60 else COLOR_ERROR
        self.signal_quality_lbl.setText(f"<span style='color: {sqc};'>📡 {signal_quality:.1f}%</span>")

    # ── Test de velocidad ─────────────────────────────────────────────────

    def _start_speed_test(self):
        if self.speed_worker and self.speed_worker.isRunning():
            return
        self.speed_btn.setEnabled(False)
        self.speed_btn.setText("⏳...")
        self.speed_worker = SpeedTestWorker()
        self.speed_worker.finished.connect(self._on_speed_test_finished)
        self.speed_worker.error.connect(self._on_speed_test_error)
        self.speed_worker.start()

    def _on_speed_test_finished(self, result):
        self.speed_data = result
        if result.get('success', False):
            self.download_lbl.setText(f"⬇ {result.get('download_mbps', 0):.1f}Mbps")
            self.upload_lbl.setText(f"⬆ {result.get('upload_mbps', 0):.1f}Mbps")
            self.ping_lbl.setText(f"🏓 {result.get('ping_ms', 0):.1f}ms")
        self.speed_btn.setEnabled(True)
        self.speed_btn.setText("📊 Medir")

    def _on_speed_test_error(self, error_msg):
        self.download_lbl.setText("⬇ Error")
        self.upload_lbl.setText("⬆ Error")
        self.ping_lbl.setText("🏓 Error")
        self.speed_btn.setEnabled(True)
        self.speed_btn.setText("📊 Medir")

    # ── Capacidad del router ──────────────────────────────────────────────

    def _load_router_capacity(self):
        mac      = self.red_meta.get("BSSID")
        vendor   = self.red_meta.get("Fabricante")
        wifi_tech = self.red_meta.get("Tecnologia", "")

        if mac and vendor:
            self.capacity_worker = RouterCapacityWorker(mac, vendor, wifi_tech)
            self.capacity_worker.finished.connect(self._on_capacity_loaded)
            self.capacity_worker.start()
        else:
            self.router_capacity = 50
            self.router_model    = "No detectado"
            self._update_router_info()
            self._handle_scan_logic()

    def _on_capacity_loaded(self, router_info):
        self.router_capacity = router_info.get("max_devices", 50)
        self.router_model    = router_info.get("model", "No detectado")
        self._update_router_info()
        self._handle_scan_logic()

    def _update_router_info(self):
        self.router_info_lbl.setText(f"🛜 Router: {self.router_model}")

    def _handle_scan_logic(self):
        self._check_network_connection()
        if self.is_connected_to_network:
            self._start_devices_scan()
        else:
            self._show_capacity_only()

    # ── Escaneo de dispositivos ───────────────────────────────────────────

    def _start_devices_scan(self):
        self.loading_lbl.setText("🔍 Escaneando la red en busca de dispositivos...")
        self.scan_worker = DevicesScanWorker(self.red_meta)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _show_capacity_only(self):
        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        msg = QLabel("🛡️ Conéctate a esta red para ver los dispositivos")
        msg.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        self.scroll_layout.addWidget(msg)

        self.devices_count_lbl.setText(f"📱 Conectados: 0/{self.router_capacity} dispositivos")
        self.usage_lbl.setText("📈 Uso: 0%")
        self.scroll_layout.addStretch()

    def _on_scan_finished(self, result):
        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        if result.get('success', False):
            devices      = result.get('devices', [])
            total_devices = len(devices)
            max_devices  = result.get('max_devices') or self.router_capacity or 50

            self.current_devices = total_devices
            self.devices_count_lbl.setText(f"Conectados: {total_devices}/{max_devices} dispositivos")
            usage = min(100, int((total_devices / max_devices) * 100)) if max_devices > 0 else 0
            self.usage_lbl.setText(f"📈 Uso: {usage}%")

            if devices:
                for device in devices:
                    self.scroll_layout.addWidget(self._create_device_card(device))
            else:
                lbl = QLabel("No se encontraron dispositivos en la red")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.scroll_layout.addWidget(lbl)
        else:
            error_msg = result.get('error', 'Error desconocido')
            lbl = QLabel(f"Error: {error_msg}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(lbl)

    def _create_device_card(self, device: Dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_CARD};
                border-radius: 6px;
                border: 1px solid {COLOR_CARD_BORDER};
                padding: 12px;
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        card.setLayout(layout)

        type_lbl = QLabel(device.get('type', '💻 Dispositivo'))
        type_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(type_lbl)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        ip_lbl     = QLabel(f"📍 IP: {device.get('ip', 'N/A')}")
        mac_lbl    = QLabel(f"🔗 MAC: {device.get('mac', 'N/A')}")
        vendor_lbl = QLabel(f"🏭 {device.get('vendor', 'Desconocido')}")

        ip_lbl.setFont(QFont("Segoe UI", 10))
        mac_lbl.setFont(QFont("Segoe UI", 9))
        vendor_lbl.setFont(QFont("Segoe UI", 9))

        info_layout.addWidget(ip_lbl)
        info_layout.addWidget(mac_lbl)
        info_layout.addWidget(vendor_lbl)
        layout.addLayout(info_layout)
        layout.addStretch()

        return card

    # ── NetGuard ──────────────────────────────────────────────────────────

    def _open_netguard(self):
        """Abrir NetGuard como ventana independiente.
        Si ya está abierta la focaliza en lugar de abrir otra instancia.
        """
        if not NETGUARD_OK or NetGuardWindow is None:
            return

        if self.netguard_window is not None:
            try:
                self.netguard_window.showNormal()
                self.netguard_window.raise_()
                self.netguard_window.activateWindow()
                return
            except RuntimeError:
                self.netguard_window = None

        win = NetGuardWindow()
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        win.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        win.destroyed.connect(self._on_netguard_closed)
        win.show()
        win.raise_()
        win.activateWindow()
        self.netguard_window = win

    def _on_netguard_closed(self):
        self.netguard_window = None

    # ── Cierre limpio ─────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self.netguard_window is not None:
            try:
                self.netguard_window.close()
            except RuntimeError:
                pass
            self.netguard_window = None

        if self.capacity_worker and self.capacity_worker.isRunning():
            self.capacity_worker.stop()
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.stop()
        if self.speed_worker and self.speed_worker.isRunning():
            self.speed_worker.stop()

        event.accept()