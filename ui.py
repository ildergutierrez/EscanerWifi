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
                background-color: #1a1a1a;
                color: #e6e6e6;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Título con gradiente
        title_lbl = QLabel(titulo)
        title_lbl.setFont(QFont("Verdana", 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet("""
            QLabel {
                color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF6B6B, stop:0.5 #4ECDC4, stop:1 #45B7D1);
                padding: 10px;
                background-color: #2a2a2a;
                border-radius: 8px;
            }
        """)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)
        
        # Área de texto scrollable
        text_area = QTextEdit()
        text_area.setReadOnly(True)
        text_area.setFont(QFont("Verdana", 11))
        text_area.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                color: #e6e6e6;
                border: 2px solid #404040;
                border-radius: 8px;
                padding: 12px;
                selection-background-color: #4ECDC4;
            }
        """)
        text_area.setText(texto)
        layout.addWidget(text_area)

    def set_icon(self):
        """Establecer el icono de la ventana"""
        icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

# ----------------- Configuración visual mejorada -----------------
CARD_WIDTH = 300
CARD_HEIGHT = 140

COLOR_BG = "#0f0f0f"
COLOR_CARD = "#1e1e1e"
COLOR_CARD_BORDER = "#363636"
COLOR_TEXT = "#f0f0f0"
COLOR_ACCENT = "#4ECDC4"
COLOR_GREEN = "#4CAF50"
COLOR_YELLOW = "#FFC107"
COLOR_RED = "#FF6B6B"
COLOR_MUTED = "#888888"
COLOR_PURPLE = "#9C27B0"
COLOR_BLUE = "#2196F3"
COLOR_ORANGE = "#FF9800"

def signal_color_by_dbm(signal_dbm: Optional[float]) -> str:
    try:
        if signal_dbm is None:
            return COLOR_MUTED
        s = float(signal_dbm)
        if s >= -60:
            return "#4CAF50"  # Verde brillante
        if s >= -70:
            return "#FFC107"  # Amarillo
        if s >= -80:
            return "#FF9800"  # Naranja
        return "#FF5252"      # Rojo
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
            result = f"⚠️ Error: {e}"
        
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
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {COLOR_CARD}, stop:1 #252525);
                border-radius: 12px;
                border: 2px solid {COLOR_CARD_BORDER};
            }}
            QLabel {{ color: {COLOR_TEXT}; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        ssid_lbl = QLabel(self.red.get("SSID","<sin nombre>"))
        ssid_lbl.setFont(QFont("Verdana", 13, QFont.Weight.Bold))
        ssid_lbl.setStyleSheet(f"color:{COLOR_ACCENT}; background-color: transparent;")
        top_row.addWidget(ssid_lbl, stretch=1)

        color = signal_color_by_dbm(self.red.get("Señal"))
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color}; font-size:24px; background-color: transparent;")
        top_row.addWidget(dot, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(top_row)

        sig = self.red.get("Señal")
        est = self.red.get("Estimacion_m")
        est_text = f" | 📏 {est}m" if est is not None else ""
        info_lbl = QLabel(f"📶 Señal: {sig} dBm{est_text}")
        info_lbl.setFont(QFont("Verdana", 10))
        info_lbl.setStyleSheet("color:#dcdcdc; background-color: transparent;")
        layout.addWidget(info_lbl)

        sec = self.red.get("Seguridad","N/A")
        ancho = self.red.get("AnchoCanal","Desconocido")
        footer_lbl = QLabel(f"🔐 {sec}  •  📡 {ancho}")
        footer_lbl.setFont(QFont("Verdana", 9))
        footer_lbl.setStyleSheet("color:#bfbfbf; background-color: transparent;")
        layout.addWidget(footer_lbl)

        layout.addStretch()
        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().show_traffic_for_bssid(self.red.get("BSSID"), self.red)
        else:
            super().mousePressEvent(event)

# ----------------- Botón con Efecto de Carga -----------------
class LoadingButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.normal_style = ""
        self.loading_style = ""
        self.is_loading = False
        self.loading_animation = QPropertyAnimation(self, b"geometry")
        self.loading_animation.setDuration(1000)
        self.loading_animation.setLoopCount(-1)  # Loop infinito
        
    def start_loading(self):
        """Iniciar efecto de carga"""
        self.is_loading = True
        self.setEnabled(False)
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        
        # Animación de pulsación
        original_geometry = self.geometry()
        self.loading_animation.setStartValue(original_geometry)
        self.loading_animation.setEndValue(original_geometry)
        self.loading_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.loading_animation.start()
        
    def stop_loading(self):
        """Detener efecto de carga"""
        self.is_loading = False
        self.setEnabled(True)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.loading_animation.stop()

# ----------------- Diálogo de Detalles con Indicadores de Carga -----------------
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
        
        self.setWindowTitle(f"🔍 Detalles - {red_meta.get('SSID', 'Red')}")
        self.setMinimumSize(850, 600)
        self.setup_ui()
        
    def set_icon(self):
        """Establecer el icono de la ventana"""
        icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
    def setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a1a, stop:1 #2d2d2d);
                color: #e6e6e6;
                border-radius: 15px;
            }
            * {
                font-family: 'Verdana';
            }
        """)
        
        # Cambiar cursor a espera durante operaciones
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(20, 20, 20, 20)
        outer_layout.setSpacing(15)
        self.setLayout(outer_layout)

        # Título del diálogo
        title_lbl = QLabel(f"📡 Análisis de Red: {self.red_meta.get('SSID', 'Desconocida')}")
        title_lbl.setFont(QFont("Verdana", 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet("""
            QLabel {
                color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4ECDC4, stop:1 #45B7D1);
                padding: 12px;
                background-color: #2a2a2a;
                border-radius: 10px;
                border: 2px solid #404040;
            }
        """)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer_layout.addWidget(title_lbl)

        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border-radius: 12px;
                border: 2px solid #404040;
            }
            QLabel {
                color: #e6e6e6;
                background-color: transparent;
            }
        """)
        info_layout = QFormLayout()
        info_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        info_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        info_layout.setHorizontalSpacing(25)
        info_layout.setVerticalSpacing(10)
        info_frame.setLayout(info_layout)
        outer_layout.addWidget(info_frame)

        def make_value_label(text, color: Optional[str] = None):
            lbl = QLabel(str(text))
            lbl.setFont(QFont("Verdana", 11))
            lbl.setStyleSheet(f"color:{color or '#e6e6e6'}; background-color: transparent;")
            return lbl

        # Datos de la red
        ssid = self.red_meta.get("SSID", "<sin nombre>")
        signal = self.red_meta.get("Señal", None)
        freq = self.red_meta.get("Frecuencia", None)
        banda = self.red_meta.get("Banda", "Desconocida")
        canal = self.red_meta.get("Canal", "Desconocido")
        seguridad = self.red_meta.get("Seguridad", "Desconocido")
        ancho = self.red_meta.get("AnchoCanal", "Desconocido")
        est = self.red_meta.get("Estimacion_m", None)
        tecnologia = self.red_meta.get("Tecnologia", "Desconocida")

        # Datos básicos con emojis y colores
        info_layout.addRow(QLabel("🔹 SSID:"), make_value_label(ssid, COLOR_ACCENT))
        info_layout.addRow(QLabel("🔹 Dirección MAC:"), make_value_label(self.bssid, COLOR_MUTED))
        
        # Fabricante con indicador de carga
        self.vendor_lbl = make_value_label("🔄 Buscando fabricante...", "#FFC107")
        info_layout.addRow(QLabel("🏭 Fabricante:"), self.vendor_lbl)

        sig_color = signal_color_by_dbm(signal)
        sig_text = f"{signal} dBm" if signal is not None else "N/A"
        info_layout.addRow(QLabel("📶 Intensidad de señal:"), make_value_label(sig_text, sig_color))
        info_layout.addRow(QLabel("📡 Frecuencia:"), make_value_label(f"{freq} MHz" if freq else "N/A", COLOR_BLUE))
        info_layout.addRow(QLabel("🛰️ Banda:"), make_value_label(banda, COLOR_PURPLE))
        info_layout.addRow(QLabel("📺 Canal:"), make_value_label(canal, COLOR_ORANGE))
        info_layout.addRow(QLabel("🔐 Seguridad:"), make_value_label(seguridad, COLOR_GREEN))
        info_layout.addRow(QLabel("📶 Ancho de canal:"), make_value_label(ancho, COLOR_ACCENT))
        dist_text = f"≈ {est} metros" if est is not None else "N/A"
        info_layout.addRow(QLabel("📏 Distancia estimada:"), make_value_label(dist_text, "#4ECDC4"))
        info_layout.addRow(QLabel("⚙️ Tecnología:"), make_value_label(tecnologia, "#FF6B6B"))
        
        # Estilo para las etiquetas de la izquierda
        for row in range(info_layout.rowCount()):
            label_widget = info_layout.itemAt(row, QFormLayout.ItemRole.LabelRole).widget()
            if label_widget:
                label_widget.setFont(QFont("Verdana", 11, QFont.Weight.Bold))
                label_widget.setStyleSheet("color: #4ECDC4; background-color: transparent;")

        # Botones de sugerencias con indicadores de carga
        suger_frame = QFrame()
        suger_frame.setStyleSheet("background-color: transparent;")
        suger_layout = QHBoxLayout()
        suger_layout.setSpacing(15)
        suger_frame.setLayout(suger_layout)

        # Botón de tecnología con efecto de carga
        self.btn_tecn = QPushButton("🔧 Sugerencia de Tecnología")
        self.btn_tecn.setFont(QFont("Verdana", 12, QFont.Weight.Bold))
        self.btn_tecn.setMinimumHeight(50)
        
        # Botón de protocolo con efecto de carga
        self.btn_proto = QPushButton("🔐 Sugerencia de Protocolo")
        self.btn_proto.setFont(QFont("Verdana", 12, QFont.Weight.Bold))
        self.btn_proto.setMinimumHeight(50)

        # Conectar señales
        self.btn_tecn.clicked.connect(lambda: self._handle_sugerencia("tecnologia"))
        self.btn_proto.clicked.connect(lambda: self._handle_sugerencia("protocolo"))

        suger_layout.addWidget(self.btn_tecn)
        suger_layout.addWidget(self.btn_proto)
        outer_layout.addWidget(suger_frame)

        # Iniciar búsqueda de fabricante
        self._start_vendor_lookup()

    def _update_buttons_state(self):
        """Actualizar estado de los botones según disponibilidad"""
        vendor_ready = self.vendor_completed
        has_active_suggestions = any(worker.isRunning() for worker in self.suggestion_workers.values())
        
        if not vendor_ready:
            # Fabricante aún no listo
            style_disabled = """
                QPushButton {
                    background-color: #555555;
                    color: #999999;
                    padding: 12px 20px;
                    border-radius: 10px;
                    border: 2px solid #666666;
                    font-weight: bold;
                }
            """
            self.btn_tecn.setStyleSheet(style_disabled)
            self.btn_proto.setStyleSheet(style_disabled)
            self.btn_tecn.setEnabled(False)
            self.btn_proto.setEnabled(False)
            self.btn_tecn.setText("⏳ Esperando fabricante...")
            self.btn_proto.setText("⏳ Esperando fabricante...")
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            
        elif has_active_suggestions:
            # Sugerencia en proceso - Efecto de carga activo
            style_loading = """
                QPushButton {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #FFD700, stop:0.5 #FFA500, stop:1 #FFD700);
                    color: #000000;
                    padding: 12px 20px;
                    border-radius: 10px;
                    border: 2px solid #FFC107;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #FFD700, stop:0.5 #FFA500, stop:1 #FFD700);
                }
            """
            self.btn_tecn.setStyleSheet(style_loading)
            self.btn_proto.setStyleSheet(style_loading)
            self.btn_tecn.setEnabled(False)
            self.btn_proto.setEnabled(False)
            
            # Determinar qué botón está cargando
            if "tecnologia" in self.suggestion_workers and self.suggestion_workers["tecnologia"].isRunning():
                self.btn_tecn.setText("🔄 Consultando IA...")
                self.btn_proto.setText("⏸️ Esperando...")
            elif "protocolo" in self.suggestion_workers and self.suggestion_workers["protocolo"].isRunning():
                self.btn_tecn.setText("⏸️ Esperando...")
                self.btn_proto.setText("🔄 Consultando IA...")
            
            # Cambiar cursor a espera
            self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
            
        else:
            # Listos para usar
            style_tecn = """
                QPushButton {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4ECDC4, stop:1 #45B7D1);
                    color: white;
                    padding: 12px 20px;
                    border-radius: 10px;
                    border: 2px solid #5CDBD3;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3DBBB3, stop:1 #35A7C1);
                    border: 2px solid #4ECDC4;
                }
                QPushButton:pressed {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #2CA9A1, stop:1 #2597B1);
                }
            """
            style_proto = """
                QPushButton {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #FF6B6B, stop:1 #FF8E53);
                    color: white;
                    padding: 12px 20px;
                    border-radius: 10px;
                    border: 2px solid #FF8A80;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #FF5252, stop:1 #FF7B42);
                    border: 2px solid #FF6B6B;
                }
                QPushButton:pressed {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #FF4040, stop:1 #FF6B35);
                }
            """
            self.btn_tecn.setStyleSheet(style_tecn)
            self.btn_proto.setStyleSheet(style_proto)
            self.btn_tecn.setEnabled(True)
            self.btn_proto.setEnabled(True)
            self.btn_tecn.setText("🔧 Sugerencia de Tecnología")
            self.btn_proto.setText("🔐 Sugerencia de Protocolo")
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

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
            QMessageBox.information(self, "⏳ Espera requerida", 
                                  "Por favor espera a que termine la búsqueda del fabricante antes de solicitar sugerencias.")
            return

        # Verificar si ya hay un thread activo para este tipo
        if tipo in self.suggestion_workers and self.suggestion_workers[tipo].isRunning():
            QMessageBox.information(self, "🔄 En progreso", 
                                  f"Ya hay una solicitud de {tipo} en proceso. Espera a que termine.")
            return

        # Crear y configurar worker
        worker = SuggestionWorker(self.red_meta, tipo)
        self.suggestion_workers[tipo] = worker
        
        worker.finished.connect(lambda result: self._on_suggestion_finished(tipo, result))
        worker.finished.connect(worker.deleteLater)
        
        # Actualizar UI con efectos de carga
        self._update_buttons_state()
        
        # Iniciar worker
        worker.start()

        # Mostrar mensaje de confirmación
        msg = QMessageBox(self)
        msg.setWindowTitle("🔄 Consulta Iniciada")
        msg.setText(f"Se está generando la sugerencia de {tipo}. Por favor espera...")
        msg.setIcon(QMessageBox.Icon.Information)
        # Aplicar color blanco al texto
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #FFFFFF;   /* Fondo oscuro */
                color: white;                /* Texto blanco */
            }
            QPushButton {
                background-color: #4FC3F7;
                color: #0b0b0b;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #29B6F6;
            }
        """)
        msg.exec()

    def _on_suggestion_finished(self, tipo, result):
        """Callback cuando termina una sugerencia"""
        # Remover worker de la lista
        if tipo in self.suggestion_workers:
            del self.suggestion_workers[tipo]
        
        # Mostrar resultado en ventana emergente
        suggestion_dialog = SuggestionWindow(f"💡 Sugerencia de {tipo}", result, parent=self)
        suggestion_dialog.exec()
        
        # Actualizar botones
        self._update_buttons_state()

    def closeEvent(self, event):
        """Manejar cierre del diálogo - detener todos los threads"""
        # Detener vendor worker
        if self.vendor_worker and self.vendor_worker.isRunning():
            self.vendor_worker.stop()
        
        # Detener suggestion workers
        for worker in self.suggestion_workers.values():
            if worker.isRunning():
                worker.stop()
        
        event.accept()

