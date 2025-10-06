import sys
import os
from typing import Optional
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

try:
    from vendor_lookup import get_vendor
except Exception:
    def get_vendor(_):
        return "Desconocido"

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

# ----------------- Workers -----------------
class ScanWorker(QThread):
    finished = pyqtSignal(list)
    def run(self):
        try:
            redes = scan_wifi()
            self.finished.emit(redes)
        except Exception:
            self.finished.emit([])

class SuggestionWorker(QThread):
    finished = pyqtSignal(str)
    
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
        except Exception as e:
            result = f"Error: {e}"
        
        if self._is_running:
            self.finished.emit(result)
    
    def stop(self):
        self._is_running = False
        self.quit()
        self.wait(1000)

class VendorWorker(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, bssid):
        super().__init__()
        self.bssid = bssid
        self._is_running = True
        
    def run(self):
        if not self._is_running:
            return
        try:
            vendor = get_vendor(self.bssid)
            # print("Fabricado:",vendor,"Mac",self.bssid)
        except Exception:
            vendor = "Desconocido"
        
        if self._is_running:
            self.finished.emit(vendor)
    
    def stop(self):
        self._is_running = False
        self.quit()
        self.wait(1000)

# ----------------- UI Elements -----------------
class Card(QFrame):
    def __init__(self, red: dict, parent=None):
        super().__init__(parent)
        self.red = red
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_CARD};
                border-radius: 8px;
                border: 1px solid {COLOR_CARD_BORDER};
            }}
            QLabel {{
                color: {COLOR_TEXT};
                background-color: transparent;
            }}
        """)
        self._build_ui()

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

        # Distancia estimada
        distance = self.red.get("Estimacion_m")
        if distance:
            distance_lbl = QLabel(f"📏 ≈ {distance} metros")
            distance_lbl.setFont(QFont("Segoe UI", 9))
            distance_lbl.setStyleSheet(f"color: {COLOR_MUTED};")
            info_layout.addWidget(distance_lbl)

        layout.addLayout(info_layout)
        layout.addStretch()
        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().show_traffic_for_bssid(self.red.get("BSSID"), self.red)
        else:
            super().mousePressEvent(event)

# ----------------- Diálogo de Detalles Profesional -----------------
class NetworkDetailsDialog(QDialog):
    def __init__(self, bssid: str, red_meta: dict, parent=None):
        super().__init__(parent)
        self.bssid = bssid
        self.red_meta = red_meta
        
        # Establecer icono
        self.set_icon()
        
        # Control de threads activos
        self.vendor_worker = None
        self.suggestion_workers = {}
        self.vendor_completed = False
        
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

        buttons_layout.addWidget(self.btn_tecn)
        buttons_layout.addWidget(self.btn_proto)
        outer_layout.addWidget(buttons_frame)

        # Conectar señales
        self.btn_tecn.clicked.connect(lambda: self._handle_sugerencia("tecnologia"))
        self.btn_proto.clicked.connect(lambda: self._handle_sugerencia("protocolo"))

        # Iniciar búsqueda de fabricante
        self._start_vendor_lookup()

    def _update_buttons_state(self):
        """Actualizar estado de los botones"""
        vendor_ready = self.vendor_completed
        has_active_suggestions = any(worker.isRunning() for worker in self.suggestion_workers.values())
        
        self.btn_tecn.setEnabled(vendor_ready and not has_active_suggestions)
        self.btn_proto.setEnabled(vendor_ready and not has_active_suggestions)

        if not vendor_ready:
            self.btn_tecn.setText("⏳ Esperando fabricante...")
            self.btn_proto.setText("⏳ Esperando fabricante...")
        elif has_active_suggestions:
            self.btn_tecn.setText("🔄 Analizando...")
            self.btn_proto.setText("🔄 Analizando...")
        else:
            self.btn_tecn.setText("🔍 Análisis de Tecnología")
            self.btn_proto.setText("🔒 Análisis de Protocolo")

    def _start_vendor_lookup(self):
        """Iniciar búsqueda de fabricante"""
        self.vendor_worker = VendorWorker(self.bssid)
        self.vendor_worker.finished.connect(self._on_vendor_finished)
        self.vendor_worker.finished.connect(self.vendor_worker.deleteLater)
        self.vendor_worker.start()
        self._update_buttons_state()

    def _on_vendor_finished(self, vendor):
        """Callback cuando termina la búsqueda de fabricante"""
        self.vendor_lbl.setText(vendor)
        self.vendor_completed = True
        self.vendor_worker = None
        self._update_buttons_state()

    def _handle_sugerencia(self, tipo):
        """Manejar solicitud de sugerencia"""
        if not self.vendor_completed:
            return

        if tipo in self.suggestion_workers and self.suggestion_workers[tipo].isRunning():
            return

        worker = SuggestionWorker(self.red_meta, tipo)
        self.suggestion_workers[tipo] = worker
        
        worker.finished.connect(lambda result: self._on_suggestion_finished(tipo, result))
        worker.finished.connect(worker.deleteLater)
        
        self._update_buttons_state()
        worker.start()

    def _on_suggestion_finished(self, tipo, result):
        """Callback cuando termina una sugerencia"""
        if tipo in self.suggestion_workers:
            del self.suggestion_workers[tipo]
        
        titulo = "Análisis de Tecnología" if tipo == "tecnologia" else "Análisis de Protocolo"
        suggestion_dialog = SuggestionWindow(titulo, result, parent=self)
        suggestion_dialog.exec()
        
        self._update_buttons_state()

    def closeEvent(self, event):
        """Manejar cierre del diálogo"""
        if self.vendor_worker and self.vendor_worker.isRunning():
            self.vendor_worker.stop()
        
        for worker in self.suggestion_workers.values():
            if worker.isRunning():
                worker.stop()
        
        event.accept()

# ----------------- Main Window Profesional -----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Establecer icono
        self.set_icon()
        
        self.setWindowTitle("Escáner WiFi Corporativo")
        self.setMinimumSize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Título principal
        title = QLabel("Escáner WiFi Corporativo")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet(f"""
            QLabel {{
                color: #FFFFFF;
                padding: 20px;
                background-color: {COLOR_CARD};
                border-radius: 8px;
                border-bottom: 4px solid {COLOR_ACCENT};
            }}
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

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
        self.timer.start(3000) #Cada 3 segundos
        self.lanzar_scan()

        # Estilo principal
        self.setStyleSheet(f"QMainWindow {{ background-color: {COLOR_BG}; }}")

    def set_icon(self):
        """Establecer el icono de la ventana principal"""
        icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def lanzar_scan(self):
        """Iniciar escaneo de redes"""
        if not hasattr(self, 'scan_worker') or not self.scan_worker.isRunning():
            self.scan_worker = ScanWorker()
            self.scan_worker.finished.connect(self._scan_done)
            self.scan_worker.start()

    def _scan_done(self, redes):
        """Callback cuando termina el escaneo"""
        self.redes = redes
        self.cantidad_label.setText(f"Redes detectadas: {len(redes)}")
        
        if self.is_first_scan and redes:
            self.scanning_label.hide()
            self.is_first_scan = False
        
        self.construir_cards()

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

    def resizeEvent(self, event):
        self.construir_cards()
        return super().resizeEvent(event)

    def show_traffic_for_bssid(self, bssid: str, red_meta: dict = None):
        """Mostrar diálogo de detalles"""
        dialog = NetworkDetailsDialog(bssid, red_meta or {}, self)
        dialog.exec()

# ----------------- Main -----------------
def main():
    app = QApplication(sys.argv)
    
    # Establecer estilo de aplicación
    app.setStyle('Fusion')
    
    # Establecer icono
    icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
        # Forzar icono en la barra de tareas (Windows)
        import ctypes
        myappid = 'corporate.wifi.scanner.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()