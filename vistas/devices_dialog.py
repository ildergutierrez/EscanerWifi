"""
vistas/devices_dialog.py – Diálogo de dispositivos conectados con test de velocidad
"""
import sys
import os
import subprocess
import platform
from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QScrollArea, QGridLayout, QPushButton, QFrame, QDialog,
    QTextEdit, QHBoxLayout, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QIcon, QCursor, QMouseEvent

# ── Rutas del proyecto ────────────────────────────────────────────────────
# Este archivo vive en EscanerWifi/vistas/
# El __init__.py de vistas/ ya configura sys.path al importar el paquete.
# Este bloque es un respaldo por si el archivo se ejecuta directamente.
_VISTAS_DIR = os.path.abspath(os.path.dirname(__file__))    # EscanerWifi/vistas/
_PROJ_ROOT  = os.path.dirname(_VISTAS_DIR)                  # EscanerWifi/
_BACKEND    = os.path.join(_PROJ_ROOT, "backend")           # EscanerWifi/backend/
_NETWORK    = os.path.join(_PROJ_ROOT, "network")           # EscanerWifi/network/
for _p in (_PROJ_ROOT, _BACKEND, _NETWORK):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Imports del backend ───────────────────────────────────────────────────
from main import scan_wifi
from ai_suggestions import sugerencia_tecnologia, sugerencia_protocolo
from network_status import (get_connected_wifi_info, is_current_network,
                             get_network_congestion, is_connected_to_network)

try:
    from network_speed import test_network_speed
except ImportError:
    def test_network_speed():
        return {"success": False, "error": "Módulo no disponible",
                "download_mbps": 0.0, "upload_mbps": 0.0, "ping_ms": 999.0}

try:
    from vendor_lookup import get_vendor, get_enhanced_vendor_info
except Exception:
    def get_vendor(_): return "Desconocido"
    def get_enhanced_vendor_info(bssid, ssid=None):
        return {"vendor": "Desconocido", "is_random": False,
                "original_mac": bssid, "original_vendor": "Desconocido"}

try:
    from ap_device_scanner import get_connected_devices, get_devices_count, get_current_network_info
except Exception:
    def get_connected_devices(red_info=None):
        return {"success": False, "devices": [], "total_devices": 0,
                "max_devices": 50, "usage_percentage": 0}
    def get_devices_count(red_info=None): return 0
    def get_current_network_info(): return None

try:
    from mac_capacidad import get_router_info
except ImportError:
    def get_router_info(mac: str, wifi_tech: str = "", vendor: str = "") -> Dict:
        return {"model": "No detectado", "max_devices": 50,
                "wifi_standard": "Desconocido", "confidence": "low"}

# ── NetGuard ──────────────────────────────────────────────────────────────
# _NETWORK ya está en sys.path desde el bloque de rutas arriba
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

from vistas.workers import (SpeedTestWorker, RouterCapacityWorker, DevicesScanWorker)

# diagnóstico (se importa desde aquí para no duplicar)
from ap_device_scanner import get_current_network_info
from network_status import get_network_congestion

class SuggestionWindow(QDialog):
    def __init__(self, titulo: str, texto: str, parent=None):
        super().__init__(parent)
        
        # Establecer icono
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
        
        # Título con estilo profesional
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
        
        # Área de texto scrollable
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
        """Establecer el icono de la ventana"""
        icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))


# Colores para estados de señal
def signal_color_by_dbm(signal_dbm: Optional[float]) -> str:
    try:
        if signal_dbm is None:
            return COLOR_MUTED
        s = float(signal_dbm)
        if s >= -60:
            return COLOR_SUCCESS  # Verde
        if s >= -70:
            return "#FFB900"     # Amarillo corporativo
        if s >= -80:
            return COLOR_WARNING  # Naranja
        return COLOR_ERROR        # Rojo
    except Exception:
        return COLOR_MUTED