# ----------------- Main Window Mejorada -----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Establecer icono
        self.set_icon()
        
        self.setWindowTitle("Escáner WiFi Avanzado")
        self.setMinimumSize(1100, 700)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        APP_FONT = "Verdana"

        # Título principal con gradiente
        title = QLabel("Escáner WiFi Avanzado")
        title.setFont(QFont(APP_FONT, 24, QFont.Weight.Bold))
        title.setStyleSheet("""
            QLabel {
                color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4ECDC4, stop:0.5 #45B7D1, stop:1 #FF6B6B);
                padding: 15px;
                background-color: #2a2a2a;
                border-radius: 12px;
                border: 3px solid #404040;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Contador de redes
        self.cantidad_label = QLabel("📊 Cantidad de redes: 0")
        self.cantidad_label.setFont(QFont(APP_FONT, 14))
        self.cantidad_label.setStyleSheet("""
            QLabel {
                color: #4ECDC4;
                padding: 8px;
                background-color: #2a2a2a;
                border-radius: 8px;
                border: 2px solid #404040;
            }
        """)
        self.cantidad_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.cantidad_label)

        # Botón Ver todas
        self.btn_ver_todas = QPushButton("🔍 Ver todas las redes")
        self.btn_ver_todas.setFont(QFont(APP_FONT, 14, QFont.Weight.Bold))
        self.btn_ver_todas.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9C27B0, stop:1 #E91E63);
                color: white;
                padding: 15px 25px;
                border-radius: 10px;
                border: 2px solid #BA68C8;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8E24AA, stop:1 #D81B60);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7B1FA2, stop:1 #C2185B);
            }
        """)
        self.btn_ver_todas.clicked.connect(self.mostrar_todas)
        self.btn_ver_todas.hide()
        main_layout.addWidget(self.btn_ver_todas, alignment=Qt.AlignmentFlag.AlignCenter)

        # Área de scroll con estilo
        self.scroll = QScrollArea()
        self.scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1a1a1a;
                border: 2px solid #404040;
                border-radius: 12px;
            }
            QScrollBar:vertical {
                background-color: #2a2a2a;
                width: 15px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #4ECDC4;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #3DBBB3;
            }
        """)
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: #1a1a1a;")
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setContentsMargins(15, 15, 15, 15)
        self.grid.setHorizontalSpacing(20)
        self.grid.setVerticalSpacing(20)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll)

        self.redes = []
        self.mostrar_todas_flag = False

        # Timer para escaneo automático
        self.timer = QTimer()
        self.timer.timeout.connect(self.lanzar_scan)
        self.timer.start(2000)
        self.lanzar_scan()

        # Estilo principal de la ventana
        self.setStyleSheet(f"""
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {COLOR_BG}, stop:1 #1a1a1a);
            }}
        """)

    def set_icon(self):
        """Establecer el icono de la ventana principal"""
        icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def lanzar_scan(self):
        self.scan_worker = ScanWorker()
        self.scan_worker.finished.connect(self._scan_done)
        self.scan_worker.start()

    def _scan_done(self, redes):
        self.redes = redes
        self.cantidad_label.setText(f"📊 Cantidad de redes: {len(redes)}")
        self.construir_cards()

    def construir_cards(self):
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w: 
                w.setParent(None)

        ancho_px = max(1, self.scroll_content.width() or self.width())
        num_cols = max(1, ancho_px // (CARD_WIDTH + 30))
        max_cards = num_cols * 3
        redes_mostrar = self.redes
        if not self.mostrar_todas_flag and len(self.redes) > max_cards:
            redes_mostrar = self.redes[:max_cards]
            self.btn_ver_todas.show()
        else:
            self.btn_ver_todas.hide()

        for idx, r in enumerate(redes_mostrar):
            row, col = divmod(idx, num_cols)
            card = Card(r)
            self.grid.addWidget(card, row, col)

    def resizeEvent(self, event):
        self.construir_cards()
        return super().resizeEvent(event)

    def mostrar_todas(self):
        self.mostrar_todas_flag = True
        self.construir_cards()

    def show_traffic_for_bssid(self, bssid: str, red_meta: dict = None):
        """Mostrar diálogo de detalles con gestión propia de threads"""
        dialog = NetworkDetailsDialog(bssid, red_meta or {}, self)
        dialog.exec()

# ----------------- Main -----------------
def main():
    app = QApplication(sys.argv)
    
    # Establecer icono para toda la aplicación
    icon_path = os.path.join(os.path.dirname(__file__), "wifi.png")
    if os.path.exists(icon_path):
        # Método 1: Establecer para toda la aplicación
        app.setWindowIcon(QIcon(icon_path))
        
        # Método 2: Truco para forzar el icono en la barra de tareas
        import ctypes
        myappid = 'escaner.wifi.avanzado.1.0'  # ID único arbitrario
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    window = MainWindow()
    
    # Método 3: Establecer icono específicamente en la ventana principal
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    
    window.show()
    sys.exit(app.exec())
if __name__ == "__main__":
    main()