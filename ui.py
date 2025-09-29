# ui.py
"""
Interfaz principal del Escáner WiFi (PyQt6).
Muestra tarjetas y diálogo de detalles.
En el diálogo mostramos 'Seguridad' (AKM) y 'AnchoCanal' (en lugar de 'Cifrado').
"""

import sys
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QScrollArea, QGridLayout, QPushButton, QFrame, QDialog,
    QMessageBox, QHBoxLayout, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from main import scan_wifi
from ai_suggestions import sugerencia_tecnologia, sugerencia_protocolo


# Visual constants
CARD_WIDTH = 280
CARD_HEIGHT = 120

# Colors
COLOR_BG = "#0b0b0b"
COLOR_CARD = "#121212"
COLOR_CARD_BORDER = "#2a2a2a"
COLOR_TEXT = "#e6e6e6"
COLOR_ACCENT = "#4FC3F7"
COLOR_GREEN = "#4CAF50"
COLOR_YELLOW = "#FFC107"
COLOR_RED = "#F44336"
COLOR_MUTED = "#9E9E9E"


def signal_color_by_dbm(signal_dbm: Optional[float]) -> str:
    """Devuelve un color hex según la intensidad de señal (dBm)."""
    try:
        if signal_dbm is None:
            return COLOR_MUTED
        s = float(signal_dbm)
        if s >= -60:
            return COLOR_GREEN
        if s >= -75:
            return COLOR_YELLOW
        return COLOR_RED
    except Exception:
        return COLOR_MUTED


