"""
ui.py – Punto de entrada principal de EscanerWifi
"""
# ── 1. stdlib primero ─────────────────────────────────────────────────────
import sys
import os
import subprocess
import platform
from typing import Optional, Dict

# ── 2. Rutas del proyecto (ANTES de cualquier import local) ───────────────
# ui.py vive en EscanerWifi/  (raíz del proyecto)
# backend/ vive en EscanerWifi/backend/
# vistas/  vive en EscanerWifi/vistas/
# network/ vive en EscanerWifi/network/
_PROJ_ROOT = os.path.abspath(os.path.dirname(__file__))        # ← EscanerWifi/
_BACKEND   = os.path.join(_PROJ_ROOT, "backend")               # ← EscanerWifi/backend/
_NETWORK   = os.path.join(_PROJ_ROOT, "network")               # ← EscanerWifi/network/
_VISTAS    = os.path.join(_PROJ_ROOT, "vistas")                # ← EscanerWifi/vistas/
for _p in (_PROJ_ROOT, _BACKEND, _NETWORK, _VISTAS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── 3. Verificar librerias (ahora backend/ ya está en sys.path) ───────────
# FIX: import explícito con prefijo de paquete para evitar colisión con
#      cualquier "librerias.py" flotante en sys.path.
from backend.librerias import verificar_librerias
#verificar_librerias()

# ── 4. PyQt6 ─────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QScrollArea, QGridLayout, QPushButton, QFrame, QDialog,
    QTextEdit, QHBoxLayout, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QIcon, QCursor, QMouseEvent

# ── 5. Imports del backend ────────────────────────────────────────────────
# FIX: todos los imports del backend usan prefijo explícito "backend."
#      para evitar colisión con módulos del sistema (especialmente "main").
from backend.main import scan_wifi
from backend.ai_suggestions import sugerencia_tecnologia, sugerencia_protocolo

# FIX: get_current_network_info se importa SOLO desde backend.network_status.
#      Antes se sobreescribía (silenciosamente) con la versión de ap_device_scanner,
#      dejando la función como stub "return None" cuando ese módulo fallaba.
from backend.network_status import (
    get_connected_wifi_info,
    is_current_network,
    get_network_congestion,
    is_connected_to_network,
    get_current_network_info,   # ← fuente única y confiable
)

# Módulos opcionales — el try/except es correcto aquí porque son mejoras,
# no funcionalidad crítica. NUNCA incluir get_current_network_info en estos bloques.
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
    # FIX: get_current_network_info NO se importa aquí para no sobreescribir
    #      la versión correcta que ya importamos arriba desde backend.network_status.
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

# ── 6. NetGuard (módulo de red separado) ──────────────────────────────────
# _NETWORK ya fue agregado a sys.path arriba.
try:
    from network.ui_ia.main_window import MainWindow as NetGuardWindow
    NETGUARD_OK = True
except ImportError as _e:
    print(f"NetGuard no disponible: {_e}")
    NETGUARD_OK = False
    NetGuardWindow = None

# ── 7. Vistas ─────────────────────────────────────────────────────────────
from vistas.workers import ScanWorker, RouterCapacityWorker
from vistas.card import Card
from vistas.network_details import NetworkDetailsDialog

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
        if signal_dbm is None:
            return COLOR_MUTED
        s = float(signal_dbm)
        if s >= -60: return COLOR_SUCCESS
        if s >= -70: return "#FFB900"
        if s >= -80: return COLOR_WARNING
        return COLOR_ERROR
    except Exception:
        return COLOR_MUTED


# ── Diagnóstico de red (helper de depuración) ─────────────────────────────
def diagnosticar_red_actual():
    """Imprime en consola la información real de la red conectada."""
    try:
        info = get_current_network_info()
        print(f"🔍 [DIAG] get_current_network_info → {info}")
    except Exception as e:
        print(f"❌ [DIAG] Error al obtener info de red: {e}")


# ── DevicesDialog ─────────────────────────────────────────────────────────
class DevicesDialog(QDialog):
    def __init__(self, red_meta: dict, parent=None):
        super().__init__(parent)
        self.red_meta = red_meta
        self.router_capacity = 50
        self.router_model = "No detectado"
        self.current_devices = 0
        self.is_connected_to_network = False

        # Workers
        self.capacity_worker = None
        self.scan_worker = None
        self.speed_worker = None
        # Referencia fuerte a la ventana NetGuard (evita GC mientras está abierta)
        self.netguard_window = None

        # Datos de velocidad
        self.speed_data = {
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "ping_ms": 0.0,
            "success": False
        }

        # Datos de calidad de red
        self.network_quality = {
            "stability": 0.0,
            "packet_loss": 0.0,
            "latency": 0.0,
            "signal_quality": 0.0
        }

        self.set_icon()
        self.setWindowTitle(f"Dispositivos Conectados - {red_meta.get('SSID', 'Red')}")
        self.setMinimumSize(900, 700)
        self.setup_ui()

        # Timer de actualización automática cada 2 minutos
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._auto_refresh_devices)
        self.refresh_timer.start(120000)

        print("🚀 INICIANDO DevicesDialog DIAGNÓSTICO")
        diagnosticar_red_actual()

        # FIX: _check_network_connection ya usa get_current_network_info
        #      que ahora proviene exclusivamente de backend.network_status.
        self._check_network_connection()

        if self.is_connected_to_network:
            self._start_devices_scan()
        else:
            self._show_capacity_only()

    def set_icon(self):
    # wifi.png está en img/, no en la raíz donde vive ui.py
        icon_path = os.path.join(os.path.dirname(__file__), "img/wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Estado de conexión
        self.connection_status_lbl = QLabel("🔄 Verificando conexión...")
        self.connection_status_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(self.connection_status_lbl)

        # Frame de capacidad / velocidad
        self.capacity_frame = QFrame()
        capacity_layout = QVBoxLayout()
        capacity_layout.setContentsMargins(15, 15, 15, 15)
        self.capacity_frame.setLayout(capacity_layout)

        speed_frame = QFrame()
        speed_layout = QHBoxLayout()
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_frame.setLayout(speed_layout)

        self.speed_btn = QPushButton("⚡ Test Velocidad")
        self.speed_btn.setFont(QFont("Segoe UI", 9))
        self.speed_btn.setFixedWidth(130)
        self.speed_btn.clicked.connect(self._run_speed_test)
        speed_layout.addWidget(self.speed_btn)

        if NETGUARD_OK:
            self.netguard_btn = QPushButton("🔒 NetGuard")
            self.netguard_btn.setFont(QFont("Segoe UI", 9))
            self.netguard_btn.setFixedWidth(90)
            self.netguard_btn.setToolTip(
                "Abrir analizador de seguridad de red (puertos y vulnerabilidades)"
            )
            self.netguard_btn.clicked.connect(self._open_netguard)
            speed_layout.addWidget(self.netguard_btn)

        capacity_layout.addWidget(speed_frame)

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

        # Lista de dispositivos
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
        self.scroll_layout = QVBoxLayout(self.scroll_content)
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

        buttons_layout = QHBoxLayout()
        btn_close = QPushButton("Cerrar")
        btn_close.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        btn_close.setMinimumHeight(40)
        btn_close.clicked.connect(self.close)
        buttons_layout.addWidget(btn_close)
        layout.addLayout(buttons_layout)

    def _run_speed_test(self):
        """Lanzar test de velocidad en hilo separado."""
        self.speed_btn.setEnabled(False)
        self.speed_btn.setText("⏳ Midiendo...")

        class SpeedWorker(QThread):
            finished = pyqtSignal(dict)
            def run(self):
                self.finished.emit(test_network_speed())

        self.speed_worker = SpeedWorker()
        self.speed_worker.finished.connect(self._on_speed_result)
        self.speed_worker.start()

    def _on_speed_result(self, result: dict):
        self.speed_data = result
        self.speed_btn.setEnabled(True)
        self.speed_btn.setText("⚡ Test Velocidad")
        if result.get("success"):
            dl = result.get("download_mbps", 0)
            ul = result.get("upload_mbps", 0)
            ping = result.get("ping_ms", 0)
            self.speed_btn.setToolTip(
                f"↓ {dl:.1f} Mbps  ↑ {ul:.1f} Mbps  ping {ping:.0f} ms"
            )

    def _auto_refresh_devices(self):
        if self.is_connected_to_network:
            self._update_network_quality()
            self._start_devices_scan()

    def _check_network_connection(self):
        """
        Verifica si estamos conectados a la red objetivo.
        FIX: usa get_current_network_info() que ahora proviene exclusivamente
             de backend.network_status, garantizando que nunca sea None stub.
        """
        current_network = get_current_network_info()

        print(f"🔍 DIAGNÓSTICO COMPLETO:")
        print(f"   - current_network: {current_network}")
        print(f"   - red_meta (objetivo): {self.red_meta.get('SSID')}")

        if not current_network:
            print("   ❌ get_current_network_info() devolvió None o vacío")
            self.is_connected_to_network = False
            self.connection_status_lbl.setText(
                "🔴 No conectado a ninguna red - Escaneo limitado"
            )
            self.connection_status_lbl.setStyleSheet(
                f"color: {COLOR_WARNING}; font-weight: bold;"
            )
            return

        target_ssid  = self.red_meta.get("SSID")
        # network_status devuelve claves en minúscula ('ssid'), soportar ambas
        current_ssid = current_network.get("ssid") or current_network.get("SSID")
        current_ssid_upper = {k.upper(): v for k, v in current_network.items()}

        self.is_connected_to_network = (current_ssid == target_ssid)

        if self.is_connected_to_network:
            self.red_meta.update(current_ssid_upper)
            self.connection_status_lbl.setText(
                "🟢 Conectado a esta red - Escaneo activo"
            )
            self.connection_status_lbl.setStyleSheet(
                f"color: {COLOR_SUCCESS}; font-weight: bold;"
            )
            self._update_network_quality()
        else:
            if current_ssid:
                self.connection_status_lbl.setText(
                    f"🔶 Conectado a otra red ('{current_ssid}') - Escaneo limitado"
                )
            else:
                self.connection_status_lbl.setText(
                    "🔴 No conectado a esta red - Escaneo limitado"
                )
            self.connection_status_lbl.setStyleSheet(
                f"color: {COLOR_WARNING}; font-weight: bold;"
            )

    def _update_network_quality(self):
        """Actualizar métricas de calidad de red."""
        if not self.is_connected_to_network:
            return
        try:
            congestion_info = get_network_congestion()
            if congestion_info:
                self.network_quality = {
                    "stability":     congestion_info.get("stability_percentage", 0.0),
                    "packet_loss":   congestion_info.get("packet_loss", 0.0),
                    "latency":       congestion_info.get("latency", 0.0),
                    "signal_quality": congestion_info.get("signal_quality", 0.0),
                }
        except Exception as e:
            print(f"[DevicesDialog] Error actualizando calidad de red: {e}")

    def _start_devices_scan(self):
        self.loading_lbl.setText("🔍 Escaneando la red en busca de dispositivos...")

        class DevicesScanWorker(QThread):
            finished = pyqtSignal(dict)
            def __init__(self, red_meta):
                super().__init__()
                self._red_meta = red_meta
            def run(self):
                self.finished.emit(get_connected_devices(self._red_meta))

        self.scan_worker = DevicesScanWorker(self.red_meta)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _show_capacity_only(self):
        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        msg = QLabel("🛡️ Conéctate a esta red para ver los dispositivos")
        msg.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        self.scroll_layout.addWidget(msg)

        self.devices_count_lbl.setText(
            f"📱 Conectados: 0/{self.router_capacity} dispositivos"
        )
        self.usage_lbl.setText("📈 Uso: 0%")
        self.scroll_layout.addStretch()

    def _on_scan_finished(self, result: dict):
        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        print("respuestas:", result)

        if result.get("success", False):
            devices     = result.get("devices", [])
            total       = len(devices)
            max_devices = result.get("max_devices") or self.router_capacity or 50
            self.current_devices = total
            self.devices_count_lbl.setText(
                f"Conectados: {total}/{max_devices} dispositivos"
            )
            usage = min(100, int((total / max_devices) * 100)) if max_devices > 0 else 0
            self.usage_lbl.setText(f"📈 Uso: {usage}%")

            if devices:
                for device in devices:
                    self.scroll_layout.addWidget(self._create_device_card(device))
            else:
                no_dev = QLabel("No se encontraron dispositivos en la red")
                no_dev.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.scroll_layout.addWidget(no_dev)
        else:
            error_msg = result.get("error", "Error desconocido")
            err_lbl = QLabel(f"Error: {error_msg}")
            err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(err_lbl)

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

        type_lbl = QLabel(device.get("type", "💻 Dispositivo"))
        type_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(type_lbl)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.addWidget(QLabel(f"📍 IP: {device.get('ip', 'N/A')}"))
        info_layout.addWidget(QLabel(f"🔗 MAC: {device.get('mac', 'N/A')}"))
        info_layout.addWidget(QLabel(f"🏭 {device.get('vendor', 'Desconocido')}"))
        layout.addLayout(info_layout)
        layout.addStretch()

        return card

    def _open_netguard(self):
        """
        Abrir NetGuard como ventana independiente.
        Sin padre (parent=None) → no queda atrapada detrás del diálogo modal.
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


# ── Punto de entrada ──────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    from vistas.main_window_wifi import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()