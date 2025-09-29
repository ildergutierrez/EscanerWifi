# ui.py con PyQt6 (fondo negro + cards delineadas + muestra estimacion)
import sys
import os
import json
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout,
    QScrollArea, QGridLayout, QPushButton, QFrame, QDialog,
    QTableWidget, QTableWidgetItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from main import scan_wifi  # usa la función actualizada

CARD_WIDTH = 220
CARD_HEIGHT = 120

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
    if not os.path.isdir(captures_dir):
        return results

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
                    src_norm = normalize_mac(src) if src else None
                    dst_norm = normalize_mac(dst) if dst else None
                    if src_norm == norm or dst_norm == norm:
                        results.append(j)
                        if len(results) >= max_matches:
                            return results
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return results

class Card(QFrame):
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
        ssid_label = QLabel(f"📶 {red.get('SSID', '')}")
        ssid_label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        ssid_label.setStyleSheet(f"color: {self.color_por_senal(red.get('Señal'))};")
        layout.addWidget(ssid_label)

        # Mostrar señal y estimación en la card (si está disponible)
       
    

        info_label = QLabel(
            f"Señal: {red.get('Señal')} dBm\n"
            f"AKM: {red.get('Seguridad')}\n"
        )
        info_label.setFont(QFont("Consolas", 9))
        layout.addWidget(info_label)

        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Al hacer click, abrimos un diálogo con detalles y (si hay captures) paquetes relacionados
            self.window().show_traffic_for_bssid(self.red.get("BSSID"), self.red)
        else:
            super().mousePressEvent(event)

    def color_por_senal(self, signal):
        try:
            if signal is None:
                return "#9E9E9E"
            if signal >= -50: return "#4CAF50"
            elif signal >= -70: return "#FFC107"
            else: return "#F44336"
        except Exception:
            return "#9E9E9E"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Escáner WiFi")
        self.setMinimumSize(900, 600)

        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)

        self.title = QLabel("Escáner WiFi")
        self.title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.title.setStyleSheet("color: white;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.cantidad_label = QLabel("Cantidad de redes: 0")
        self.cantidad_label.setStyleSheet("color: white;")
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
            # llamamos scan_wifi() con los mismos supuestos por defecto; si quieres cambiarlos pásalos aquí
            self.redes = scan_wifi()
            self.cantidad_label.setText(f"Cantidad de redes: {len(self.redes)}")
            self.construir_cards()
        except Exception as e:
            self.cantidad_label.setText(f"Error: {e}")

    def construir_cards(self):
        for i in reversed(range(self.grid.count())):
            widget = self.grid.itemAt(i).widget()
            if widget:
                widget.setParent(None)

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

    # ----------------- Funcionalidad para mostrar tráfico relacionado -----------------
    def show_traffic_for_bssid(self, bssid, red_meta=None):
        """
        Busca en captures/*.jsonl paquetes relacionados con bssid y muestra diálogo con
        resumen y ejemplos. Si no hay captures o no hay coincidencias, muestra mensaje.
        """
        matches = []
        if bssid:
            matches = find_packets_matching_bssid(
                bssid, captures_dir="captures", max_matches=200, files_to_scan=20
            )

        dlg = QDialog(self)
        dlg.setWindowTitle(f"📡 Detalles - {red_meta.get('SSID') if red_meta else bssid}")
        dlg.setMinimumSize(850, 550)
        layout = QVBoxLayout()

        # ---------- Tarjeta de información de la red ----------
        if red_meta:
            info_box = QFrame()
            info_layout = QVBoxLayout()
            info_box.setLayout(info_layout)
            info_box.setStyleSheet("""
                QFrame {
                    background-color: #1e1e1e;
                    border: 1px solid #444;
                    border-radius: 10px;
                    padding: 5px;
                }
                QLabel { color: #ddd; font-size: 14px; }
            """)

            title = QLabel("Información del Punto de Acceso")
            title.setStyleSheet("color: #4FC3F7; font-weight: bold; font-size: 15px;")
            info_layout.addWidget(title)

            info_lines = [
                f"🔹 SSID: {red_meta.get('SSID')}",
                f"🔹 BSSID: {red_meta.get('BSSID')}",
                f"📶 Señal: {red_meta.get('Señal')} dBm",
                f"📡 Frecuencia: {red_meta.get('Frecuencia')} MHz",
                f"🛰️ Banda: {red_meta.get('Banda')}",
                f"📺 Canal: {red_meta.get('Canal')}",
                f"🔒 AKM: {red_meta.get('Seguridad')}",
                f"🛠️ Cifrado: {red_meta.get('Cifrado')}",
                f"📡 Potencia de transmisión: {red_meta.get('TxPower_usado', 'Desconocida')} dBm",
                f"📡 Exponente de pérdida: {red_meta.get('PathLossExp', 'Desconocido')} ",
            ]

            est = red_meta.get("Estimacion_m")
            if est is not None:
                info_lines.append(
                    f"📏 Distancia Estimada: {est} metros" 
                )

            for line in info_lines:
                lbl = QLabel(line)
                info_layout.addWidget(lbl)

            layout.addWidget(info_box)

        # ---------- Tabla de tráfico ----------
        layout.addSpacing(15)

        if matches:
            lbl = QLabel(f"📦 Paquetes encontrados: {len(matches)} (ejemplos)")
            lbl.setStyleSheet("color: #4FC3F7; font-weight: bold; font-size: 14px;")
            layout.addWidget(lbl)

            table = QTableWidget()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels(
                ["⏱ Tiempo", "📡 Src MAC", "📡 Dst MAC", "🌐 Src IP", "🌐 Dst IP", "⚡ Protocolo"]
            )
            table.setRowCount(len(matches))

            for i, m in enumerate(matches):
                table.setItem(i, 0, QTableWidgetItem(str(m.get("ts", ""))))
                table.setItem(i, 1, QTableWidgetItem(str(m.get("src_mac", ""))))
                table.setItem(i, 2, QTableWidgetItem(str(m.get("dst_mac", ""))))
                table.setItem(i, 3, QTableWidgetItem(str(m.get("src_ip", ""))))
                table.setItem(i, 4, QTableWidgetItem(str(m.get("dst_ip", ""))))
                table.setItem(i, 5, QTableWidgetItem(str(m.get("l4", ""))))

            table.resizeColumnsToContents()
            table.setAlternatingRowColors(True)
            table.setStyleSheet("""
                QTableWidget {
                    background-color: #121212;
                    alternate-background-color: #1e1e1e;
                    color: #ddd;
                    gridline-color: #444;
                    border: 1px solid #333;
                    border-radius: 8px;
                }
                QHeaderView::section {
                    background-color: #2c2c2c;
                    color: #4FC3F7;
                    font-weight: bold;
                    padding: 6px;
                    border: none;
                }
            """)
            layout.addWidget(table)
        else:
            lbl = QLabel("⚠️ No se encontraron paquetes relacionados en 'captures/' (o no hay capturas).")
            lbl.setStyleSheet("color: #f88; font-weight: bold; font-size: 13px;")
            layout.addWidget(lbl)

        # ---------- Botón ----------
        layout.addSpacing(15)
        btn = QPushButton("Cerrar")
        btn.setFixedWidth(120)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #4FC3F7;
                color: black;
                font-weight: bold;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #81D4FA;
            }
        """)
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        dlg.setLayout(layout)
        dlg.setStyleSheet("QDialog { background-color: #0d0d0d; }")
        dlg.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QMainWindow { background-color: #000; }
        QScrollArea { background-color: #000; }
        QWidget { background-color: #000; }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