class Card(QFrame):
    def __init__(self, red: dict, parent=None):
        super().__init__(parent)
        self.red = red
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_CARD};
                border-radius: 10px;
                border: 2px solid {COLOR_CARD_BORDER};
            }}
            QLabel {{ color: {COLOR_TEXT}; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Row 1: SSID + colored dot
        top_row = QHBoxLayout()
        ssid_lbl = QLabel(self.red.get("SSID", "<sin nombre>"))
        ssid_lbl.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        ssid_lbl.setStyleSheet(f"color: {COLOR_ACCENT};")
        top_row.addWidget(ssid_lbl, stretch=1)

        color = signal_color_by_dbm(self.red.get("Señal"))
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 18px;")
        top_row.addWidget(dot, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(top_row)

        sig = self.red.get("Señal")
        est = self.red.get("Estimacion_m")
        est_text = f" | Dist: {est} m" if est is not None else ""
        info_lbl = QLabel(f"Señal: {sig} dBm{est_text}")
        info_lbl.setFont(QFont("Consolas", 9))
        info_lbl.setStyleSheet("color: #dcdcdc;")
        layout.addWidget(info_lbl)

        # Mostrar AKM y Ancho de banda (en la card)
        sec = self.red.get("Seguridad", "N/A")
        ancho = self.red.get("AnchoCanal", "Desconocido")
        footer_lbl = QLabel(f"AKM: {sec}  •  Ancho: {ancho}")
        footer_lbl.setFont(QFont("Consolas", 9))
        footer_lbl.setStyleSheet("color: #bfbfbf;")
        layout.addWidget(footer_lbl)

        layout.addStretch()
        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().show_traffic_for_bssid(self.red.get("BSSID"), self.red)
        else:
            super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Escáner WiFi")
        self.setMinimumSize(1000, 660)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(8)

        title = QLabel("Escáner WiFi")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLOR_TEXT};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        self.cantidad_label = QLabel("Cantidad de redes: 0")
        self.cantidad_label.setStyleSheet(f"color: {COLOR_TEXT};")
        self.cantidad_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.cantidad_label)

        self.btn_ver_todas = QPushButton("🔎 Ver todas")
        self.btn_ver_todas.setStyleSheet("""
            QPushButton {
                background-color: #222;
                color: #e6e6e6;
                padding: 7px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2f2f2f; }
        """)
        self.btn_ver_todas.clicked.connect(self.mostrar_todas)
        self.btn_ver_todas.hide()
        main_layout.addWidget(self.btn_ver_todas, alignment=Qt.AlignmentFlag.AlignCenter)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet(f"background-color: {COLOR_BG};")  # fondo oscuro
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setContentsMargins(12, 12, 12, 12)
        self.grid.setHorizontalSpacing(20)
        self.grid.setVerticalSpacing(20)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll)

        self.redes = []
        self.mostrar_todas_flag = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.actualizar)
        self.timer.start(5000)

        self.actualizar()

        self.setStyleSheet(f"QMainWindow {{ background-color: {COLOR_BG}; }}")

    def actualizar(self):
        try:
            self.redes = scan_wifi()
            self.cantidad_label.setText(f"Cantidad de redes: {len(self.redes)}")
            self.construir_cards()
        except Exception as e:
            self.cantidad_label.setText(f"Error: {e}")

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
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Detalles - {red_meta.get('SSID') if red_meta else bssid}")
        dlg.setMinimumSize(820, 520)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(12)

        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{ background-color: #121212; border-radius: 10px; border: 1px solid #2f2f2f; }}
            QLabel {{ color: {COLOR_TEXT}; }}
        """)
        info_layout = QFormLayout()
        info_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        info_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        info_layout.setHorizontalSpacing(24)
        info_layout.setVerticalSpacing(8)
        info_frame.setLayout(info_layout)

        def make_value_label(text, color: Optional[str] = None):
            lbl = QLabel(str(text))
            lbl.setFont(QFont("Consolas", 11))
            if color:
                lbl.setStyleSheet(f"color: {color};")
            else:
                lbl.setStyleSheet(f"color: {COLOR_TEXT};")
            return lbl

        if red_meta is None:
            red_meta = {}

        ssid = red_meta.get("SSID", "<sin nombre>")
        bssid = red_meta.get("BSSID", bssid or "")
        fabricante = red_meta.get("Fabricante", "Desconocido")
        signal = red_meta.get("Señal", None)
        freq = red_meta.get("Frecuencia", None)
        banda = red_meta.get("Banda", "Desconocida")
        canal = red_meta.get("Canal", "Desconocido")
        seguridad = red_meta.get("Seguridad", "Desconocido")
        ancho = red_meta.get("AnchoCanal", "Desconocido")
        est = red_meta.get("Estimacion_m", None)
        tecnologia = red_meta.get("Tecnologia", "Desconocida")

        info_layout.addRow(QLabel("🔹 SSID:"), make_value_label(ssid))
        info_layout.addRow(QLabel("🔹 BSSID:"), make_value_label(bssid))
        info_layout.addRow(QLabel("🏭 Fabricante:"), make_value_label(fabricante))

        sig_color = signal_color_by_dbm(signal)
        sig_text = f"{signal} dBm" if signal is not None else "N/A"
        info_layout.addRow(QLabel("📶 Señal:"), make_value_label(sig_text, sig_color))

        info_layout.addRow(QLabel("📡 Frecuencia:"), make_value_label(f"{freq} MHz" if freq else "N/A"))
        info_layout.addRow(QLabel("🛰️ Banda:"), make_value_label(banda))
        info_layout.addRow(QLabel("📺 Canal:"), make_value_label(canal))

        # mostramos AKM (Seguridad) y ancho de canal (en lugar de 'Cifrado')
        info_layout.addRow(QLabel("🔐 AKM (Seguridad):"), make_value_label(seguridad))
        info_layout.addRow(QLabel("📶 Ancho de canal:"), make_value_label(ancho))

        dist_text = f"≈ {est} m" if est is not None else "N/A"
        info_layout.addRow(QLabel("📏 Distancia Estimada:"), make_value_label(dist_text))

        info_layout.addRow(QLabel("⚙️ Tecnología:"), make_value_label(tecnologia))

        outer_layout.addWidget(info_frame)

        suger_frame = QFrame()
        suger_layout = QHBoxLayout()
        suger_frame.setLayout(suger_layout)

        btn_tecn = QPushButton("Sugerencia de tecnología")
        btn_tecn.setFixedWidth(240)
        btn_tecn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: black;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
            }}
            QPushButton:hover {{ background-color: #81D4FA; }}
        """)
        btn_tecn.clicked.connect(lambda: self._handle_sugerencia_tecnologia(red_meta))

        btn_proto = QPushButton("Sugerencia de protocolo")
        btn_proto.setFixedWidth(240)
        btn_proto.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_GREEN};
                color: black;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
            }}
            QPushButton:hover {{ background-color: #66BB6A; }}
        """)
        btn_proto.clicked.connect(lambda: self._handle_sugerencia_protocolo(red_meta))

        suger_layout.addStretch()
        suger_layout.addWidget(btn_tecn)
        suger_layout.addWidget(btn_proto)
        suger_layout.addStretch()

        outer_layout.addWidget(suger_frame)

        note = QLabel("ℹ️ Detección de trama deshabilitada — recomendaciones heurísticas.")
        note.setStyleSheet(f"color: #bdbdbd; font-size: 12px;")
        outer_layout.addWidget(note)

        close_btn = QPushButton("Cerrar")
        close_btn.setFixedWidth(140)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: black;
                font-weight: bold;
                padding: 9px;
                border-radius: 8px;
            }}
            QPushButton:hover {{ background-color: #29B6F6; }}
        """)
        close_btn.clicked.connect(dlg.accept)
        outer_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        dlg.setLayout(outer_layout)
        dlg.setStyleSheet(f"QDialog {{ background-color: {COLOR_BG}; }}")
        dlg.exec()

    def _handle_sugerencia_tecnologia(self, red_meta: dict):
        suggestion = sugerencia_tecnologia(red_meta)
        QMessageBox.information(self, "Sugerencia de tecnología", suggestion)

    def _handle_sugerencia_protocolo(self, red_meta: dict):
        suggestion = sugerencia_protocolo(red_meta)
        QMessageBox.information(self, "Sugerencia de protocolo", suggestion)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
