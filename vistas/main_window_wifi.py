"""
vistas/main_window_wifi.py – Ventana principal del escáner WiFi
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

from vistas.workers import ScanWorker, RouterCapacityWorker
from vistas.card import Card
from vistas.network_details import NetworkDetailsDialog

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