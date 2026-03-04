"""
vistas/network_details.py – Diálogo de detalles y análisis de una red WiFi
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

from vistas.workers import VendorWorker, SuggestionWorker
from vistas.devices_dialog import DevicesDialog, SuggestionWindow

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
        
        # Diccionario para guardar textos originales de botones
        self.botones_texto_original = {}
        
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
            # No cambiar el texto aquí porque ya lo cambiamos en _handle_sugerencia
            pass
        else:
            # Restaurar textos originales SOLO si no hay textos guardados
            if "tecnologia" not in self.botones_texto_original:
                self.btn_tecn.setText("🔍 Análisis de Tecnología")
            if "protocolo" not in self.botones_texto_original:
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
        print(f"🔄 Iniciando análisis de {tipo}")  # Debug
        
        if not self.vendor_completed or self._is_closing:
            print(f"❌ No se puede analizar: vendor_completed={self.vendor_completed}, _is_closing={self._is_closing}")
            return

        if tipo in self.suggestion_workers and self.suggestion_workers[tipo].isRunning():
            print(f"⏳ Ya hay un análisis de {tipo} en curso")
            return

        # Guardar texto original y cambiar el texto del botón correspondiente a "Analizando..."
        if tipo == "tecnologia":
            self.botones_texto_original[tipo] = self.btn_tecn.text()
            self.btn_tecn.setText("🔄 Analizando...")
            self.btn_tecn.setEnabled(False)
            print(f"🔍 Botón tecnología cambiado a: {self.btn_tecn.text()}")
        else:  # protocolo
            self.botones_texto_original[tipo] = self.btn_proto.text()
            self.btn_proto.setText("🔄 Analizando...")
            self.btn_proto.setEnabled(False)
            print(f"🔒 Botón protocolo cambiado a: {self.btn_proto.text()}")

        worker = SuggestionWorker(self.red_meta, tipo)
        self.suggestion_workers[tipo] = worker
        
        worker.finished.connect(lambda result: self._on_suggestion_finished(tipo, result))
        worker.error.connect(lambda e: self._on_suggestion_error(tipo, e))
        worker.finished.connect(worker.deleteLater)
        
        self._update_buttons_state()
        worker.start()
        print(f"✅ Worker de {tipo} iniciado")

    def _on_suggestion_error(self, tipo, error_msg):
        """Callback cuando hay error en la sugerencia"""
        print(f"❌ Error sugerencia {tipo}: {error_msg}")
        
        # Restaurar el texto original del botón
        if tipo in self.botones_texto_original:
            texto_original = self.botones_texto_original[tipo]
            if tipo == "tecnologia":
                self.btn_tecn.setText(texto_original)
                self.btn_tecn.setEnabled(True)
                print(f"🔍 Botón tecnología restaurado a: {self.btn_tecn.text()}")
            else:
                self.btn_proto.setText(texto_original)
                self.btn_proto.setEnabled(True)
                print(f"🔒 Botón protocolo restaurado a: {self.btn_proto.text()}")
            del self.botones_texto_original[tipo]
        
        # Mostrar mensaje de error
        QMessageBox.warning(
            self,
            "Error en análisis",
            f"No se pudo completar el análisis de {tipo}.\n\nError: {error_msg}"
        )
        
        if tipo in self.suggestion_workers:
            del self.suggestion_workers[tipo]
        self._update_buttons_state()

    def _on_suggestion_finished(self, tipo, result):
        """Callback cuando termina una sugerencia"""
        print(f"✅ Análisis de {tipo} completado")  # Debug
        
        if not self._is_closing and tipo in self.suggestion_workers:
            
            # Restaurar el texto original del botón
            if tipo in self.botones_texto_original:
                texto_original = self.botones_texto_original[tipo]
                if tipo == "tecnologia":
                    self.btn_tecn.setText(texto_original)
                    self.btn_tecn.setEnabled(True)
                    print(f"🔍 Botón tecnología restaurado a: {self.btn_tecn.text()}")
                else:
                    self.btn_proto.setText(texto_original)
                    self.btn_proto.setEnabled(True)
                    print(f"🔒 Botón protocolo restaurado a: {self.btn_proto.text()}")
                del self.botones_texto_original[tipo]
            
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
        self.botones_texto_original.clear()
        
        event.accept()
# ----------------- Main Window Profesional -----------------