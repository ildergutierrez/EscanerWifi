# ui.py con PyQt6 (fondo negro + cards delineadas)
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QScrollArea, QGridLayout, QPushButton, QFrame, QDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from main import scan_wifi
import os, json
from collections import deque

def normalize_mac(mac):
    """Normaliza MAC a formato AA:BB:CC:DD:EE:FF en mayúsculas."""
    if not mac:
        return None
    s = "".join(ch for ch in mac if ch.isalnum()).upper()
    if len(s) < 12:
        return None
    parts = [s[i:i+2] for i in range(0, 12, 2)]
    return ":".join(parts)

def find_packets_matching_bssid(bssid, captures_dir="captures", max_matches=200, files_to_scan=10):
    """
    Busca en los JSONL de captures las entradas con src_mac o dst_mac == bssid.
    - bssid: string (ej "AA:BB:CC:DD:EE:FF" o "aabbcc:..."), se normaliza.
    - devuelve una lista de metadatos (hasta max_matches).
    """
    norm = normalize_mac(bssid)
    if not norm:
        return []

    results = []
    # listar archivos capture_*.jsonl ordenados por fecha descendente (nuevos primero)
    files = [f for f in os.listdir(captures_dir) if f.startswith("capture_") and f.endswith(".jsonl")]
    files = sorted(files, reverse=True)
    files = files[:files_to_scan]

    for fname in files:
        path = os.path.join(captures_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        j = json.loads(line)
                    except Exception:
                        continue
                    src = j.get("src_mac", "")
                    dst = j.get("dst_mac", "")
                    # normalizar si vienen sin ':'
                    if src:
                        src_norm = normalize_mac(src)
                    else:
                        src_norm = None
                    if dst:
                        dst_norm = normalize_mac(dst)
                    else:
                        dst_norm = None
                    if src_norm == norm or dst_norm == norm:
                        results.append(j)
                        if len(results) >= max_matches:
                            return results
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return results


CARD_WIDTH = 220
CARD_HEIGHT = 120


class Card(QFrame):  # Clase que representa una tarjeta de red WiFi
    def __init__(self, red, parent=None):
        super().__init__(parent)
        self.red = red
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setStyleSheet("""
            QFrame {
                background-color: #111;
                border-radius: 10px;
                border: 2px solid #555;
                margin-bottom: 12px;
                font-size: 14px;
                font-family: "Verdana";
            }
            QLabel {
                color: white;
            }
        """)

        layout = QVBoxLayout()
        ssid_label = QLabel(f"📶 {red['SSID']}")
        ssid_label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        ssid_label.setStyleSheet(f"color: {self.color_por_senal(red['Señal'])};")
        layout.addWidget(ssid_label)

        info_label = QLabel(
            f"Señal: {red['Señal']} dBm\n"
            f"Canal: {red['Canal']} | {red['Banda']}\n"
            f"Seguridad: {red['Seguridad']}"
        )
        info_label.setFont(QFont("Consolas", 9))
        layout.addWidget(info_label)

        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            dialog = DetalleDialog(self.red, self)
            dialog.exec()

    def color_por_senal(self, signal):
        if signal >= -50: return "#4CAF50"
        elif signal >= -70: return "#FFC107"
        else: return "#F44336"


class DetalleDialog(QDialog):  # Diálogo para mostrar detalles de la red
    def __init__(self, red, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Detalles de {red['SSID']}")
        self.setFixedSize(400, 300)
        layout = QVBoxLayout()
        for k, v in red.items():
            lbl = QLabel(f"{k}: {v}")
            lbl.setStyleSheet("color: white;")
            layout.addWidget(lbl)
        self.setLayout(layout)
        self.setStyleSheet("background-color: #000;")


class MainWindow(QMainWindow):  # Clase principal de la ventana
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Escáner WiFi")
        self.setMinimumSize(800, 600)

        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)

        self.title = QLabel("Escáner WiFi")
        self.title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.title.setStyleSheet("color: white;") # Título principal
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.cantidad_label = QLabel("Cantidad de redes: 0") 
        self.cantidad_label.setStyleSheet("color: white;")  # Etiqueta para mostrar la cantidad de redes
        self.cantidad_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.layout.addWidget(self.title)
        self.layout.addWidget(self.cantidad_label)

        # Botón "Ver todas"
        self.boton_ver_todas = QPushButton("🔎 Ver todas")
        self.boton_ver_todas.setStyleSheet("background-color: #333; color: white; padding: 6px;")
        self.boton_ver_todas.clicked.connect(self.mostrar_todas)
        self.layout.addWidget(self.boton_ver_todas)
        self.boton_ver_todas.hide()

        # Scroll con grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid = QGridLayout(self.scroll_content)
        self.scroll.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll)

        self.setCentralWidget(self.container)
        self.redes = []
        self.mostrar_todas_flag = False

        # Timer para actualizar
        self.timer = QTimer()
        self.timer.timeout.connect(self.actualizar)
        self.timer.start(5000)

        self.actualizar()

    def actualizar(self):
        try:
            self.redes = scan_wifi()
            self.cantidad_label.setText(f"Cantidad de redes: {len(self.redes)}")
            self.construir_cards()
        except Exception as e:
            self.cantidad_label.setText(f"Error: {e}")

    def construir_cards(self):
        for i in reversed(range(self.grid.count())):
            self.grid.itemAt(i).widget().setParent(None)

        ancho = self.scroll_content.width() or self.width()
        num_cols = max(1, ancho // CARD_WIDTH)

        max_cards = num_cols * 3  # mostramos 3 filas por defecto
        redes_mostrar = self.redes

        if not self.mostrar_todas_flag and len(self.redes) > max_cards:
            redes_mostrar = self.redes[:max_cards]
            self.boton_ver_todas.show()
        else:
            self.boton_ver_todas.hide()

        for i, r in enumerate(redes_mostrar):
            row, col = divmod(i, num_cols)
            self.grid.addWidget(Card(r), row, col)

    def resizeEvent(self, event):
        self.construir_cards()
        return super().resizeEvent(event)

    def mostrar_todas(self):
        self.mostrar_todas_flag = True
        self.construir_cards()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Fondo global negro
    app.setStyleSheet("""
        QMainWindow { background-color: #000; }
        QScrollArea { background-color: #000; }
        QWidget { background-color: #000; }
        
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