# ----------------- Workers Mejorados -----------------


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
        
        # Establecer icono
        self.set_icon()
        
        self.setWindowTitle(f"Dispositivos Conectados - {red_meta.get('SSID', 'Red')}")
        self.setMinimumSize(900, 700)
        self.setup_ui()
        
        # Timer de actualización automática
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._auto_refresh_devices)
        self.refresh_timer.start(120000)  # 2 minutos
         # ✅ DIAGNÓSTICO INMEDIATO
        print("🚀 INICIANDO DevicesDialog DIAGNÓSTICO")
        diagnosticar_red_actual()
        # ✅ PRIMERO verificar conexión (esto actualizará red_meta si es necesario)
        self._check_network_connection()
        
        # LUEGO cargar capacidad del router
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

        # Información de capacidad
        self.capacity_frame = QFrame()
        capacity_layout = QVBoxLayout()
        capacity_layout.setContentsMargins(20, 15, 20, 15)
        self.capacity_frame.setLayout(capacity_layout)
        
        # Información del router
        self.router_info_lbl = QLabel("🔄 Detectando información del router...")
        self.router_info_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        capacity_layout.addWidget(self.router_info_lbl)
        
        # Estado de conexión
        self.connection_status_lbl = QLabel()
        self.connection_status_lbl.setFont(QFont("Segoe UI", 11))
        capacity_layout.addWidget(self.connection_status_lbl)
        
        # ============ SECCIÓN COMPACTA: CALIDAD DE RED ============
        quality_frame = QFrame()
        quality_layout = QHBoxLayout()
        quality_layout.setContentsMargins(10, 5, 10, 5)
        quality_frame.setLayout(quality_layout)
        
        # Título calidad de red
        quality_title = QLabel("📊 Calidad:")
        quality_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        quality_title.setStyleSheet(f"color: {COLOR_ACCENT}; min-width: 60px;")
        quality_layout.addWidget(quality_title)
        
        # Estabilidad
        self.stability_lbl = QLabel("🔄 --%")
        self.stability_lbl.setFont(QFont("Segoe UI", 9))
        self.stability_lbl.setToolTip("Estabilidad de la red")
        quality_layout.addWidget(self.stability_lbl)
        
        # Pérdida de paquetes
        self.packet_loss_lbl = QLabel("📦 --%")
        self.packet_loss_lbl.setFont(QFont("Segoe UI", 9))
        self.packet_loss_lbl.setToolTip("Pérdida de paquetes")
        quality_layout.addWidget(self.packet_loss_lbl)
        
        # Latencia
        self.latency_lbl = QLabel("🏓 -- ms")
        self.latency_lbl.setFont(QFont("Segoe UI", 9))
        self.latency_lbl.setToolTip("Latencia/Ping")
        quality_layout.addWidget(self.latency_lbl)
        
        # Calidad de señal
        self.signal_quality_lbl = QLabel("📡 --%")
        self.signal_quality_lbl.setFont(QFont("Segoe UI", 9))
        self.signal_quality_lbl.setToolTip("Calidad de señal")
        quality_layout.addWidget(self.signal_quality_lbl)
        
        quality_layout.addStretch()
        capacity_layout.addWidget(quality_frame)
        
        # Sección de velocidad
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
            self.netguard_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #0d419d;
                    color: #e6edf3;
                    border: 1px solid #1f6feb;
                    border-radius: 4px;
                    padding: 3px 6px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background-color: #1158c7; }}
                QPushButton:disabled {{ background-color: #333; color: #666; }}
            """)
            self.netguard_btn.clicked.connect(self._open_netguard)
            speed_layout.addWidget(self.netguard_btn)
        
        capacity_layout.addWidget(speed_frame)
        
        # Información de dispositivos
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
            
        # Scroll area
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

        # Botones
        buttons_layout = QHBoxLayout()
        btn_close = QPushButton("Cerrar")
        btn_close.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        btn_close.setMinimumHeight(40)
        btn_close.clicked.connect(self.close)
        buttons_layout.addWidget(btn_close)
        layout.addLayout(buttons_layout)

    def _auto_refresh_devices(self):
        """Actualizar automáticamente la lista de dispositivos"""
        if self.is_connected_to_network:
            self._update_network_quality()
            self._start_devices_scan()

    def _check_network_connection(self):
        """Verificar si está conectado a esta red usando información REAL"""
        # Obtener información REAL de la red actualmente conectada
        current_network = get_current_network_info()
        
        # ✅ DIAGNÓSTICO COMPLETO
        print(f"🔍 DIAGNÓSTICO COMPLETO:")
        print(f"   - current_network: {current_network}")
        print(f"   - red_meta (objetivo): {self.red_meta.get('SSID')}")
        
        if not current_network:
            print("   ❌ get_current_network_info() devolvió None o vacío")
            self.is_connected_to_network = False
            self.connection_status_lbl.setText("🔴 No conectado a ninguna red - Escaneo limitado")
            self.connection_status_lbl.setStyleSheet(f"color: {COLOR_WARNING}; font-weight: bold;")
            return
        
        # ✅ CORRECCIÓN: Usar claves en minúsculas (como viene de get_current_network_info)
        target_ssid = self.red_meta.get("SSID")
        # current_network usa 'ssid' en minúscula, no 'SSID'
        current_ssid = current_network.get("ssid") or current_network.get("SSID")  # Intentar ambas
        
        # Solo comparar por SSID (el BSSID puede cambiar)
        self.is_connected_to_network = (current_ssid == target_ssid)
        
        # # ✅ DEBUG: Mostrar información para diagnosticar
        # print(f"   - Red objetivo: '{target_ssid}'")
        # print(f"   - Red actual: '{current_ssid}'")
        # print(f"   - ¿Coinciden?: {self.is_connected_to_network}")
        # print(f"   - Claves disponibles en current_network: {list(current_network.keys())}")
        
        # ✅ ACTUALIZAR red_meta con información REAL si estamos conectados
        if self.is_connected_to_network:
            # Mantener los datos específicos de escaneo pero actualizar con info real
            # Convertir claves a mayúsculas para consistencia
            current_network_upper = {}
            for key, value in current_network.items():
                current_network_upper[key.upper()] = value
            
            self.red_meta.update(current_network_upper)
            
            self.connection_status_lbl.setText("🟢 Conectado a esta red - Escaneo activo")
            self.connection_status_lbl.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")
            # Obtener métricas de calidad de red
            self._update_network_quality()
        else:
            # Verificar si estamos en una red diferente
            if current_ssid:
                self.connection_status_lbl.setText(f"🔶 Conectado a otra red ('{current_ssid}') - Escaneo limitado")
            else:
                self.connection_status_lbl.setText("🔴 No conectado a esta red - Escaneo limitado")
            self.connection_status_lbl.setStyleSheet(f"color: {COLOR_WARNING}; font-weight: bold;") 

    def _update_network_quality(self):
        """Actualizar métricas de calidad de red desde network_status"""
        if self.is_connected_to_network:
            try:
                # Obtener información de congestión/calidad de red
                congestion_info = get_network_congestion()
                
                if congestion_info:
                    # Actualizar datos locales
                    self.network_quality = {
                        "stability": congestion_info.get('stability_percentage', 0.0),
                        "packet_loss": congestion_info.get('packet_loss', 0.0),
                        "latency": congestion_info.get('latency', 0.0),
                        "signal_quality": congestion_info.get('signal_quality', 0.0)
                    }
                    
                    # Actualizar UI con colores según la calidad
                    self._update_quality_ui()
                    
            except Exception as e:
                print(f"Error obteniendo calidad de red: {e}")

    def _update_quality_ui(self):
        """Actualizar la UI con las métricas de calidad"""
        # Estabilidad
        stability = self.network_quality["stability"]
        stability_color = COLOR_SUCCESS if stability >= 80 else COLOR_WARNING if stability >= 60 else COLOR_ERROR
        self.stability_lbl.setText(f"<span style='color: {stability_color};'>🔄 {stability:.1f}%</span>")
        
        # Pérdida de paquetes
        packet_loss = self.network_quality["packet_loss"]
        packet_loss_color = COLOR_SUCCESS if packet_loss <= 5 else COLOR_WARNING if packet_loss <= 15 else COLOR_ERROR
        self.packet_loss_lbl.setText(f"<span style='color: {packet_loss_color};'>📦 {packet_loss:.1f}%</span>")
        
        # Latencia
        latency = self.network_quality["latency"]
        latency_color = COLOR_SUCCESS if latency <= 50 else COLOR_WARNING if latency <= 100 else COLOR_ERROR
        self.latency_lbl.setText(f"<span style='color: {latency_color};'>🏓 {latency:.1f}ms</span>")
        
        # Calidad de señal
        signal_quality = self.network_quality["signal_quality"]
        signal_color = COLOR_SUCCESS if signal_quality >= 80 else COLOR_WARNING if signal_quality >= 60 else COLOR_ERROR
        self.signal_quality_lbl.setText(f"<span style='color: {signal_color};'>📡 {signal_quality:.1f}%</span>")

    def _start_speed_test(self):
        """Iniciar test de velocidad"""
        if self.speed_worker and self.speed_worker.isRunning():
            return
            
        self.speed_btn.setEnabled(False)
        self.speed_btn.setText("⏳...")
        
        self.speed_worker = SpeedTestWorker()
        self.speed_worker.finished.connect(self._on_speed_test_finished)
        self.speed_worker.error.connect(self._on_speed_test_error)
        self.speed_worker.start()

    def _on_speed_test_finished(self, result):
        """Callback cuando termina el test de velocidad"""
        self.speed_data = result
        
        if result.get('success', False):
            download = result.get('download_mbps', 0)
            upload = result.get('upload_mbps', 0)
            ping = result.get('ping_ms', 0)
            
            self.download_lbl.setText(f"⬇ {download:.1f}Mbps")
            self.upload_lbl.setText(f"⬆ {upload:.1f}Mbps")
            self.ping_lbl.setText(f"🏓 {ping:.1f}ms")
        
        self.speed_btn.setEnabled(True)
        self.speed_btn.setText("📊 Medir")

    def _on_speed_test_error(self, error_msg):
        """Callback cuando hay error en el test de velocidad"""
        self.download_lbl.setText("⬇ Error")
        self.upload_lbl.setText("⬆ Error")
        self.ping_lbl.setText("🏓 Error")
        self.speed_btn.setEnabled(True)
        self.speed_btn.setText("📊 Medir")

    def _load_router_capacity(self):
        """Cargar información de capacidad del router"""
        mac = self.red_meta.get("BSSID")
        vendor = self.red_meta.get("Fabricante")
        wifi_tech = self.red_meta.get("Tecnologia", "")
        
        if mac and vendor:
            self.capacity_worker = RouterCapacityWorker(mac, vendor, wifi_tech)
            self.capacity_worker.finished.connect(self._on_capacity_loaded)
            self.capacity_worker.start()
        else:
            self.router_capacity = 50
            self.router_model = "No detectado"
            self._update_router_info()
            self._handle_scan_logic()
    
    def _on_capacity_loaded(self, router_info):
        """Callback cuando se carga la capacidad del router"""
        self.router_capacity = router_info.get("max_devices", 50)
        self.router_model = router_info.get("model", "No detectado")
        self._update_router_info()
        self._handle_scan_logic()
    
    def _update_router_info(self):
        """Actualizar la información del router en la UI"""
        model_text = f"🛜 Router: {self.router_model}" 
        self.router_info_lbl.setText(model_text)
    
    def _handle_scan_logic(self):
        """Manejar la lógica de escaneo basada en el estado de conexión"""
        # ✅ PRIMERO verificar y actualizar la conexión
        self._check_network_connection()
        
        if self.is_connected_to_network:
            self._start_devices_scan()
        else:
            self._show_capacity_only()
    
    def _start_devices_scan(self):
        """Iniciar escaneo de dispositivos"""
        self.loading_lbl.setText("🔍 Escaneando la red en busca de dispositivos...")
        
        self.scan_worker = DevicesScanWorker(self.red_meta)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.start()
    
    def _show_capacity_only(self):
        """Mostrar solo información de capacidad"""
        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
        
        security_msg = QLabel("🛡️ Conéctate a esta red para ver los dispositivos")
        security_msg.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        security_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        security_msg.setWordWrap(True)
        self.scroll_layout.addWidget(security_msg)
        
        self.devices_count_lbl.setText(f"📱 Conectados: 0/{self.router_capacity} dispositivos")
        self.usage_lbl.setText("📈 Uso: 0%")
        self.scroll_layout.addStretch()
    
    def _on_scan_finished(self, result):
        """Callback cuando termina el escaneo de dispositivos"""
        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
                print("respuestas:",result)
        if result.get('success', False):
            print("respuestas.get:",result)
            devices = result.get('devices', [])
            total_devices = len(devices)
            max_devices = result.get('max_devices') or self.router_capacity or 50

            self.current_devices = total_devices
            self.devices_count_lbl.setText(f"Conectados: {total_devices}/{max_devices} dispositivos")
            usage = min(100, int((total_devices / max_devices) * 100)) if max_devices > 0 else 0
            self.usage_lbl.setText(f"📈 Uso: {usage}%")

            if devices:
                for device in devices:
                    self.scroll_layout.addWidget(self._create_device_card(device))
            else:
                no_dev = QLabel("No se encontraron dispositivos en la red")
                no_dev.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.scroll_layout.addWidget(no_dev)
        else:
            error_msg = result.get('error', 'Error desconocido')
            err_lbl = QLabel(f"Error: {error_msg}")
            err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(err_lbl)

    def _create_device_card(self, device: Dict) -> QFrame:
        """Crear tarjeta para dispositivo"""
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
        
        # Icono y tipo
        type_lbl = QLabel(device.get('type', '💻 Dispositivo'))
        type_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(type_lbl)
        
        # Información
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        ip_lbl = QLabel(f"📍 IP: {device.get('ip', 'N/A')}")
        ip_lbl.setFont(QFont("Segoe UI", 10))
        
        mac_lbl = QLabel(f"🔗 MAC: {device.get('mac', 'N/A')}")
        mac_lbl.setFont(QFont("Segoe UI", 9))
        
        vendor_lbl = QLabel(f"🏭 {device.get('vendor', 'Desconocido')}")
        vendor_lbl.setFont(QFont("Segoe UI", 9))
        
        info_layout.addWidget(ip_lbl)
        info_layout.addWidget(mac_lbl)
        info_layout.addWidget(vendor_lbl)
        layout.addLayout(info_layout)
        layout.addStretch()
        
        return card

    def _open_netguard(self):
        """Abrir NetGuard como ventana completamente independiente.
        
        Sin padre (parent=None) + WindowFlags explícitos → la ventana no queda
        atrapada detrás del diálogo ni se cierra con él.
        """
        if not NETGUARD_OK or NetGuardWindow is None:
            return
        # Si ya existe y es válida, traerla al frente
        if self.netguard_window is not None:
            try:
                self.netguard_window.showNormal()
                self.netguard_window.raise_()
                self.netguard_window.activateWindow()
                return
            except RuntimeError:
                self.netguard_window = None
        # Sin padre: Qt no la trata como hija del diálogo modal
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
        """Limpiar referencia cuando NetGuard se cierra."""
        self.netguard_window = None

    def closeEvent(self, event):
        """Manejar cierre del diálogo"""
        # Cerrar NetGuard si está abierto
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

# ----------------- Diálogo de Detalles Profesional -----------------