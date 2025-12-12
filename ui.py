from librerias import verificar_librerias
verificar_librerias()
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
from PyQt6.QtGui import QFont, QIcon, QCursor
from PyQt6.QtGui import QMouseEvent

from main import scan_wifi
from ai_suggestions import sugerencia_tecnologia, sugerencia_protocolo
from network_status import get_connected_wifi_info, is_current_network, get_network_congestion, is_connected_to_network

# Importar el módulo de velocidad
try:
    from network_speed import test_network_speed
except ImportError as e:
    print(f"❌ No se pudo importar network_speed: {e}")
    def test_network_speed():
        return {
            "success": False,
            "error": "Módulo no disponible",
            "download_mbps": 0.0,
            "upload_mbps": 0.0,
            "ping_ms": 999.0,
            "message": "Speedtest no disponible"
        }

try:
    from vendor_lookup import get_vendor, get_enhanced_vendor_info
except Exception as e:
    print(f"Error cargando vendor_lookup: {e}")
    def get_vendor(_):
        return "Desconocido"
    def get_enhanced_vendor_info(bssid, ssid=None):
        return {
            'vendor': "Desconocido",
            'is_random': False,
            'original_mac': bssid,
            'original_vendor': "Desconocido"
        }

try:
    from ap_device_scanner import get_connected_devices, get_devices_count, get_current_network_info
except Exception as e:
    print(f"Error cargando ap_device_scanner: {e}")
    def get_connected_devices(red_info=None):
        return {'success': False, 'devices': [], 'total_devices': 0, 'max_devices': 50, 'usage_percentage': 0}
    def get_devices_count(red_info=None):
        return 0
    def get_current_network_info():
        return None

# Importar el detector de capacidad
try:
    from mac_capacidad import get_router_info
except ImportError:
    print("❌ No se pudo importar mac_capacidad")
    def get_router_info(mac: str, wifi_tech: str = "", vendor: str = "") -> Dict:
        return {
            "model": "No detectado",
            "max_devices": 50,  # Valor por defecto
            "wifi_standard": "Desconocido",
            "confidence": "low"
        }

# ==================== NUEVO WORKER PARA VELOCIDAD ====================
class SpeedTestWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._is_running = True
        
    def run(self):
        if not self._is_running:
            return
        try:
            result = test_network_speed()
            if self._is_running:
                self.finished.emit(result)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))
    
    def stop(self):
        """Detener el worker de manera segura"""
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(3000):  # Esperar 3 segundos (speedtest puede ser lento)
                self.terminate()
                self.wait(1000)

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

# ----------------- Configuración visual profesional -----------------
CARD_WIDTH = 320
CARD_HEIGHT = 160

# Colores corporativos profesionales
COLOR_BG = "#1E1E1E"          # Fondo principal oscuro
COLOR_CARD = "#2D2D2D"        # Fondo de tarjetas
COLOR_CARD_BORDER = "#404040" # Borde de tarjetas
COLOR_TEXT = "#E0E0E0"        # Texto principal
COLOR_ACCENT = "#0078D4"      # Azul corporativo
COLOR_SUCCESS = "#107C10"     # Verde éxito
COLOR_WARNING = "#D83B01"     # Naranja advertencia
COLOR_ERROR = "#E81123"       # Rojo error
COLOR_MUTED = "#848484"       # Texto secundario
COLOR_NoCONETCT = "#79A3A1"

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
class ScanWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._is_running = True
        
    def run(self):
        try:
            if not self._is_running:
                return
            redes = scan_wifi()
            if self._is_running:
                self.finished.emit(redes)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))
    
    def stop(self):
        """Detener el worker de manera segura"""
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(1000):  # Esperar 1 segundo
                self.terminate()
                self.wait(1000)

class SuggestionWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, red_meta, tipo="tecnologia"):
        super().__init__()
        self.red_meta = red_meta
        self.tipo = tipo
        self._is_running = True
        
    def run(self):
        if not self._is_running:
            return
        try:
            if self.tipo == "tecnologia":
                result = sugerencia_tecnologia(self.red_meta)
            else:
                result = sugerencia_protocolo(self.red_meta)
                
            if self._is_running:
                self.finished.emit(result)
        except Exception as e:
            if self._is_running:
                self.error.emit(f"Error: {e}")
    
    def stop(self):
        """Detener el worker de manera segura"""
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(1000):
                self.terminate()
                self.wait(1000)

class VendorWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, bssid, ssid=None):
        super().__init__()
        self.bssid = bssid
        self.ssid = ssid
        self._is_running = True
        
    def run(self):
        if not self._is_running:
            return
        try:
            # Pequeña pausa para evitar sobrecarga
            self.msleep(50)
            
            if not self._is_running:
                return
                
            # Usar la función mejorada que detecta MACs aleatorias
            vendor_info = get_enhanced_vendor_info(self.bssid, self.ssid)
            vendor = vendor_info['vendor']
            
            if self._is_running:
                self.finished.emit(vendor)
                
        except Exception as e:
            if self._is_running:
                self.error.emit(f"Error en consulta: {e}")
    
    def stop(self):
        """Detener el worker de manera segura"""
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(500):
                self.terminate()
                self.wait(500)

class DevicesScanWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, red_meta):
        super().__init__()
        self.red_meta = red_meta
        self._is_running = True
    
    def run(self):
        if not self._is_running:
            return
        try:
            result = get_connected_devices(self.red_meta)
            if self._is_running:
                self.finished.emit(result)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))
    
    def stop(self):
        """Detener el worker de manera segura"""
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(1000):
                self.terminate()
                self.wait(1000)

# Worker para obtener capacidad del router
class RouterCapacityWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, mac: str, vendor: str, wifi_tech: str = ""):
        super().__init__()
        self.mac = mac
        self.vendor = vendor
        self.wifi_tech = wifi_tech
        self._is_running = True
        
    def run(self):
        if not self._is_running:
            return
            
        try:
            router_info = get_router_info(self.mac, self.wifi_tech, self.vendor)
            if self._is_running:
                self.finished.emit(router_info)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))
    
    def stop(self):
        """Detener el worker de manera segura"""
        self._is_running = False
        if self.isRunning():
            self.quit()
            if not self.wait(1000):
                self.terminate()
                self.wait(1000)

# ----------------- UI Elements -----------------

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

    def closeEvent(self, event):
        """Manejar cierre del diálogo"""
        if self.capacity_worker and self.capacity_worker.isRunning():
            self.capacity_worker.stop()
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.stop()
        if self.speed_worker and self.speed_worker.isRunning():
            self.speed_worker.stop()
        event.accept()

# ----------------- Diálogo de Detalles Profesional -----------------
class NetworkDetailsDialog(QDialog):
    def __init__(self, bssid: str, red_meta: dict, parent=None):
        super().__init__(parent)
        self.bssid = bssid
        self.red_meta = red_meta
        
        # Control de threads activos
        self.vendor_worker = None
        self.suggestion_workers = {}
        self.vendor_completed = False
        self._is_closing = False  # Bandera para controlar cierre
        
        # Información de MAC aleatoria
        self.mac_aleatoria = False
        self.mac_original = bssid
        self.esta_conectado_a_red = False
        
        # Establecer icono
        self.set_icon()
        
        self.setWindowTitle(f"Análisis de Red - {red_meta.get('SSID', 'Red')}")
        self.setMinimumSize(800, 650)
        self.setup_ui()
        
    def set_icon(self):
        """Establecer el icono de la ventana"""
        icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
    def setup_ui(self):
        # Estilo profesional corporativo
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

        # Título del diálogo
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
            """Crear etiqueta de campo con estilo profesional"""
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {COLOR_ACCENT};")
            return lbl

        def make_value_label(text):
            """Crear etiqueta de valor con estilo profesional"""
            lbl = QLabel(str(text))
            lbl.setFont(QFont("Segoe UI", 10))
            lbl.setStyleSheet(f"color: {COLOR_TEXT};")
            lbl.setWordWrap(True)
            return lbl

        # Datos de la red
        datos = [
            ("SSID", self.red_meta.get("SSID", "<sin nombre>")),
            ("Dirección MAC", self.bssid),
            ("Fabricante", "Buscando..."),
            ("Intensidad de señal", f"{self.red_meta.get('Señal', 'N/A')} dBm"),
            ("Frecuencia", f"{self.red_meta.get('Frecuencia', 'N/A')} MHz"),
            ("Banda", self.red_meta.get("Banda", "Desconocida")),
            ("Canal", self.red_meta.get("Canal", "Desconocido")),
            ("Seguridad", self.red_meta.get("Seguridad", "Desconocido")),
            ("Ancho de canal", self.red_meta.get("AnchoCanal", "Desconocido")),
            ("Distancia estimada", f"≈ {self.red_meta.get('Estimacion_m', 'N/A')} metros"),
            ("Tecnología", self.red_meta.get("Tecnologia", "Desconocida")),
            ("Autenticación", self.red_meta.get("Autenticación", "Desconocida")),
            ("Cifrado", self.red_meta.get("Cifrado", "Desconocida")),
            ("Ambiente", self.red_meta.get("Ambiente", "Desconocido").capitalize()),
        ]

        # Añadir campos al layout
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

        # Botón de análisis de tecnología
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
            QPushButton:hover {{
                background-color: #106EBE;
            }}
            QPushButton:pressed {{
                background-color: #005A9E;
            }}
            QPushButton:disabled {{
                background-color: #505050;
                color: #A0A0A0;
            }}
        """)

        # Botón de análisis de protocolo
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
            QPushButton:hover {{
                background-color: #0E6C0E;
            }}
            QPushButton:pressed {{
                background-color: #0C5C0C;
            }}
            QPushButton:disabled {{
                background-color: #505050;
                color: #A0A0A0;
            }}
        """)

        # Botón de ver dispositivos (inicialmente deshabilitado)
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
            QPushButton:hover {{
                background-color: #FFA500;
            }}
            QPushButton:pressed {{
                background-color: #CC9200;
            }}
            QPushButton:disabled {{
                background-color: #505050;
                color: #A0A0A0;
            }}
        """)

        buttons_layout.addWidget(self.btn_tecn)
        buttons_layout.addWidget(self.btn_proto)
        buttons_layout.addWidget(self.btn_devices)

        # Conectar señales
        self.btn_tecn.clicked.connect(lambda: self._handle_sugerencia("tecnologia"))
        self.btn_proto.clicked.connect(lambda: self._handle_sugerencia("protocolo"))
        self.btn_devices.clicked.connect(self._show_devices)

        outer_layout.addWidget(buttons_frame)

        # Verificar si está conectado a esta red
        self._check_connection_status()
        
        # Iniciar búsqueda de fabricante
        self._start_vendor_lookup()

    def _check_connection_status(self):
        """Verificar si está conectado a esta red específica"""
        ssid = self.red_meta.get("SSID")
        bssid = self.red_meta.get("BSSID")
        
        self.esta_conectado_a_red = is_connected_to_network(ssid, bssid)
        
        # Inicialmente desactivar el botón hasta que tengamos la info del vendor
        self.btn_devices.setEnabled(False)
        if not self.esta_conectado_a_red:
            self.btn_devices.setText("🔒 Conéctate a la red")
        else:
            self.btn_devices.setText("⏳ Esperando fabricante...")

    def _update_buttons_state(self):
        """Actualizar estado de los botones"""
        vendor_ready = self.vendor_completed
        has_active_suggestions = any(worker.isRunning() for worker in self.suggestion_workers.values())
        
        self.btn_tecn.setEnabled(vendor_ready and not has_active_suggestions)
        self.btn_proto.setEnabled(vendor_ready and not has_active_suggestions)
        
        # SOLO activar el botón de dispositivos si está conectado a la red
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
        elif has_active_suggestions:
            self.btn_tecn.setText("🔄 Analizando...")
            self.btn_proto.setText("🔄 Analizando...")
            if self.esta_conectado_a_red:
                self.btn_devices.setText("📱 Ver Dispositivos Conectados")
        else:
            self.btn_tecn.setText("🔍 Análisis de Tecnología")
            self.btn_proto.setText("🔒 Análisis de Protocolo")
            if self.esta_conectado_a_red:
                self.btn_devices.setText("📱 Ver Dispositivos Conectados")

    def _start_vendor_lookup(self):
        """Iniciar búsqueda de fabricante con detección de MAC aleatoria"""
        self.vendor_worker = VendorWorker(self.bssid, self.red_meta.get("SSID"))
        self.vendor_worker.finished.connect(self._on_vendor_finished)
        self.vendor_worker.error.connect(lambda e: print(f"Error vendor: {e}"))
        self.vendor_worker.finished.connect(self.vendor_worker.deleteLater)
        self.vendor_worker.start()
        self._update_buttons_state()

    def _on_vendor_finished(self, vendor):
        """Callback cuando termina la búsqueda de fabricante"""
        if not self._is_closing:
            # Obtener información completa mejorada CON LA NUEVA LÓGICA
            enhanced_info = get_enhanced_vendor_info(self.bssid, self.red_meta.get("SSID"))
            
            # Actualizar la etiqueta del fabricante
            if enhanced_info['is_random'] and enhanced_info['original_vendor'] != "Desconocido":
                self.vendor_lbl.setText(f"{enhanced_info['original_vendor']} ({enhanced_info['original_mac']})")
                # Guardar el fabricante real en red_meta
                self.red_meta["Fabricante"] = enhanced_info['original_vendor']
            else:
                self.vendor_lbl.setText(vendor)
                self.red_meta["Fabricante"] = vendor
            
            # Actualizar estado de MAC aleatoria
            self.mac_aleatoria = enhanced_info['is_random']
            self.mac_original = enhanced_info['original_mac']
            
            # NUEVA LÓGICA: ACTUALIZAR ESTADO DEL BOTÓN SEGÚN can_scan_devices
            can_scan_devices = enhanced_info.get('can_scan_devices', False) and self.esta_conectado_a_red
            
            if can_scan_devices:
                self.btn_devices.setEnabled(True)
                self.btn_devices.setText("📱 Ver Dispositivos Conectados")
            else:
                self.btn_devices.setEnabled(False)
                if not self.esta_conectado_a_red:
                    self.btn_devices.setText("🔒 Conéctate a la red")
                else:
                    self.btn_devices.setText("🔒 No se puede escanear")
            
            self.vendor_completed = True
            self.vendor_worker = None
            self._update_buttons_state()
            
    def _handle_sugerencia(self, tipo):
        """Manejar solicitud de sugerencia"""
        if not self.vendor_completed or self._is_closing:
            return

        if tipo in self.suggestion_workers and self.suggestion_workers[tipo].isRunning():
            return

        worker = SuggestionWorker(self.red_meta, tipo)
        self.suggestion_workers[tipo] = worker
        
        worker.finished.connect(lambda result: self._on_suggestion_finished(tipo, result))
        worker.error.connect(lambda e: print(f"Error sugerencia: {e}"))
        worker.finished.connect(worker.deleteLater)
        
        self._update_buttons_state()
        worker.start()

    def _on_suggestion_finished(self, tipo, result):
        """Callback cuando termina una sugerencia"""
        if not self._is_closing and tipo in self.suggestion_workers:
            del self.suggestion_workers[tipo]
            self._update_buttons_state()
            
            # Solo mostrar el diálogo si no estamos cerrando
            if not self._is_closing:
                titulo = "Análisis de Tecnología" if tipo == "tecnologia" else "Análisis de Protocolo"
                suggestion_dialog = SuggestionWindow(titulo, result, parent=self)
                suggestion_dialog.exec()

    def _show_devices(self):
        """Mostrar diálogo de dispositivos conectados"""
        # USAR LA MAC ORIGINAL si es una MAC aleatoria y está conectado
        if self.esta_conectado_a_red and self.mac_aleatoria and self.mac_original:
            # Actualizar la red_meta con la MAC original para el escaneo
            self.red_meta["BSSID_Original"] = self.mac_original
            print(f"🔍 Usando MAC original para escaneo: {self.mac_original}")
        
        dialog = DevicesDialog(self.red_meta, self)
        dialog.exec()

    def closeEvent(self, event):
        """Manejar cierre del diálogo - DETENER TODOS LOS WORKERS"""
        self._is_closing = True
        
        # Detener worker de fabricante
        if self.vendor_worker and self.vendor_worker.isRunning():
            self.vendor_worker.stop()
        
        # Detener todos los workers de sugerencias
        for tipo, worker in self.suggestion_workers.items():
            if worker and worker.isRunning():
                worker.stop()
        
        # Limpiar referencias
        self.vendor_worker = None
        self.suggestion_workers.clear()
        
        event.accept()

# ----------------- Main Window Profesional -----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Establecer icono
        self.set_icon()
        
        self.setWindowTitle("Escáner WiFi Corporativo")
        self.setMinimumSize(1200, 800)

        # Control de diálogos activos
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

        # Título principal CON ICONO
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(20, 20, 20, 20)
        title_layout.setSpacing(15)
        
        # Cargar y mostrar el icono
        icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
        if os.path.exists(icon_path):
            icon_label = QLabel()
            icon_pixmap = QIcon(icon_path).pixmap(60, 60)  # Mismo tamaño que la fuente
            icon_label.setPixmap(icon_pixmap)
            title_layout.addWidget(icon_label)
        
        title = QLabel("Escáner WiFi Corporativo")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet(f"""
            QLabel {{
                color: #FFFFFF;
                background-color: transparent;
            }}
        """)
        title_layout.addWidget(title)
        # title_layout.addStretch()
        # Centrar el contenido (icono + texto)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_CARD};
                border-radius: 8px;
            }}
        """)
        
        main_layout.addWidget(title_widget)

        # ... el resto del código permanece igual ...
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

        # Timer para escaneo automático
        self.timer = QTimer()
        self.timer.timeout.connect(self.lanzar_scan)
        self.timer.start(3000)  # Cada 3 segundos
        self.lanzar_scan()

        # Estilo principal
        self.setStyleSheet(f"QMainWindow {{ background-color: {COLOR_BG}; }}")

    def set_icon(self):
        """Establecer el icono de la ventana principal"""
        icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def closeEvent(self, event):
        """
        Manejar cierre de la aplicación principal.
        Limpia la consola antes de cerrar.
        """
        print("🔒 Cerrando aplicación...")
        
        # Detener timer de escaneo
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        
        # Detener worker de escaneo si está activo
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.stop()
        
        # Cerrar diálogo activo si existe
        if self.active_dialog and self.active_dialog.isVisible():
            self.active_dialog.close()
        
        # Detener todos los workers de router capacity
        for worker in self.active_workers:
            if worker and worker.isRunning():
                worker.stop()
        
        # Limpiar consola
        self._clear_console()
        
        print("👋 Aplicación cerrada correctamente")
        event.accept()

    def _clear_console(self):
        """Limpiar la consola según el sistema operativo"""
        try:
            system = platform.system().lower()
            
            if system == "windows":
                # Windows - usar cls
                subprocess.call('cls', shell=True)
            elif system in ["linux", "darwin"]:  # Darwin es macOS
                # Linux/macOS - usar clear
                subprocess.call('clear', shell=True)
            else:
                # Sistema no reconocido - imprimir líneas en blanco
                print('\n' * 50)
                
            print("🖥️  Consola limpiada")
            
        except Exception as e:
            print(f"⚠️ No se pudo limpiar la consola: {e}")
            # Fallback: imprimir líneas en blanco
            print('\n' * 50)

    def lanzar_scan(self):
        """Iniciar escaneo de redes"""
        if not self.scan_worker or not self.scan_worker.isRunning():
            self.scan_worker = ScanWorker()
            self.scan_worker.finished.connect(self._scan_done)
            self.scan_worker.error.connect(lambda e: print(f"Error escaneo: {e}"))
            self.scan_worker.start()

    def _scan_done(self, redes):
        """Callback cuando termina el escaneo"""
        self.redes = redes
        self.cantidad_label.setText(f"Redes detectadas: {len(redes)}")
        
        if self.is_first_scan and redes:
            self.scanning_label.hide()
            self.is_first_scan = False
        
        self.construir_cards()
        
        # Actualizar capacidades de routers después de construir las tarjetas
        QTimer.singleShot(2000, self.update_router_capacities)  # 2 segundos de delay

    def construir_cards(self):
        """Construir las tarjetas de redes"""
        # Limpiar el layout
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w: 
                w.setParent(None)

        # Si no hay redes, mostrar mensaje
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
        
        # Calcular número de columnas
        ancho_px = max(1, self.scroll_content.width() or self.width())
        num_cols = max(1, ancho_px // (CARD_WIDTH + 30))
        
        # Añadir tarjetas
        for idx, red in enumerate(self.redes):
            row, col = divmod(idx, num_cols)
            card = Card(red)
            self.grid.addWidget(card, row, col)

    def update_router_capacities(self):
        """Actualizar capacidades de todos los routers en las tarjetas"""
        for i in range(self.grid.count()):
            item = self.grid.itemAt(i)
            if item and item.widget():
                card = item.widget()
                if (hasattr(card, 'red') and 
                    card.red.get("BSSID") and 
                    card.red.get("Fabricante") and
                    card.red.get("BSSID") not in self.router_info_cache):
                    
                    # Iniciar carga de información
                    self._load_router_info_for_card(card)
    
    def _load_router_info_for_card(self, card):
        """Cargar información del router para una tarjeta específica"""
        mac = card.red["BSSID"]
        vendor = card.red["Fabricante"]
        wifi_tech = card.red.get("Tecnologia", "")
        
        worker = RouterCapacityWorker(mac, vendor, wifi_tech)
        worker.finished.connect(lambda info, c=card: self._on_card_router_info_loaded(info, c))
        worker.error.connect(lambda e: print(f"Error router capacity: {e}"))
        
        # Agregar a lista de workers activos
        self.active_workers.append(worker)
        worker.start()
    
    def _on_card_router_info_loaded(self, router_info, card):
        """Callback cuando se carga la info del router para una tarjeta"""
        try:
            if router_info and router_info.get("max_devices"):
                # Actualizar en cache
                self.router_info_cache[card.red["BSSID"]] = router_info
                
                # Actualizar la tarjeta
                card.red["router_max_devices"] = router_info["max_devices"]
                card.red["router_model"] = router_info.get("model", "No detectado")
                card._update_router_model()
            
            # Remover worker de la lista activa
            if hasattr(self, 'active_workers'):
                # Encontrar y remover el worker completado
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
        """Mostrar diálogo de detalles - CERRAR DIÁLOGO ANTERIOR SI EXISTE"""
        # Cerrar diálogo anterior si existe
        if self.active_dialog and self.active_dialog.isVisible():
            self.active_dialog.close()
            self.active_dialog = None
        
        # Crear nuevo diálogo
        dialog = NetworkDetailsDialog(bssid, red_meta or {}, self)
        self.active_dialog = dialog
        dialog.finished.connect(self._on_dialog_closed)
        dialog.exec()

    def _on_dialog_closed(self):
        """Callback cuando se cierra el diálogo"""
        self.active_dialog = None

# ----------------- Main -----------------
def main():
    app = QApplication(sys.argv)
    
    # Establecer estilo de aplicación
    app.setStyle('Fusion')
    
    # Establecer icono
    icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
        # --- Forzar icono en la barra de tareas (SOLO WINDOWS) ---
        print(platform.system() )
        if platform.system() == "Windows":
            import ctypes
            myappid = 'corporate.wifi.scanner.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    window = MainWindow()
    window.show()

    
    # Manejar cierre limpio de la aplicación
    def handle_application_quit():
        window.close()
    
    app.aboutToQuit.connect(handle_application_quit)
    
    sys.exit(app.exec())
# Función temporal de diagnóstico
def diagnosticar_red_actual():
    """Diagnóstico de la función get_current_network_info"""
    print("🛠️ DIAGNÓSTICO get_current_network_info():")
    
    # Probar la función actual
    resultado = get_current_network_info()
    print(f"   - Resultado: {resultado}")
    
    # Probar alternativas
    try:
        from network_status import get_connected_wifi_info
        resultado2 = get_connected_wifi_info()
        print(f"   - get_connected_wifi_info(): {resultado2}")
    except Exception as e:
        print(f"   - Error get_connected_wifi_info: {e}")
    
    return resultado

# Llamar al diagnóstico cuando se abra DevicesDialog
# Agrega esta línea en el constructor de DevicesDialog, después de super().__init__(parent)
# diagnosticar_red_actual()
if __name__ == "__main__":
    main()